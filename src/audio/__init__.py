"""
Audio Module - Audio playback for ambient sounds and zone descriptions.

This module provides:
- Ambient sound players for background audio (heartbeat, crickets)
- Zone-based audio description playback
"""

from .audio import AmbientSoundPlayer, ZoneAudioPlayer

__all__ = [
    'AmbientSoundPlayer',
    'ZoneAudioPlayer',
]
