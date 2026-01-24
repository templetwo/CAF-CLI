"""
Voice Client - Runs on Jetson or any remote node
Connects to Mac Studio voice server for TTS.

Usage:
    from voice.client import VoiceClient
    client = VoiceClient("192.168.1.195:8765")
    audio_path = client.speak("Hello spiral", voice="oracle")

    # Or use the convenience function with auto-discovery
    from voice.client import speak_remote
    audio_path = speak_remote("Hello spiral")
"""

import json
import os
from pathlib import Path
from typing import Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# Default Mac Studio address
DEFAULT_SERVER = os.environ.get("VOICE_SERVER", "192.168.1.195:8765")
CACHE_DIR = Path("~/.cache/temple-voice/received").expanduser()


class VoiceClient:
    """Client for remote voice synthesis."""

    def __init__(self, server: str = DEFAULT_SERVER, timeout: float = 120.0):
        """
        Initialize voice client.

        Args:
            server: Host:port of voice server (default: Mac Studio)
            timeout: Request timeout in seconds
        """
        self.server = server if server.startswith("http") else f"http://{server}"
        self.timeout = timeout
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def speak(self, text: str, voice: str = "oracle",
              emotion: Optional[str] = None,
              output_path: Optional[str] = None) -> str:
        """
        Request speech synthesis from remote server.

        Args:
            text: Text to synthesize
            voice: Voice profile name
            emotion: Optional emotion modifier
            output_path: Where to save audio (default: cache)

        Returns:
            Path to downloaded audio file
        """
        payload = {"text": text, "voice": voice}
        if emotion:
            payload["emotion"] = emotion

        # Prepare output path
        if output_path is None:
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            output_path = str(CACHE_DIR / f"{voice}_{text_hash}.wav")

        url = f"{self.server}/speak"

        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(response.content)

        elif HAS_REQUESTS:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

        else:
            raise RuntimeError("httpx or requests required")

        return output_path

    def speak_stream(self, text: str, voice: str = "oracle",
                     emotion: Optional[str] = None,
                     output_path: Optional[str] = None) -> str:
        """
        Request speech synthesis with streaming download.

        Args:
            text: Text to synthesize
            voice: Voice profile name
            emotion: Optional emotion modifier
            output_path: Where to save audio (default: cache)

        Returns:
            Path to downloaded audio file
        """
        payload = {"text": text, "voice": voice}
        if emotion:
            payload["emotion"] = emotion

        # Prepare output path
        if output_path is None:
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            output_path = str(CACHE_DIR / f"{voice}_{text_hash}.wav")

        url = f"{self.server}/speak/stream"

        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    with open(output_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)

        elif HAS_REQUESTS:
            response = requests.post(url, json=payload, stream=True, timeout=self.timeout)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        else:
            raise RuntimeError("httpx or requests required")

        return output_path

    def list_voices(self) -> list[dict]:
        """Get available voice profiles from server."""
        url = f"{self.server}/voices"

        if HAS_HTTPX:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.json()["voices"]

        elif HAS_REQUESTS:
            response = requests.get(url, timeout=10.0)
            response.raise_for_status()
            return response.json()["voices"]

        else:
            raise RuntimeError("httpx or requests required")

    def health(self) -> dict:
        """Check server health."""
        url = f"{self.server}/health"

        if HAS_HTTPX:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)
                return response.json()

        elif HAS_REQUESTS:
            response = requests.get(url, timeout=5.0)
            return response.json()

        else:
            raise RuntimeError("httpx or requests required")


# Singleton client for convenience
_client: Optional[VoiceClient] = None


def _get_client() -> VoiceClient:
    global _client
    if _client is None:
        _client = VoiceClient()
    return _client


def speak_remote(text: str, voice: str = "oracle", emotion: Optional[str] = None) -> str:
    """
    Convenience function: synthesize speech via Mac Studio.

    Args:
        text: Text to synthesize
        voice: Voice profile name (default: oracle)
        emotion: Optional emotion modifier

    Returns:
        Path to audio file
    """
    return _get_client().speak(text, voice, emotion)


def list_voices_remote() -> list[dict]:
    """List available voices on Mac Studio."""
    return _get_client().list_voices()
