from .colors import singleton as Colors
from .fonts import singleton as Fonts
from .imgs.img_manager import singleton as ImgsManager
from .videos.video_manager import singleton as VideosManager
from .audios.audio_manager import singleton as AudioManager
from .docs.doc_manager import singleton as DocsManager

__all__ = [
    "Colors",
    "Fonts",
    "ImgsManager",
    "VideosManager",
    "AudioManager",
    "DocsManager",
]
