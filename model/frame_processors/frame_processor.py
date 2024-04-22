# mypy: ignore-errors
from typing import Optional
from ..content import Content
from ..simple_camio import (
    MovementMedianFilter,
    AmbientSoundPlayer,
    ImageAnnotator,
    GestureDetector,
    load_camera_parameters,
    LayeredAudio
)
import numpy as np
import pyglet


class FrameProcessor:
    def __init__(
        self, content: Content, calibration_file: Optional[str] = None
    ) -> None:
        self.content = content

        if calibration_file is not None:
            self.intrinsic_matrix = load_camera_parameters(calibration_file)
            self.annotator = ImageAnnotator(self.intrinsic_matrix)

        self.model_detector = self.get_model_detector()
        self.interaction = self.get_interaction_policy()
        self.audio_player = self.get_audio_player()
        self.pose_detector = self.get_pose_detector()
        self.layered_audio = self.get_layered_audio(self.audio_player)
        self.motion_filter = MovementMedianFilter()
        self.gesture_detector = GestureDetector()
        self.crickets_player = AmbientSoundPlayer(content.crickets())
        self.heartbeat_player = AmbientSoundPlayer(content.heartbeat())
        self.heartbeat_player.set_volume(0.05)

        self.audio_player.play_description()

    def get_interaction_policy(self):
        raise NotImplementedError(
            "get_interaction_policy must be implemented by subclass"
        )

    def get_model_detector(self):
        raise NotImplementedError("get_model_detector must be implemented by subclass")

    def get_audio_player(self):
        raise NotImplementedError("get_audio_player must be implemented by subclass")

    def get_pose_detector(self):
        raise NotImplementedError("get_pose_detector must be implemented by subclass")

    def get_layered_audio(self, audio_player):
        return LayeredAudio(audio_player)

    def start(self) -> None:
        self.audio_player.play_welcome()
        self.audio_player.play_description()
        self.crickets_player.play_sound()

    def process(self, img: np.ndarray) -> np.ndarray:
        pyglet.clock.tick()
        pyglet.app.platform_event_loop.dispatch_posted_events()
        return img

    def destroy(self) -> None:
        self.crickets_player.pause_sound()
        self.heartbeat_player.pause_sound()
        self.audio_player.pause()
