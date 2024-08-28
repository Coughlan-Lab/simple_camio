import json
import os
import threading as th
import time
from dataclasses import dataclass, field
from enum import Enum
from queue import PriorityQueue
from typing import Optional

import pyttsx3


@dataclass(order=True)
class TTSAnnouncement:
    class Priority(Enum):
        NONE = 3
        LOW = 2
        MEDIUM = 1
        HIGH = 0

    text: str = field(compare=False)
    priority: Priority
    name: str = field(default="", compare=False)


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
        self.main_lock = th.Condition()
        self.waiting_loop_running = th.Event()

        self.queue: PriorityQueue[TTSAnnouncement] = PriorityQueue()
        self.current_msg_word_index = 0
        self.current_announcement: Optional[TTSAnnouncement] = None

    def start(self) -> None:
        self.engine.startLoop(False)
        th.Thread(target=self.__queue_loop).start()

    def stop(self) -> None:
        self.running = False

        with self.main_lock:
            self.main_lock.notify()

    def stop_speaking(self) -> None:
        self.queue.queue.clear()
        self.engine.stop()

    def is_speaking(self) -> bool:
        return bool(self.engine.isBusy())

    def say(
        self,
        text: str,
        priority: TTSAnnouncement.Priority = TTSAnnouncement.Priority.LOW,
        name: str = "",
    ) -> None:
        if text == "":
            return

        if (
            self.current_announcement is not None
            and self.current_announcement.priority.value < priority.value
        ):  # min value is high priority
            self.stop_speaking()

        self.queue.put(TTSAnnouncement(text, priority, name))

    def __say_now(self, text: str, name: str) -> None:
        self.engine.say(text, name=name)
        self.engine.iterate()

    def __on_utterance_started(self, name: str) -> None:
        pass

    def __on_utterance_finished(self, name: str, completed: bool) -> None:
        with self.main_lock:
            self.main_lock.notify()

    def __on_word_started(self, name: str, location: int, length: int) -> None:
        self.current_msg_word_index = location

    def __queue_loop(self) -> None:
        self.running = True

        with self.main_lock:
            while self.running:

                self.current_announcement = None
                next_announcement = (
                    self.queue.get()
                )  # blocks until an item is available

                self.current_announcement = next_announcement
                self.current_msg_word_index = 0

                self.__say_now(
                    self.current_announcement.text, self.current_announcement.name
                )

                self.main_lock.wait()

        self.engine.endLoop()

    def welcome(self) -> None:
        self.say(self.res["welcome"], name="welcome message")

    def instructions(self) -> None:
        self.say(self.res["instructions"], name="instructions")

    def goodbye(self) -> None:
        self.say(self.res["goodbye"], name="goodbye message")

    def waiting_llm(self) -> None:
        self.say(
            self.res["waiting"],
            name="waiting llm message",
            priority=TTSAnnouncement.Priority.MEDIUM,
        )

    def llm_error(self) -> None:
        self.say(
            self.res["error"],
            name="llm error message",
            priority=TTSAnnouncement.Priority.HIGH,
        )

    def no_description(self) -> None:
        self.say(self.res["no_description"], name="no description message")

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
