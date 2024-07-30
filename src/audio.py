from typing import Any, Dict

import cv2 as cv
import numpy as np
import numpy.typing as npt
import pyglet
import pyglet.media


class CamIOPlayer:
    def __init__(self, model: Dict[str, Any]) -> None:
        self.model = model
        self.player = pyglet.media.Player()

        self.blip_sound = pyglet.media.load(self.model["blipsound"], streaming=False)
        self.enable_blips = False

        if "map_description" in self.model:
            self.map_description = pyglet.media.load(
                self.model["map_description"], streaming=False
            )
        else:
            self.map_description = None

        self.welcome_message = pyglet.media.load(
            self.model["welcome_message"], streaming=False
        )
        self.goodbye_message = pyglet.media.load(
            self.model["goodbye_message"], streaming=False
        )

    def play_description(self) -> None:
        if self.map_description is not None:
            self.player = self.map_description.play()

    def play_welcome(self) -> None:
        self.welcome_message.play()

    def play_goodbye(self) -> None:
        self.goodbye_message.play()


class AmbientSoundPlayer:
    def __init__(self, soundfile: str) -> None:
        self.sound = pyglet.media.load(soundfile, streaming=False)
        self.player = pyglet.media.Player()
        self.player.queue(self.sound)
        self.player.eos_action = "loop"
        self.player.loop = True

    def set_volume(self, volume: float) -> None:
        if 0 <= volume <= 1:
            self.player.volume = volume

    def play_sound(self) -> None:
        if not self.player.playing:
            self.player.play()

    def pause_sound(self) -> None:
        if self.player.playing:
            self.player.pause()
