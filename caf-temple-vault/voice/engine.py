"""
Temple Vault Voice Engine
Qwen3-TTS wrapper for sovereign speech synthesis.

Usage:
    from voice import VoiceEngine
    engine = VoiceEngine()
    engine.speak("The spiral continues", voice="oracle")
"""

import json
from pathlib import Path
from typing import Optional

# Lazy import - only load TTS when needed
_tts_model = None

PROFILES_DIR = Path("~/TempleVault/vault/chronicle/voices").expanduser()
CACHE_DIR = Path("~/.cache/temple-voice").expanduser()


def _get_model():
    """Lazy-load Qwen3-TTS model."""
    global _tts_model
    if _tts_model is None:
        try:
            from qwen_tts import Qwen3TTSModel
            _tts_model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-1.7B")
            print("[voice] Qwen3-TTS loaded")
        except ImportError:
            raise RuntimeError("qwen-tts not installed. Run: pip install qwen-tts")
    return _tts_model


class VoiceProfile:
    """Voice profile for consistent synthesis."""

    def __init__(self, name: str, profile_type: str = "design",
                 ref_audio: Optional[str] = None,
                 ref_text: Optional[str] = None,
                 instruct: str = ""):
        self.name = name
        self.type = profile_type
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        self.instruct = instruct

    @classmethod
    def load(cls, name: str) -> "VoiceProfile":
        """Load profile from vault."""
        profile_path = PROFILES_DIR / f"{name}.json"
        if profile_path.exists():
            data = json.loads(profile_path.read_text())
            return cls(**data)
        # Default profile
        return cls(name=name, instruct=f"Voice of {name}")

    def save(self):
        """Save profile to vault."""
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "type": self.type,
            "ref_audio": self.ref_audio,
            "ref_text": self.ref_text,
            "instruct": self.instruct
        }
        (PROFILES_DIR / f"{self.name}.json").write_text(json.dumps(data, indent=2))


class VoiceEngine:
    """Main voice synthesis engine."""

    def __init__(self):
        self.profiles: dict[str, VoiceProfile] = {}
        self._load_profiles()

    def _load_profiles(self):
        """Load all profiles from vault."""
        if PROFILES_DIR.exists():
            for f in PROFILES_DIR.glob("*.json"):
                profile = VoiceProfile.load(f.stem)
                self.profiles[profile.name] = profile

        # Ensure default oracle profile exists
        if "oracle" not in self.profiles:
            self.profiles["oracle"] = VoiceProfile(
                name="oracle",
                profile_type="design",
                instruct="Warm, wise voice with measured cadence. Speaks with clarity and depth."
            )

    def speak(self, text: str, voice: str = "oracle",
              emotion: Optional[str] = None,
              output_path: Optional[str] = None) -> str:
        """
        Synthesize speech from text.

        Args:
            text: Text to speak
            voice: Profile name (default: oracle)
            emotion: Optional emotion modifier
            output_path: Where to save audio (default: cache)

        Returns:
            Path to generated audio file
        """
        model = _get_model()
        profile = self.profiles.get(voice, self.profiles["oracle"])

        # Build instruction
        instruct = profile.instruct
        if emotion:
            instruct = f"{instruct} Express {emotion}."

        # Prepare output path
        if output_path is None:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            output_path = str(CACHE_DIR / f"{voice}_{text_hash}.wav")

        # Generate audio
        if profile.type == "clone" and profile.ref_audio:
            # Voice cloning mode
            audio = model.synthesize(
                text=text,
                ref_audio=profile.ref_audio,
                ref_text=profile.ref_text,
                instruct=instruct
            )
        else:
            # Design mode (no reference audio)
            audio = model.synthesize(
                text=text,
                instruct=instruct
            )

        # Save audio
        import soundfile as sf
        sf.write(output_path, audio, samplerate=24000)

        return output_path

    def clone(self, ref_audio: str, name: str,
              ref_text: Optional[str] = None,
              instruct: str = "") -> VoiceProfile:
        """
        Create a voice clone from reference audio.

        Args:
            ref_audio: Path to reference audio (3-10 seconds)
            name: Name for the new profile
            ref_text: Transcript of reference audio (recommended)
            instruct: Additional voice instructions

        Returns:
            New VoiceProfile
        """
        profile = VoiceProfile(
            name=name,
            profile_type="clone",
            ref_audio=ref_audio,
            ref_text=ref_text,
            instruct=instruct or f"Clone of {name}"
        )
        profile.save()
        self.profiles[name] = profile
        return profile


# Convenience functions for direct use
_engine: Optional[VoiceEngine] = None

def _get_engine() -> VoiceEngine:
    global _engine
    if _engine is None:
        _engine = VoiceEngine()
    return _engine

def speak(text: str, voice: str = "oracle", emotion: Optional[str] = None) -> str:
    """Synthesize speech. Returns path to audio file."""
    return _get_engine().speak(text, voice, emotion)

def voice_clone(ref_audio: str, name: str, ref_text: Optional[str] = None) -> VoiceProfile:
    """Create voice clone from reference audio."""
    return _get_engine().clone(ref_audio, name, ref_text)
