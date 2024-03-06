import os
import cv2 as cv
import datetime
import time
import numpy as np
import pickle
import json
import argparse
import pyglet.media
from scipy import stats
from collections import deque
from simple_camio_3d import SIFTModelDetector, InteractionPolicyOBJ, CamIOPlayerOBJ
from simple_camio_2d import InteractionPolicy2D, CamIOPlayer2D, ModelDetectorAruco, parse_aruco_codes, get_aruco_dict_id_from_string, sort_corners_by_id
from simple_camio_mp import PoseDetectorMP
from simple_camio_mp_3d import PoseDetectorMP3D


# The PoseDetector class determines the pose of the pointer, and returns the
# position of the tip in the coordinate system of the model.
class PoseDetector:
    def __init__(self, model, intrinsic_matrix):
        # Parse the Aruco markers placement positions from the parameter file into a numpy array, and get the associated ids
        self.stylus = self.load_stylus_parameters(model['stylus_file'])
        self.obj, self.list_of_ids = parse_aruco_codes(self.stylus['positioningData']['arucoCodes'])
        self.aruco_dict = cv.aruco.Dictionary_get(get_aruco_dict_id_from_string(self.stylus['positioningData']['arucoType']))
        self.arucoParams = cv.aruco.DetectorParameters_create()
        self.arucoParams.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX
        self.intrinsic_matrix = intrinsic_matrix

    # Function to load stylus parameters from a JSON file
    def load_stylus_parameters(self, filename):
        if os.path.isfile(filename):
            with open(filename, 'r') as f:
                stylus_params = json.load(f)
                print("loaded stylus parameters from file.")
        else:
            print("No stylus parameters file found.")
            exit(0)
        return stylus_params['stylus']

    # Main function to detect aruco markers in the image and use solvePnP to determine the pose
    def detect(self, frame, rvec_model, tvec_model):
        corners, ids, _ = cv.aruco.detectMarkers(frame, self.aruco_dict, parameters=self.arucoParams)
        scene, use_index = sort_corners_by_id(corners, ids, self.list_of_ids)
        if ids is None or not any(use_index):
            print("No pointer detected.")
            return None
        retval, self.rvec_aruco, self.tvec_aruco = cv.solvePnP(self.obj[use_index, :], scene[use_index, :], self.intrinsic_matrix, None)

        # Get pointer location in coordinates of the aruco markers
        point_of_interest = self.reverse_project(self.tvec_aruco, rvec_model, tvec_model)
        return point_of_interest

    # Draw a green dot on the origin to denote where the pointer is pointing
    def drawOrigin(self, img_scene, color=(0, 255, 0)):
        backprojection_pt, other = cv.projectPoints(np.array([0, 0, 0], dtype=np.float32).reshape(1, 3),
                                                    self.rvec_aruco, self.tvec_aruco, self.intrinsic_matrix, None)
        cv.circle(img_scene, (int(backprojection_pt[0, 0, 0]), int(backprojection_pt[0, 0, 1])), 2, color, 2)
        return img_scene

    # Function to reverse the projection of a point given a rvec and tvec
    def reverse_project(self, point, rvec, tvec):
        poi = np.matrix(point)
        R, _ = cv.Rodrigues(rvec)
        R_mat = np.matrix(R)
        R_inv = np.linalg.inv(R_mat)
        T = np.matrix(tvec)
        return np.array(R_inv * (poi - T))


class MovementFilter:
    def __init__(self):
        self.prev_position = None
        self.BETA = 0.5

    def push_position(self, position):
        if self.prev_position is None:
            self.prev_position = position
        else:
            self.prev_position = self.prev_position*(1-self.BETA) + position*self.BETA
        return self.prev_position


class MovementMedianFilter:
    def __init__(self):
        self.MAX_QUEUE_LENGTH = 30
        self.positions = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.times = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.AVERAGING_TIME = .7

    def push_position(self, position):
        self.positions.append(position)
        now = time.time()
        self.times.append(now)
        i = len(self.times)-1
        Xs = []
        Ys = []
        Zs = []
        while i >= 0 and now - self.times[i] < self.AVERAGING_TIME:
            Xs.append(self.positions[i][0])
            Ys.append(self.positions[i][1])
            Zs.append(self.positions[i][2])
            i -= 1
        return np.array([np.median(Xs), np.median(Ys), np.median(Zs)])

