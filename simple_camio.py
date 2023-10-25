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


# Function to sort corners by id based on how they are arranged
def sort_corners_by_id(corners, ids, id_list, scene):
    use_index = np.zeros(len(id_list)*4, dtype=bool)
    for i in range(len(corners)):
        id = ids[i, 0]
        if id in id_list:
            corner_num = id_list.index(id)
            for j in range(4):
                use_index[4 * corner_num + j] = True
                scene[4 * corner_num + j, :] = corners[i][0][j]
    return scene, use_index


# Function to reverse the projection of a point given a rvec and tvec
def reverse_project(point, rvec, tvec):
    poi = np.matrix(point)
    R, _ = cv.Rodrigues(rvec)
    R_mat = np.matrix(R)
    R_inv = np.linalg.inv(R_mat)
    T = np.matrix(tvec)
    return np.array(R_inv * (poi - T))


# Function to create 3D points from 2D pixels on a sheet of paper
def get_3d_points_from_pixels(obj_pts, pixels_per_cm):
    pts_3d = np.empty((len(obj_pts), 3), dtype=np.float32)
    for i in range(len(obj_pts)):
        pts_3d[i, 0] = obj_pts[i, 0] / pixels_per_cm
        pts_3d[i, 1] = obj_pts[i, 1] / pixels_per_cm
        pts_3d[i, 2] = 0
    return pts_3d


# Draws the axes on the image
def drawAxes(img, imgpts):
    imgpts = imgpts.astype(int)
    corner = tuple(imgpts[3].ravel())
    img = cv.line(img, corner, tuple(imgpts[0].ravel()), (255, 0, 0), 5)
    img = cv.line(img, corner, tuple(imgpts[1].ravel()), (0, 255, 0), 5)
    img = cv.line(img, corner, tuple(imgpts[2].ravel()), (0, 0, 255), 5)
    return img


# Retrieves the zone of the point of interest on the map
def get_zone(point_of_interest, img_map, pixels_per_cm):
    x = int(point_of_interest[0] * pixels_per_cm)
    y = int(point_of_interest[1] * pixels_per_cm)
    if 0 <= x < img_map.shape[1] and 0 <= y < img_map.shape[0]:
        return img_map[y, x]
    else:
        return 0


def match_color(rgb_color_list, bgr_color_np_array):
    if np.array_equal(np.array(rgb_color_list[::-1]), np.squeeze(bgr_color_np_array)):
        return True
    else:
        return False


# Returns the dictionary in the list of dictionaries that matches the color given
def get_dict_from_color(list_of_dicts, color):
    for dictionary in list_of_dicts:
        if (dictionary['color'] == color):
            return dictionary
    return None


# Returns the index of the dictionary in the list of dictionaries that matches the color given
def get_dict_idx_from_color(list_of_dicts, color):
    for i in range(len(list_of_dicts)):
        dictionary = list_of_dicts[i]
        if match_color(dictionary['color'], color):
            return i
    return -1


# Parses the list of aruco codes and returns the 2D points and ids
def parse_aruco_codes(list_of_aruco_codes):
    obj = np.empty((len(list_of_aruco_codes)*4,3), dtype=np.float32)
    ids = []
    for cnt, aruco_code in enumerate(list_of_aruco_codes):
        for i in range(4):
            obj[cnt*4+i,:] = aruco_code['position'][i]
        ids.append(aruco_code['id'])
    return obj, ids


# Returns the dictionary code for the given string
def get_arcuo_dict_from_string(aruco_dict_string):
    if aruco_dict_string == "DICT_4X4_50":
        return cv.aruco.DICT_4X4_50
    elif aruco_dict_string == "DICT_4X4_100":
        return cv.aruco.DICT_4X4_100
    elif aruco_dict_string == "DICT_4X4_250":
        return cv.aruco.DICT_4X4_250
    elif aruco_dict_string == "DICT_4X4_1000":
        return cv.aruco.DICT_4X4_1000
    elif aruco_dict_string == "DICT_5X5_50":
        return cv.aruco.DICT_5X5_50
    elif aruco_dict_string == "DICT_5X5_100":
        return cv.aruco.DICT_5X5_100
    elif aruco_dict_string == "DICT_5X5_250":
        return cv.aruco.DICT_5X5_250

