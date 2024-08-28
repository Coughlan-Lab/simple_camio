import json
import os
import threading as th
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, Optional

import pyttsx3


class AnnouncementType(Enum):
    WELCOME = "welcome"
    INSTRUCTIONS = "instructions"
    GOODBYE = "goodbye"
    WAITING = "waiting"
    ERROR = "error"
    NO_DESCRIPTION = "no_description"
    POSITION_UPDATE = "position_update"
    MAP_DESCRIPTION = "map_description"
    LLM_RESPONSE = "llm_response"


@dataclass(order=True)
class Announcement:
    class Priority(IntEnum):
        NONE = 0
        LOW = 1
        MEDIUM = 2
        HIGH = 3

    text: str = field(compare=False)
    priority: Priority
    name: AnnouncementType


def generate_random_id() -> str:
    return str(uuid.uuid4())


class TTS:
    RATE = 200
    WAITING_LOOP_INTERVAL = 7

    def __init__(self, res_file: str, rate: int = RATE) -> None:
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)

        self.engine.connect("started-utterance", self.__on_utterance_started)
        self.engine.connect("finished-utterance", self.__on_utterance_finished)
        self.engine.connect("started-word", self.__on_word_started)

        if not os.path.exists(res_file):
            raise FileNotFoundError("Resource file not found.")

        with open(res_file, "r") as f:
            self.res = json.load(f)

        self.running = False
        self.waiting_loop_running = th.Event()

        self.current_msg_word_index = 0
        self.current_announcement: Optional[Announcement] = None
        self.announcements: Dict[str, Announcement] = dict()

    def start(self) -> None:
        self.engine.startLoop(False)

    def stop(self) -> None:
        self.engine.endLoop()

    def stop_speaking(self) -> None:
        self.announcements.clear()
        self.engine.stop()

    def is_speaking(self) -> bool:
        return bool(self.engine.isBusy())

    def toggle(self) -> None:
        if self.is_speaking():
            self.stop_speaking()

        elif self.current_announcement is not None:
            self.say(
                self.current_announcement.text[self.current_msg_word_index :],
                self.current_announcement.name,
                stop_current=True,
                priority=self.current_announcement.priority,
            )

    def say(
        self,
        text: str,
        announcement_type: AnnouncementType,
        priority: Announcement.Priority = Announcement.Priority.LOW,
        stop_current: bool = False,
    ) -> None:
        if text == "":
            return

        if stop_current and (
            self.current_announcement is None
            or priority >= self.current_announcement.priority
        ):
            self.stop_speaking()

        announcement = Announcement(text, priority, announcement_type)
        self.announcements[announcement.name.value] = announcement

        # Add the announcement to the queue
        self.engine.say(announcement.text, announcement.name.value)
        self.engine.iterate()

    def __on_utterance_started(self, name: str) -> None:
        self.current_announcement = self.announcements.get(name, None)

        if self.current_announcement is not None:
            del self.announcements[name]

    def __on_utterance_finished(self, name: str, completed: bool) -> None:
        pass

    def __on_word_started(self, name: str, location: int, length: int) -> None:
        self.current_msg_word_index = location

    def welcome(self) -> None:
        self.say(
            self.res["welcome"],
            announcement_type=AnnouncementType.WELCOME,
            priority=Announcement.Priority.MEDIUM,
        )

    def instructions(self) -> None:
        self.say(
            self.res["instructions"],
            announcement_type=AnnouncementType.INSTRUCTIONS,
            priority=Announcement.Priority.MEDIUM,
        )

    def goodbye(self) -> None:
        self.say(
            self.res["goodbye"],
            announcement_type=AnnouncementType.GOODBYE,
            stop_current=True,
            priority=Announcement.Priority.HIGH,
        )

    def waiting_llm(self) -> None:
        self.say(
            self.res["waiting"],
            announcement_type=AnnouncementType.WAITING,
            priority=Announcement.Priority.MEDIUM,
            stop_current=True,
        )

    def llm_error(self) -> None:
        self.say(
            self.res["error"],
            announcement_type=AnnouncementType.ERROR,
            priority=Announcement.Priority.HIGH,
            stop_current=True,
        )

    def no_description(self) -> None:
        self.say(
            self.res["no_description"],
            announcement_type=AnnouncementType.NO_DESCRIPTION,
            stop_current=True,
            priority=Announcement.Priority.HIGH,
        )

    def start_waiting_loop(self) -> None:
        if self.waiting_loop_running.is_set():
            return

        self.waiting_loop_running.set()

        th.Thread(target=self.waiting_loop).start()

    def stop_waiting_loop(self) -> None:
        if not self.waiting_loop_running.is_set():
            return

        self.waiting_loop_running.clear()
        self.stop_speaking()

    def waiting_loop(self) -> None:
        time.sleep(TTS.WAITING_LOOP_INTERVAL)

        while self.waiting_loop_running.is_set():
            self.waiting_llm()
            time.sleep(TTS.WAITING_LOOP_INTERVAL)
