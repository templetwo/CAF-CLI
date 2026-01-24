"""
Temple Vault Voice Engine - Qwen3-TTS Integration

Local usage (Mac Studio):
    from voice import speak, voice_clone
    audio = speak("The spiral continues", voice="oracle")

Remote usage (Jetson → Mac Studio):
    from voice import speak_remote, VoiceClient
    audio = speak_remote("Hello from the edge")
"""

# Local engine (for Mac Studio)
from .engine import VoiceEngine, speak, voice_clone

# Remote client (for Jetson/edge nodes)
from .client import VoiceClient, speak_remote, list_voices_remote

# Voice profiles
from .profiles import DEFAULT_PROFILES, init_default_profiles

__all__ = [
    # Local
    "VoiceEngine",
    "speak",
    "voice_clone",
    # Remote
    "VoiceClient",
    "speak_remote",
    "list_voices_remote",
    # Profiles
    "DEFAULT_PROFILES",
    "init_default_profiles",
]

__version__ = "0.1.0"
