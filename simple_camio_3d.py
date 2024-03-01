import cv2 as cv
import numpy as np
import pyglet
import os
import csv
import time
from numba import jit
from scipy import stats
from collections import deque


class SIFTModelDetector:
    def __init__(self, model, intrinsic_matrix):
        self.model = model
        # Load the template image
        img_object = cv.imread(model["template_image"], cv.IMREAD_GRAYSCALE)

        # Detect SIFT keypoints
        self.detector = cv.SIFT_create()
        self.keypoints_obj, self.descriptors_obj = self.detector.detectAndCompute(img_object, mask=None)
        self.rvec = None
        self.tvec = None
        self.requires_pnp = True
        self.intrinsic_matrix = intrinsic_matrix

    def detect(self, frame):
        # If we have already computed the coordinate transform then simply return it
        if not self.requires_pnp:
            return True, self.rvec, self.tvec
        keypoints_scene, descriptors_scene = self.detector.detectAndCompute(frame, None)
        matcher = cv.DescriptorMatcher_create(cv.DescriptorMatcher_FLANNBASED)
        knn_matches = matcher.knnMatch(self.descriptors_obj, descriptors_scene, 2)

        # Only keep uniquely good matches
        RATIO_THRESH = 0.75
        good_matches = []
        for m, n in knn_matches:
            if m.distance < RATIO_THRESH * n.distance:
                good_matches.append(m)
        print("There were {} good matches".format(len(good_matches)))
        # -- Localize the object
        if len(good_matches) < 4:
            return False, None, None
        obj = np.empty((len(good_matches), 2), dtype=np.float32)
        scene = np.empty((len(good_matches), 2), dtype=np.float32)
        for i in range(len(good_matches)):
            # -- Get the keypoints from the good matches
            obj[i, 0] = self.keypoints_obj[good_matches[i].queryIdx].pt[0]
            obj[i, 1] = self.keypoints_obj[good_matches[i].queryIdx].pt[1]
            scene[i, 0] = keypoints_scene[good_matches[i].trainIdx].pt[0]
            scene[i, 1] = keypoints_scene[good_matches[i].trainIdx].pt[1]
        # Compute homography and find inliers
        H, mask_out = cv.findHomography(obj, scene, cv.RANSAC, ransacReprojThreshold=8.0, confidence=0.995)

        obj_inliers = np.empty((np.sum(mask_out), 2))
        scene_inliers = np.empty((np.sum(mask_out), 2))
        cnt = 0
        for i in range(len(mask_out)):
            if mask_out[i, 0] > 0:
                obj_inliers[cnt, :] = obj[i, :]
                scene_inliers[cnt, :] = scene[i, :]
                cnt = cnt + 1
        # Check the area covered by the inliers to see if we have enough coverage to be considered good
        hull = cv.convexHull(scene_inliers.astype(np.int32))
        if hull is None:
            hull_area = 0.0
        else:
            hull_area = cv.contourArea(hull)
        if hull_area < self.model["hull_area_thresh"] or len(scene_inliers) < self.model["inliers_thresh"] or len(obj_inliers) == 0:
            return False, None, None

        # Convert obj points to 3d points
        obj_3d = get_3d_points_from_pixels(obj_inliers, self.model["pixels_per_cm"])

        # Run PnP to get rotation and translation vectors
        retval, self.rvec, self.tvec = cv.solvePnP(obj_3d, scene_inliers, self.intrinsic_matrix, None)
        self.requires_pnp = not retval
        return retval, self.rvec, self.tvec


class InteractionPolicyOBJ:
    def __init__(self, model, intrinsic_matrix):
        self.model = model
        self.ZONE_FILTER_SIZE = 5
        self.D_SET_THRESHOLD = 1
        self.D_THRESHOLD = 2.0 * self.D_SET_THRESHOLD
        self.zone_filter = -1 * np.ones(self.ZONE_FILTER_SIZE, dtype=int)
        self.zone_filter_cnt = 0
        self.intrinsic_matrix = intrinsic_matrix
        self.map_obj = OBJ(model["model_file"], model.get("excluded_regions",[]), swapyz=True)
        R = np.array(model["model_rotation"], dtype=np.float32)
        T = np.array(model["model_translation"], dtype=np.float32)
        offset = np.array(model["model_offset"], dtype=np.float32)
        vertices = np.array(self.map_obj.vertices, dtype=np.float32).transpose()
        vertsmult = np.matmul(R, vertices) + T - offset
        self.vertices = vertsmult.transpose()

    def project_vertices(self, R, T):
        if self.vertices.shape[1] == 2:
            return
        vertices, _ = cv.projectPoints(self.vertices, R, T, self.intrinsic_matrix, None)
        self.vertices = np.squeeze(vertices)
        self.D_SET_THRESHOLD = 10
        self.D_THRESHOLD = 2.0 * self.D_SET_THRESHOLD

    def push_gesture(self, position):
        min_idx, dist = find_closest_point(position, self.vertices)
        self.zone_filter[self.zone_filter_cnt] = self.map_obj.vertex_reg_id[min_idx]
        self.zone_filter_cnt = (self.zone_filter_cnt + 1) % self.ZONE_FILTER_SIZE
        zone_id = stats.mode(self.zone_filter).mode
        if isinstance(zone_id, np.ndarray):
            zone_id = zone_id[0]
        if dist < self.D_THRESHOLD:
            self.D_THRESHOLD = 3.0 * self.D_SET_THRESHOLD
            return self.map_obj.Region_names[zone_id]
        else:
            self.D_THRESHOLD = 2.0 * self.D_SET_THRESHOLD
            return -1


