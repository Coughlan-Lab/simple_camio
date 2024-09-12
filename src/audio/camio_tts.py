import json
import math
import os
import time
from typing import Optional

from src.position import MovementDirection, PositionInfo

from .tts import TTS, Announcement, TextAnnouncement


class CamIOTTS(TTS):
    DETAILED_NODES_ANNOUNCEMENT_DELAY = 1.5
    DETAILED_ANNOUNCEMENT_DELAY = 2.5

    ANNOUNCEMENT_INTERVAL = 0.25
    ERROR_INTERVAL = 3.5

    def __init__(self, res_file: str, rate: int = TTS.DEFAULT_RATE) -> None:
        super().__init__(rate)

        if not os.path.exists(res_file):
            raise FileNotFoundError("Resource file not found.")

        with open(res_file, "r") as f:
            self.res = json.load(f)

        self.last_pos_info = PositionInfo.NONE
        self.last_pos_change_timestamp = math.inf

    def llm_response(self, response: str) -> Optional[Announcement]:
        return self.stop_and_say(
            response,
            category=Announcement.Category.LLM,
            priority=Announcement.Priority.HIGH,
        )

    def welcome(self) -> Optional[Announcement]:
        return self.say(
            self.res["welcome"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def instructions(self) -> Optional[Announcement]:
        return self.say(
            self.res["instructions"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def goodbye(self) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["goodbye"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.HIGH,
        )

    def waiting_llm(self) -> Optional[Announcement]:
        return self.say(
            self.res["waiting_llm"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def start_waiting_llm_loop(self) -> None:
        return self._start_one_msg_loop(self.waiting_llm)

    def stop_waiting_llm_loop(self) -> None:
        return self._stop_one_msg_loop()

    def llm_error(self) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["llm_error"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def question_error(self) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["no_question_error"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def no_map_description(self) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["no_map_description"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def map_description(self, description: str) -> Optional[Announcement]:
        return self.say(
            f"Map description:\n{description}",
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.HIGH,
        )

    def no_pointing(self) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["no_pointing"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def destination_reached(self) -> Optional[Announcement]:
        announced = self.stop_and_say(
            self.res["destination_reached"],
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.MEDIUM,
        )

        return announced

    def wrong_direction(self) -> Optional[Announcement]:
        if (
            time.time() - self._timestamps[Announcement.Category.ERROR]
            < CamIOTTS.ERROR_INTERVAL
        ):
            return None

        return self.stop_and_say(
            self.res["wrong_direction"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.MEDIUM,
        )

    def more_than_one_hand(self) -> Optional[Announcement]:
        if (
            time.time() - self._timestamps[Announcement.Category.ERROR]
            < CamIOTTS.ERROR_INTERVAL
        ):
            return None

        return self.stop_and_say(
            self.res["more_than_one_hand"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.MEDIUM,
        )

    def hand_side(self, side: str) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["hand_side"].format(side),
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def announce_position(self, info: PositionInfo) -> None:
        current_time = time.time()
        if self.__has_changed_position(info):
            self.last_pos_change_timestamp = current_time

        if (
            current_time - self._timestamps[Announcement.Category.GRAPH]
            < CamIOTTS.ANNOUNCEMENT_INTERVAL
        ):
            return

        if info.graph_element is None:
            return

        if self.__has_changed_position(info) and not self.__is_repeated(
            info.description
        ):
            self.last_pos_change_timestamp = current_time

            if len(info.description) == 0 or self.__stop_and_say_position(info):
                self.last_pos_info = info

            return

        if not self.last_pos_info.is_still_valid() or self.__should_play_detailed(info):
            if self.__say_position_detailed(info):
                self.last_pos_info = info
                self.last_pos_change_timestamp = math.inf

    def __has_changed_position(self, info: PositionInfo) -> bool:
        return self.last_pos_info.graph_element != info.graph_element

    def __is_repeated(self, description: str) -> bool:
        repeated = False
        if isinstance(self.last_announcement, TextAnnouncement):
            repeated = self.last_announcement.text == description

        if isinstance(self.current_announcement, TextAnnouncement):
            repeated = repeated or self.current_announcement.text == description

        return repeated

    def __should_play_detailed(self, info: PositionInfo) -> bool:
        if info.graph_element is None:
            return False

        return (
            info.movement == MovementDirection.NONE
            and time.time() - self.last_pos_change_timestamp > self.__get_delay(info)
            and not self.__is_repeated(info.graph_element.get_complete_description())
        )

    def __get_delay(self, info: PositionInfo) -> float:
        return (
            CamIOTTS.DETAILED_NODES_ANNOUNCEMENT_DELAY
            if info.is_node()
            else CamIOTTS.DETAILED_ANNOUNCEMENT_DELAY
        )

    def __stop_and_say_position(self, info: PositionInfo) -> Optional[Announcement]:
        return self.stop_and_say(
            info.description,
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.LOW,
        )

    def __say_position_detailed(self, info: PositionInfo) -> Optional[Announcement]:
        description = (
            info.graph_element.get_complete_description()
            if info.graph_element is not None
            else ""
        )

        return self.say(
            description,
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.LOW,
        )
