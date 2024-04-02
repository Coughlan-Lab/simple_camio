# mypy: ignore-errors
from .frame_processor import FrameProcessor
from ..simple_camio import PoseDetector
from ..simple_camio_3d import CamIOPlayerOBJ, InteractionPolicyOBJ
from ..simple_camio_2d import ModelDetectorAruco
import cv2
import numpy as np


class StylusArucop3DFP(FrameProcessor):
    def get_audio_player(self):
        return CamIOPlayerOBJ(self.content.as_dict())

    def get_model_detector(self):
        return ModelDetectorAruco(self.content.as_dict(), self.intrinsic_matrix)

    def get_interaction_policy(self):
        return InteractionPolicyOBJ(self.content.as_dict(), self.intrinsic_matrix)

    def get_pose_detector(self):
        return PoseDetector(self.content.as_dict(), self.intrinsic_matrix)

    def process(self, img: np.ndarray) -> np.ndarray:
        img = super().process(img)

        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ok, rotation, translation = self.model_detector.detect(img_gray)

        if not ok:
            self.heartbeat_player.pause_sound()
            self.crickets_player.play_sound()
            return img
        self.crickets_player.pause_sound()

        img = self.annotator.annotate_image(img, [], rotation, translation)

        # Detect aruco marker for pointer in image
        point_of_interest = self.pose_detector.detect(img_gray, rotation, translation)

        # If no pointer is detected, move on to the next frame
        if point_of_interest is None:
            self.heartbeat_player.pause_sound()
            return img
        self.heartbeat_player.play_sound()

        # Draw where the user was pointing
        img = self.pose_detector.drawOrigin(img)

        # Determine if the user is trying to make a gesture
        gesture_loc, gesture_status = self.gesture_detector.push_position(
            point_of_interest
        )

        if gesture_status != "moving":
            img = self.annotator.draw_points_in_image(
                img, gesture_loc, rotation, translation
            )

        zone_id = self.interaction.push_gesture(gesture_loc)
        self.audio_player.convey(zone_id, gesture_status)
        return img