class GestureDetector:
    def __init__(self):
        self.MAX_QUEUE_LENGTH = 30
        self.positions = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.times = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.DWELL_TIME_THRESH = .75
        self.X_MVMNT_THRESH = 0.95
        self.Y_MVMNT_THRESH = 0.95
        self.Z_MVMNT_THRESH = 4.0

    def push_position(self, position):
        self.positions.append(position)
        now = time.time()
        self.times.append(now)
        i = len(self.times)-1
        Xs = []
        Ys = []
        Zs = []
        while (i >= 0 and now - self.times[i] < self.DWELL_TIME_THRESH):
            Xs.append(self.positions[i][0])
            Ys.append(self.positions[i][1])
            Zs.append(self.positions[i][2])
            i -= 1
        Xdiff = max(Xs) - min(Xs)
        Ydiff = max(Ys) - min(Ys)
        Zdiff = max(Zs) - min(Zs)
        print("(i: " + str(i) + ") X: " + str(Xdiff) + ", Y: " + str(Ydiff) + ", Z: " + str(Zdiff))
        if Xdiff < self.X_MVMNT_THRESH and Ydiff < self.Y_MVMNT_THRESH and Zdiff < self.Z_MVMNT_THRESH:
            return np.array([sum(Xs)/float(len(Xs)), sum(Ys)/float(len(Ys)), sum(Zs)/float(len(Zs))]), 'still'
        else:
            return position, 'moving'


class AmbientSoundPlayer:
    def __init__(self, soundfile):
        self.sound = pyglet.media.load(soundfile, streaming=False)
        self.player = pyglet.media.Player()
        self.player.queue(self.sound)
        self.player.eos_action = 'loop'
        self.player.loop = True

    def set_volume(self, volume):
        if 0 <= volume <= 1:
            self.player.volume = volume

    def play_sound(self):
        if not self.player.playing:
            self.player.play()

    def pause_sound(self):
        if self.player.playing:
            self.player.pause()


class ImageAnnotator:
    def __init__(self, intrinsic_matrix):
        self.intrinsic_matrix = intrinsic_matrix

    # Draws the axes on the image
    def drawAxes(self, img, imgpts):
        imgpts = imgpts.astype(int)
        corner = tuple(imgpts[3].ravel())
        img = cv.line(img, corner, tuple(imgpts[0].ravel()), (255, 0, 0), 5)
        img = cv.line(img, corner, tuple(imgpts[1].ravel()), (0, 255, 0), 5)
        img = cv.line(img, corner, tuple(imgpts[2].ravel()), (0, 0, 255), 5)
        return img

    # Draws axes and projects the 3D points onto the image
    def draw_points_in_image(self, img_scene_color, obj, rvec, tvec):
        # Draws the 3D points on the image
        backprojection_pts, other = cv.projectPoints(obj, rvec, tvec, self.intrinsic_matrix, None)
        for pts in backprojection_pts:
            cv.circle(img_scene_color, (int(pts[0, 0]), int(pts[0, 1])), 4, (255, 255, 255), 2)
        return img_scene_color

    # Draws axes and projects the 3D points onto the image
    def draw_point_in_image(self, img_scene_color, obj):
        # Draws the 3D points on the image
        cv.circle(img_scene_color, (int(obj[0]), int(obj[1])), 4, (255, 255, 255), 2)
        return img_scene_color

    # Draws axes and projects the 3D points onto the image
    def annotate_image(self, img_scene_color, obj, rvec, tvec):
        # Draws the 3D points on the image
        if len(obj) > 0:
            backprojection_pts, other = cv.projectPoints(obj, rvec, tvec, self.intrinsic_matrix, None)
            for idx, pts in enumerate(backprojection_pts):
                cv.circle(img_scene_color, (int(pts[0, 0]), int(pts[0, 1])), 4, (255, 255, 255), 2)
                cv.line(img_scene_color, (int(pts[0, 0] - 1), int(pts[0, 1])), (int(pts[0, 0]) + 1, int(pts[0, 1])),
                        (255, 0, 0), 1)
                cv.line(img_scene_color, (int(pts[0, 0]), int(pts[0, 1]) - 1), (int(pts[0, 0]), int(pts[0, 1]) + 1),
                        (255, 0, 0), 1)
            # Draw axes on the image
        axis = np.float32([[6, 0, 0], [0, 6, 0], [0, 0, -6], [0, 0, 0]]).reshape(-1, 3)
        axis_pts, other = cv.projectPoints(axis, rvec, tvec, self.intrinsic_matrix, None)
        img_scene_color = self.drawAxes(img_scene_color, axis_pts)
        return img_scene_color