#========================================
pixels_per_cm_obj = 118.49  # text-with-aruco.png
focal_length_x = 1.88842395e+03
focal_length_y = 1.89329463e+03
camera_center_x = 9.21949329e+02
camera_center_y = 3.34464319e+02
distortion = np.array([0.09353041, -0.12232207, 0.00182885, -0.00131933, -0.30184632], dtype=np.float32) * 0
use_external_cam = 0
#========================================

parser = argparse.ArgumentParser(description='Code for CamIO.')
parser.add_argument('--input1', help='Path to input zone image.', default='UkraineMap.json')
args = parser.parse_args()

if os.path.isfile('camera_parameters.json'):
    with open('camera_parameters.json', 'r') as f:
        cam_params = json.load(f)
        print("loaded camera parameters from file.")
else:
    print("No camera parameters file found. Please run simple_calibration.py script.")
    exit(0)
intrinsic_matrix = np.array([[cam_params['focal_length_x'], 0.0, cam_params['camera_center_x']],
                             [0.00000000e+00, cam_params['focal_length_y'], cam_params['camera_center_y']],
                             [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]], dtype=np.float32)

# Zone filter logic
prev_zone_name = None
zone_filter_size = 10
zone_filter = -1*np.ones(zone_filter_size, dtype=int)
zone_filter_cnt = 0

# Load map parameters
with open(args.input1, 'r') as fp:
    map_params_data = json.load(fp)
model = map_params_data['model']
# Load color image
img_map_color = cv.imread(model['filename'], cv.IMREAD_COLOR)  # Image.open(cv.samples.findFile(args.input1))
img_map = cv.cvtColor(img_map_color, cv.COLOR_BGR2GRAY)

obj, list_of_ids = parse_aruco_codes(model['positioningData']['arucoCodes'])
scene = np.empty((len(list_of_ids)*4, 2), dtype=np.float32)
player = pyglet.media.Player()
cap = cv.VideoCapture(use_external_cam)
start_time = time.time()
cap.set(cv.CAP_PROP_FRAME_HEIGHT,1080) #set camera image height
cap.set(cv.CAP_PROP_FRAME_WIDTH,1920) #set camera image width
cap.set(cv.CAP_PROP_FOCUS,0)