class GestureDetector:
    def __init__(self):
        self.MAX_QUEUE_LENGTH = 30
        self.positions = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.times = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.DWELL_TIME_THRESH = .75
        self.X_MVMNT_THRESH = 0.5
        self.Y_MVMNT_THRESH = 0.5
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


# Class to load and represent an object file
class OBJ:
    def __init__(self, filename, exclude_regions=[], swapyz=False):
        """Loads a Wavefront OBJ file. """
        self.vertices = []
        self.normals = []
        self.texcoords = []
        self.faces = []
        self.Region_names = []
        self.vertex_reg_id = []

        material = None
        current_reg_id = -1
        for line in open(filename, "r"):
            if line.startswith('#'): continue
            values = line.split()
            if not values: continue
            if values[0] == 'o':
                self.Region_names.append(values[1])
                current_reg_id += 1
            elif current_reg_id > -1 and \
                    any([reg_name in self.Region_names[current_reg_id] for reg_name in exclude_regions]):
                continue
            elif values[0] == 'v':
                v = list(map(float, values[1:4]))
                if swapyz:
                    v = v[0], v[2], v[1]
                self.vertices.append(v)
                self.vertex_reg_id.append(current_reg_id)
            elif values[0] == 'vn':
                v = list(map(float, values[1:4]))
                if swapyz:
                    v = v[0], v[2], v[1]
                self.normals.append(v)
            elif values[0] == 'vt':
                self.texcoords.append(map(float, values[1:3]))
            elif values[0] in ('usemtl', 'usemat'):
                material = values[1]
            elif values[0] == 'mtllib':
                self.mtl = (values[1])
            elif values[0] == 'f':
                face = []
                texcoords = []
                norms = []
                for v in values[1:]:
                    w = v.split('/')
                    face.append(int(w[0]))
                    if len(w) >= 2 and len(w[1]) > 0:
                        texcoords.append(int(w[1]))
                    else:
                        texcoords.append(0)
                    if len(w) >= 3 and len(w[2]) > 0:
                        norms.append(int(w[2]))
                    else:
                        norms.append(0)
                self.faces.append((face, norms, texcoords, material))


class CamIOPlayerOBJ:
    def __init__(self, model):
        self.model = model
        self.prev_zone = None
        self.prev_zone_moving = -1
        self.sound_files = {}
        self.player = pyglet.media.Player()
        self.blip_sound = pyglet.media.load(self.model['blipsound'], streaming=False)
        self.welcome_message = pyglet.media.load(self.model['welcome_message'], streaming=False)
        self.goodbye_message = pyglet.media.load(self.model['goodbye_message'], streaming=False)
        zone_dict = self.generate_zone_dict(self.model['soundfile_mapping'])
        for key in zone_dict.keys():
            if os.path.exists(zone_dict[key]):
                self.sound_files[key] = pyglet.media.load(zone_dict[key], streaming=False)
            else:
                print("warning. file not found:" + zone_dict[key])

    # Function to generate a dictionary for names of zones based on a csv file
    def generate_zone_dict(self, csv_file):
        zone_dict = {}
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                zone_dict[row['Object ID']] = row['Name']
        return zone_dict

    def play_welcome(self):
        self.welcome_message.play()

    def play_goodbye(self):
        self.goodbye_message.play()

    def convey(self, zone, status):
        if status == "moving":
            if self.prev_zone_moving != zone:
                if self.player.playing:
                    self.player.delete()
                try:
                    self.player = self.blip_sound.play()
                except(BaseException):
                    print("Exception raised. Cannot play sound. Please restart the application.")
                self.prev_zone_moving = zone
            #self.prev_zone = None
            return
        if zone not in self.sound_files:
            self.prev_zone = None
            return
        if self.prev_zone != zone:
            if self.player.playing:
                self.player.delete()
            sound = self.sound_files[zone]
            try:
                self.player = sound.play()
            except(BaseException):
                print("Exception raised. Cannot play sound. Please restart the application.")
            self.prev_zone = zone


# Function to turn pixel positions into 3D world coordinates
def get_3d_points_from_pixels(obj_pts, pixels_per_cm):
    pts_3d = np.empty((len(obj_pts), 3), dtype=np.float32)
    for i in range(len(obj_pts)):
        pts_3d[i, 0] = obj_pts[i, 0] / pixels_per_cm
        pts_3d[i, 1] = obj_pts[i, 1] / pixels_per_cm
        pts_3d[i, 2] = 0
    return pts_3d


@jit(nopython=True)
def find_closest_point(point, points):
    """Finds the closest point in a list of points to a given point"""
    min_dist = np.linalg.norm(point.transpose() - points[0, :])
    min_index = 0
    for i in range(1, len(points)):
        dist = np.linalg.norm(point.transpose() - points[i, :])
        if dist < min_dist:
            min_dist = dist
            min_index = i
    return min_index, min_dist