def select_cam_port():
    available_ports, working_ports, non_working_ports = list_ports()
    if len(working_ports) == 1:
        return working_ports[0][0]
    elif len(working_ports) > 1:
        print("The following cameras were detected:")
        for i in range(len(working_ports)):
            print(f'{i}) Port {working_ports[i][0]}: {working_ports[i][1]} x {working_ports[i][2]}')
        cam_selection = input("Please select which camera you would like to use: ")
        return working_ports[int(cam_selection)][0]
    else:
        return 0

def list_ports():
    """
    Test the ports and returns a tuple with the available ports and the ones that are working.
    """
    non_working_ports = []
    dev_port = 0
    working_ports = []
    available_ports = []
    while len(non_working_ports) < 3:  # if there are more than 2 non working ports stop the testing.
        camera = cv.VideoCapture(dev_port)
        if not camera.isOpened():
            non_working_ports.append(dev_port)
            print("Port %s is not working." % dev_port)
        else:
            is_reading, img = camera.read()
            w = camera.get(3)
            h = camera.get(4)
            if is_reading:
                print("Port %s is working and reads images (%s x %s)" % (dev_port, h, w))
                working_ports.append((dev_port, h, w))
            else:
                print("Port %s for camera ( %s x %s) is present but does not read." % (dev_port, h, w))
                available_ports.append(dev_port)
        dev_port += 1
    return available_ports, working_ports, non_working_ports


# Function to load camera intrinsic parameters from a JSON file
def load_camera_parameters(filename):
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            cam_params = json.load(f)
            print("loaded camera parameters from file.")
    else:
        print("No camera parameters file found. Please run simple_calibration.py script.")
        exit(0)
    intrinsic_matrix = np.array([[cam_params['focal_length_x'], 0.0, cam_params['camera_center_x']],
                                 [0.00000000e+00, cam_params['focal_length_y'], cam_params['camera_center_y']],
                                 [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]], dtype=np.float32)
    return intrinsic_matrix


# Function to load map parameters from a JSON file
def load_map_parameters(filename):
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            map_params = json.load(f)
            print("loaded map parameters from file.")
    else:
        print("No map parameters file found.")
        exit(0)
    return map_params['model']


# ========================================
cam_port = select_cam_port()
# ========================================

parser = argparse.ArgumentParser(description='Code for CamIO.')
parser.add_argument('--input1', help='Path to input zone image.', default='UkraineMap.json')
args = parser.parse_args()

# Load map and camera parameters
model = load_map_parameters(args.input1)
intrinsic_matrix = load_camera_parameters('camera_parameters.json')

# Initialize objects
if model["modelType"] == "2D":
    model_detector = ModelDetectorAruco(model, intrinsic_matrix)
    pose_detector = PoseDetector(model, intrinsic_matrix)
    gesture_detector = GestureDetector()
    motion_filter = MovementMedianFilter()
    image_annotator = ImageAnnotator(intrinsic_matrix)
    interact = InteractionPolicy2D(model)
    camio_player = CamIOPlayer2D(model)
    camio_player.play_welcome()
    crickets_player = AmbientSoundPlayer(model['crickets'])
    heartbeat_player = AmbientSoundPlayer(model['heartbeat'])
elif model["modelType"] == "3D":
    model_detector = SIFTModelDetector(model, intrinsic_matrix)
    pose_detector = PoseDetector(model, intrinsic_matrix)
    gesture_detector = GestureDetector()
    motion_filter = MovementMedianFilter()
    image_annotator = ImageAnnotator(intrinsic_matrix)
    interact = InteractionPolicyOBJ(model, intrinsic_matrix)
    camio_player = CamIOPlayerOBJ(model)
    camio_player.play_welcome()
    crickets_player = AmbientSoundPlayer(model['crickets'])
    heartbeat_player = AmbientSoundPlayer(model['heartbeat'])
elif model["modelType"] == "mediapipe":
    model_detector = ModelDetectorAruco(model, intrinsic_matrix)
    pose_detector = PoseDetectorMP(model, intrinsic_matrix)
    motion_filter = MovementMedianFilter()
    image_annotator = ImageAnnotator(intrinsic_matrix)
    interact = InteractionPolicy2D(model)
    camio_player = CamIOPlayer2D(model)
    camio_player.play_welcome()
    crickets_player = AmbientSoundPlayer(model['crickets'])
    heartbeat_player = AmbientSoundPlayer(model['heartbeat'])
