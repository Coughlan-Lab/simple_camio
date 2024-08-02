from typing import Any, Dict, Optional

import pyglet
import pyglet.media
import pyttsx3
import speech_recognition as sr


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

    def is_speaking(self) -> bool:
        return bool(self.engine.isBusy())

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

    def error(self) -> None:
        self.say("An error occurred in obtaining a response. Please try again.")


class STT:
    TIMEOUT = 5
    PHRASE_TIME_LIMIT = 7

    def __init__(
        self, timeout: int = TIMEOUT, phrase_time_limit: int = PHRASE_TIME_LIMIT
    ) -> None:
        self.recognizer = sr.Recognizer()
        self.timeout = timeout
        self.phrase_time_limit = phrase_time_limit

        self.listening = False

    def is_listening(self) -> bool:
        return self.listening

    def calibrate(self) -> None:
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            # Vosk model preload
            self.get_from_audio(sr.AudioData(b"", 16000, 2))

    def get_input(self) -> Optional[str]:
        self.listening = True

        try:
            with sr.Microphone() as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=self.phrase_time_limit,
                )
        except Exception:
            return None

        input = self.get_from_audio(audio)

        self.listening = False
        return input

    def get_from_audio(self, audio: sr.AudioData) -> Optional[str]:
        try:
            result = self.recognizer.recognize_vosk(audio)
            return str(result)[14:-3]
        except Exception:
            return None


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
