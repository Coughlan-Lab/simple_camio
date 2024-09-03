import os
import threading
import wave
from typing import Optional

import pyaudio
import pyglet

from src.frame_processing import HandStatus


class AudioLooper(threading.Thread):
    CHUNK = 1024

    def __init__(self, filepath: str) -> None:
        assert self.check_extension(filepath), "File must be a .wav file"

        super(AudioLooper, self).__init__(daemon=True)

        self.filepath = os.path.abspath(filepath)
        self.running = False
        self.is_paused = True

    def run(self) -> None:
        wf = wave.open(self.filepath, "rb")
        player = pyaudio.PyAudio()

        stream = player.open(
            format=player.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
        )

        self.running = True
        while self.running:
            while not self.is_paused:
                data = wf.readframes(self.CHUNK)
                stream.write(data)
                if data == b"":  # If file is over then rewind.
                    wf.rewind()
                    data = wf.readframes(self.CHUNK)

        stream.close()
        player.terminate()

    def play(self) -> None:
        self.is_paused = False

    def pause(self) -> None:
        self.is_paused = True

    def stop(self) -> None:
        self.is_paused = True
        self.running = False

    def check_extension(self, path: str) -> bool:
        return path.endswith(".wav")


class AudioManager:
    def __init__(
        self,
        background_path: str,
        pointing_path: str,
        start_path: Optional[str] = None,
        end_path: Optional[str] = None,
    ) -> None:
        self.background_player = AudioLooper(background_path)
        self.background_player.start()

        self.pointing_player = pyglet.media.load(pointing_path, streaming=False)
        self.hand_status = HandStatus.NOT_FOUND

        if start_path is not None:
            self.start_audio = pyglet.media.load(start_path, streaming=False)
        else:
            self.start_audio = None

        if end_path is not None:
            self.end_audio = pyglet.media.load(end_path, streaming=False)
        else:
            self.end_audio = None

    def check_extension(self, path: str) -> bool:
        return path.endswith(".wav")

    def update(self, hand_status: HandStatus) -> None:
        if hand_status == self.hand_status:
            return
        self.hand_status = hand_status

        if self.hand_status == HandStatus.POINTING:
            self.background_player.pause()
            self.play_pointing()
        else:
            self.background_player.play()

    def start(self) -> None:
        self.background_player.play()

    def stop(self) -> None:
        self.background_player.stop()
        self.background_player.join()

    def play_pointing(self) -> None:
        self.pointing_player.play()

    def play_start_signal(self) -> None:
        if self.start_audio is not None:
            self.start_audio.play()

    def play_end_signal(self) -> None:
        if self.end_audio is not None:
            self.end_audio.play()
