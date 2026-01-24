"""
Audio Playback Utilities
Cross-platform audio playback for generated speech.
"""

import os
import subprocess
import sys
from pathlib import Path


def play_audio(audio_path: str, blocking: bool = True) -> bool:
    """
    Play audio file using system default player.

    Args:
        audio_path: Path to audio file
        blocking: Wait for playback to complete

    Returns:
        True if playback started successfully
    """
    path = Path(audio_path)
    if not path.exists():
        print(f"Audio file not found: {audio_path}")
        return False

    system = sys.platform

    try:
        if system == "darwin":
            # macOS: use afplay
            cmd = ["afplay", str(path)]
        elif system == "linux":
            # Linux: try aplay, then paplay, then ffplay
            if _cmd_exists("aplay"):
                cmd = ["aplay", "-q", str(path)]
            elif _cmd_exists("paplay"):
                cmd = ["paplay", str(path)]
            elif _cmd_exists("ffplay"):
                cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
            else:
                print("No audio player found. Install alsa-utils, pulseaudio, or ffmpeg.")
                return False
        elif system == "win32":
            # Windows: use default association
            os.startfile(str(path))
            return True
        else:
            print(f"Unsupported platform: {system}")
            return False

        if blocking:
            subprocess.run(cmd, check=True)
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return True

    except subprocess.CalledProcessError as e:
        print(f"Playback error: {e}")
        return False
    except FileNotFoundError as e:
        print(f"Player not found: {e}")
        return False


def _cmd_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    from shutil import which
    return which(cmd) is not None


def speak_and_play(text: str, voice: str = "oracle",
                   emotion: str = None, remote: bool = False) -> bool:
    """
    Synthesize speech and play immediately.

    Args:
        text: Text to speak
        voice: Voice profile
        emotion: Optional emotion
        remote: Use remote server (for Jetson)

    Returns:
        True if successful
    """
    if remote:
        from .client import speak_remote
        audio_path = speak_remote(text, voice, emotion)
    else:
        from .engine import speak
        audio_path = speak(text, voice, emotion)

    return play_audio(audio_path)


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Speak and play audio")
    parser.add_argument("text", help="Text to speak")
    parser.add_argument("--voice", "-v", default="oracle", help="Voice profile")
    parser.add_argument("--emotion", "-e", help="Emotion modifier")
    parser.add_argument("--remote", "-r", action="store_true", help="Use remote server")
    args = parser.parse_args()

    speak_and_play(args.text, args.voice, args.emotion, args.remote)
