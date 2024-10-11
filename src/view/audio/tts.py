import threading as th
import time
import uuid
from abc import ABC
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, ClassVar, Optional

import pyttsx3

from src.modules_repository import Module


def generate_random_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class Announcement(ABC):
    class Category(Enum):
        SYSTEM = "system"
        GRAPH = "graph"
        NAVIGATION = "navigation"
        LLM = "llm"
        ERROR = "error"

    class Priority(IntEnum):
        NONE = 0
        LOW = 1
        MEDIUM = 2
        HIGH = 3

    id: str = field(default_factory=generate_random_id)
    category: Category = field(default=Category.SYSTEM, compare=False)
    priority: Priority = field(default=Priority.LOW, compare=False)

    NONE: ClassVar["Announcement"]

    def is_error(self) -> bool:
        return self.category == Announcement.Category.ERROR

    def is_system(self) -> bool:
        return self.category == Announcement.Category.SYSTEM

    def is_graph(self) -> bool:
        return self.category == Announcement.Category.GRAPH

    def is_llm(self) -> bool:
        return self.category == Announcement.Category.LLM

    def is_navigation(self) -> bool:
        return self.category == Announcement.Category.NAVIGATION


Announcement.NONE = Announcement(priority=Announcement.Priority.NONE)


@dataclass(frozen=True)
class TextAnnouncement(Announcement):
    text: str = field(default="", compare=False)


@dataclass(frozen=True)
class PauseAnnouncement(Announcement):
    duration: float = field(default=1.0, compare=False)


