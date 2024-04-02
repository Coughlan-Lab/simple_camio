# mypy: ignore-errors
import numpy as np
from .frame_processor import FrameProcessor
from ..simple_camio_mp import ModelDetectorArucoMP, PoseDetectorMP
from ..simple_camio_2d import CamIOPlayer2D, InteractionPolicy2D
import cv2


class FingerAruco2DFP(FrameProcessor):
    def get_audio_player(self):
        return CamIOPlayer2D(self.content.as_dict())

    def get_model_detector(self):
        return ModelDetectorArucoMP(self.content.as_dict())

    def get_interaction_policy(self):
        return InteractionPolicy2D(self.content.as_dict())

    def get_pose_detector(self):
        return PoseDetectorMP(self.content.as_dict())

    def process(self, img: np.ndarray) -> np.ndarray:
        img = super().process(img)

        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ok, rotation, translation = self.model_detector.detect(img_gray)

        if not ok:
            self.heartbeat_player.pause_sound()
            self.crickets_player.play_sound()
            return img
        self.crickets_player.pause_sound()

        gesture_loc, gesture_status, img = self.pose_detector.detect(
            img, rotation, translation
        )

        if gesture_loc is None:
            self.heartbeat_player.pause_sound()
            return img
        self.heartbeat_player.play_sound()

        zone_id = self.interaction.push_gesture(gesture_loc)
        self.audio_player.convey(zone_id, gesture_status)
        return img
