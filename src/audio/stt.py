import os
from typing import Optional

import pyglet
import speech_recognition as sr


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
