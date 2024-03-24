import os
import sys
import cv2 as cv
import datetime
import numpy as np
import argparse
import json
from typing import Tuple
from scipy import optimize


def solvePnP_lists_from_focal_length(fl, obj_list, scene_list, cx, cy):
    sum_of_offsets = 0
    for scene, obj in zip(scene_list, obj_list):
        sum_of_offsets += solvePnP_from_focal_length(fl, obj, scene, cx, cy)
    return sum_of_offsets


def solvePnP_from_focal_length(fl, obj, scene, cx, cy):
    intrinsic_matrix = np.transpose(np.array([[fl[0], 0.0, 0.0], [0.0, fl[0], 0.0], [cx, cy, 1.0]], dtype=np.float32))
    retval, rvec, tvec = cv.solvePnP(obj, scene, intrinsic_matrix, None)
    backprojection_pts, other = cv.projectPoints(obj, rvec, tvec, intrinsic_matrix, None)
    offsets = []
    for i in range(len(scene)):
        offsets.append(np.sqrt(
            (backprojection_pts[i, 0, 0] - scene[i, 0]) ** 2 + (backprojection_pts[i, 0, 1] - scene[i, 1]) ** 2))
    mean_offset = np.mean(offsets)
    return mean_offset


# Parses the list of aruco codes and returns the 2D points and ids
def parse_aruco_codes(list_of_aruco_codes):
    obj_array = np.empty((len(list_of_aruco_codes) * 4, 3), dtype=np.float32)
    ids = []
    for cnt, aruco_code in enumerate(list_of_aruco_codes):
        for i in range(4):
            obj_array[cnt * 4 + i, :] = aruco_code['position'][i]
        ids.append(aruco_code['id'])
    return obj_array, ids


# Function to sort corners by id based on the order specified in the id_list,
# such that the scene array matches the obj array in terms of aruco marker ids
# and the appropriate corners.
def sort_corners_by_id(corners, ids, id_list):
    use_index = np.zeros(len(id_list) * 4, dtype=bool)
    scene = np.empty((len(id_list) * 4, 2), dtype=np.float32)
    for i in range(len(corners)):
        id = ids[i, 0]
        if id in id_list:
            corner_num = id_list.index(id)
            for j in range(4):
                use_index[4 * corner_num + j] = True
                scene[4 * corner_num + j, :] = corners[i][0][j]
    return scene, use_index


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


def resize_with_pad(image: np.array, new_shape: Tuple[int, int],
                    padding_color: Tuple[int] = (255, 255, 255)) -> np.array:
    original_shape = (image.shape[1], image.shape[0])
    ratio = float(max(new_shape)) / max(original_shape)
    new_size = tuple([int(x * ratio) for x in original_shape])

    if new_size[0] > new_shape[0] or new_size[1] > new_shape[1]:
        ratio = float(min(new_shape)) / min(original_shape)
        new_size = tuple([int(x * ratio) for x in original_shape])

    image = cv.resize(image, new_size)
    delta_w = new_shape[0] - new_size[0]
    delta_h = new_shape[1] - new_size[1]
    top, bottom = delta_h // 2, delta_h - (delta_h // 2)
    left, right = delta_w // 2, delta_w - (delta_w // 2)

    image = cv.copyMakeBorder(image, top, bottom, left, right, cv.BORDER_CONSTANT, None, value=padding_color)
    return image


# Function to load map parameters from a JSON file
def load_map_parameters(filename):
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            map_params = json.load(f)
            print("loaded map parameters from file.")
    else:
        print("No parameters file found at " + filename)
        print("Usage: simple_calibration.exe --input1 <filename>")
        print(" ")
        print("Press any key to exit.")
        _ = sys.stdin.read(1)
        exit(0)
    return map_params['model']


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


# ========================================
pixels_per_cm_obj = 118.49  # text-with-aruco.png
focal_length_x = 950.4602909088135
focal_length_y = 950.4602909088135
camera_center_x = 640.0
camera_center_y = 360.0
distortion = np.array([0.09353041, -0.12232207, 0.00182885, -0.00131933, -0.30184632], dtype=np.float32) * 0
# ========================================

