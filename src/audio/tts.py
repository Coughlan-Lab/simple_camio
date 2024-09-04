import json
import os
import threading as th
import time
import uuid
from abc import ABC
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Callable, Optional

import pyttsx3

from src.graph import PositionInfo


def generate_random_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class Announcement(ABC):
    class Category(Enum):
        SYSTEM = "system"
        GRAPH = "graph"
        LLM = "llm"
        ERROR = "error"

    class Priority(IntEnum):
        NONE = 0
        LOW = 1
        MEDIUM = 2
        HIGH = 3

    id: str = field(default_factory=generate_random_id)


@dataclass(frozen=True)
class TextAnnouncement(Announcement):
    text: str = field(default="", compare=False)
    category: Announcement.Category = Announcement.Category.SYSTEM
    priority: Announcement.Priority = Announcement.Priority.LOW


@dataclass(frozen=True)
class PauseAnnouncement(Announcement):
    duration: float = field(default=1.0, compare=False)


NONE_ANNOUNCEMENT = TextAnnouncement(priority=Announcement.Priority.NONE)


class TTS:
    RATE = 200

    WAITING_LOOP_INTERVAL = 7
    ERROR_INTERVAL = 5
    GRAPH_INTERVAL = 0.25

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

        self.current_announcement_index = 0
        self.current_announcement: TextAnnouncement = NONE_ANNOUNCEMENT
        self.paused_announcement: Optional[TextAnnouncement] = None

        self.queue: deque[Announcement] = deque()

        self.__running = th.Event()
        self.__waiting_loop_running = th.Event()
        self.__is_speaking = th.Event()

        self.main_lock = th.RLock()
        self.queue_cond = th.Condition()
        self.is_speaking_cond = th.Condition()

        self.timestamps = {category: 0.0 for category in Announcement.Category}

        self.on_announcement_ended: Callable[[Announcement.Category], None] = (
            lambda _: None
        )

        self.loop_thread: Optional[th.Thread] = None

    def start(self) -> None:
        with self.main_lock:
            if self.__running.is_set():
                return

            self.loop_thread = th.Thread(target=self.__loop, daemon=True)
            self.loop_thread.start()

    def stop(self) -> None:
        with self.main_lock:
            if not self.__running.is_set() or self.loop_thread is None:
                return

            self.__running.clear()

            with self.queue_cond:
                self.queue_cond.notify_all()
            with self.is_speaking_cond:
                self.is_speaking_cond.notify_all()

            self.loop_thread.join()
            self.loop_thread = None

    def __loop(self) -> None:
        self.__running.set()

        try:
            self.engine.startLoop(False)

            while self.__running.is_set():
                with self.queue_cond:
                    while not self.queue and self.__running.is_set():
                        self.queue_cond.wait()

                    if not self.__running.is_set():
                        break

                    next_announcement = self.queue.popleft()

                if isinstance(next_announcement, PauseAnnouncement):
                    time.sleep(next_announcement.duration)

                elif isinstance(next_announcement, TextAnnouncement):
                    with self.is_speaking_cond:
                        self.current_announcement = next_announcement

                        self.engine.say(
                            self.current_announcement.text,
                            name=self.current_announcement.id,
                        )
                        self.engine.iterate()

                        self.timestamps[self.current_announcement.category] = (
                            time.time()
                        )

                with self.is_speaking_cond:
                    while self.is_speaking() and self.__running.is_set():
                        self.is_speaking_cond.wait()

                if isinstance(next_announcement, TextAnnouncement):
                    self.on_announcement_ended(self.current_announcement.category)
                    self.current_announcement = NONE_ANNOUNCEMENT

            self.engine.endLoop()

        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"An error occurred in TTS loop: {e}")

    def stop_speaking(self) -> None:
        if len(self.queue) > 0:
            with self.queue_cond:
                self.queue.clear()
                self.queue_cond.notify_all()

        self.engine.stop()

    def is_speaking(self) -> bool:
        return self.__is_speaking.is_set()

    def toggle_pause(self) -> None:
        if self.paused_announcement is not None:
            self.stop_and_say(
                self.paused_announcement.text,
                self.paused_announcement.category,
                Announcement.Priority.HIGH,
            )

            self.paused_announcement = None
            return

        with self.is_speaking_cond:
            if self.is_speaking():
                if self.current_announcement.category not in {
                    Announcement.Category.ERROR,
                    Announcement.Category.GRAPH,
                }:
                    self.paused_announcement = TextAnnouncement(
                        text=self.current_announcement.text[
                            self.current_announcement_index :
                        ],
                        priority=self.current_announcement.priority,
                        category=self.current_announcement.category,
                    )
                self.stop_speaking()

    def __on_utterance_started(self, name: str) -> None:
        self.__is_speaking.set()

    def __on_utterance_finished(self, name: str, completed: bool) -> None:
        with self.is_speaking_cond:
            self.__is_speaking.clear()
            self.is_speaking_cond.notify()

    def __on_word_started(self, name: str, location: int, length: int) -> None:
        self.current_announcement_index = location

    def say(
        self,
        text: str,
        category: Announcement.Category,
        priority: Announcement.Priority = Announcement.Priority.LOW,
    ) -> bool:
        text = text.strip()
        if len(text) == 0:
            return False

        announcement = TextAnnouncement(text=text, priority=priority, category=category)

        with self.queue_cond:
            self.queue.append(announcement)
            self.queue_cond.notify()

        return True

    def stop_and_say(
        self,
        text: str,
        category: Announcement.Category,
        priority: Announcement.Priority = Announcement.Priority.LOW,
    ) -> bool:
        with self.queue_cond:
            if priority < self.current_announcement.priority:
                return False

            with self.is_speaking_cond:
                self.stop_speaking()

            return self.say(text, category, priority)

    def pause(self, duration: float) -> None:
        with self.queue_cond:
            self.queue.append(PauseAnnouncement(duration=duration))
            self.queue_cond.notify_all()

    def position_info(
        self, position_info: PositionInfo, stop_previous: bool = False
    ) -> bool:
        if (
            time.time() - self.timestamps[Announcement.Category.GRAPH]
            < TTS.GRAPH_INTERVAL
        ):
            return False

        fn = self.stop_and_say if stop_previous else self.say
        return fn(
            position_info.description,
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.LOW,
        )

    def llm_response(self, response: str) -> bool:
        return self.stop_and_say(
            response,
            category=Announcement.Category.LLM,
            priority=Announcement.Priority.HIGH,
        )

    def welcome(self) -> None:
        self.say(
            self.res["welcome"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def instructions(self) -> None:
        self.say(
            self.res["instructions"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def goodbye(self) -> None:
        self.stop_and_say(
            self.res["goodbye"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.HIGH,
        )

    def waiting_llm(self) -> None:
        self.stop_and_say(
            self.res["waiting_llm"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def llm_error(self) -> None:
        self.stop_and_say(
            self.res["llm_error"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def question_error(self) -> None:
        self.stop_and_say(
            self.res["no_question_error"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def no_map_description(self) -> None:
        self.stop_and_say(
            self.res["no_map_description"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def map_description(self, description: str) -> None:
        self.say(
            f"Map description:\n{description}",
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.HIGH,
        )

    def no_pointing(self) -> None:
        self.stop_and_say(
            self.res["no_pointing"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def more_than_one_hand(self) -> None:
        if (
            time.time() - self.timestamps[Announcement.Category.ERROR]
            < TTS.ERROR_INTERVAL
        ):
            return

        self.stop_and_say(
            self.res["more_than_one_hand"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.MEDIUM,
        )

    def start_waiting_loop(self) -> None:
        if self.__waiting_loop_running.is_set():
            return

        th.Thread(target=self.__waiting_loop, daemon=True).start()

    def stop_waiting_loop(self) -> None:
        if not self.__waiting_loop_running.is_set():
            return

        self.__waiting_loop_running.clear()
        self.stop_speaking()

    def __waiting_loop(self) -> None:
        self.__waiting_loop_running.set()
        time.sleep(TTS.WAITING_LOOP_INTERVAL / 2)

        while self.__waiting_loop_running.is_set():
            self.waiting_llm()
            time.sleep(TTS.WAITING_LOOP_INTERVAL)
