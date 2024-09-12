import argparse
from enum import Enum
from typing import Any, Dict


class Lang(Enum):
    EN = "en"
    IT = "it"


class Config:
    __instance = None

    def __new__(cls) -> "Config":
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self) -> None:
        self.name = "CamIO"

        self.debug = False
        self.lang = Lang.EN.value

        self.llm_enabled = True
        self.stt_enabled = True
        self.tts_rate = 200

        self.feets_per_pixel = 1.0
        self.feets_per_inch = 1.0
        self.template_path = ""

        self.temperature = 0.0

    @property
    def inches_per_feet(self) -> float:
        return 1 / self.feets_per_inch

    @property
    def pixels_per_feet(self) -> float:
        return 1 / self.feets_per_pixel

    def load_args(self, args: argparse.Namespace) -> None:
        self.debug = args.debug
        self.llm_enabled = not args.no_llm
        self.stt_enabled = not args.no_stt
        self.lang = args.lang.value
        self.tts_rate = args.tts_rate

    def load_model(self, model: Dict[str, Any]) -> None:
        self.feets_per_pixel = model["feets_per_pixel"]
        self.feets_per_inch = model["feets_per_inch"]
        self.template_path = model["template_image"]


config = Config()
