import json
import os
import threading as th
import time
from typing import Optional

import pyglet
import pyglet.media
import pyttsx3
import speech_recognition as sr

from src.frame_processing import HandStatus


class TTS:
    RATE = 200
    WAITING_LOOP_INTERVAL = 7

    def __init__(self, res_file: str, rate: int = RATE) -> None:
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)

        if not os.path.exists(res_file):
            raise FileNotFoundError("Resource file not found.")

        with open(res_file, "r") as f:
            self.res = json.load(f)

        self.waiting_loop_running = th.Event()
        self.lock = th.Lock()

    def start(self) -> None:
        self.engine.startLoop(False)

    def stop(self) -> None:
        self.engine.endLoop()

    def stop_speaking(self) -> None:
        self.engine.stop()

    def is_speaking(self) -> bool:
        return bool(self.engine.isBusy())

    def say(self, text: str) -> None:
        if text == "":
            return

        self.engine.say(text)
        self.engine.iterate()

    def welcome(self) -> None:
        self.say(self.res["welcome"])

    def instructions(self) -> None:
        self.say(self.res["instructions"])

    def goodbye(self) -> None:
        self.say(self.res["goodbye"])

    def waiting(self) -> None:
        self.say(self.res["waiting"])

    def error(self) -> None:
        self.say(self.res["error"])

    def no_description(self) -> None:
        self.say(self.res["no_description"])

    def start_waiting_loop(self) -> None:
        with self.lock:
            if self.waiting_loop_running.is_set():
                return

            self.waiting_loop_running.set()

            waiting_thread = th.Thread(target=self.waiting_loop)
            waiting_thread.start()

    def stop_waiting_loop(self) -> None:
        with self.lock:
            if not self.waiting_loop_running.is_set():
                return

            self.waiting_loop_running.clear()
            self.stop_speaking()

    def waiting_loop(self) -> None:
        time.sleep(TTS.WAITING_LOOP_INTERVAL)

        while self.waiting_loop_running.is_set():
            self.waiting()
            time.sleep(TTS.WAITING_LOOP_INTERVAL)


class STT:
    TIMEOUT = 5
    PHRASE_TIME_LIMIT = 7
    FINAL_SILENCE_DURATION = 0.4

    def __init__(
        self,
        timeout: int = TIMEOUT,
        phrase_time_limit: int = PHRASE_TIME_LIMIT,
        start_filename: Optional[str] = None,
        end_filename: Optional[str] = None,
    ) -> None:
        self.recognizer = sr.Recognizer()

        self.timeout = timeout
        self.phrase_time_limit = phrase_time_limit

        self.processing_input = False

        if start_filename is not None:
            self.start_audio = pyglet.media.load(start_filename, streaming=False)
        else:
            self.start_audio = None

        if end_filename is not None:
            self.end_audio = pyglet.media.load(end_filename, streaming=False)
        else:
            self.end_audio = None

    def is_processing(self) -> bool:
        return self.processing_input

    def stop_processing(self) -> None:
        self.processing_input = False
        self.recognizer.listening = False

    def on_question_ended(self) -> None:
        self.recognizer.listening = False

    def calibrate(self) -> None:
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)

    def process_input(self) -> Optional[str]:
        self.processing_input = True

        self.play_start_signal()

        try:
            with sr.Microphone() as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=self.phrase_time_limit,
                )
        except Exception:
            self.processing_input = False
            self.play_end_signal()
            return None

        if not self.processing_input:
            self.play_end_signal()
            return None

        text = self.get_from_audio(audio)

        if not self.processing_input or text == "":
            self.play_end_signal()
            return None

        self.processing_input = False
        self.play_end_signal()

        return text

    def play_start_signal(self) -> None:
        if self.start_audio is not None:
            self.start_audio.play()

    def play_end_signal(self) -> None:
        if self.end_audio is not None:
            self.end_audio.play()

    def get_from_audio(self, audio: sr.AudioData) -> Optional[str]:
        try:
            result = self.recognizer.recognize_google_cloud(
                audio, os.getenv("GOOGLE_SPEECH_CLOUD_KEY_FILE")
            )
            return str(result).strip()
        except Exception:
            return None


class AmbientSoundPlayer:
    def __init__(self, white_noise_filename: str, crickets_filename: str) -> None:
        self.white_noise = pyglet.media.load(white_noise_filename, streaming=False)
        self.crickets = pyglet.media.load(crickets_filename, streaming=False)

        self.player = pyglet.media.Player()
        self.player.loop = True
        self.player.queue(self.crickets)

        self.playing_crickets = True
        self.player.play()

    def update(self, gesture: HandStatus) -> None:
        if gesture == HandStatus.POINTING:
            self.play_white_noise()
        else:
            self.play_crickets()

    def play_white_noise(self) -> None:
        if self.playing_crickets:
            self.player.queue(self.white_noise)
            self.player.next_source()
            self.playing_crickets = False

    def play_crickets(self) -> None:
        if not self.playing_crickets:
            self.player.queue(self.crickets)
            self.player.next_source()
            self.playing_crickets = True

    def stop(self) -> None:
        self.player.pause()
