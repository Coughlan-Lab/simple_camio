import argparse

from .utils import StrEnum


class Lang(StrEnum):
    EN_US = "en_US"
    EN_GB = "en_GB"
    IT = "it_IT"


class Gender(StrEnum):
    MALE = "VoiceGenderMale"
    FEMALE = "VoiceGenderFemale"
    NEUTRAL = "VoiceGenderNeuter"


camio_parser = argparse.ArgumentParser(description="CamIO, with LLM integration")

camio_parser.add_argument("--model", help="Path to model json file.", required=True)
camio_parser.add_argument(
    "--out",
    help="Path to chat save file.",
    default="out/last_chat.txt",
)

camio_parser.add_argument(
    "--lang", help="System language", type=Lang, choices=list(Lang), default=Lang.EN_GB
)
camio_parser.add_argument(
    "--tts-rate",
    help="TTS speed rate (words per minute).",
    type=int,
    default=200,
)
camio_parser.add_argument(
    "--tts-gender",
    help="TTS voice gender",
    type=Gender,
    choices=list(Gender),
    default=Gender.MALE,
)

camio_parser.add_argument(
    "--no-llm",
    help="Disable llm interaction.",
    action="store_true",
    default=False,
)
camio_parser.add_argument(
    "--no-stt",
    help="Replace STT with keyboard input.",
    action="store_true",
    default=False,
)

camio_parser.add_argument(
    "--debug",
    help="Enable debug mode.",
    action="store_true",
    default=False,
)


def get_args() -> argparse.Namespace:
    return camio_parser.parse_args()
