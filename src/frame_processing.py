from typing import Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import numpy.typing as npt

from .utils import *


class SIFTModelDetector:
    def __init__(self, template_filename: str) -> None:
        # Load the template image
        img_template = cv2.imread(template_filename, cv2.IMREAD_GRAYSCALE)
        self.shape = img_template.shape

        # Detect SIFT keypoints
        self.detector = cv2.SIFT_create()
        self.keypoints_obj, self.descriptors_obj = self.detector.detectAndCompute(
            img_template, mask=None
        )

        self.rotation: Optional[npt.NDArray[np.float32]] = None

        self.requires_pnp = True

    def detect(
        self, frame: npt.NDArray[np.uint8]
    ) -> Tuple[bool, Optional[npt.NDArray[np.float32]]]:
        if not self.requires_pnp:
            return True, self.rotation

        keypoints_scene, descriptors_scene = self.detector.detectAndCompute(frame, None)
        matcher = cv2.DescriptorMatcher_create(cv2.DescriptorMatcher_FLANNBASED)
        try:
            knn_matches = matcher.knnMatch(self.descriptors_obj, descriptors_scene, 2)
        except:
            return False, None

        RATIO_THRESH = 0.75
        good_matches = list()
        for m, n in knn_matches:
            if m.distance < RATIO_THRESH * n.distance:
                good_matches.append(m)
        # print("There were {} good matches".format(len(good_matches)))

        # -- Localize the object
        if len(good_matches) < 4:
            return False, None

        obj = np.empty((len(good_matches), 2), dtype=np.float32)
        scene = np.empty((len(good_matches), 2), dtype=np.float32)
        for i in range(len(good_matches)):
            # -- Get the keypoints from the good matches
            obj[i, 0] = self.keypoints_obj[good_matches[i].queryIdx].pt[0]
            obj[i, 1] = self.keypoints_obj[good_matches[i].queryIdx].pt[1]
            scene[i, 0] = keypoints_scene[good_matches[i].trainIdx].pt[0]
            scene[i, 1] = keypoints_scene[good_matches[i].trainIdx].pt[1]

        # Compute homography and find inliers
        H, _ = cv2.findHomography(
            scene, obj, cv2.RANSAC, ransacReprojThreshold=8.0, confidence=0.995
        )

        return H is not None, H


class PoseDetector:
    def __init__(self) -> None:
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def detect(
        self, img: npt.NDArray[np.uint8], H: npt.NDArray[np.float32]
    ) -> Tuple[Optional[npt.NDArray[np.float32]], Optional[str], npt.NDArray[np.uint8]]:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img.flags.writeable = True

        results = self.hands.process(img)

        if not results.multi_hand_landmarks or len(results.multi_hand_landmarks) == 0:
            return None, None, img

        coors = np.zeros((4, 3), dtype=float)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        hand_landmarks = results.multi_hand_landmarks[0]

        for k in [1, 2, 3, 4]:  # joints in thumb
            coors[k - 1, 0], coors[k - 1, 1], coors[k - 1, 2] = (
                hand_landmarks.landmark[k].x,
                hand_landmarks.landmark[k].y,
                hand_landmarks.landmark[k].z,
            )

        for k in [5, 6, 7, 8]:  # joints in index finger
            coors[k - 5, 0], coors[k - 5, 1], coors[k - 5, 2] = (
                hand_landmarks.landmark[k].x,
                hand_landmarks.landmark[k].y,
                hand_landmarks.landmark[k].z,
            )
        ratio_index = self.ratio(coors)

        for k in [9, 10, 11, 12]:  # joints in middle finger
            coors[k - 9, 0], coors[k - 9, 1], coors[k - 9, 2] = (
                hand_landmarks.landmark[k].x,
                hand_landmarks.landmark[k].y,
                hand_landmarks.landmark[k].z,
            )
        ratio_middle = self.ratio(coors)

        for k in [13, 14, 15, 16]:  # joints in ring finger
            coors[k - 13, 0], coors[k - 13, 1], coors[k - 13, 2] = (
                hand_landmarks.landmark[k].x,
                hand_landmarks.landmark[k].y,
                hand_landmarks.landmark[k].z,
            )
        ratio_ring = self.ratio(coors)

        for k in [17, 18, 19, 20]:  # joints in little finger
            coors[k - 17, 0], coors[k - 17, 1], coors[k - 17, 2] = (
                hand_landmarks.landmark[k].x,
                hand_landmarks.landmark[k].y,
                hand_landmarks.landmark[k].z,
            )
        ratio_little = self.ratio(coors)

        # overall = ratio_index / ((ratio_middle + ratio_ring + ratio_little) / 3)
        # print("overall evidence for index pointing:", overall)

        self.mp_drawing.draw_landmarks(
            img,
            hand_landmarks,
            self.mp_hands.HAND_CONNECTIONS,
            self.mp_drawing_styles.get_default_hand_landmarks_style(),
            self.mp_drawing_styles.get_default_hand_connections_style(),
        )

        position = np.array(
            [
                [
                    hand_landmarks.landmark[8].x * img.shape[1],
                    hand_landmarks.landmark[8].y * img.shape[0],
                ]
            ],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        position = cv2.perspectiveTransform(position, H)[0][0]

        if (
            (ratio_index > 0.7)
            and (ratio_middle < 0.95)
            and (ratio_ring < 0.95)
            and (ratio_little < 0.95)
        ):
            print(hand_landmarks.landmark[8].z)
            return (
                np.array([position[0], position[1], 0]),
                "pointing",
                img,
            )
        else:
            return (
                np.array([position[0], position[1], 0]),
                "moving",
                img,
            )

    def ratio(
        self, coors: npt.NDArray[np.float32]
    ) -> (
        np.float32
    ):  # ratio is 1 if points are collinear, lower otherwise (minimum is 0)
        d = np.linalg.norm(coors[0, :] - coors[3, :])
        a = np.linalg.norm(coors[0, :] - coors[1, :])
        b = np.linalg.norm(coors[1, :] - coors[2, :])
        c = np.linalg.norm(coors[2, :] - coors[3, :])

        return d / (a + b + c)
