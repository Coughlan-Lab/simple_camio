from enum import Enum, IntEnum
from typing import Any, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import numpy.typing as npt

from src.graph import Coords
from src.utils import Buffer

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

landmarks = mp_hands.HandLandmark.__members__.values()

active_landmark_style = mp_styles.get_default_hand_landmarks_style()
inactive_landmark_style = mp_styles.get_default_hand_landmarks_style()
active_connection_style = mp_styles.get_default_hand_connections_style()
inactive_connection_style = mp_styles.get_default_hand_connections_style()

red_style = mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=7, circle_radius=1)
green_style = mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=7, circle_radius=1)
for landmark1 in landmarks:
    active_landmark_style[landmark1] = green_style
    inactive_landmark_style[landmark1] = red_style

    for landmark2 in landmarks:
        if landmark1 == landmark2:
            continue

        active_connection_style[landmark1] = green_style
        inactive_connection_style[landmark1] = red_style


class HandStatus(Enum):
    MORE_THAN_ONE_HAND = -1
    NOT_FOUND = 0
    POINTING = 1
    MOVING = 2


def ratio(
    coors: npt.NDArray[np.float32],
) -> np.float32:  # ratio is 1 if points are collinear, lower otherwise (minimum is 0)
    d = np.linalg.norm(coors[0, :] - coors[3, :])
    a = np.linalg.norm(coors[0, :] - coors[1, :])
    b = np.linalg.norm(coors[1, :] - coors[2, :])
    c = np.linalg.norm(coors[2, :] - coors[3, :])

    return d / (a + b + c)


class Hand:
    POINTING_THRESHOLD = 0.15

    class Side(IntEnum):
        LEFT = 0
        RIGHT = 1

    def __init__(self, side: Side, visible: bool, landmarks) -> None:
        self.side = side
        self.visible = visible
        self.landmarks = landmarks
        self.pointing_ratio = self.__get_pointing_ratio()

    @property
    def is_pointing(self) -> bool:
        return self.pointing_ratio > self.POINTING_THRESHOLD

    @property
    def landmark(self) -> List[Any]:
        return self.landmarks

    def draw(self, img: npt.NDArray[np.uint8]) -> None:
        mp_drawing.draw_landmarks(
            img,
            self,
            connections=mp_hands.HAND_CONNECTIONS,
            landmark_drawing_spec=(
                active_landmark_style if self.is_pointing else inactive_landmark_style
            ),
            connection_drawing_spec=(
                active_connection_style
                if self.is_pointing
                else inactive_connection_style
            ),
        )

    def __get_pointing_ratio(self) -> float:
        """
        This function calculates the pointing ratio of a hand.
        The pointing ratio is a floating point number between -1 and 1.
        If the pointing ratio is positive, the hand is pointing.
        """

        if not self.visible:
            return 0.0

        coors = np.zeros((4, 3), dtype=float)

        for k in [5, 6, 7, 8]:  # joints in index finger
            coors[k - 5, 0], coors[k - 5, 1], coors[k - 5, 2] = (
                self.landmarks[k].x,
                self.landmarks[k].y,
                self.landmarks[k].z,
            )
        ratio_index = ratio(coors)

        for k in [9, 10, 11, 12]:  # joints in middle finger
            coors[k - 9, 0], coors[k - 9, 1], coors[k - 9, 2] = (
                self.landmarks[k].x,
                self.landmarks[k].y,
                self.landmarks[k].z,
            )
        ratio_middle = ratio(coors)

        for k in [13, 14, 15, 16]:  # joints in ring finger
            coors[k - 13, 0], coors[k - 13, 1], coors[k - 13, 2] = (
                self.landmarks[k].x,
                self.landmarks[k].y,
                self.landmarks[k].z,
            )
        ratio_ring = ratio(coors)

        for k in [17, 18, 19, 20]:  # joints in little finger
            coors[k - 17, 0], coors[k - 17, 1], coors[k - 17, 2] = (
                self.landmarks[k].x,
                self.landmarks[k].y,
                self.landmarks[k].z,
            )
        ratio_little = ratio(coors)

        overall = ratio_index - ((ratio_middle + ratio_ring + ratio_little) / 3)
        # print("overall evidence for index pointing:", overall)

        return float(overall)


class PoseDetector:

    def __init__(self, image_size: Tuple[float, float]) -> None:
        self.image_size = image_size

        self.hands_detector = mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.75,
            min_tracking_confidence=0.75,
            max_num_hands=4,
        )
        self.buffers = [Buffer(20) for _ in range(2)]

    def detect(
        self, img: npt.NDArray[np.uint8], H: npt.NDArray[np.float32]
    ) -> Tuple[HandStatus, Optional[Coords], npt.NDArray[np.uint8]]:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        img.flags.writeable = False
        results = self.hands_detector.process(img)
        img.flags.writeable = True

        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        hands = self.process_results(img, H, results)
        if len(hands) == 0:
            return HandStatus.NOT_FOUND, None, img

        for hand in hands:
            hand.draw(img)

        # for i, hand in enumerate(hands):
        #    self.buffers[results.multi_handedness[i].classification[0].index].add(
        #        self.get_index_position(hand, img, H)
        #    )

        pointing_hands = [h for h in hands if h.is_pointing]

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

    def process_results(
        self, img: npt.NDArray[np.uint8], H: npt.NDArray[np.float32], results
    ) -> List[Hand]:
        if not results.multi_hand_landmarks:
            return list()

        return [
            Hand(
                side=Hand.Side(results.multi_handedness[i].classification[0].index),
                visible=self.is_index_on_the_map(hand, img, H),
                landmarks=hand.landmark,
            )
            for i, hand in enumerate(results.multi_hand_landmarks)
        ]
