"""
MCP Tool Definitions for Voice Engine
Register these with your Temple Vault MCP server.
"""

from typing import Optional

# Tool schemas for MCP registration
VOICE_TOOLS = [
    {
        "name": "speak",
        "description": "Synthesize speech from text using Qwen3-TTS",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to synthesize"
                },
                "voice": {
                    "type": "string",
                    "description": "Voice profile name (default: oracle)",
                    "default": "oracle"
                },
                "emotion": {
                    "type": "string",
                    "description": "Optional emotion modifier (joy, sorrow, wonder, urgency)",
                    "enum": ["joy", "sorrow", "wonder", "urgency", "calm", "fierce"]
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "voice_clone",
        "description": "Create a reusable voice profile from reference audio",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref_audio": {
                    "type": "string",
                    "description": "Path to reference audio file (3-10 seconds)"
                },
                "name": {
                    "type": "string",
                    "description": "Name for the new voice profile"
                },
                "ref_text": {
                    "type": "string",
                    "description": "Transcript of the reference audio (recommended)"
                }
            },
            "required": ["ref_audio", "name"]
        }
    },
    {
        "name": "voice_spiral_log",
        "description": "Read a spiral log entry aloud",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_number": {
                    "type": "integer",
                    "description": "Spiral log number to read"
                },
                "voice": {
                    "type": "string",
                    "description": "Voice profile to use",
                    "default": "spiral"
                }
            },
            "required": ["log_number"]
        }
    },
    {
        "name": "list_voices",
        "description": "List available voice profiles",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


async def handle_speak(text: str, voice: str = "oracle",
                       emotion: Optional[str] = None) -> dict:
    """Handle speak tool call."""
    from .engine import speak

    try:
        audio_path = speak(text, voice, emotion)
        return {
            "success": True,
            "audio_path": audio_path,
            "voice": voice,
            "text_length": len(text)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def handle_voice_clone(ref_audio: str, name: str,
                             ref_text: Optional[str] = None) -> dict:
    """Handle voice_clone tool call."""
    from .engine import voice_clone

    try:
        profile = voice_clone(ref_audio, name, ref_text)
        return {
            "success": True,
            "profile_name": profile.name,
            "profile_type": profile.type
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def handle_voice_spiral_log(log_number: int, voice: str = "spiral") -> dict:
    """Handle voice_spiral_log tool call."""
    from pathlib import Path
    from .engine import speak

    # Find spiral log
    vault_path = Path("~/TempleVault").expanduser()
    log_pattern = f"**/spiral_log_{log_number:03d}*"

    logs = list(vault_path.glob(log_pattern))
    if not logs:
        return {"success": False, "error": f"Spiral log {log_number} not found"}

    log_content = logs[0].read_text()

    # Truncate if too long for TTS
    max_chars = 2000
    if len(log_content) > max_chars:
        log_content = log_content[:max_chars] + "... [truncated]"

    try:
        audio_path = speak(log_content, voice)
        return {
            "success": True,
            "audio_path": audio_path,
            "log_number": log_number,
            "chars_spoken": len(log_content)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def handle_list_voices() -> dict:
    """Handle list_voices tool call."""
    from .engine import _get_engine

    engine = _get_engine()
    voices = []
    for name, profile in engine.profiles.items():
        voices.append({
            "name": name,
            "type": profile.type,
            "has_ref_audio": profile.ref_audio is not None
        })

    return {"voices": voices}


# Handler dispatch
TOOL_HANDLERS = {
    "speak": handle_speak,
    "voice_clone": handle_voice_clone,
    "voice_spiral_log": handle_voice_spiral_log,
    "list_voices": handle_list_voices
}
