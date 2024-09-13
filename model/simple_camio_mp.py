import cv2
import numpy as np
import cv2 as cv
import mediapipe as mp
from scipy import stats
from tkinter import simpledialog
from collections import deque
from .simple_camio_2d import parse_aruco_codes, get_aruco_dict_id_from_string, sort_corners_by_id
from google.protobuf.json_format import MessageToDict


class ModelDetectorArucoMP:
    def __init__(self, model):
        # Parse the Aruco markers placement positions from the parameter file into a numpy array, and get the associated ids
        self.obj, self.list_of_ids = parse_aruco_codes(model['positioningData']['arucoCodes'])
        # Define aruco marker dictionary and parameters object to include subpixel resolution
        self.aruco_dict_scene = cv.aruco.Dictionary_get(
            get_aruco_dict_id_from_string(model['positioningData']['arucoType']))
        self.arucoParams = cv.aruco.DetectorParameters_create()
        self.arucoParams.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX

    def detect(self, frame):
        # Detect the markers in the frame
        (corners, ids, rejected) = cv.aruco.detectMarkers(frame, self.aruco_dict_scene, parameters=self.arucoParams)
        scene, use_index = sort_corners_by_id(corners, ids, self.list_of_ids)
        if ids is None or not any(use_index):
            print("No markers found.")
            return False, None, None

        # Run solvePnP using the markers that have been observed to determine the pose
        H, mask_out = cv.findHomography(scene[use_index, :], self.obj[use_index, :2], cv.RANSAC, ransacReprojThreshold=8.0, confidence=0.995)
        return True, H, None


def ratio(coors):  # ratio is 1 if points are collinear, lower otherwise (minimum is 0)
    d = np.linalg.norm(coors[0, :] - coors[3, :])
    a = np.linalg.norm(coors[0, :] - coors[1, :])
    b = np.linalg.norm(coors[1, :] - coors[2, :])
    c = np.linalg.norm(coors[2, :] - coors[3, :])

    return d / (a + b + c)


class PoseDetectorMP:
    def __init__(self, model):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.pixels_per_cm = model['pixels_per_cm']

    def detect(self, image, H, _):
        image = cv.cvtColor(image, cv.COLOR_BGR2RGB)
        handedness = list()
        results = self.hands.process(image)
        coors = np.zeros((4,3), dtype=float)
        # Draw the hand annotations on the image.
        image.flags.writeable = True
        image = cv.cvtColor(image, cv.COLOR_RGB2BGR)
        index_pos = None
        movement_status = None
        if results.multi_hand_landmarks:
            for h, hand_landmarks in enumerate(results.multi_hand_landmarks):
                handedness.append(MessageToDict(results.multi_handedness[h])['classification'][0]['label'])
                for k in [1, 2, 3, 4]:  # joints in thumb
                    coors[k - 1, 0], coors[k - 1, 1], coors[k - 1, 2] = hand_landmarks.landmark[k].x, \
                                                                        hand_landmarks.landmark[k].y, \
                                                                        hand_landmarks.landmark[k].z
                ratio_thumb = ratio(coors)

                for k in [5, 6, 7, 8]:  # joints in index finger
                    coors[k - 5, 0], coors[k - 5, 1], coors[k - 5, 2] = hand_landmarks.landmark[k].x, \
                                                                        hand_landmarks.landmark[k].y, \
                                                                        hand_landmarks.landmark[k].z
                ratio_index = ratio(coors)

                for k in [9, 10, 11, 12]:  # joints in middle finger
                    coors[k - 9, 0], coors[k - 9, 1], coors[k - 9, 2] = hand_landmarks.landmark[k].x, \
                                                                        hand_landmarks.landmark[k].y, \
                                                                        hand_landmarks.landmark[k].z
                ratio_middle = ratio(coors)

                for k in [13, 14, 15, 16]:  # joints in ring finger
                    coors[k - 13, 0], coors[k - 13, 1], coors[k - 13, 2] = hand_landmarks.landmark[k].x, \
                                                                           hand_landmarks.landmark[k].y, \
                                                                           hand_landmarks.landmark[k].z
                ratio_ring = ratio(coors)

                for k in [17, 18, 19, 20]:  # joints in little finger
                    coors[k - 17, 0], coors[k - 17, 1], coors[k - 17, 2] = hand_landmarks.landmark[k].x, \
                                                                           hand_landmarks.landmark[k].y, \
                                                                           hand_landmarks.landmark[k].z
                ratio_little = ratio(coors)

                # print(ratio_thumb, ratio_index, ratio_middle, ratio_ring, ratio_little)
                # overall = ratio_index / ((ratio_middle + ratio_ring + ratio_little) / 3)
                # print('overall evidence for index pointing:', overall)

                self.mp_drawing.draw_landmarks(
                    image,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style())

                position = np.matmul(H, np.array([hand_landmarks.landmark[8].x*image.shape[1],
                                                  hand_landmarks.landmark[8].y*image.shape[0], 1]))
                if index_pos is None:
                    index_pos = np.array([position[0]/position[2], position[1]/position[2], 0], dtype=float)
                    #index_pos = np.array([hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y, 0])
                if (ratio_index > 0.7) and (ratio_middle < 0.95) and (ratio_ring < 0.95) and (ratio_little < 0.95):
                    if movement_status != "pointing" or len(handedness) > 1 and handedness[1] == handedness[0]:
                        index_pos = np.array([position[0] / position[2], position[1] / position[2], 0], dtype=float)
                        #index_pos = np.array([hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y, 0])
                        movement_status = "pointing"
                    else:
                        index_pos =np.append(index_pos, np.array([position[0] / position[2], position[1] / position[2], 0], dtype=float))
                        movement_status = "too_many"
                elif movement_status != "pointing":
                    movement_status = "moving"
        return index_pos, movement_status, image, results


