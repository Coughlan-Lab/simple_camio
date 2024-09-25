# mypy: ignore-errors
from ..content import Content
from .frame_processor import FrameProcessor
from ..simple_camio_mp_3d import PoseDetectorMP3D
from ..simple_camio_3d import SIFTModelDetector, CamIOPlayerOBJ, InteractionPolicyOBJ
import cv2
import numpy as np


class FingerSift3DFP(FrameProcessor):
    def get_audio_player(self):
        return CamIOPlayerOBJ(self.content.as_dict())

    def get_model_detector(self):
        return SIFTModelDetector(self.content.as_dict(), self.intrinsic_matrix)

    def get_interaction_policy(self):
        return InteractionPolicyOBJ(self.content.as_dict(), self.intrinsic_matrix)

    def get_pose_detector(self):
        return PoseDetectorMP3D()

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

        self.interaction.project_vertices(rotation, translation)
        gesture_loc, gesture_status, img = self.pose_detector.detect(img)

        if gesture_loc is None:
            self.heartbeat_player.pause_sound()
            return img
        self.heartbeat_player.play_sound()

        if gesture_status != "moving":
            img = self.annotator.draw_point_in_image(img, gesture_loc)

        zone_id = self.interaction.push_gesture(gesture_loc)
        self.audio_player.convey(zone_id, gesture_status)
        return img