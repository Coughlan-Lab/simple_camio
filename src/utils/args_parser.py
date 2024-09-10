import argparse

camio_parser = argparse.ArgumentParser(description="CamIO, with LLM integration")
camio_parser.add_argument(
    "--model",
    help="Path to model json file.",
    default="models/new_york/new_york.json",
)
camio_parser.add_argument(
    "--out",
    help="Path to chat save file.",
    default="out/last_chat.txt",
)
camio_parser.add_argument(
    "--tts_rate",
    help="TTS speed rate (words per minute).",
    type=int,
    default=200,
)
camio_parser.add_argument(
    "--debug",
    help="Debug mode.",
    action="store_true",
    default=False,
)
camio_parser.add_argument(
    "--no-llm",
    help="Disable llm interaction.",
    action="store_true",
    default=False,
)
camio_parser.add_argument(
    "--lang",
    help="System language",
    choices=["en"],
    default="en",
)


def get_args() -> argparse.Namespace:
    return camio_parser.parse_args()