class InteractionPolicyMP:
    def __init__(self, model):
        self.model = model
        self.image_map_color = cv.imread(model['preview'], cv.IMREAD_COLOR)
        self.ZONE_FILTER_SIZE = 10
        self.Z_THRESHOLD = 2.0
        self.zone_filter = -1 * np.ones(self.ZONE_FILTER_SIZE, dtype=int)
        self.zone_filter_cnt = 0

    def push_gesture(self, position):
        zone_color = self.get_zone(position, self.image_map_color, self.model['pixels_per_cm'])
        self.zone_filter[self.zone_filter_cnt] = self.get_dict_idx_from_color(zone_color)
        self.zone_filter_cnt = (self.zone_filter_cnt + 1) % self.ZONE_FILTER_SIZE
        zone = stats.mode(self.zone_filter).mode
        if isinstance(zone, np.ndarray):
            zone = zone[0]
        if np.abs(position[2]) < self.Z_THRESHOLD:
            return zone
        else:
            return -1


class HotspotConstructor:
    def __init__(self, camio_player, interaction_policy):
        self.MAX_QUEUE_LENGTH = 5
        self.MIN_TOUCH_COUNT = 4
        self.is_pointing = list()
        self.is_index_touching = deque(maxlen=self.MAX_QUEUE_LENGTH)
        self.is_currently_touching = False
        self.camio_player = camio_player
        self.interaction_policy = interaction_policy

    def detect(self, results, img):
        coors = np.zeros((4, 3), dtype=float)
        is_pointing = list()
        index_pos = list()
        has_pointed = False
        has_three_fingers = False
        dist = 0
        info_string = str()
        if results.multi_hand_landmarks:
            for h, hand_landmarks in enumerate(results.multi_hand_landmarks):
                for k in [1, 2, 3, 4]:  # joints in thumb
                    coors[k - 1, 0], coors[k - 1, 1], coors[k - 1, 2] = hand_landmarks.landmark[k].x, \
                                                                        hand_landmarks.landmark[k].y, \
                                                                        hand_landmarks.landmark[k].z
                ratio_thumb = ratio(coors)

                for k in [5, 6, 7, 8]:  # joints in index finger
                    coors[k - 5, 0], coors[k - 5, 1], coors[k - 5, 2] = hand_landmarks.landmark[k].x, \
                                                                        hand_landmarks.landmark[k].y, \
                                                                        hand_landmarks.landmark[k].z
                ratio_index = ratio(coors)

                for k in [9, 10, 11, 12]:  # joints in middle finger
                    coors[k - 9, 0], coors[k - 9, 1], coors[k - 9, 2] = hand_landmarks.landmark[k].x, \
                                                                        hand_landmarks.landmark[k].y, \
                                                                        hand_landmarks.landmark[k].z
                ratio_middle = ratio(coors)

                for k in [13, 14, 15, 16]:  # joints in ring finger
                    coors[k - 13, 0], coors[k - 13, 1], coors[k - 13, 2] = hand_landmarks.landmark[k].x, \
                                                                           hand_landmarks.landmark[k].y, \
                                                                           hand_landmarks.landmark[k].z
                ratio_ring = ratio(coors)

                for k in [17, 18, 19, 20]:  # joints in little finger
                    coors[k - 17, 0], coors[k - 17, 1], coors[k - 17, 2] = hand_landmarks.landmark[k].x, \
                                                                           hand_landmarks.landmark[k].y, \
                                                                           hand_landmarks.landmark[k].z
                ratio_little = ratio(coors)
                is_pointing.append(
                    ratio_index > 0.7 and ratio_middle < 0.95 and ratio_ring < 0.95 and ratio_little < 0.95)
                if (ratio_index > 0.7 and ratio_middle < 0.95 and ratio_ring < 0.95 and ratio_little < 0.95):
                    has_pointed = True
                is_three_fingers = ratio_index > 0.7 and ratio_middle > 0.7 and ratio_ring > 0.7 and ratio_little < 0.95
                distance = max(np.linalg.norm(np.array([hand_landmarks.landmark[8].x - hand_landmarks.landmark[12].x,
                                                    hand_landmarks.landmark[8].y - hand_landmarks.landmark[12].y,
                                                    hand_landmarks.landmark[8].z - hand_landmarks.landmark[12].z])),
                                np.linalg.norm(np.array([hand_landmarks.landmark[16].x - hand_landmarks.landmark[12].x,
                                                    hand_landmarks.landmark[16].y - hand_landmarks.landmark[12].y,
                                                    hand_landmarks.landmark[16].z - hand_landmarks.landmark[12].z])))
                if is_three_fingers and distance < 0.09:
                    has_three_fingers = True

                index_pos.append(hand_landmarks.landmark[8])
            if len(is_pointing) > 1:
                if (has_pointed and has_three_fingers):  # (is_pointing[0] and is_pointing[1]) or
                    dist = np.linalg.norm(np.array([(index_pos[0].x - index_pos[1].x) * img.shape[1],
                                                    (index_pos[0].y - index_pos[1].y) * img.shape[0]]))
                    # print(dist)
                    self.is_index_touching.append(dist < 60)
                else:
                    self.is_index_touching.append(False)
            else:
                self.is_index_touching.append(False)
        else:
            self.is_index_touching.append(False)
        if not self.is_currently_touching:
            cnt = 0
            for is_touching in self.is_index_touching:
                cnt += int(is_touching)
            if cnt >= self.MIN_TOUCH_COUNT:
                self.is_currently_touching = True
                return True, dist
        else:
            cnt = 0
            for is_touching in self.is_index_touching:
                cnt += int(not is_touching)
            if cnt >= self.MIN_TOUCH_COUNT:
                self.is_currently_touching = False
        return False, dist

    def add_hotspot(self, point, content):
        self.camio_player.play_sparkle()
        label = simpledialog.askstring("Label","Please type the label for this point:")
        if label is None:
            return
        color = self.camio_player.add_new_hotspot(label)
        self.interaction_policy.make_new_hotspot(point, color)
        content.write_to_json()



