from .colors import singleton as Colors
from .fonts import singleton as Fonts
from .imgs.imgs_manager import singleton as ImgsManager
from .videos.videos_manager import singleton as VideosManager

__all__ = ["Colors", "Fonts", "ImgsManager", "VideosManager"]
