import os
import sys
import cv2 as cv
import time
import zipfile
import numpy as np
import json
import argparse
import pyglet.media
from collections import deque
from simple_camio_2d import InteractionPolicy2D, CamIOPlayer2D
from simple_camio_mp import PoseDetectorMP, SIFTModelDetectorMP



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


def draw_rect_in_image(image, sz, H):
    img_corners = np.array([[0,0],[sz[1],0],[sz[1],sz[0]],[0,sz[0]]], dtype=np.float32)
    img_corners = np.reshape(img_corners, [-1, 1, 2])
    H_inv = np.linalg.inv(H)
    pts = cv.perspectiveTransform(img_corners, H_inv)
    for pt in pts:
        image = cv.circle(image, (int(pt[0][0]), int(pt[0][1])), 3, (0, 255, 0), -1)
    return image


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

# Function to load from a .camio file
def load_camio_file(filename):
    model = {"filename":"ColorMap.png",
      "template_image": "template.png",
      "blipsound":"MP3/quick_blip.wav",
      "welcome_message":"MP3/welcome.mp3",
      "goodbye_message":"MP3/goodbye.mp3",
      "heartbeat": "MP3/white_noise.mp3",
      "crickets": "MP3/crickets.mp3",
      "modelType": "sift_2d_mediapipe"
        }
    if os.path.isfile(filename):
        with zipfile.ZipFile(filename, "r") as zip_ref:
            zip_ref.extractall()
            zip_list = zip_ref.namelist()
        for filename in zip_list:
            if "data.json" in filename:
                datafile = filename
                break
        for filename in zip_list:
            if "colorMap.png" in filename:
                model["filename"] = filename
                break
        for filename in zip_list:
            if "template.png" in filename:
                model['template_image'] = filename
                break
        with open(datafile, "r") as f:
            map_params = json.load(f)
            model["hotspots"] = map_params["hotspots"]
            for hotspot in model["hotspots"]:
                if "sound" in hotspot:
                    hotspot["audioDescription"] = hotspot["sound"]
                else:
                    hotspot["audioDescription"] = ""
                hotspot['textDescription'] = hotspot['title'] + '. ' + hotspot['description']
    return model, zip_list


# Function to load map parameters from a JSON file
def load_map_parameters(filename):
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            map_params = json.load(f)
            print("loaded map parameters from file.")
    else:
        print("No map parameters file found at " + filename)
        print("Usage: simple_camio.exe --input1 <filename>")
        print(" ")
        print("Press any key to exit.")
        _ = sys.stdin.read(1)
        exit(0)
    return map_params['model']


parser = argparse.ArgumentParser(description='Code for CamIO.')
parser.add_argument('--input1', help='Path to parameter json file.', default='models/UkraineMap/UkraineMap.json')
args = parser.parse_args()

model_path = args.input1
if ".camio" in model_path:
    model, zip_list = load_camio_file(model_path)
else:
    # Load map and camera parameters
    model = load_map_parameters(model_path)
    zip_list = None

# ========================================
cam_port = select_cam_port()
# ========================================

# Initialize objects
if model["modelType"] == "sift_2d_mediapipe":
    model_detector = SIFTModelDetectorMP(model)
    pose_detector = PoseDetectorMP(model)
    gesture_detector = GestureDetector()
    motion_filter = MovementMedianFilter()
    interact = InteractionPolicy2D(model)
    camio_player = CamIOPlayer2D(model)
    camio_player.play_welcome()
    crickets_player = AmbientSoundPlayer(model['crickets'])
    heartbeat_player = AmbientSoundPlayer(model['heartbeat'])

if zip_list:
    for file in zip_list:
        if os.path.isfile(file):
            os.remove(file)
heartbeat_player.set_volume(.05)
cap = cv.VideoCapture(cam_port)
cap.set(cv.CAP_PROP_FRAME_HEIGHT, 1080)  # set camera image height
cap.set(cv.CAP_PROP_FRAME_WIDTH, 1920)  # set camera image width
cap.set(cv.CAP_PROP_FOCUS, 0)
loop_has_run = False
timer = time.time() - 1
print("Press \"h\" key to update map position in image.")
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
        if waitkey == ord('h'):
            model_detector.requires_homography = True
        if waitkey == ord('b'):
            camio_player.enable_blips = not camio_player.enable_blips
            if camio_player.enable_blips:
                print("Blips have been enabled.")
            else:
                print("Blips have been disabled.")
    prev_time = timer
    timer = time.time()
    elapsed_time = timer - prev_time
    #print("current fps: " + str(1/elapsed_time))
    pyglet.clock.tick()
    pyglet.app.platform_event_loop.dispatch_posted_events()
    img_scene_color = frame.copy()
    loop_has_run = True

    # load images grayscale
    img_scene_gray = cv.cvtColor(img_scene_color, cv.COLOR_BGR2GRAY)
    # Detect aruco markers for map in image
    retval, H, tvec = model_detector.detect(img_scene_gray)

    # If no  markers found, continue to next iteration
    if not retval:
        heartbeat_player.pause_sound()
        crickets_player.play_sound()
        continue

    camio_player.play_description()
    crickets_player.pause_sound()

    gesture_loc, gesture_status, img_scene_color = pose_detector.detect(frame, H, tvec)
    if gesture_loc is None:
        heartbeat_player.pause_sound()
        img_scene_color = draw_rect_in_image(img_scene_color, interact.image_map_color.shape, H)
        continue
    heartbeat_player.play_sound()

    # Determine zone from point of interest
    zone_id = interact.push_gesture(gesture_loc)

    # If the zone id is valid, play the sound for the zone
    camio_player.convey(zone_id, gesture_status)

    # Draw points in image
    img_scene_color = draw_rect_in_image(img_scene_color, interact.image_map_color.shape, H)

camio_player.play_goodbye()
heartbeat_player.pause_sound()
crickets_player.pause_sound()
time.sleep(1)
