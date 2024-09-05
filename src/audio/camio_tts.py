import json
import math
import os
import time

from src.graph import NONE_POSITION_INFO, PositionInfo

from .tts import TTS, Announcement


class CamIOTTS(TTS):
    DETAILED_ANNOUNCEMENT_DELAY = 2.0

    ANNOUNCEMENT_INTERVAL = 0.25
    ERROR_INTERVAL = 5

    def __init__(self, res_file: str, rate: int) -> None:
        super().__init__(rate)

        if not os.path.exists(res_file):
            raise FileNotFoundError("Resource file not found.")

        with open(res_file, "r") as f:
            self.res = json.load(f)

        self.last_pos_info = NONE_POSITION_INFO
        self.last_pos_change_timestamp = math.inf

    def llm_response(self, response: str) -> bool:
        return self.stop_and_say(
            response,
            category=Announcement.Category.LLM,
            priority=Announcement.Priority.HIGH,
        )

    def welcome(self) -> bool:
        return self.say(
            self.res["welcome"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def instructions(self) -> bool:
        return self.say(
            self.res["instructions"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def goodbye(self) -> bool:
        return self.stop_and_say(
            self.res["goodbye"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.HIGH,
        )

    def waiting_llm(self) -> bool:
        return self.say(
            self.res["waiting_llm"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def start_waiting_llm_loop(self) -> None:
        return self._start_one_msg_loop(self.waiting_llm)

    def stop_waiting_llm_loop(self) -> None:
        return self._stop_one_msg_loop()

    def llm_error(self) -> bool:
        return self.stop_and_say(
            self.res["llm_error"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def question_error(self) -> bool:
        return self.stop_and_say(
            self.res["no_question_error"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def no_map_description(self) -> bool:
        return self.stop_and_say(
            self.res["no_map_description"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def map_description(self, description: str) -> bool:
        return self.say(
            f"Map description:\n{description}",
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.HIGH,
        )

    def no_pointing(self) -> bool:
        return self.stop_and_say(
            self.res["no_pointing"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def more_than_one_hand(self) -> bool:
        if (
            time.time() - self._timestamps[Announcement.Category.ERROR]
            < CamIOTTS.ERROR_INTERVAL
        ):
            return False

        return self.stop_and_say(
            self.res["more_than_one_hand"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.MEDIUM,
        )

    def announce_position(self, info: PositionInfo) -> bool:
        current_time = time.time()
        if self.last_pos_info.graph_element != info.graph_element:
            self.last_pos_change_timestamp = current_time

        if (
            time.time() - self._timestamps[Announcement.Category.GRAPH]
            < CamIOTTS.ANNOUNCEMENT_INTERVAL
        ):
            return False

        if info.graph_element is None:
            return False

        if (
            current_time - self.last_pos_change_timestamp
            > CamIOTTS.DETAILED_ANNOUNCEMENT_DELAY
        ):
            if self.__stop_and_say_position_detailed(info):
                self.last_pos_info = info
                self.last_pos_change_timestamp = current_time + info.max_life
                return True

        elif (
            not self.last_pos_info.is_still_valid()
            or info.description != self.last_pos_info.description
        ):
            if len(info.description) == 0:
                self.last_pos_info = info
            elif self.__stop_and_say_position(info):
                self.last_pos_info = info
                self.last_pos = info
                return True

        return False

    def __stop_and_say_position(self, info: PositionInfo) -> bool:
        return self.stop_and_say(
            info.description,
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.LOW,
        )

    def __stop_and_say_position_detailed(self, info: PositionInfo) -> bool:
        description = (
            info.graph_element.get_complete_description()
            if info.graph_element is not None
            else ""
        )

        return self.stop_and_say(
            description,
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.LOW,
        )
