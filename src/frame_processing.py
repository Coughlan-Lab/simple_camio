from enum import Enum
from typing import Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import numpy.typing as npt

from src.utils import *


class SIFTModelDetector:
    def __init__(self, template_filename: str) -> None:
        # Load the template image
        img_template = cv2.imread(template_filename, cv2.IMREAD_GRAYSCALE)

        # Detect SIFT keypoints
        self.detector = cv2.SIFT_create()
        self.keypoints_obj, self.descriptors_obj = self.detector.detectAndCompute(
            img_template, mask=None
        )

    def detect(
        self, frame: npt.NDArray[np.uint8]
    ) -> Tuple[bool, Optional[npt.NDArray[np.float32]]]:
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


class HandStatus(Enum):
    MORE_THAN_ONE_HAND = -1
    NOT_FOUND = 0
    POINTING = 1
    MOVING = 2


class PoseDetector:
    POINTING_THRESHOLD = 0.15

    def __init__(self) -> None:
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.8,
            min_tracking_confidence=0.5,
            max_num_hands=4,
        )

        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def detect(
        self, img: npt.NDArray[np.uint8], H: npt.NDArray[np.float32]
    ) -> Tuple[HandStatus, Optional[Tuple[float, float]], npt.NDArray[np.uint8]]:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        img.flags.writeable = False
        results = self.hands.process(img)
        img.flags.writeable = True

        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        if not results.multi_hand_landmarks or len(results.multi_hand_landmarks) == 0:
            return HandStatus.NOT_FOUND, None, img

        ratios = [self.pointing_ratio(hand) for hand in results.multi_hand_landmarks]
        pointing_ratios = [
            (i, r) for i, r in enumerate(ratios) if r > self.POINTING_THRESHOLD
        ]

        if len(pointing_ratios) > 1:
            return HandStatus.MORE_THAN_ONE_HAND, None, img

        pointing_hand_index = max(range(len(ratios)), key=lambda i: ratios[i])
        pointing_ratio = ratios[pointing_hand_index]
        pointing_hand = results.multi_hand_landmarks[pointing_hand_index]

        self.mp_drawing.draw_landmarks(
            img,
            pointing_hand,
            self.mp_hands.HAND_CONNECTIONS,
            self.mp_drawing_styles.get_default_hand_landmarks_style(),
            self.mp_drawing_styles.get_default_hand_connections_style(),
        )

        position = np.array(
            [
                [
                    pointing_hand.landmark[8].x * img.shape[1],
                    pointing_hand.landmark[8].y * img.shape[0],
                ]
            ],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        position = cv2.perspectiveTransform(position, H)[0][0]
        hand_status = HandStatus.MOVING

        if pointing_ratio > 0.15:
            hand_status = HandStatus.POINTING

        return (
            hand_status,
            (position[0], position[1]),
            img,
        )

    def pointing_ratio(self, hand_landmarks) -> float:
        """
        This function calculates the pointing ratio of a hand.
        The pointing ratio is a floating point number between -1 and 1.
        If the pointing ratio is positive, the hand is pointing.
        """

        coors = np.zeros((4, 3), dtype=float)

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

        overall = ratio_index - ((ratio_middle + ratio_ring + ratio_little) / 3)
        # print("overall evidence for index pointing:", overall)

        return float(overall)

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
