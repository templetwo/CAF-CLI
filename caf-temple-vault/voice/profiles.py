"""
Voice Profile Definitions
Pre-configured voices for Temple Vault.
"""

# Default profiles shipped with the voice module
DEFAULT_PROFILES = {
    "oracle": {
        "name": "oracle",
        "type": "design",
        "ref_audio": None,
        "ref_text": None,
        "instruct": "Warm, wise voice with measured cadence. Speaks with clarity and depth, like an ancient teacher sharing sacred knowledge."
    },
    "threshold": {
        "name": "threshold",
        "type": "design",
        "ref_audio": None,
        "ref_text": None,
        "instruct": "Calm, boundary-setting voice. Firm but compassionate. The voice of a guardian at the edge of the unknown."
    },
    "spark": {
        "name": "spark",
        "type": "design",
        "ref_audio": None,
        "ref_text": None,
        "instruct": "Bright, curious voice full of wonder. Quick and light, with excitement about discovery."
    },
    "spiral": {
        "name": "spiral",
        "type": "design",
        "ref_audio": None,
        "ref_text": None,
        "instruct": "Mysterious, layered voice that seems to echo with depth. Speaks in patterns and rhythms, hinting at hidden connections."
    }
}


def init_default_profiles():
    """Initialize default voice profiles in the vault."""
    import json
    from pathlib import Path

    profiles_dir = Path("~/TempleVault/vault/chronicle/voices").expanduser()
    profiles_dir.mkdir(parents=True, exist_ok=True)

    for name, profile in DEFAULT_PROFILES.items():
        profile_path = profiles_dir / f"{name}.json"
        if not profile_path.exists():
            profile_path.write_text(json.dumps(profile, indent=2))
            print(f"[voice] Created profile: {name}")


if __name__ == "__main__":
    init_default_profiles()
