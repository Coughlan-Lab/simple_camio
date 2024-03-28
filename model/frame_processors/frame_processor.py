# mypy: ignore-errors
from ..content import Content
from ..simple_camio import MovementMedianFilter, AmbientSoundPlayer
import numpy as np
import pyglet


class FrameProcessor:
    def __init__(self, content: Content):
        self.content = content

        self.model_detector = self.get_model_detector()
        self.interaction = self.get_interaction_policy()
        self.audio_player = self.get_audio_player()

        self.motion_filter = MovementMedianFilter()
        self.crickets_player = AmbientSoundPlayer(content.crickets())
        self.heartbeat_player = AmbientSoundPlayer(content.heartbeat())
        self.heartbeat_player.set_volume(0.05)

    def get_interaction_policy(self):
        raise NotImplementedError(
            "get_interaction_policy must be implemented by subclass"
        )

    def get_model_detector(self):
        raise NotImplementedError("get_model_detector must be implemented by subclass")

    def get_audio_player(self):
        raise NotImplementedError("get_audio_player must be implemented by subclass")

    def start(self) -> None:
        self.audio_player.play_welcome()
        self.audio_player.play_description()
        self.crickets_player.play_sound()

    def process(self, img: np.ndarray) -> np.ndarray:
        pyglet.clock.tick()
        pyglet.app.platform_event_loop.dispatch_posted_events()
        return img

    def destroy(self) -> None:
        pass
