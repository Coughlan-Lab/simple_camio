import numpy as np
import cv2 as cv
import mediapipe as mp

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

                print(ratio_thumb, ratio_index, ratio_middle, ratio_ring, ratio_little)
                overall = ratio_index / ((ratio_middle + ratio_ring + ratio_little) / 3)
                print('overall evidence for index pointing:', overall)

                self.mp_drawing.draw_landmarks(
                    image,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style())

                position = np.array(
                    [hand_landmarks.landmark[8].x * image.shape[1], hand_landmarks.landmark[8].y * image.shape[0]])

                if (ratio_index > 0.7) and (ratio_middle < 0.95) and (ratio_ring < 0.95) and (ratio_little < 0.95):
                    print(hand_landmarks.landmark[8])
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
