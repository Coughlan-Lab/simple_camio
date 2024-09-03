from enum import Enum
from typing import Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import numpy.typing as npt

from src.graph import Coords


class HandStatus(Enum):
    MORE_THAN_ONE_HAND = -1
    NOT_FOUND = 0
    POINTING = 1
    MOVING = 2


class PoseDetector:
    POINTING_THRESHOLD = 0.15
    MAP_MARGIN = 50  # meters

    def __init__(self, image_size: Tuple[float, float]) -> None:
        self.image_size = image_size

        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.75,
            min_tracking_confidence=0.5,
            max_num_hands=4,
        )

        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def detect(
        self, img: npt.NDArray[np.uint8], H: npt.NDArray[np.float32]
    ) -> Tuple[HandStatus, Optional[Coords], npt.NDArray[np.uint8]]:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        img.flags.writeable = False
        results = self.hands.process(img)
        img.flags.writeable = True

        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        hands = results.multi_hand_landmarks
        if not hands or len(hands) == 0:
            return HandStatus.NOT_FOUND, None, img

        for hand in hands:
            self.mp_drawing.draw_landmarks(
                img,
                hand,
                self.mp_hands.HAND_CONNECTIONS,
                self.mp_drawing_styles.get_default_hand_landmarks_style(),
                self.mp_drawing_styles.get_default_hand_connections_style(),
            )

        hands = list(filter(lambda h: self.is_index_on_the_map(h, img, H), hands))
        ratios = list(map(lambda h: self.pointing_ratio(h), hands))
        pointing_hands = [
            h for h, r in zip(hands, ratios) if r > self.POINTING_THRESHOLD
        ]

        if len(pointing_hands) == 0:
            return HandStatus.MOVING, None, img
        if len(pointing_hands) > 1:
            return HandStatus.MORE_THAN_ONE_HAND, None, img

        pointing_hand = pointing_hands[0]

        return (
            HandStatus.POINTING,
            self.get_index_position(pointing_hand, img, H),
            img,
        )

    def get_index_position(
        self, hand_landmarks, img: npt.NDArray[np.uint8], H: npt.NDArray[np.float32]
    ) -> Coords:
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
        return Coords(position[0], position[1])

    def is_index_on_the_map(
        self, hand_landmarks, img: npt.NDArray[np.uint8], H: npt.NDArray[np.float32]
    ) -> bool:
        index_position = self.get_index_position(hand_landmarks, img, H)

        return (
            0 <= index_position[0] < self.image_size[0]
            and 0 <= index_position[1] < self.image_size[1]
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
