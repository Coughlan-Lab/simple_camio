import json
import os

import pygame

from src.frame_processing import GestureResult
from src.modules_repository import Module
from src.position import PositionInfo

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


class AudioManager(Module):
    def __init__(self, sound_file: str) -> None:
        super().__init__()

        if not os.path.exists(sound_file):
            raise FileNotFoundError("Sound file not found.")

        with open(sound_file, "r") as f:
            sounds = json.load(f)

        self.pointing_sound = pygame.mixer.Sound(sounds["pointing"])
        self.poi_sound = pygame.mixer.Sound(sounds["poi"])
        self.hand_status = GestureResult.Status.NOT_FOUND

        self.start_recording_sound = pygame.mixer.Sound(sounds["start_recording"])
        self.end_recording_sound = pygame.mixer.Sound(sounds["end_recording"])

        self.waypoint_reached_sound = pygame.mixer.Sound(sounds["waypoint_reached"])
        self.destination_reached_sound = pygame.mixer.Sound(
            sounds["destination_reached"]
        )

        self.background_player = AudioLooper(sounds["background"])
        self.background_player.play()

        self.last_pos_info = PositionInfo.NONE

    def start(self) -> None:
        self.background_player.play()

    def stop(self) -> None:
        self.background_player.stop()

    def play_pointing(self) -> None:
        self.pointing_sound.play()

    def play_start_recording(self) -> None:
        self.start_recording_sound.play()

    def play_end_recording(self) -> None:
        self.end_recording_sound.play()

    def play_waypoint_reached(self) -> None:
        self.waypoint_reached_sound.play()

    def play_destination_reached(self) -> None:
        self.destination_reached_sound.play()

    def hand_feedback(self, hand_status: GestureResult.Status) -> None:
        if hand_status == self.hand_status:
            return
        self.hand_status = hand_status

        if self.hand_status == GestureResult.Status.POINTING:
            self.background_player.pause()
            self.play_pointing()
        else:
            self.background_player.play()

    def position_feedback(self, info: PositionInfo) -> None:
        if self.last_pos_info.graph_element == info.graph_element:
            return

        self.last_pos_info = info
        if info.is_poi():
            self.poi_sound.play()
