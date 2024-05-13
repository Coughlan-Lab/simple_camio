# mypy: ignore-errors
import numpy as np
from .frame_processor import FrameProcessor
from ..simple_camio_mp import PoseDetectorMP, SIFTModelDetectorMP
from ..simple_camio_3d import SIFTModelDetector
from ..simple_camio_2d import CamIOPlayer2D, InteractionPolicy2D
import cv2


class FingerSift2DFP(FrameProcessor):
    def get_audio_player(self):
        return CamIOPlayer2D(self.content.as_dict())

    def get_model_detector(self):
        return SIFTModelDetectorMP(self.content.as_dict())

    def get_interaction_policy(self):
        return InteractionPolicy2D(self.content.as_dict())

    def get_pose_detector(self):
        return PoseDetectorMP(self.content.as_dict())

    def process(self, img: np.ndarray) -> np.ndarray:
        img = super().process(img)

        if self.frame_count == 0:
            self.model_detector.requires_homography = True
        self.frame_count = (self.frame_count + 1) % 100
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ok, rotation, translation = self.model_detector.detect(img_gray)

        if not ok:
            self.heartbeat_player.pause_sound()
            self.crickets_player.play_sound()
            return img
        self.crickets_player.pause_sound()

        gesture_loc, gesture_status, img, hand_results = self.pose_detector.detect(
            img, rotation, translation
        )

        layer_change, dist = self.layered_audio.detect(hand_results, img)
        if dist:
            cv2.putText(img, str(dist), (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2, cv2.LINE_AA)

        if gesture_loc is None:
            self.heartbeat_player.pause_sound()
            return img
        self.heartbeat_player.play_sound()

        gesture_loc = gesture_loc / self.interaction.model['pixels_per_cm']
        zone_id = self.interaction.push_gesture(gesture_loc)
        if zone_id in self.audio_player.hotspots:
            text = self.audio_player.hotspots[zone_id]['textDescription']
            col = (0, 255, 0)
        else:
            text = str(zone_id)
            col = (0,0,255)
        cv2.putText(img, text, (10, 560), cv2.FONT_HERSHEY_SIMPLEX, 2, col, 2, cv2.LINE_AA)
        self.audio_player.convey(zone_id, gesture_status, layer_change)
        return img
