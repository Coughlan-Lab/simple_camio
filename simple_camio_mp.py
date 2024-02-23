import numpy as np
import cv2 as cv
import mediapipe as mp

class PoseDetectorMP:
    def __init__(self, model, intrinsic_matrix):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.intrinsic_matrix = intrinsic_matrix
        self.image_map_color = cv.imread(model['filename'], cv.IMREAD_COLOR)
        self.pixels_per_cm = model['pixels_per_cm']

    def detect(self, image, rvec_model, tvec_model):
        image = cv.cvtColor(image, cv.COLOR_BGR2RGB)

        results = self.hands.process(image)
        coors = np.zeros((4,3), dtype=float)
        # Draw the hand annotations on the image.
        image.flags.writeable = True
        image = cv.cvtColor(image, cv.COLOR_RGB2BGR)
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

                print(ratio_thumb, ratio_index, ratio_middle, ratio_ring, ratio_little)
                overall = ratio_index / ((ratio_middle + ratio_ring + ratio_little) / 3)
                print('overall evidence for index pointing:', overall)

                self.mp_drawing.draw_landmarks(
                    image,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style())

                corners, _ = cv.projectPoints(np.array([[0,0,0],[self.image_map_color.shape[1]/self.pixels_per_cm, 0, 0],
                                            [self.image_map_color.shape[1]/self.pixels_per_cm,
                                            self.image_map_color.shape[0]/self.pixels_per_cm, 0],
                                            [0, self.image_map_color.shape[0]/self.pixels_per_cm, 0]], dtype=np.float32),
                                            rvec_model, tvec_model, self.intrinsic_matrix, None)

                perspective_transform_matrix = cv.getPerspectiveTransform(np.squeeze(corners),
                                                                          np.array([[0,0],[self.image_map_color.shape[1]/self.pixels_per_cm,0],
                                                                          [self.image_map_color.shape[1]/self.pixels_per_cm,
                                                                          self.image_map_color.shape[0]/self.pixels_per_cm],
                                                                          [0, self.image_map_color.shape[0]/self.pixels_per_cm]], dtype=np.float32), cv.DECOMP_LU)

                position = np.matmul(perspective_transform_matrix, np.array([hand_landmarks.landmark[8].x*image.shape[1],
                                                                             hand_landmarks.landmark[8].y*image.shape[0], 1]))
                if (ratio_index > 0.7) and (ratio_middle < 0.95) and (ratio_ring < 0.95) and (ratio_little < 0.95):
                    print(hand_landmarks.landmark[8])
                    return np.array([position[0]/position[2], position[1]/position[2], 0], dtype=float), "pointing", image
                else:
                    return np.array([position[0]/position[2], position[1]/position[2], 0], dtype=float), "moving", image
        return None, None, image


    def ratio(self, coors):  # ratio is 1 if points are collinear, lower otherwise (minimum is 0)
        d = np.linalg.norm(coors[0, :] - coors[3, :])
        a = np.linalg.norm(coors[0, :] - coors[1, :])
        b = np.linalg.norm(coors[1, :] - coors[2, :])
        c = np.linalg.norm(coors[2, :] - coors[3, :])

        return d / (a + b + c)

class InteractionPolicyMP:
    def __init__(self, model, intrinsic_matrix):
        self.model = model
        self.intrinsic_matrix = intrinsic_matrix
        self.image_map_color = cv.imread(model['filename'], cv.IMREAD_COLOR)
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