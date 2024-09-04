from typing import Optional

import pygame

from src.frame_processing import HandStatus

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
        background_path: str,
        pointing_path: str,
        start_recording_path: Optional[str] = None,
        end_recording_path: Optional[str] = None,
    ) -> None:
        self.pointing_sound = pygame.mixer.Sound(pointing_path)
        self.hand_status = HandStatus.NOT_FOUND

        if start_recording_path is not None:
            self.start_recording_sound = pygame.mixer.Sound(start_recording_path)
        else:
            self.start_recording_sound = None

        if end_recording_path is not None:
            self.end_recording_sound = pygame.mixer.Sound(end_recording_path)
        else:
            self.end_recording_sound = None

        self.background_player = AudioLooper(background_path)
        self.background_player.play()

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

    def play_start_signal(self) -> None:
        if self.start_recording_sound is not None:
            self.start_recording_sound.play()

    def play_end_signal(self) -> None:
        if self.end_recording_sound is not None:
            self.end_recording_sound.play()
