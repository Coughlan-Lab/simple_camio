import os
from typing import Optional, Set

import speech_recognition as sr

from src.modules_repository import Module
from google.cloud import speech  # unused, but needed for pre-loading the module


class STT(Module):
    TIMEOUT = 10
    PHRASE_TIME_LIMIT = 20
    FINAL_SILENCE_DURATION = 3.0

    def __init__(self) -> None:
        super().__init__()

        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = STT.FINAL_SILENCE_DURATION

        self.recording_audio = False
        self.microphone = sr.Microphone()

        self.commands: Set[str] = set()

    @property
    def is_recording(self) -> bool:
        return self.recording_audio

    def on_question_ended(self) -> None:
        self.recognizer.stop_listening()

    def calibrate(self) -> None:
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)

    def add_command(self, command: str) -> None:
        self.commands.add(command)

    def remove_command(self, command: str) -> None:
        self.commands.discard(command)

    def get_audio(self) -> Optional[sr.AudioData]:
        if self.recording_audio:
            return None

        self.recording_audio = True

        try:
            with self.microphone as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=STT.TIMEOUT,
                    phrase_time_limit=STT.PHRASE_TIME_LIMIT,
                )
        except Exception:
            return None
        finally:
            self.recording_audio = False

        return audio

    def audio_to_text(self, audio: sr.AudioData) -> Optional[str]:
        try:
            result = self.recognizer.recognize_google_cloud(
                audio,
                os.getenv("GOOGLE_SPEECH_CLOUD_KEY_FILE"),
                model="latest_short",
                preferred_phrases=list(self.commands),
            )

            return str(result).strip()
        except Exception:
            return None
