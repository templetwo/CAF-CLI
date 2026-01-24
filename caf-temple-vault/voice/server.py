"""
Voice Server - Runs on Mac Studio
Provides TTS endpoints for remote nodes (Jetson, etc.)

Usage:
    python3 -m voice.server --port 8765

Endpoints:
    POST /speak      - Synthesize speech, return audio
    POST /clone      - Create voice profile
    GET  /voices     - List available voices
    GET  /health     - Health check
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from .engine import VoiceEngine, VoiceProfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice.server")


class VoiceServer:
    """HTTP server for remote TTS requests."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.engine: Optional[VoiceEngine] = None

    async def init_engine(self):
        """Lazy-initialize the voice engine."""
        if self.engine is None:
            logger.info("Initializing voice engine...")
            self.engine = VoiceEngine()
            logger.info(f"Engine ready with {len(self.engine.profiles)} profiles")

    async def handle_speak(self, request: web.Request) -> web.Response:
        """Handle speak request - return audio file."""
        await self.init_engine()

        try:
            data = await request.json()
            text = data.get("text", "")
            voice = data.get("voice", "oracle")
            emotion = data.get("emotion")

            if not text:
                return web.json_response({"error": "No text provided"}, status=400)

            logger.info(f"Speak request: voice={voice}, len={len(text)}")

            # Generate audio
            audio_path = self.engine.speak(text, voice, emotion)

            # Return audio file
            return web.FileResponse(
                audio_path,
                headers={
                    "Content-Type": "audio/wav",
                    "X-Voice": voice,
                    "X-Text-Length": str(len(text))
                }
            )

        except Exception as e:
            logger.error(f"Speak error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_speak_stream(self, request: web.Request) -> web.StreamResponse:
        """Handle speak request - stream audio chunks."""
        await self.init_engine()

        try:
            data = await request.json()
            text = data.get("text", "")
            voice = data.get("voice", "oracle")
            emotion = data.get("emotion")

            if not text:
                return web.json_response({"error": "No text provided"}, status=400)

            logger.info(f"Stream request: voice={voice}, len={len(text)}")

            # Generate audio to file first (Qwen3-TTS doesn't support true streaming yet)
            audio_path = self.engine.speak(text, voice, emotion)

            # Stream the file in chunks
            response = web.StreamResponse(
                status=200,
                headers={
                    "Content-Type": "audio/wav",
                    "X-Voice": voice,
                    "Transfer-Encoding": "chunked"
                }
            )
            await response.prepare(request)

            chunk_size = 8192
            with open(audio_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    await response.write(chunk)
                    await asyncio.sleep(0)  # Yield to event loop

            await response.write_eof()
            return response

        except Exception as e:
            logger.error(f"Stream error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_clone(self, request: web.Request) -> web.Response:
        """Handle voice clone request."""
        await self.init_engine()

        try:
            # Handle multipart form with audio file
            reader = await request.multipart()

            ref_audio_path = None
            name = None
            ref_text = None
            instruct = ""

            async for part in reader:
                if part.name == "audio":
                    # Save uploaded audio
                    audio_dir = Path("~/.cache/temple-voice/uploads").expanduser()
                    audio_dir.mkdir(parents=True, exist_ok=True)

                    filename = part.filename or "ref_audio.wav"
                    ref_audio_path = str(audio_dir / filename)

                    with open(ref_audio_path, "wb") as f:
                        while chunk := await part.read_chunk():
                            f.write(chunk)

                elif part.name == "name":
                    name = (await part.read()).decode()
                elif part.name == "ref_text":
                    ref_text = (await part.read()).decode()
                elif part.name == "instruct":
                    instruct = (await part.read()).decode()

            if not ref_audio_path or not name:
                return web.json_response(
                    {"error": "audio file and name required"},
                    status=400
                )

            logger.info(f"Clone request: name={name}")

            profile = self.engine.clone(ref_audio_path, name, ref_text, instruct)

            return web.json_response({
                "success": True,
                "profile": {
                    "name": profile.name,
                    "type": profile.type,
                    "ref_audio": profile.ref_audio
                }
            })

        except Exception as e:
            logger.error(f"Clone error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_voices(self, request: web.Request) -> web.Response:
        """List available voice profiles."""
        await self.init_engine()

        voices = []
        for name, profile in self.engine.profiles.items():
            voices.append({
                "name": name,
                "type": profile.type,
                "instruct": profile.instruct[:100] + "..." if len(profile.instruct) > 100 else profile.instruct,
                "has_ref_audio": profile.ref_audio is not None
            })

        return web.json_response({"voices": voices})

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "ok",
            "engine_loaded": self.engine is not None,
            "profiles": len(self.engine.profiles) if self.engine else 0
        })

    def create_app(self) -> web.Application:
        """Create the aiohttp application."""
        app = web.Application()

        app.router.add_post("/speak", self.handle_speak)
        app.router.add_post("/speak/stream", self.handle_speak_stream)
        app.router.add_post("/clone", self.handle_clone)
        app.router.add_get("/voices", self.handle_voices)
        app.router.add_get("/health", self.handle_health)

        return app

    def run(self):
        """Run the voice server."""
        if not HAS_AIOHTTP:
            raise RuntimeError("aiohttp required. Run: pip install aiohttp")

        app = self.create_app()
        logger.info(f"Voice server starting on {self.host}:{self.port}")
        web.run_app(app, host=self.host, port=self.port)


def main():
    parser = argparse.ArgumentParser(description="Temple Vault Voice Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8765, help="Port number")
    args = parser.parse_args()

    server = VoiceServer(host=args.host, port=args.port)
    server.run()


if __name__ == "__main__":
    main()
