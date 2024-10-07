import threading as th
from typing import Optional, Callable, Dict

from src.config import config
from src.frame_processing import GestureResult
from src.llm import LLM
from src.modules_repository import ModulesRepository
from src.position import PositionHandler, PositionInfo
from src.view import KeyboardManager, UserAction
from src.view.audio import STT, Announcement, AudioManager, CamIOTTS
from src.llm import LLM

import os
import json


class VoiceCommands:
    def __init__(self, file: str) -> None:
        if not os.path.exists(file):
            raise FileNotFoundError(f"Voice commands file not found: {file}")

        self.__commands: Dict[str, UserAction] = dict()

        with open(file, "r") as f:
            commands = json.load(f)

        for action, command in commands.items():
            self.__commands[command] = UserAction[action]

    def __contains__(self, command: str) -> bool:
        return command in self.__commands

    def __getitem__(self, command: str) -> UserAction:
        return self.__commands[command]

    def __iter__(self):
        return iter(self.__commands.keys())


class CommandController:
    def __init__(
        self,
        repository: ModulesRepository,
        voice_commands_file: str,
        on_action: Callable[[UserAction], None],
    ) -> None:
        self.repository = repository
        self.voice_commands = VoiceCommands(voice_commands_file)

        self.on_action = on_action
        self.handling_thread: Optional[HandlingThread] = None

        for command in self.voice_commands:
            self.stt.add_command(command)

    @property
    def llm(self) -> LLM:
        return self.repository[LLM]

    @property
    def stt(self) -> STT:
        return self.repository[STT]

    def handle_command(self) -> None:
        if self.is_handling_command():
            return

        self.handling_thread = HandlingThread.handle(
            self.repository, self.voice_commands, self.__on_voice_command
        )

    def stop_handling_command(self) -> None:
        if self.handling_thread is not None:
            self.handling_thread.stop()
            self.handling_thread = None

    def is_handling_command(self) -> bool:
        return self.handling_thread is not None and self.handling_thread.is_running()

    def __on_voice_command(self, command: str) -> None:
        if command in self.voice_commands:
            self.on_action(self.voice_commands[command])


class HandlingThread(th.Thread):
    def __init__(
        self,
        repository: ModulesRepository,
        commands: VoiceCommands,
        on_voice_command: Callable[[str], None],
    ) -> None:
        super().__init__()

        self.repository = repository

        self.voice_commands = commands
        self.on_command = on_voice_command

        self.stop_event = th.Event()
        self.announcement_id: Optional[str] = None
        self.tts.on_announcement_ended = self.on_announcement_ended

        self.waiting_tts = th.Condition()

    @staticmethod
    def handle(
        repository: ModulesRepository,
        voice_commands: VoiceCommands,
        on_action: Callable[[str], None],
    ) -> "HandlingThread":
        handling_thread = HandlingThread(repository, voice_commands, on_action)
        handling_thread.start()
        return handling_thread

    def is_running(self) -> bool:
        return not self.stop_event.is_set() and self.is_alive()

    def run(self) -> None:
        self.tts.stop_speaking()
        position = self.__get_position()

        if config.stt_enabled:
            command = self.__get_command_from_stt()
        else:
            command = self.__get_command_from_keyboard()

        if self.stop_event.is_set():
            print("Stopping command handler.")
            return

        if len(command) == 0:
            self.tts.no_question_error()
            return

        print(f"Command: {command}")

        if command in self.voice_commands:
            self.on_command(command)
            return

        self.tts.start_waiting_llm_loop()

        position = self.__get_position() or position

        answer = self.llm.ask(command, position) or ""
        self.tts.stop_waiting_llm_loop()

        if self.stop_event.is_set():
            print("Stopping user input handler.")
            return

        self.__process_answer(answer)

    def __get_command_from_stt(self) -> str:
        print("Listening...")

        self.audio_manager.play_start_recording()
        recording = self.stt.get_audio()
        self.audio_manager.play_end_recording()

        if recording is None or self.stop_event.is_set():
            return ""

        return self.stt.audio_to_text(recording) or ""

    def __get_command_from_keyboard(self) -> str:
        self.keyboard.pause()

        self.audio_manager.play_start_recording()
        question = input("Input: ").strip()
        self.audio_manager.play_end_recording()

        self.keyboard.resume()
        return question

    def __process_answer(self, answer: str) -> None:
        self.tts.stop_speaking()

        if len(answer) == 0:
            announcement = self.tts.llm_error()
        else:
            announcement = self.tts.llm_response(answer)

        if announcement is not None:
            self.announcement_id = announcement.id

        self.tts.add_pause(2.0)
        self.__wait_tts()

    def __wait_tts(self) -> None:
        if self.announcement_id is None:
            return

        with self.waiting_tts:
            while not self.stop_event.is_set():
                self.waiting_tts.wait()

    def stop(self) -> None:
        if self.stop_event.is_set():
            return

        self.stop_event.set()
        self.tts.on_announcement_ended = None
        self.llm.stop()
        self.tts.stop_waiting_llm_loop()

        with self.waiting_tts:
            self.waiting_tts.notify_all()

    def on_announcement_ended(
        self, announcement: Announcement, announced: bool
    ) -> None:
        if self.announcement_id != announcement.id:
            return

        if self.hand_status == GestureResult.Status.POINTING:
            self.audio_manager.play_pointing()

        self.stop_event.set()
        with self.waiting_tts:
            self.waiting_tts.notify_all()

        self.tts.on_announcement_ended = None

    def __get_position(self) -> Optional[PositionInfo]:
        if (
            self.hand_status == GestureResult.Status.POINTING
            and self.position_handler.last_info.is_still_valid()
        ):
            return self.position_handler.last_info

    @property
    def tts(self) -> CamIOTTS:
        return self.repository[CamIOTTS]

    @property
    def stt(self) -> STT:
        return self.repository[STT]

    @property
    def hand_status(self) -> GestureResult.Status:
        return self.audio_manager.hand_status

    @property
    def position_handler(self) -> PositionHandler:
        return self.repository[PositionHandler]

    @property
    def llm(self) -> LLM:
        return self.repository[LLM]

    @property
    def audio_manager(self) -> AudioManager:
        return self.repository[AudioManager]

    @property
    def keyboard(self) -> KeyboardManager:
        return self.repository[KeyboardManager]
