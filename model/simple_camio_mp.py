import numpy as np
import cv2 as cv
import mediapipe as mp
from scipy import stats
from .simple_camio_2d import parse_aruco_codes, get_aruco_dict_id_from_string, sort_corners_by_id


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


class PoseDetectorMP:
    def __init__(self, model):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.pixels_per_cm = model['pixels_per_cm']

    def detect(self, image, H, _):
        image = cv.cvtColor(image, cv.COLOR_BGR2RGB)

        results = self.hands.process(image)
        coors = np.zeros((4,3), dtype=float)
        # Draw the hand annotations on the image.
        image.flags.writeable = True
        image = cv.cvtColor(image, cv.COLOR_RGB2BGR)
        index_pos = None
        movement_status = None
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                for k in [1, 2, 3, 4]:  # joints in thumb
                    coors[k - 1, 0], coors[k - 1, 1], coors[k - 1, 2] = hand_landmarks.landmark[k].x, \
                                                                        hand_landmarks.landmark[k].y, \
                                                                        hand_landmarks.landmark[k].z
                ratio_thumb = self.ratio(coors)

                for k in [5, 6, 7, 8]:  # joints in index finger
                    coors[k - 5, 0], coors[k - 5, 1], coors[k - 5, 2] = hand_landmarks.landmark[k].x, \
                                                                        hand_landmarks.landmark[k].y, \
                                                                        hand_landmarks.landmark[k].z
                ratio_index = self.ratio(coors)

                for k in [9, 10, 11, 12]:  # joints in middle finger
                    coors[k - 9, 0], coors[k - 9, 1], coors[k - 9, 2] = hand_landmarks.landmark[k].x, \
                                                                        hand_landmarks.landmark[k].y, \
                                                                        hand_landmarks.landmark[k].z
                ratio_middle = self.ratio(coors)

                for k in [13, 14, 15, 16]:  # joints in ring finger
                    coors[k - 13, 0], coors[k - 13, 1], coors[k - 13, 2] = hand_landmarks.landmark[k].x, \
                                                                           hand_landmarks.landmark[k].y, \
                                                                           hand_landmarks.landmark[k].z
                ratio_ring = self.ratio(coors)

                for k in [17, 18, 19, 20]:  # joints in little finger
                    coors[k - 17, 0], coors[k - 17, 1], coors[k - 17, 2] = hand_landmarks.landmark[k].x, \
                                                                           hand_landmarks.landmark[k].y, \
                                                                           hand_landmarks.landmark[k].z
                ratio_little = self.ratio(coors)

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
                if (ratio_index > 0.7) and (ratio_middle < 0.95) and (ratio_ring < 0.95) and (ratio_little < 0.95):
                    index_pos = np.array([position[0] / position[2], position[1] / position[2], 0], dtype=float)
                    movement_status = "pointing"
                elif movement_status != "pointing":
                    movement_status = "moving"
        return index_pos, movement_status, image, results

    def ratio(self, coors):  # ratio is 1 if points are collinear, lower otherwise (minimum is 0)
        d = np.linalg.norm(coors[0, :] - coors[3, :])
        a = np.linalg.norm(coors[0, :] - coors[1, :])
        b = np.linalg.norm(coors[1, :] - coors[2, :])
        c = np.linalg.norm(coors[2, :] - coors[3, :])

        return d / (a + b + c)

class InteractionPolicyMP:
    def __init__(self, model):
        self.model = model
        self.image_map_color = cv.imread(model['preview'], cv.IMREAD_COLOR)
        self.ZONE_FILTER_SIZE = 10
        self.Z_THRESHOLD = 2.0
        self.zone_filter = -1 * np.ones(self.ZONE_FILTER_SIZE, dtype=int)
        self.zone_filter_cnt = 0

    # Sergio: we are currently returning the zone id also when the ring buffer is not full. Is this the desired behavior?
    # the impact is clearly minor, but conceptually I am not convinced that this is the right behavior.
    # Sergio (2): I have a concern about this function, I will discuss it in an email.
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
        self.H = H
        self.requires_homography = False
        return True, H, None