# Main loop
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("No camera image returned.")
        break

    img_scene_color = frame

    # load images grayscale
    img_scene = cv.cvtColor(img_scene_color, cv.COLOR_BGR2GRAY)

    # Define aruco marker dictionary and parameters object to include subpixel resolution
    aruco_dict = cv.aruco.Dictionary_get(get_arcuo_dict_from_string(model['positioningData']['arucoType']))
    arucoParams = cv.aruco.DetectorParameters_create()
    arucoParams.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX
    # Detect aruco markers in image
    (corners, ids, rejected) = cv.aruco.detectMarkers(img_scene, aruco_dict, parameters=arucoParams)
    scene, use_index = sort_corners_by_id(corners, ids, list_of_ids, scene)

    if ids is None or not any(use_index):
        print("No markers found.")
        cv.imshow('image reprojection', img_scene_color)
        waitkey = cv.waitKey(1)
        if waitkey == 27:
            print('Escape.')
            cap.release()
            cv.destroyAllWindows()
            break
        continue

    # Run solvePnP using the markers that have been observed
    retval, rvec, tvec = cv.solvePnP(obj[use_index, :], scene[use_index, :], intrinsic_matrix, None)

    # Draw axes on the image
    axis = np.float32([[6, 0, 0], [0, 6, 0], [0, 0, -6], [0, 0, 0]]).reshape(-1, 3)
    axis_pts, other = cv.projectPoints(axis, rvec, tvec, intrinsic_matrix, None)
    img_scene_color = drawAxes(img_scene_color, axis_pts)

    # Draw circles on the backprojected corner points
    backprojection_pts, other = cv.projectPoints(obj, rvec, tvec, intrinsic_matrix, None)
    for idx, pts in enumerate(backprojection_pts):
        cv.circle(img_scene_color, (int(pts[0, 0]), int(pts[0, 1])), 4, (255, 255, 255), 2)
        cv.line(img_scene_color, (int(pts[0, 0] - 1), int(pts[0, 1])), (int(pts[0, 0]) + 1, int(pts[0, 1])),
                (255, 0, 0), 1)
        cv.line(img_scene_color, (int(pts[0, 0]), int(pts[0, 1]) - 1), (int(pts[0, 0]), int(pts[0, 1]) + 1),
                (255, 0, 0), 1)
        # cv.line(img_scene_color, (int(pts[0,0]), int(pts[0,1])), (int(scene[idx,0]), int(scene[idx,1])), (0, 255, 0), 1)

    # Set up aruco detection for the pointer marker
    aruco_dict = cv.aruco.Dictionary_get(cv.aruco.DICT_5X5_50)
    dp = cv.aruco.DetectorParameters_create()
    dp.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX

    corners, ids, _ = cv.aruco.detectMarkers(img_scene, aruco_dict, parameters=dp)
    obj_aruco = np.empty((4, 3), dtype=np.float32)
    scene_aruco = np.empty((4, 2), dtype=np.float32)

    # if we are just using 1 large marker
    obj_aruco[0, :] = [0.5, 0.5, 0]
    obj_aruco[1, :] = [3.5, 0.5, 0]
    obj_aruco[2, :] = [3.5, 3.5, 0]
    obj_aruco[3, :] = [0.5, 3.5, 0]

    if len(corners) > 0:
        for i in range(4):
            scene_aruco[i, :] = corners[0][0][i]
            cv.circle(img_scene_color, (int(scene_aruco[i, 0]), int(scene_aruco[i, 1])), 3, (255, 255, 255), 2)
    else:
        cv.imshow('image reprojection', img_scene_color)
        waitkey = cv.waitKey(1)
        if waitkey == 27:
            print('Escape.')
            cap.release()
            cv.destroyAllWindows()
            break
        continue

    retval, rvec_aruco, tvec_aruco = cv.solvePnP(obj_aruco, scene_aruco, intrinsic_matrix, distortion)
    # Backproject pointer tip and draw it on the image
    backprojection_pt, other = cv.projectPoints(np.array([0, 0, 0], dtype=np.float32).reshape(1, 3), rvec_aruco,
                                                tvec_aruco, intrinsic_matrix, distortion)
    if len(corners) > 0:
        cv.circle(img_scene_color, (int(backprojection_pt[0, 0, 0]), int(backprojection_pt[0, 0, 1])), 2, (0, 255, 0), 2)

    # Get pointer location in coordinates of the aruco markers
    point_of_interest = reverse_project(tvec_aruco, rvec, tvec)

    # Filter the zones by returning the mode of the last [zone_filter_size] zones
    zone_color = get_zone(point_of_interest, img_map_color, pixels_per_cm_obj)
    zone_filter[zone_filter_cnt] = get_dict_idx_from_color(model['hotspots'], zone_color)
    zone_filter_cnt = (zone_filter_cnt + 1) % zone_filter_size
    zone = stats.mode(zone_filter).mode[0]

    # Check if the Z position is within the threshold, if so, play a sound
    Z_threshold_cm = 2.0
    if np.abs(point_of_interest[2]) < Z_threshold_cm and zone > -1:
        zone_name = model['hotspots'][zone]['textDescription']
        if prev_zone_name != zone_name:
            soundfile = model['hotspots'][zone]['audioDescription']
            if os.path.exists(soundfile) and time.time() - start_time > 0.5:
                sound = pyglet.media.load(soundfile, streaming=False)
                # player.next_source()
                # player.queue(sound)
                # player.play()
                try:
                    sound.play()
                except(BaseException):
                    print("Exception raised. Cannot play sound. Please restart the application.")
                start_time = time.time()
                #playsound(soundfile, block=False)
        prev_zone_name = zone_name
        print(zone_name)
    else:
        pass
        #prev_zone_name = None
    # print(point_of_interest)#, dist, current_region)

    now = datetime.datetime.now()
    cv.imshow('image reprojection', img_scene_color)
    waitkey = cv.waitKey(1)
    if waitkey == ord('s'):
        cv.imwrite(f'{now.strftime("%Y.%m.%d.%H.%M.%S")}_backproject.jpg', img_scene_color)
    if waitkey == 27 or waitkey == ord('q'):#Escape key
        print('Escape.')
        cap.release()
        cv.destroyAllWindows()
        break