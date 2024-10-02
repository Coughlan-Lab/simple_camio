import json
import math
import os
import time
from typing import Optional

from src.position import MovementDirection, PositionInfo
from src.frame_processing import Hand

from .tts import TTS, Announcement, TextAnnouncement


class CamIOTTS(TTS):
    ANNOUNCEMENT_INTERVAL = 0.25
    ERROR_INTERVAL = 3.5

    def __init__(self, res_file: str, rate: int = TTS.DEFAULT_RATE) -> None:
        super().__init__(rate)

        if not os.path.exists(res_file):
            raise FileNotFoundError("Resource file not found.")

        with open(res_file, "r") as f:
            self.res = json.load(f)

        self.position_handler = PositionAnnouncer(self)

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

    def waiting(self) -> Optional[Announcement]:
        return self.say(
            self.res["waiting"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def start_waiting_llm_loop(self) -> None:
        return self._start_one_msg_loop(self.waiting)

    def stop_waiting_llm_loop(self) -> None:
        return self._stop_one_msg_loop()

    def llm_error(self) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["llm_error"],
            category=Announcement.Category.ERROR | Announcement.Category.LLM,
            priority=Announcement.Priority.HIGH,
        )

    def no_question_error(self) -> Optional[Announcement]:
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
            category=Announcement.Category.NAVIGATION,
            priority=Announcement.Priority.MEDIUM,
        )

        return announced

    def position_paused(self) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["position_paused"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def position_resumed(self) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["position_resumed"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

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

    def hand_side(self, side: Hand.Side) -> Optional[Announcement]:
        return self.stop_and_say(
            self.res["hand_side"].format(side),
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def position(self, info: PositionInfo) -> Optional[Announcement]:
        if (
            time.time() - self._timestamps[Announcement.Category.GRAPH]
            < CamIOTTS.ANNOUNCEMENT_INTERVAL
        ):
            return

        return self.position_handler.announce(info)


class PositionAnnouncer:
    DETAILED_NODES_ANNOUNCEMENT_DELAY = 1.0
    DETAILED_ANNOUNCEMENT_DELAY = 2.0

    def __init__(self, tts: TTS) -> None:
        self.tts = tts

        self.last_position = PositionInfo.NONE
        self.last_pos_change_timestamp = math.inf

    def announce(self, position: PositionInfo) -> Optional[Announcement]:
        current_time = time.time()
        if self.__has_changed_position(position):
            self.last_pos_change_timestamp = current_time

        if position.graph_element is None:
            return None

        announcement: Optional[Announcement] = None
        if self.__has_changed_position(position) and not self.__is_repeated(
            position.description
        ):
            self.last_pos_change_timestamp = current_time

            if len(position.description) == 0 or (
                announcement := self.__announce_base(position)
            ):
                self.last_position = position

        if not self.last_position.is_still_valid() or self.__should_play_detailed(
            position
        ):
            if announcement := self.__announce_detailed(position):
                self.last_position = position
                self.last_pos_change_timestamp = math.inf

        return announcement

    def __has_changed_position(self, info: PositionInfo) -> bool:
        return self.last_position.graph_element != info.graph_element

    def __is_repeated(self, description: str) -> bool:
        repeated = False
        if isinstance(self.tts.last_announcement, TextAnnouncement):
            repeated = self.tts.last_announcement.text == description

        if isinstance(self.tts.current_announcement, TextAnnouncement):
            repeated = repeated or self.tts.current_announcement.text == description

        return repeated

    def __should_play_detailed(self, info: PositionInfo) -> bool:
        if info.graph_element is None:
            return False

        return (
            info.movement == MovementDirection.NONE
            and time.time() - self.last_pos_change_timestamp > self.__get_delay(info)
            and not self.__is_repeated(info.complete_description)
        )

    def __get_delay(self, info: PositionInfo) -> float:
        return (
            PositionAnnouncer.DETAILED_NODES_ANNOUNCEMENT_DELAY
            if info.is_node()
            else PositionAnnouncer.DETAILED_ANNOUNCEMENT_DELAY
        )

    def __announce_base(self, info: PositionInfo) -> Optional[Announcement]:
        return self.tts.stop_and_say(
            info.description,
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.LOW,
        )

    def __announce_detailed(self, info: PositionInfo) -> Optional[Announcement]:
        description = (
            info.complete_description if info.graph_element is not None else ""
        )

        return self.tts.say(
            description,
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.LOW,
        )
