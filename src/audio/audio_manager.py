import json
import os
from typing import Optional

import pygame

from src.frame_processing import HandStatus
from src.graph import NONE_POSITION_INFO, PositionInfo

pygame.mixer.init()


class AudioLooper:
    def __init__(self, filepath: str) -> None:
        pygame.mixer.music.load(filepath)

    def play(self) -> None:
        pygame.mixer.music.play(-1)

    def pause(self) -> None:
        pygame.mixer.music.pause()

    def stop(self) -> None:
        pygame.mixer.music.stop()


class AudioManager:
    def __init__(
        self,
        sound_file: str,
    ) -> None:
        if not os.path.exists(sound_file):
            raise FileNotFoundError("Sound file not found.")

        with open(sound_file, "r") as f:
            sounds = json.load(f)

        self.pointing_sound = pygame.mixer.Sound(sounds["pointing"])
        self.poi_sound = pygame.mixer.Sound(sounds["poi"])
        self.hand_status = HandStatus.NOT_FOUND

        self.start_recording_sound: Optional[pygame.mixer.Sound]
        if start_recording_path := sounds.get("start_recording"):
            self.start_recording_sound = pygame.mixer.Sound(start_recording_path)
        else:
            self.start_recording_sound = None

        self.end_recording_sound: Optional[pygame.mixer.Sound]
        if end_recording_path := sounds.get("end_recording"):
            self.end_recording_sound = pygame.mixer.Sound(end_recording_path)
        else:
            self.end_recording_sound = None

        self.background_player = AudioLooper(sounds["background"])
        self.background_player.play()

        self.last_pos_info = NONE_POSITION_INFO

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

    def play_pointing(self) -> None:
        self.pointing_sound.play()

    def play_start_recording(self) -> None:
        if self.start_recording_sound is not None:
            self.start_recording_sound.play()

    def play_end_recording(self) -> None:
        if self.end_recording_sound is not None:
            self.end_recording_sound.play()

    def position_feedback(self, info: PositionInfo) -> None:
        if self.last_pos_info.graph_element == info.graph_element:
            return

        self.last_pos_info = info
        if info.is_poi():
            self.poi_sound.play()
