import numpy as np
import cv2 as cv
import mediapipe as mp
from scipy import stats
from .simple_camio_3d import OBJ, find_closest_point

class PoseDetectorMP3D:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(model_complexity=0, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def detect(self, image):
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
                #
                # print(ratio_thumb, ratio_index, ratio_middle, ratio_ring, ratio_little)
                # overall = ratio_index / ((ratio_middle + ratio_ring + ratio_little) / 3)
                # print('overall evidence for index pointing:', overall)

                self.mp_drawing.draw_landmarks(
                    image,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style())

                position = np.array(
                    [hand_landmarks.landmark[8].x * image.shape[1], hand_landmarks.landmark[8].y * image.shape[0]])

                if (ratio_index > 0.7) and (ratio_middle < 0.95) and (ratio_ring < 0.95) and (ratio_little < 0.95):
                    #print(hand_landmarks.landmark[8])
                    return position, "pointing", image
                else:
                    return position, "moving", image
        return None, None, image


    def ratio(self, coors):  # ratio is 1 if points are collinear, lower otherwise (minimum is 0)
        d = np.linalg.norm(coors[0, :] - coors[3, :])
        a = np.linalg.norm(coors[0, :] - coors[1, :])
        b = np.linalg.norm(coors[1, :] - coors[2, :])
        c = np.linalg.norm(coors[2, :] - coors[3, :])

        return d / (a + b + c)

class InteractionPolicyOBJObject:
    def __init__(self, model, intrinsic_matrix):
        self.model = model
        self.ZONE_FILTER_SIZE = 5
        self.D_SET_THRESHOLD = 1
        self.D_THRESHOLD = 2.0 * self.D_SET_THRESHOLD
        self.zone_filter = -1 * np.ones(self.ZONE_FILTER_SIZE, dtype=int)
        self.zone_filter_cnt = 0
        self.intrinsic_matrix = intrinsic_matrix
        self.map_obj = OBJ(model["model_file"], model.get("excluded_regions",[]), swapyz=model.get("swapyz",True))
        R = np.array(model["model_rotation"], dtype=np.float32)
        T = np.array(model["model_translation"], dtype=np.float32)
        offset = np.array(model["model_offset"], dtype=np.float32)
        vertices = np.array(self.map_obj.vertices, dtype=np.float32).transpose()
        vertsmult = np.matmul(R, vertices) + T - offset
        self.vertices_3d = vertsmult.transpose()
        self.mid_point = np.mean(self.vertices_3d, axis=0)

    def project_vertices(self, R, T):
        vertices, _ = cv.projectPoints(self.vertices_3d, R, T, self.intrinsic_matrix, None)
        self.vertices = np.squeeze(vertices)
        self.D_SET_THRESHOLD = 30
        self.D_THRESHOLD = 2.0 * self.D_SET_THRESHOLD
        R_mat, _ = cv.Rodrigues(R)
        R_inv = np.linalg.inv(R_mat)
        self.T = np.matmul(R_inv,-T).transpose()

    def push_gesture(self, position):
        # First determine which points are on the right side of the object
        is_visible = np.linalg.norm(self.mid_point-self.T) > np.linalg.norm(self.vertices_3d-self.T,axis=1)
        idx = np.linspace(0,len(is_visible),len(is_visible),endpoint=False,dtype=int)[is_visible]
        min_idx, dist = find_closest_point(position, self.vertices[is_visible,:])
        self.zone_filter[self.zone_filter_cnt] = self.map_obj.vertex_reg_id[idx[min_idx]]
        self.zone_filter_cnt = (self.zone_filter_cnt + 1) % self.ZONE_FILTER_SIZE
        zone = stats.mode(self.zone_filter).mode
        if isinstance(zone, np.ndarray):
            zone = zone[0]
        if dist < self.D_THRESHOLD:
            self.D_THRESHOLD = 3.0 * self.D_SET_THRESHOLD
            return self.map_obj.Region_names[zone]
        else:
            self.D_THRESHOLD = 2.0 * self.D_SET_THRESHOLD
            return -1