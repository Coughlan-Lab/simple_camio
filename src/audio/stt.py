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

        self.recording_audio = False

    @property
    def is_recording(self) -> bool:
        return self.recording_audio

    def on_question_ended(self) -> None:
        self.recognizer.listening = False

    def calibrate(self) -> None:
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)

    def get_audio(self) -> Optional[sr.AudioData]:
        if self.recording_audio:
            return None

        self.recording_audio = True

        try:
            with sr.Microphone() as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=self.phrase_time_limit,
                )
        except Exception:
            return None
        finally:
            self.recording_audio = False

        return audio

    def audio_to_text(self, audio: sr.AudioData) -> Optional[str]:
        try:
            result = self.recognizer.recognize_google_cloud(
                audio, os.getenv("GOOGLE_SPEECH_CLOUD_KEY_FILE")
            )
            return str(result).strip()
        except Exception:
            return None
