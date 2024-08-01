from typing import Any, Dict

import pyglet
import pyglet.media
import pyttsx3


class TTS:
    def __init__(self, model: Dict[str, Any], rate: int) -> None:
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)

        self.map_description = model.get("map_description", None)

    def start(self) -> None:
        self.engine.startLoop(False)

    def stop(self) -> None:
        self.engine.endLoop()

    def stop_speaking(self) -> None:
        self.engine.stop()

    def say(self, text: str) -> None:
        self.engine.say(text)
        self.engine.iterate()

    def welcome(self) -> None:
        self.say("Welcome to CamIO!")

    def description(self) -> None:
        if self.description is not None:
            self.say(self.map_description)

    def goodbye(self) -> None:
        self.say("Goodbye!")


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