class SIFTModelDetectorMP:
    def __init__(self, model):
        self.model = model
        # Load the template image
        img_object = cv.imread(
            model["template_image"], cv.IMREAD_GRAYSCALE
        )

        # Detect SIFT keypoints
        self.detector = cv.SIFT_create()
        self.keypoints_obj, self.descriptors_obj = self.detector.detectAndCompute(
            img_object, mask=None
        )
        self.requires_homography = True
        self.H = None
        self.MIN_INLIER_COUNT = 40

    def detect(self, frame):
        # If we have already computed the coordinate transform then simply return it
        if not self.requires_homography:
            return True, self.H, None
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
        self.scene = np.empty((len(good_matches), 2), dtype=np.float32)
        for i in range(len(good_matches)):
            # -- Get the keypoints from the good matches
            obj[i, 0] = self.keypoints_obj[good_matches[i].queryIdx].pt[0]
            obj[i, 1] = self.keypoints_obj[good_matches[i].queryIdx].pt[1]
            self.scene[i, 0] = keypoints_scene[good_matches[i].trainIdx].pt[0]
            self.scene[i, 1] = keypoints_scene[good_matches[i].trainIdx].pt[1]
        # Compute homography and find inliers
        H, self.mask_out = cv.findHomography(
            self.scene, obj, cv.RANSAC, ransacReprojThreshold=8.0, confidence=0.995
        )
        total = sum([int(i) for i in self.mask_out])
        obj_in = np.empty((total,2),dtype=np.float32)
        scene_in = np.empty((total,2),dtype=np.float32)
        index = 0
        for i in range(len(self.mask_out)):
            if self.mask_out[i]:
                obj_in[index,:] = obj[i,:]
                scene_in[index,:] = self.scene[i,:]
                index += 1
        scene_out = np.squeeze(cv2.perspectiveTransform(scene_in.reshape(-1,1,2), H))
        biggest_distance = 0
        sum_distance = 0
        for i in range(len(scene_out)):
            dist = cv2.norm(obj_in[i,:],scene_out[i,:],cv2.NORM_L2)
            sum_distance += dist
            if dist > biggest_distance:
                biggest_distance = dist
        ave_dist = sum_distance/total
        print(f'Inlier count: {total}. Biggest distance: {biggest_distance}. Average distance: {ave_dist}.')
        if total > self.MIN_INLIER_COUNT:
            self.H = H
            self.requires_homography = False
            return True, H, None
        elif self.H is not None:
            return True, self.H, None
        else:
            return False, None, None