class TTS(Module):
    DEFAULT_RATE = 200
    ONE_MSG_LOOP_INTERVAL = 7

    def __init__(self, rate: int = DEFAULT_RATE) -> None:
        super().__init__()

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)

        self.engine.connect("started-utterance", self.__on_utterance_started)
        self.engine.connect("finished-utterance", self.__on_utterance_finished)
        self.engine.connect("started-word", self.__on_word_started)

        self.current_announcement_index = 0
        self.current_announcement = Announcement.NONE
        self.last_announcement = Announcement.NONE
        self.paused_announcement: Optional[TextAnnouncement] = None

        self.queue: deque[Announcement] = deque()

        self.__running = th.Event()
        self.__one_msg_loop_running = th.Event()
        self.__is_speaking = th.Event()

        self.main_lock = th.RLock()
        self.queue_cond = th.Condition()
        self.is_speaking_cond = th.Condition()

        self._timestamps = {category: 0.0 for category in Announcement.Category}
        self._enabled = {category: True for category in Announcement.Category}

        self.on_announcement_ended: Optional[Callable[[Announcement, bool], None]] = (
            None
        )

        self.loop_thread: Optional[th.Thread] = None

    def is_speaking(self) -> bool:
        return self.__is_speaking.is_set()

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

    def disable_category(self, category: Announcement.Category) -> None:
        self._enabled[category] = False

    def disable_all_categories(self) -> None:
        for category in self._enabled:
            self._enabled[category] = False

    def enable_category(self, category: Announcement.Category) -> None:
        self._enabled[category] = True

    def enable_all_categories(self) -> None:
        for category in self._enabled:
            self._enabled[category] = True

    def is_enabled(self, category: Announcement.Category) -> bool:
        return self._enabled[category]

    def __loop(self) -> None:
        self.__running.set()

        self.engine.startLoop(False)

        while self.__running.is_set():
            announcement = self.__get_next_announcement()
            if announcement is None:
                continue

            self.current_announcement = announcement

            if isinstance(announcement, PauseAnnouncement):
                self.__announce_pause(announcement)
            elif isinstance(announcement, TextAnnouncement):
                self.__announce_text(announcement)

            self.last_announcement = self.current_announcement
            self.current_announcement = Announcement.NONE

            self.__on_announcement_ended(self.last_announcement, True)

        self.engine.endLoop()

    def stop_speaking(self) -> None:
        with self.queue_cond:
            for announcement in self.queue:
                self.__on_announcement_ended(announcement, False)

            self.queue.clear()
            self.queue_cond.notify_all()

            with self.is_speaking_cond:
                self.engine.stop()
                self.is_speaking_cond.notify_all()

    def say(
        self,
        text: Optional[str],
        category: Announcement.Category,
        priority: Announcement.Priority = Announcement.Priority.LOW,
    ) -> Optional[Announcement]:
        if text is None or not self._enabled[category]:
            return None

        text = text.strip()
        if len(text) == 0:
            return None

        announcement = TextAnnouncement(text=text, priority=priority, category=category)

        with self.queue_cond:
            self.queue.append(announcement)
            self.queue_cond.notify_all()

        return announcement

    def stop_and_say(
        self,
        text: Optional[str],
        category: Announcement.Category,
        priority: Announcement.Priority = Announcement.Priority.LOW,
    ) -> Optional[Announcement]:
        with self.queue_cond:
            max_priority = Announcement.Priority.NONE
            if len(self.queue) > 0:
                max_priority = max([ann.priority for ann in self.queue])

            current_priority = self.current_announcement.priority
            if current_priority > max_priority:
                max_priority = current_priority

            if priority < max_priority:
                return None

            self.stop_speaking()

            return self.say(text, category, priority)

    def add_pause(self, duration: float) -> None:
        with self.queue_cond:
            self.queue.append(PauseAnnouncement(duration=duration))
            self.queue_cond.notify_all()

    def toggle_pause(self) -> None:
        if self.paused_announcement is not None:
            self.__resume_paused()
        else:
            self.__pause_current()

    def _start_one_msg_loop(self, msg_fn: Callable[[], Any]) -> None:
        if self.__one_msg_loop_running.is_set():
            return

        th.Thread(target=self.__one_msg_loop, daemon=True, args=(msg_fn,)).start()

    def _stop_one_msg_loop(self) -> None:
        if not self.__one_msg_loop_running.is_set():
            return

        self.__one_msg_loop_running.clear()

    def __one_msg_loop(self, msg_fn: Callable[[], Any]) -> None:
        self.__one_msg_loop_running.set()
        time.sleep(TTS.ONE_MSG_LOOP_INTERVAL / 2)

        while self.__one_msg_loop_running.is_set():
            msg_fn()
            time.sleep(TTS.ONE_MSG_LOOP_INTERVAL)

    def __on_announcement_ended(
        self, announcement: Announcement, announced: bool
    ) -> None:
        if self.on_announcement_ended is not None:
            self.on_announcement_ended(announcement, announced)

    def __resume_paused(self) -> None:
        if self.paused_announcement is None:
            return

        self.stop_and_say(
            self.paused_announcement.text,
            self.paused_announcement.category,
            self.paused_announcement.priority,
        )

        self.paused_announcement = None

    def __pause_current(self) -> None:
        if not isinstance(self.current_announcement, TextAnnouncement):
            return

        with self.is_speaking_cond:
            if not self.is_speaking():
                return

            current = self.current_announcement
            if self.current_announcement_index >= len(current.text):
                return

            if not current.is_error() and not current.is_graph():
                self.paused_announcement = TextAnnouncement(
                    text=current.text[self.current_announcement_index :],
                    priority=Announcement.Priority.HIGH,
                    category=current.category,
                )

            self.stop_speaking()

    def __on_utterance_started(self, name: str) -> None:
        pass

    def __on_utterance_finished(self, name: str, completed: bool) -> None:
        self.current_announcement_index = 0

        with self.is_speaking_cond:
            self.__is_speaking.clear()
            self.is_speaking_cond.notify_all()

    def __on_word_started(self, name: str, location: int, length: int) -> None:
        self.current_announcement_index = location

    def __get_next_announcement(self) -> Optional[Announcement]:
        with self.queue_cond:
            while not self.queue and self.__running.is_set():
                self.queue_cond.wait()

            if not self.__running.is_set():
                return None

            return self.queue.popleft()

    def __announce_pause(self, announcement: PauseAnnouncement) -> None:
        self._timestamps[announcement.category] = time.time()
        time.sleep(announcement.duration)

    def __announce_text(self, announcement: TextAnnouncement) -> None:
        with self.is_speaking_cond:
            self.engine.iterate()
            self.__is_speaking.set()
            self._timestamps[announcement.category] = time.time()

        print(announcement.text)

        # Should block until the utterance is finished
        # But on MacOS, the engine doesn't seem to be blocking
        # The while loop is a workaround
        self.engine.say(
            announcement.text,
            name=announcement.id,
        )

        with self.is_speaking_cond:
            while self.is_speaking() and self.__running.is_set():
                self.is_speaking_cond.wait()
