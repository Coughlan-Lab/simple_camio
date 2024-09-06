import threading as th
import time
import uuid
from abc import ABC
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Callable, Optional

import pyttsx3


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
    text: Optional[str] = field(default=None, compare=False)
    category: Announcement.Category = Announcement.Category.SYSTEM
    priority: Announcement.Priority = Announcement.Priority.LOW


@dataclass(frozen=True)
class PauseAnnouncement(Announcement):
    duration: float = field(default=1.0, compare=False)


NONE_ANNOUNCEMENT = TextAnnouncement(priority=Announcement.Priority.NONE)


class TTS:
    RATE = 200
    ONE_MSG_LOOP_INTERVAL = 7
    ERROR_INTERVAL = 5

    def __init__(self, rate: int = RATE) -> None:
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)

        self.engine.connect("started-utterance", self.__on_utterance_started)
        self.engine.connect("finished-utterance", self.__on_utterance_finished)
        self.engine.connect("started-word", self.__on_word_started)

        self.current_announcement_index = 0
        self.current_announcement: TextAnnouncement = NONE_ANNOUNCEMENT
        self.last_announcement: TextAnnouncement = NONE_ANNOUNCEMENT
        self.paused_announcement: Optional[TextAnnouncement] = None

        self.queue: deque[Announcement] = deque()

        self.__running = th.Event()
        self.__one_msg_loop_running = th.Event()
        self.__is_speaking = th.Event()

        self.main_lock = th.RLock()
        self.queue_cond = th.Condition()
        self.is_speaking_cond = th.Condition()

        self._timestamps = {category: 0.0 for category in Announcement.Category}

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
                        self.last_announcement = self.current_announcement
                        self.current_announcement = next_announcement

                        self.engine.say(
                            self.current_announcement.text,
                            name=self.current_announcement.id,
                        )
                        self.engine.iterate()

                        self._timestamps[self.current_announcement.category] = (
                            time.time()
                        )

                with self.is_speaking_cond:
                    while self.is_speaking() and self.__running.is_set():
                        self.is_speaking_cond.wait()

                if isinstance(next_announcement, TextAnnouncement):
                    self.on_announcement_ended(self.current_announcement.category)
                    self.last_announcement = self.current_announcement
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
            if (
                self.is_speaking()
                and self.current_announcement.text is not None
                and self.current_announcement_index
                < len(self.current_announcement.text)
            ):
                if self.current_announcement.category not in [
                    Announcement.Category.ERROR,
                    Announcement.Category.GRAPH,
                ]:
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
        text: Optional[str],
        category: Announcement.Category,
        priority: Announcement.Priority = Announcement.Priority.LOW,
    ) -> bool:
        if text is None:
            return False

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
        text: Optional[str],
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

    def _start_one_msg_loop(self, msg_fn: Callable[[], bool]) -> None:
        if self.__one_msg_loop_running.is_set():
            return

        th.Thread(target=self.__one_msg_loop, daemon=True, args=(msg_fn,)).start()

    def _stop_one_msg_loop(self) -> None:
        if not self.__one_msg_loop_running.is_set():
            return

        self.__one_msg_loop_running.clear()

    def __one_msg_loop(self, msg_fn: Callable[[], bool]) -> None:
        self.__one_msg_loop_running.set()
        time.sleep(TTS.ONE_MSG_LOOP_INTERVAL / 2)

        while self.__one_msg_loop_running.is_set():
            msg_fn()
            time.sleep(TTS.ONE_MSG_LOOP_INTERVAL)