elif model["modelType"] == "mediapipe_3d":
    model_detector = SIFTModelDetector(model, intrinsic_matrix)
    pose_detector = PoseDetectorMP3D()
    gesture_detector = GestureDetector()
    motion_filter = MovementMedianFilter()
    image_annotator = ImageAnnotator(intrinsic_matrix)
    interact = InteractionPolicyOBJ(model, intrinsic_matrix)
    camio_player = CamIOPlayerOBJ(model)
    camio_player.play_welcome()
    crickets_player = AmbientSoundPlayer(model['crickets'])
    heartbeat_player = AmbientSoundPlayer(model['heartbeat'])
heartbeat_player.set_volume(.05)
cap = cv.VideoCapture(cam_port)
cap.set(cv.CAP_PROP_FRAME_HEIGHT, 1080)  # set camera image height
cap.set(cv.CAP_PROP_FRAME_WIDTH, 1920)  # set camera image width
cap.set(cv.CAP_PROP_FOCUS, 0)
loop_has_run = False
timer = time.time() - 1

# Main loop
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("No camera image returned.")
        break
    if loop_has_run:
        cv.imshow('image reprojection', img_scene_color)
        waitkey = cv.waitKey(1)
        if waitkey == 27 or waitkey == ord('q'):
            print('Escape.')
            cap.release()
            cv.destroyAllWindows()
            break
        if waitkey == ord('r'):
            model_detector.requires_pnp = True
    prev_time = timer
    timer = time.time()
    elapsed_time = timer - prev_time
    print("current fps: " + str(1/elapsed_time))
    pyglet.clock.tick()
    pyglet.app.platform_event_loop.dispatch_posted_events()
    img_scene_color = frame.copy()
    loop_has_run = True

    # load images grayscale
    img_scene_gray = cv.cvtColor(img_scene_color, cv.COLOR_BGR2GRAY)
    # Detect aruco markers for map in image
    retval, rvec, tvec = model_detector.detect(img_scene_gray)

    # If no  markers found, continue to next iteration
    if not retval:
        heartbeat_player.pause_sound()
        crickets_player.play_sound()
        continue

    crickets_player.pause_sound()
    # Annotate image with 3D points and axes
    if model["modelType"] == "2D":
        img_scene_color = image_annotator.annotate_image(img_scene_color, model_detector.obj, rvec, tvec)
    else:
        img_scene_color = image_annotator.annotate_image(img_scene_color, [], rvec, tvec)

    if model["modelType"] == "mediapipe":
        gesture_loc, gesture_status, img_scene_color = pose_detector.detect(frame, rvec, tvec)
        img_scene_color = image_annotator.annotate_image(img_scene_color, [], rvec, tvec)
        if gesture_loc is None:
            heartbeat_player.pause_sound()
            continue

        heartbeat_player.play_sound()
    elif model["modelType"] == "mediapipe_3d":
        interact.project_vertices(rvec, tvec)
        gesture_loc, gesture_status, img_scene_color = pose_detector.detect(frame)
        img_scene_color = image_annotator.annotate_image(img_scene_color, [], rvec, tvec)
        if gesture_loc is None:
            heartbeat_player.pause_sound()
            continue

        heartbeat_player.play_sound()
    else:
        # Detect aruco marker for pointer in image
        point_of_interest = pose_detector.detect(img_scene_gray, rvec, tvec)

        # If no pointer is detected, move on to the next frame
        if point_of_interest is None:
            heartbeat_player.pause_sound()
            continue

        heartbeat_player.play_sound()
        # Draw where the user was pointing
        img_scene_color = pose_detector.drawOrigin(img_scene_color)

        # Determine if the user is trying to make a gesture
        gesture_loc, gesture_status = gesture_detector.push_position(point_of_interest)

    if gesture_status != "moving":
        if model['modelType'] != "mediapipe_3d":
            img_scene_color = image_annotator.draw_points_in_image(img_scene_color, gesture_loc, rvec, tvec)
        else:
            img_scene_color = image_annotator.draw_point_in_image(img_scene_color, gesture_loc)

    # Determine zone from point of interest
    # Determine zone from point of interest
    zone_id = interact.push_gesture(gesture_loc)

    # If the zone id is valid, play the sound for the zone
    camio_player.convey(zone_id, gesture_status)

camio_player.play_goodbye()
heartbeat_player.pause_sound()
crickets_player.pause_sound()
time.sleep(1)
