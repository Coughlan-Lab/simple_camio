from enum import Enum, IntEnum
from typing import Any, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import numpy.typing as npt
from mediapipe.tasks.python.vision import RunningMode
from src.graph import Coords
from src.utils import Buffer

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

landmarks = mp_hands.HandLandmark.__members__.values()

active_landmark_style = mp_styles.get_default_hand_landmarks_style()
inactive_landmark_style = mp_styles.get_default_hand_landmarks_style()
connection_style = mp_styles.get_default_hand_connections_style()

red_style = mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=5, circle_radius=1)
green_style = mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=5, circle_radius=1)
blue_style = mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=5, circle_radius=1)
for landmark1 in landmarks:
    active_landmark_style[landmark1] = green_style
    inactive_landmark_style[landmark1] = red_style


class HandStatus(Enum):
    MORE_THAN_ONE_HAND = -1
    NOT_FOUND = 0
    POINTING = 1
    EXPLORING = 2


def ratio(coors: npt.NDArray[np.float32]) -> np.float32:
    """
    This function calculates a value between 0 and 1 that represents how close the points are to be collinear.
    1 means that the points are collinear, 0 means that the points are as far as possible.
    """
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

    def draw(self, img: npt.NDArray[np.uint8], active: bool = False) -> None:
        mp_drawing.draw_landmarks(
            img,
            self,
            connections=mp_hands.HAND_CONNECTIONS,
            landmark_drawing_spec=(
                active_landmark_style if active else inactive_landmark_style
            ),
            connection_drawing_spec=connection_style,
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
    MOVEMENT_THRESHOLD = 0.25  # inch

    def __init__(self, image_size: Tuple[float, float], feets_per_inch: float) -> None:
        self.image_size = image_size
        self.movement_threshold = self.MOVEMENT_THRESHOLD * feets_per_inch

        self.hands_detector = mp_hands.Hands(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.75,
            min_tracking_confidence=0.75,
            max_num_hands=4,
        )
        self.buffers = [
            Buffer[Coords](15) for _ in range(2)
        ]  # Left and right hand buffers
        self.last_side_pointing: Optional[Hand.Side] = None

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

        hands_per_side = {
            side: [h for h in hands if h.side == side] for side in Hand.Side
        }
        if (
            len(hands_per_side[Hand.Side.LEFT]) > 1
            or len(hands_per_side[Hand.Side.RIGHT]) > 1
        ):
            for hand in hands:
                hand.draw(img, active=False)
            return HandStatus.MORE_THAN_ONE_HAND, None, img

        for hand in hands:
            self.buffers[hand.side].add(self.get_index_position(hand, img, H))

        pointing_hands = [h for h in hands if h.is_pointing]

        if len(pointing_hands) == 0:
            self.last_side_pointing = None
            for hand in hands:
                hand.draw(img, active=False)
            return HandStatus.EXPLORING, None, img

        if len(pointing_hands) == 1:
            self.last_side_pointing = pointing_hands[0].side

        if self.is_moving(Hand.Side.LEFT):
            self.last_side_pointing = Hand.Side.LEFT

        if self.is_moving(Hand.Side.RIGHT):
            self.last_side_pointing = Hand.Side.RIGHT

        for hand in hands:
            hand.draw(img, active=hand.side == self.last_side_pointing)

        if self.last_side_pointing is not None:
            return (
                HandStatus.POINTING,
                self.buffers[self.last_side_pointing].last(),
                img,
            )

        return HandStatus.EXPLORING, None, img

    def is_moving(self, side: Hand.Side) -> bool:
        first = self.buffers[side].first()
        last = self.buffers[side].last()

        if first is None or last is None:
            return False

        return last.distance_to(first) > self.movement_threshold

    def get_index_position(
        self, hand, img: npt.NDArray[np.uint8], H: npt.NDArray[np.float32]
    ) -> Coords:
        position = np.array(
            [
                [
                    hand.landmark[8].x * img.shape[1],
                    hand.landmark[8].y * img.shape[0],
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
