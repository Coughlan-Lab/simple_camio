import os
import cv2 as cv
import datetime
import numpy as np
import argparse
from scipy import optimize
import matplotlib.pyplot as plt
from map_parameters import *


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


# Function to sort corners by id based on how they are arranged
def sort_corners_by_id(corners, id, scene):
    use_index = np.zeros(16, dtype=bool)
    for i in range(len(corners)):
        corner_num = ids[i, 0]
        if corner_num < 4:
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


# ========================================
pixels_per_cm_obj = 118.49  # text-with-aruco.png
focal_length_x = 950.4602909088135
focal_length_y = 950.4602909088135
camera_center_x = 640.0
camera_center_y = 360.0
distortion = np.array([0.09353041, -0.12232207, 0.00182885, -0.00131933, -0.30184632], dtype=np.float32) * 0
use_external_cam = 0
# ========================================

parser = argparse.ArgumentParser(description='Code for calibration.')
parser.add_argument('--input1', help='Path to input zone image.', default='zone_map.png')
args = parser.parse_args()

intrinsic_matrix = np.array([[focal_length_x, 0.00000000e+00, camera_center_x],
                             [0.00000000e+00, focal_length_y, camera_center_y],
                             [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]], dtype=np.float32)

# Load color image
img_map_color = cv.imread(args.input1, cv.IMREAD_COLOR)  # Image.open(cv.samples.findFile(args.input1))
img_map = cv.cvtColor(img_map_color, cv.COLOR_BGR2GRAY)

scene = np.empty((16, 2), dtype=np.float32)
obj_list = []
scene_list = []

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

    # Define aruco marker dictionary and parameters object to include subpixel resolution
    aruco_dict = cv.aruco.Dictionary_get(cv.aruco.DICT_4X4_50)
    arucoParams = cv.aruco.DetectorParameters_create()
    arucoParams.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX
    # Detect aruco markers in image
    (corners, ids, rejected) = cv.aruco.detectMarkers(img_scene, aruco_dict, parameters=arucoParams)
    scene, use_index = sort_corners_by_id(corners, id, scene)

    if ids is None or not any(use_index):
        #print("No markers found.")
        cv.imshow('image reprojection', img_scene_color)
        waitkey = cv.waitKey(1)
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

    now = datetime.datetime.now()
    cv.imshow('image reprojection', img_scene_color)
    waitkey = cv.waitKey(1)
    if waitkey == ord('a'):
        obj_list.append(obj[use_index, :])
        scene_list.append(scene[use_index, :])
    if waitkey == ord('g'):
        res = optimize.fmin(solvePnP_lists_from_focal_length, 1800,
                            args=(obj_list, scene_list, camera_center_x, camera_center_y))
        print(f"focal_length_x = {res[0]}\nfocal_length_y = {res[0]}\n" +
              f"camera_center_x = {frame.shape[1] / 2}\ncamera_center_y = {frame.shape[0] / 2}")
        minsums = []
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