parser = argparse.ArgumentParser(description='Code for calibration.')
parser.add_argument('--input1', help='Path to input zone image.', default='models/UkraineMap/UkraineMap.json')
args = parser.parse_args()

intrinsic_matrix = np.array([[focal_length_x, 0.00000000e+00, camera_center_x],
                             [0.00000000e+00, focal_length_y, camera_center_y],
                             [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]], dtype=np.float32)

# Load color image
template_img = cv.imread('template.png', cv.IMREAD_COLOR)

# Load aruco marker positions
model = load_map_parameters(args.input1)
obj, list_of_ids = parse_aruco_codes(model['positioningData']['arucoCodes'])

scene = np.empty((16, 2), dtype=np.float32)
obj_list = []
scene_list = []
use_external_cam = select_cam_port()
cap = cv.VideoCapture(use_external_cam)
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

    # overlay template image on video stream
    if img_scene_color.shape[1] != template_img.shape[1] or img_scene_color.shape[0] != template_img.shape[0]:
        template_img = resize_with_pad(template_img, (img_scene_color.shape[1], img_scene_color.shape[0]), (0,0,0))
    img_scene_color = (img_scene_color /2 + template_img /2) /255

    # Define aruco marker dictionary and parameters object to include subpixel resolution
    aruco_dict = cv.aruco.Dictionary_get(cv.aruco.DICT_4X4_50)
    arucoParams = cv.aruco.DetectorParameters_create()
    arucoParams.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX
    # Detect aruco markers in image
    (corners, ids, rejected) = cv.aruco.detectMarkers(img_scene, aruco_dict, parameters=arucoParams)
    scene, use_index = sort_corners_by_id(corners, ids, list_of_ids)

    if ids is None or not any(use_index):
        #print("No markers found.")
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

    # Draw circles on detected corner points
    for pts in scene[use_index, :]:
        cv.circle(img_scene_color, (int(pts[0]), int(pts[1])), 4, (255, 255, 255), 2)

    now = datetime.datetime.now()
    cv.imshow('image reprojection', img_scene_color)
    waitkey = cv.waitKey(1)
    if waitkey == 27 or waitkey == ord('q'):
        print('Escape.')
        cap.release()
        cv.destroyAllWindows()
        break
    if waitkey == ord('a'):
        obj_list.append(obj[use_index, :])
        scene_list.append(scene[use_index, :])
    if waitkey == ord('g'):
        if len(obj_list) == 0:
            obj_list.append(obj[use_index, :])
            scene_list.append(scene[use_index, :])
        res = optimize.fmin(solvePnP_lists_from_focal_length, 1000,
                            args=(obj_list, scene_list, frame.shape[1]/2, frame.shape[0]/2))
        with open('camera_parameters.json', 'w') as f:
            json.dump({'focal_length_x':res[0], 'focal_length_y':res[0], 'camera_center_x':frame.shape[1]/2, 'camera_center_y':frame.shape[0]/2}, f)
        print(f"focal_length_x = {res[0]}\nfocal_length_y = {res[0]}\n" +
              f"camera_center_x = {frame.shape[1] / 2}\ncamera_center_y = {frame.shape[0] / 2}")
        # minsums = []
        # for fl in np.linspace(300,2300, 201):
        #     minsums.append(solvePnP_lists_from_focal_length([fl], obj_list, scene_list, camera_center_x, camera_center_y))
        # plt.scatter(np.linspace(300,2300, 201), minsums)
        # plt.xlabel('Focal Length')
        # plt.ylabel('Sum of Average Reprojection Error')
        # plt.show()
        obj_list = []
        scene_list = []
    if waitkey == ord('c'):
        res = optimize.fmin(solvePnP_from_focal_length, 1800,
                            args=(obj[use_index, :], scene[use_index, :], camera_center_x, camera_center_y))
        print(f"focal_length_x = {res[0]}\nfocal_length_y = {res[0]}\n" +
              f"camera_center_x = {frame.shape[1]/2}\ncamera_center_y = {frame.shape[0]/2}")
        #cv.imwrite(f'{now.strftime("%Y.%m.%d.%H.%M.%S")}_backproject.jpg', img_scene_color)
