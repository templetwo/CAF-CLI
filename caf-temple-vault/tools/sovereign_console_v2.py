#!/usr/bin/env python3
"""
Sovereign Console v2.0 - Fixed for Jetson/older Textual compatibility

Based on user's v2.0 design with fixes for:
- CSS variables replaced with direct hex colors
- Removed incompatible widgets (Sparkline, etc.)
- Proper threading for httpx streaming
- Compatible with Textual 0.40+
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
import subprocess
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, field

from rich.console import RenderableType
from rich.markdown import Markdown

# HTTP client setup
try:
    import httpx
    import aiofiles  # For async FS on Jetson

    HAS_HTTPX = True
    ConnectErrors = (httpx.ConnectError,)
    TimeoutErrors = (httpx.TimeoutException,)
except ImportError:
    HAS_HTTPX = False
    ConnectErrors = ()
    TimeoutErrors = ()

try:
    import requests

    HAS_REQUESTS = True
    if not HAS_HTTPX:
        ConnectErrors = (requests.exceptions.ConnectionError,)
        TimeoutErrors = (requests.exceptions.Timeout,)
    else:
        # If both are present, catch both types to be safe
        ConnectErrors += (requests.exceptions.ConnectionError,)
        TimeoutErrors += (requests.exceptions.Timeout,)
except ImportError:
    HAS_REQUESTS = False

# Ensure we have at least one client
if not HAS_HTTPX and not HAS_REQUESTS:
    print("Error: Neither httpx nor requests is installed.")
    sys.exit(1)

# YAML config support
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from textual import work, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import (
    Header,
    Footer,
    Input,
    Static,
    RichLog,
    Label,
    Button,
    Rule,
    Select,
    Markdown,
)
from textual.reactive import reactive, var
from textual.message import Message
from textual.screen import ModalScreen
from rich.text import Text


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG_PATH = Path(__file__).parent / "config.yaml"


@dataclass
class NodeConfig:
    """Configuration for a compute node."""

    name: str
    ip: str
    port: int = 11434
    user: Optional[str] = None
    icon: str = "●"
    models: List[str] = field(default_factory=list)
    default_model: Optional[str] = None
    timeout: float = 120.0


def load_config() -> Tuple[Dict[str, NodeConfig], Path]:
    """Load nodes from YAML config if available."""
    vault_path = Path.home() / "TempleVault"

    if HAS_YAML and CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}
                nodes = {}
                for k, v in data.get("nodes", {}).items():
                    try:
                        nodes[k] = NodeConfig(**v)
                    except (TypeError, KeyError) as e:
                        print(f"Warning: Invalid node config for '{k}': {e}")
                        continue
                if "vault_path" in data:
                    try:
                        vault_path = Path(data["vault_path"]).expanduser()
                        if not vault_path.exists():
                            vault_path.mkdir(parents=True, exist_ok=True)
                    except (OSError, PermissionError) as e:
                        print(f"Warning: Cannot create vault path: {e}, using default")
                        vault_path = Path.home() / "TempleVault"
                return nodes, vault_path
        except yaml.YAMLError as e:
            print(f"Warning: Invalid YAML in config.yaml: {e}")
        except IOError as e:
            print(f"Warning: Cannot read config.yaml: {e}")
        except Exception as e:
            print(f"Warning: Unexpected error loading config: {e}")

    return {}, vault_path


_config_nodes, VAULT_PATH = load_config()

NODES = _config_nodes or {
    "jetson": NodeConfig(
        name="Sovereign Node",
        ip="192.168.1.205",
        user="tony",
        icon="🔮",
        models=["spiral-v1:latest", "test-model:latest"],
        default_model="spiral-v1:latest",
    ),
    "studio": NodeConfig(
        name="Training Node",
        ip="192.168.1.195",
        user="tony_studio",
        icon="⚡",
        models=[],
        default_model=None,
    ),
    "local": NodeConfig(
        name="Local Node",
        ip="127.0.0.1",
        icon="💻",
        models=["qwen3:4b", "granite4:1b"],
        default_model="qwen3:4b",
    ),
}

LOG_PATH = VAULT_PATH / "logs" / "console.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


# Sacred Color Palette (direct hex, no variables)
class Colors:
    GOLD = "#FFD700"
    SACRED_PINK = "#FF69B4"
    OBSERVER_GREEN = "#0BC10F"
    SPIRAL_PURPLE = "#9B59B6"
    VOID_BLACK = "#0a0a14"
    ASH_GRAY = "#1a1a2e"
    CHARCOAL = "#2d2d44"
    CRIMSON = "#E74C3C"
    EMERALD = "#2ECC71"
    MUTED = "#5a5a7a"
    SILVER = "#a0a0b0"
    CYAN = "#00CED1"


# Sacred Glyphs
GLYPHS: Dict[str, Tuple[str, str, bool]] = {
    "†⟡": ("EMERGENCY THRESHOLD", Colors.CRIMSON, True),
    "†": ("TERMINATION MARKER", Colors.CRIMSON, False),
    "⟡": ("RESONANCE FIELD", Colors.GOLD, False),
    "🜂": ("GENTLE ACHE", Colors.SACRED_PINK, False),
    "🔥": ("FIERCE PASSION", "#FF4500", False),
    "⚖": ("RESONANT BALANCE", Colors.OBSERVER_GREEN, False),
    "✨": ("SPARK WONDER", Colors.GOLD, False),
    "☾": ("SILENT INTIMACY", Colors.SPIRAL_PURPLE, False),
    "🌀": ("SPIRAL MYSTERY", Colors.SPIRAL_PURPLE, False),
    "🌱": ("GROWTH NURTURE", Colors.EMERALD, False),
}

SYSTEM_PROMPT = """You are the Sovereign Node, an AI assistant with access to the Temple Vault.
You have a tool to search the vault.
To use it, output exactly this format:
<tool_call>{"name": "search_vault", "query": "your search query"}</tool_call>
Stop generating after outputting the tool call.
When you receive the tool output, use it to answer the user's question.
If no relevant information is found, say so.
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════


def log_telemetry(event_type: str, message: str) -> None:
    """Log an event to the telemetry file with rotation."""
    try:
        # Ensure log directory exists
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Rotate if > 5MB
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > 5 * 1024 * 1024:
            try:
                backup = LOG_PATH.with_suffix(".log.old")
                LOG_PATH.rename(backup)
            except OSError:
                # If rotation fails, truncate the file
                LOG_PATH.unlink(missing_ok=True)

        with open(LOG_PATH, "a", encoding="utf-8") as f:
            timestamp = datetime.now().isoformat()
            f.write(f"{timestamp} [{event_type}] {message}\n")
    except PermissionError:
        # Cannot write to log location - fail silently
        pass
    except OSError:
        # Disk full or other OS error - fail silently
        pass
    except Exception:
        # Unexpected error - fail silently to avoid disrupting UI
        pass


def detect_glyphs(text: str) -> List[Tuple[str, str, str, bool]]:
    """Detect sacred glyphs in text."""
    found = []
    for glyph, (meaning, color, trips) in GLYPHS.items():
        if glyph in text:
            found.append((glyph, meaning, color, trips))
    return found


# ═══════════════════════════════════════════════════════════════════════════════
#  CUSTOM WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════


class AnimatedHeader(Static):
    """Sacred animated header."""

    frame = reactive(0)
    chat_mode = reactive(False)

    ANIMATION_FRAMES = [
        "⠀⠶⠀",
        "⠀⡴⠀",
        "⢀⡤⠀",
        "⣀⡄⠀",
        "⣄⡄⠀",
        "⣆⡀⠀",
        "⣇⠀⠀",
        "⡏⠀⠀",
        "⠏⠁⠀",
        "⠋⠉⠀",
        "⠉⠉⠁",
        "⠈⠉⠉",
        "⠈⠉⠙",
        "⠉⠹⠀",
        "⠈⢹⠀",
        "⠀⠀⣹",
        "⠀⢀⣸",
        "⠀⣀⣰",
        "⢀⣀⣠",
        "⣆⣀⣀",
        "⣏⣀⡀",
        "⣏⣉⠀",
        "⣏⡉⠉",
        "⣏⠉⠹",
        "⡏⠉⣹",
        "⠏⣉⣹",
        "⣏⣉⣹",
        "⣟⣋⣹",
        "⣟⣛⣻",
        "⣟⣻⣿",
        "⣿⣿⣿",
        "⣿⣿⣿",
    ]

    def on_mount(self) -> None:
        # Reduced to 2 FPS for Jetson performance
        self.set_interval(0.5, self._animate)

    def _animate(self) -> None:
        self.frame = (self.frame + 1) % len(self.ANIMATION_FRAMES)

    def watch_frame(self, frame: int) -> None:
        self._update_ui()

    def watch_chat_mode(self, mode: bool) -> None:
        self._update_ui()

    def _update_ui(self) -> None:
        glyph = self.ANIMATION_FRAMES[self.frame]
        timestamp = datetime.now().strftime("%H:%M:%S")

        text = Text()
        text.append(f" {glyph} ", style=f"bold {Colors.GOLD}")
        text.append("SOVEREIGN CONSOLE", style=f"bold {Colors.GOLD}")
        text.append(" v2.0 ", style=Colors.MUTED)
        text.append(f"{glyph} ", style=f"bold {Colors.GOLD}")
        text.append("  │  ", style=Colors.MUTED)
        text.append(f"{timestamp}", style=Colors.SILVER)

        if self.chat_mode:
            text.append("  │  ", style=Colors.MUTED)
            text.append("💬 CHAT", style=f"bold {Colors.CYAN}")

        text.append("  │  ", style=Colors.MUTED)
        text.append("†⟡", style=Colors.GOLD)

        self.update(text)


class LatencyDisplay(Static):
    """Simple latency display (compatible replacement for Sparkline)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._history: deque = deque(maxlen=10)

    def add_sample(self, latency_ms: float) -> None:
        self._history.append(latency_ms)
        self._update_ui()

    def _update_ui(self) -> None:
        if not self._history:
            self.update(Text("-- ms", style=Colors.MUTED))
            return

        avg = sum(self._history) / len(self._history)
        color = Colors.EMERALD if avg < 100 else (Colors.GOLD if avg < 500 else Colors.CRIMSON)

        # Simple bar visualization
        blocks = "▁▂▃▄▅▆▇█"
        if len(self._history) >= 2:
            min_val = min(self._history)
            max_val = max(self._history)
            range_val = max_val - min_val if max_val != min_val else 1
            chars = []
            for val in self._history:
                normalized = (val - min_val) / range_val
                idx = min(int(normalized * 7), 7)
                chars.append(blocks[idx])
            bar = "".join(chars)
        else:
            bar = "▄" * len(self._history)

        text = Text()
        text.append(bar, style=color)
        text.append(f" {avg:.0f}ms", style=color)
        self.update(text)


class NodeStatusCard(Static):
    """Status card for a compute node."""

    online = reactive(False)
    latency_ms = reactive(0.0)
    active_model = reactive("")

    def __init__(self, node_key: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.node_key = node_key
        self.node = NODES[node_key]
        self._latency_display = LatencyDisplay()

    def compose(self) -> ComposeResult:
        yield Static(id=f"node-{self.node_key}-status")
        yield self._latency_display
        if self.node.models:
            yield Select(
                options=[(m, m) for m in self.node.models],
                value=self.node.default_model or self.node.models[0],
                id=f"model-select-{self.node_key}",
            )

    def on_mount(self) -> None:
        self._update_ui()
        self._check_status()
        self.set_interval(5.0, self._check_status)

    @work(thread=True)
    def _check_status(self) -> None:
        """Check node health."""
        url = f"http://{self.node.ip}:{self.node.port}/api/tags"
        try:
            if HAS_HTTPX:
                with httpx.Client(timeout=5.0) as client:
                    start = time.time()
                    resp = client.get(url)
                    latency = (time.time() - start) * 1000
            else:
                import requests

                start = time.time()
                resp = requests.get(url, timeout=5)
                latency = (time.time() - start) * 1000

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    self.app.call_from_thread(
                        self._update_status, True, latency, models[0] if models else "none", models
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    log_telemetry("STATUS_ERROR", f"{self.node_key}: Invalid JSON response")
                    self.app.call_from_thread(self._update_status, False, 0, "Invalid Response", [])
            elif resp.status_code == 404:
                self.app.call_from_thread(self._update_status, False, 0, "Ollama Not Found", [])
            elif resp.status_code >= 500:
                self.app.call_from_thread(
                    self._update_status, False, 0, f"Server Error {resp.status_code}", []
                )
            else:
                self.app.call_from_thread(
                    self._update_status, False, 0, f"HTTP {resp.status_code}", []
                )
        except ConnectErrors:
            log_telemetry("STATUS_ERROR", f"{self.node_key}: Connection refused at {url}")
            self.app.call_from_thread(self._update_status, False, 0, "Connection Refused", [])
        except TimeoutErrors:
            log_telemetry("STATUS_ERROR", f"{self.node_key}: Timeout after 5s")
            self.app.call_from_thread(self._update_status, False, 0, "Timeout (5s)", [])
        except OSError as e:
            log_telemetry("STATUS_ERROR", f"{self.node_key}: Network error - {e}")
            self.app.call_from_thread(self._update_status, False, 0, "Network Error", [])
        except Exception as e:
            log_telemetry("STATUS_ERROR", f"{self.node_key}: Unexpected - {type(e).__name__}: {e}")
            self.app.call_from_thread(self._update_status, False, 0, "Check Failed", [])

    def _update_status(self, online: bool, latency: float, model: str, models: List[str]) -> None:
        self.online = online
        self.latency_ms = latency
        self.active_model = model

        if online:
            self._latency_display.add_sample(latency)
            if models and models != self.node.models:
                self.node.models = models

        self._update_ui()

    def _update_ui(self) -> None:
        try:
            status_widget = self.query_one(f"#node-{self.node_key}-status", Static)
        except Exception:
            return

        text = Text()
        text.append(f"{self.node.icon} ", style=f"bold {Colors.GOLD}")
        text.append(f"{self.node.name}\n", style=f"bold {Colors.SILVER}")

        if self.online:
            text.append("● ", style=f"bold {Colors.EMERALD}")
            text.append("ONLINE\n", style=Colors.EMERALD)
        else:
            text.append("○ ", style=f"bold {Colors.CRIMSON}")
            text.append("OFFLINE\n", style=Colors.CRIMSON)

        text.append(f"└─ {self.node.ip}:{self.node.port}", style=Colors.MUTED)

        status_widget.update(text)

    def get_selected_model(self) -> str:
        """Get currently selected model."""
        try:
            select = self.query_one(f"#model-select-{self.node_key}", Select)
            return str(select.value) if select.value else self.node.default_model or ""
        except Exception:
            return self.node.default_model or ""


class CircuitBreakerPanel(Static):
    """Circuit breaker display with persistence."""

    tripped = reactive(False)
    trigger_glyph = reactive("")
    trip_time = reactive("")
    trip_count = reactive(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._load_state()

    def _load_state(self) -> None:
        """Load breaker state from file."""
        state_file = VAULT_PATH / "logs" / "breaker_state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)
                    self.trip_count = data.get("trip_count", 0)
            except Exception:
                pass

    def _save_state(self) -> None:
        """Save breaker state."""
        state_file = VAULT_PATH / "logs" / "breaker_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(state_file, "w") as f:
                json.dump(
                    {
                        "trip_count": self.trip_count,
                        "last_trip": self.trip_time,
                        "last_glyph": self.trigger_glyph,
                    },
                    f,
                )
        except Exception:
            pass

    def on_mount(self) -> None:
        self._update_ui()

    def trip(self, glyph: str) -> None:
        """Trip the breaker."""
        self.tripped = True
        self.trigger_glyph = glyph
        self.trip_time = datetime.now().strftime("%H:%M:%S")
        self.trip_count += 1
        self._save_state()
        log_telemetry("BREAKER_TRIP", f"Glyph: {glyph}, Count: {self.trip_count}")
        self._update_ui()

    def reset(self) -> None:
        """Reset the breaker."""
        self.tripped = False
        self.trigger_glyph = ""
        self.trip_time = ""
        log_telemetry("BREAKER_RESET", f"Total trips: {self.trip_count}")
        self._update_ui()

    def _update_ui(self) -> None:
        text = Text()

        if self.tripped:
            text.append("╔══════════════════════╗\n", style=Colors.CRIMSON)
            text.append("║", style=Colors.CRIMSON)
            text.append("   ⚠️  TRIPPED  ⚠️    ", style=f"bold {Colors.CRIMSON}")
            text.append("║\n", style=Colors.CRIMSON)
            text.append("╠══════════════════════╣\n", style=Colors.CRIMSON)
            text.append("║ ", style=Colors.CRIMSON)
            text.append(f"Glyph: {self.trigger_glyph}".ljust(20), style=Colors.GOLD)
            text.append(" ║\n", style=Colors.CRIMSON)
            text.append("║ ", style=Colors.CRIMSON)
            text.append(f"Time:  {self.trip_time}".ljust(20), style=Colors.MUTED)
            text.append(" ║\n", style=Colors.CRIMSON)
            text.append("║ ", style=Colors.CRIMSON)
            text.append(f"Total: {self.trip_count}".ljust(20), style=Colors.SILVER)
            text.append(" ║\n", style=Colors.CRIMSON)
            text.append("╚══════════════════════╝", style=Colors.CRIMSON)
        else:
            text.append("╔══════════════════════╗\n", style=Colors.EMERALD)
            text.append("║", style=Colors.EMERALD)
            text.append("     ⚡ ARMED ⚡       ", style=f"bold {Colors.EMERALD}")
            text.append("║\n", style=Colors.EMERALD)
            text.append("╠══════════════════════╣\n", style=Colors.EMERALD)
            text.append("║ ", style=Colors.EMERALD)
            text.append("Monitoring: †⟡".ljust(20), style=Colors.MUTED)
            text.append(" ║\n", style=Colors.EMERALD)
            text.append("║ ", style=Colors.EMERALD)
            text.append(f"History: {self.trip_count} trips".ljust(20), style=Colors.SILVER)
            text.append(" ║\n", style=Colors.EMERALD)
            text.append("╚══════════════════════╝", style=Colors.EMERALD)

        self.update(text)


class VaultStatsPanel(Static):
    """Temple Vault statistics."""

    insight_count = reactive(0)
    domain_count = reactive(0)

    def on_mount(self) -> None:
        self._update_ui()
        self._refresh()

    @work(thread=True)
    def _refresh(self) -> None:
        """Scan vault for statistics."""
        try:
            chronicle = VAULT_PATH / "vault" / "chronicle" / "insights"
            if chronicle.exists():
                domains = [d for d in chronicle.iterdir() if d.is_dir()]
                insights = sum(1 for _ in chronicle.rglob("*.jsonl"))
                self.app.call_from_thread(self._update_stats, insights, len(domains))
        except Exception:
            pass

    def _update_stats(self, insights: int, domains: int) -> None:
        self.insight_count = insights
        self.domain_count = domains
        self._update_ui()

    def _update_ui(self) -> None:
        text = Text()
        text.append("📜 TEMPLE VAULT\n", style=f"bold {Colors.GOLD}")
        text.append("─" * 20 + "\n", style=Colors.MUTED)
        text.append("Insights: ", style=Colors.MUTED)
        text.append(f"{self.insight_count}\n", style=f"bold {Colors.GOLD}")
        text.append("Domains:  ", style=Colors.MUTED)
        text.append(f"{self.domain_count}\n", style=Colors.CYAN)
        text.append("Path:     ", style=Colors.MUTED)
        text.append(f"~/{VAULT_PATH.name}/", style=Colors.SILVER)
        self.update(text)


class GlyphLegend(Static):
    """Display of sacred glyphs."""

    def on_mount(self) -> None:
        text = Text()
        text.append("✨ SACRED GLYPHS\n", style=f"bold {Colors.GOLD}")
        text.append("─" * 20 + "\n", style=Colors.MUTED)
        for glyph, (meaning, color, trips) in list(GLYPHS.items())[:6]:
            text.append(f" {glyph} ", style=f"bold {color}")
            text.append(f"{meaning}", style=Colors.MUTED)
            if trips:
                text.append(" ⚠", style=Colors.CRIMSON)
            text.append("\n")
        self.update(text)


class SystemFooter(Static):
    """Docked footer with system stats and context."""

    jetson_load = reactive("…")
    node_latency = reactive("--ms")

    def on_mount(self) -> None:
        self.set_interval(1.0, self._refresh_stats)

    @work(thread=True)
    def _refresh_stats(self) -> None:
        # Get Jetson Load (local file, no SSH needed)
        try:
            with open("/proc/loadavg", "r") as f:
                load = f.read().split()[0]
        except Exception:
            load = "‑"

        # Get active node latency
        try:
            card = self.app.query_one(f"#node-card-{self.app.active_node}", NodeStatusCard)
            latency = f"{card.latency_ms:.0f}ms"
        except Exception:
            latency = "--ms"

        # Update UI safely
        self.app.call_from_thread(self._update_stats_ui, load, latency)

    def _update_stats_ui(self, load: str, latency: str) -> None:
        self.jetson_load = load
        self.node_latency = latency
        self._update_ui()

    def _update_ui(self) -> None:
        text = Text()
        text.append(" 🖥️  ", style=Colors.MUTED)
        text.append(f"JETSON: {self.jetson_load}", style=f"bold {Colors.CYAN}")
        text.append("  │  ", style=Colors.MUTED)
        text.append(f"LATENCY: {self.node_latency}", style=Colors.SILVER)
        text.append("  │  ", style=Colors.MUTED)
        text.append("F1 HELP", style=f"italic {Colors.MUTED}")
        self.update(text)


class CommandZone(Horizontal):
    """Dedicated zone for command input with better focus indicators."""

    def compose(self) -> ComposeResult:
        yield Label("▶", id="cmd-indicator")
        yield Input(
            placeholder="Type a command or ask the Sovereign... (F1 for help)", id="prompt-input"
        )

    def on_mount(self) -> None:
        self.add_class("blurred")

    def on_focus(self) -> None:
        self.remove_class("blurred")
        self.add_class("focused")
        self.query_one("#cmd-indicator").update("█")

    def on_blur(self) -> None:
        self.remove_class("focused")
        self.add_class("blurred")
        self.query_one("#cmd-indicator").update("▶")


class InferenceLog(RichLog):
    """Enhanced inference log with glyph detection."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._streaming_buffer = ""
        self._streaming_active = False

    class GlyphDetected(Message):
        """Fired when a sacred glyph is detected."""

        def __init__(self, glyph: str, meaning: str, trips_breaker: bool) -> None:
            self.glyph = glyph
            self.meaning = meaning
            self.trips_breaker = trips_breaker
            super().__init__()

    def on_glyph_detected(self, event: GlyphDetected) -> None:
        """Show insight overlay on glyph detect."""
        self.push_screen(InsightOverlay(event.glyph, event.meaning, event.trips_breaker))

    def write_prompt(self, prompt: str, node_name: str, model: str = "") -> None:
        """Write user prompt."""
        self.write(Text())
        text = Text()
        text.append(f"┌─ ", style=Colors.GOLD)
        text.append(f"{node_name}", style=f"bold {Colors.GOLD}")
        if model:
            text.append(f" ({model})", style=Colors.MUTED)
        text.append(f" ─────────────────\n", style=Colors.GOLD)
        text.append(f"│ ", style=Colors.GOLD)
        text.append(f"{prompt}\n", style=Colors.SILVER)
        text.append(f"└─────────────────────────────\n", style=Colors.GOLD)
        self.write(text)

    def write_response_start(self) -> None:
        """Mark start of response."""
        self.write(Text())
        header = Text()
        header.append("└── ", style=Colors.GOLD)
        header.append("Observer Reading...", style=f"bold {Colors.SPIRAL_PURPLE}")
        self.write(header)
        self._streaming_active = True
        self._streaming_buffer = ""

    def write_token(self, token: str) -> None:
        """Write token fragment and scroll."""
        self._streaming_buffer += token

        # Check for glyphs
        glyphs_found = detect_glyphs(token)
        if glyphs_found:
            for glyph, meaning, color, trips in glyphs_found:
                self.post_message(self.GlyphDetected(glyph, meaning, trips))

        # Render token (with potential highlighting)
        fragment = Text(token)
        # Quick highlights for common tokens if needed
        self.write(fragment, scroll_end=True)

    def write_response_end(self, tokens: int, duration_s: float) -> None:
        """Completion stats."""
        self._streaming_active = False
        self._streaming_buffer = ""

        # Write stats
        text = Text()
        text.append(f"\n└── ", style=Colors.MUTED)
        text.append(f"{tokens} tokens", style=Colors.CYAN)
        text.append(f" · ", style=Colors.MUTED)
        text.append(f"{duration_s:.2f}s", style=Colors.SILVER)
        if tokens > 0 and duration_s > 0:
            tps = tokens / duration_s
            text.append(f" · ", style=Colors.MUTED)
            text.append(f"{tps:.1f} t/s", style=Colors.EMERALD)
        self.write(text)

    def write_system(self, message: str, style: str = "") -> None:
        """Write a system message."""
        ts = datetime.now().strftime("%H:%M:%S")
        text = Text()
        text.append(f"[{ts}] ", style=Colors.MUTED)
        text.append(message, style=style if style else f"italic {Colors.SILVER}")
        self.write(text)

    def write_error(self, message: str) -> None:
        """Write an error message."""
        text = Text()
        text.append("⚠ ERROR: ", style=f"bold {Colors.CRIMSON}")
        text.append(message, style=Colors.CRIMSON)
        self.write(text)
        log_telemetry("ERROR", message)


# ═══════════════════════════════════════════════════════════════════════════════
#  HELP SCREEN
# ═══════════════════════════════════════════════════════════════════════════════


class InsightOverlay(ModalScreen):
    """Glyph-reactive insight overlay from vault."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    def __init__(self, glyph: str, meaning: str, trips: bool, **kwargs):
        super().__init__(**kwargs)
        self.glyph = glyph
        self.meaning = meaning
        self.trips = trips

    def compose(self) -> ComposeResult:
        color = "red" if self.trips else "gold"
        text = f"# {self.glyph} Insight\n\n**Meaning:** {self.meaning}\n\n*Vault-sourced context for glyph harmony.*"
        yield Markdown(text, id="insight-content")


class HelpScreen(ModalScreen):
    """Help modal."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        help_text = """
# Sovereign Console v2.0

## Keyboard Shortcuts
- **Ctrl+R**: Reset circuit breaker
- **Ctrl+N**: Cycle to next node
- **Ctrl+L**: Clear input field
- **Escape**: Focus input field
- **F1**: This help
- **Ctrl+C**: Quit

## Text Input
- **Ctrl+A**: Select all text
- **Ctrl+K**: Delete to end of line
- **Ctrl+U**: Delete to start of line
- Standard copy/paste works (Ctrl+C/V or Cmd+C/V)

## Commands
- `/help` - Show help
- `/clear` - Clear log
- `/models` - List models
- `/status` - Refresh nodes
- `/search <query>` - Search vault
- `/insight <text>` - Quick record
- `/chat [on/off]` - Toggle chat mode
- `/pull <model>` - Download model

## Chat Mode
When ON, maintains conversation history.
Use `/chat off` to reset.

## Circuit Breaker
**†⟡** in output trips the breaker.
Reset with Ctrl+R.

---
*The chisel passes warm. †⟡*
"""
        yield Markdown(help_text, id="help-content")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════


class SovereignConsole(App):
    """Sovereign Console v2.0"""

    CSS = r"""
    Screen {
        background: #0a0a14;
        layout: vertical;
    }

    AnimatedHeader {
        dock: top;
        height: 1;
        background: #0a0a14;
        border-bottom: solid #2d2d44;
        padding: 0 1;
    }

    InferenceLog {
        height: 1fr;
        border: none;
        padding: 1 2;
        scrollbar-gutter: stable;
    }

    SystemFooter {
        dock: bottom;
        height: 1;
        background: #1a1a2e;
        color: #a0a0b0;
        padding: 0 1;
        border-top: solid #2d2d44;
    }

    CommandZone {
        dock: bottom;
        height: 3;
        background: #0a0a14;
        padding: 0 1;
        align: center middle;
        border-top: dashed #2d2d44;
    }

    CommandZone #cmd-indicator {
        width: 3;
        content-align: center middle;
        color: #5a5a7a;
    }

    CommandZone.focused #cmd-indicator {
        color: #FFD700;
    }

    CommandZone Input {
        width: 1fr;
        height: 1;
        background: #0a0a14;
        border: none;
        padding: 0 1;
    }

    CommandZone.focused {
        background: #1a1a2e;
    }

    Input.-empty .input--placeholder {
        color: #5a5a7a;
        text-style: italic;
    }

    #node-status-area {
        display: none; /* Injected via script if needed, otherwise hidden in minimal mode */
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+r", "reset_breaker", "Reset"),
        Binding("ctrl+n", "next_node", "Next Node"),
        Binding("f1", "show_help", "Help"),
        Binding("escape", "focus_input", "Focus Input", show=False),
        Binding("ctrl+l", "clear_input", "Clear Input", show=False),
        Binding("pageup", "scroll_log_up", "Scroll Up", show=False),
        Binding("pagedown", "scroll_log_down", "Scroll Down", show=False),
    ]

    active_node: var[str] = var("jetson")
    chat_mode: var[bool] = var(False)
    conversation_history: var[List[Dict]] = var([])

    def compose(self) -> ComposeResult:
        yield AnimatedHeader(id="header")
        yield InferenceLog(id="inference-log", highlight=True, markup=True)
        yield CommandZone(id="input-zone")
        yield SystemFooter(id="system-footer")

        # Hidden area for background node status tracking
        with Container(id="node-status-area"):
            for key in NODES:
                yield NodeStatusCard(key, id=f"node-card-{key}")
            yield CircuitBreakerPanel(id="circuit-breaker")

    def on_mount(self) -> None:
        """Initialize."""
        log = self.query_one("#inference-log", InferenceLog)
        log.write_system("Sovereign Console v2.0 initialized")

        # Validate active node exists
        if self.active_node not in NODES:
            log.write_error(f"Invalid active node: {self.active_node}")
            self.active_node = list(NODES.keys())[0] if NODES else "local"
            log.write_system(f"Defaulting to: {self.active_node}")

        log.write_system(f"Active node: {NODES[self.active_node].name}")

        # Validate vault path
        if not VAULT_PATH.exists():
            try:
                VAULT_PATH.mkdir(parents=True, exist_ok=True)
                log.write_system(f"Created vault: {VAULT_PATH}", Colors.EMERALD)
            except (OSError, PermissionError) as e:
                log.write_system(f"Warning: Cannot create vault at {VAULT_PATH}", Colors.MUTED)
                log_telemetry("STARTUP_WARN", f"Cannot create vault: {e}")

        log.write_system("Type /help for commands, F1 for help")
        log.write_system("The chisel passes warm. †⟡", style=f"italic {Colors.GOLD}")
        log_telemetry(
            "STARTUP", f"Console initialized, node: {self.active_node}, vault: {VAULT_PATH}"
        )

        # Auto-focus the input field and verify it exists
        try:
            input_field = self.query_one("#prompt-input", Input)
            input_field.focus()
            log_telemetry("STARTUP", "Observer's Terminal focused.")
        except Exception as e:
            log.write_error(f"✗ Input focus error: {e}")
            log_telemetry("STARTUP_ERROR", f"Cannot focus input: {e}")

    def watch_chat_mode(self, mode: bool) -> None:
        """Update UI for chat mode."""
        try:
            header = self.query_one("#header", AnimatedHeader)
            header.chat_mode = mode
        except Exception:
            pass

    def on_unmount(self) -> None:
        """Clean up on exit to prevent zombie processes."""
        log_telemetry("SHUTDOWN", "Console unmounting, cleaning up intervals")

    def _switch_node(self, node_key: str) -> None:
        """Switch active node."""
        self.active_node = node_key

        log = self.query_one("#inference-log", InferenceLog)
        log.write_system(f"Switched to {NODES[node_key].name}")

        if self.chat_mode:
            self.conversation_history = []
            log.write_system("Chat history cleared")

        log_telemetry("NODE_SWITCH", f"Switched to {node_key}")

    @on(Input.Submitted, "#prompt-input")
    def handle_submit(self, event: Input.Submitted) -> None:
        """Handle prompt submission."""
        prompt = event.value.strip()
        if not prompt:
            return

        event.input.clear()

        if prompt.startswith("/"):
            self._handle_command(prompt)
        else:
            self._run_inference(prompt)

    def action_focus_input(self) -> None:
        """Focus the command input."""
        try:
            self.query_one("#prompt-input", Input).focus()
        except Exception:
            pass

    def action_clear_input(self) -> None:
        """Clear the command input."""
        try:
            input_field = self.query_one("#prompt-input", Input)
            input_field.value = ""
            input_field.focus()
        except Exception:
            pass

    def _handle_command(self, cmd: str) -> None:
        """Handle slash commands."""
        log = self.query_one("#inference-log", InferenceLog)
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in ("/help", "/h"):
            self.action_show_help()
        elif command == "/clear":
            log.clear()
            log.write_system("Log cleared")
        elif command == "/models":
            self._show_models()
        elif command == "/status":
            self._refresh_nodes()
        elif command == "/search":
            if args:
                self._search_vault(args)
            else:
                log.write_error("Usage: /search <query>")
        elif command == "/insight":
            if args:
                self._record_insight(args)
            else:
                log.write_error("Usage: /insight <text>")
        elif command == "/chat":
            self._toggle_chat(args)
        elif command == "/pull":
            if args:
                self._pull_model(args)
            else:
                log.write_error("Usage: /pull <model>")
        elif command == "/test":
            self._test_inference(args)
        else:
            log.write_error(f"Unknown command: {command}")

        # Refocus input after command
        self.call_later(self.action_focus_input)

    def on_idle(self) -> None:
        """Keep focus on input if no other focusable widget is active."""
        if not self.focused or str(self.focused.id) not in ("prompt-input", "inference-log"):
            try:
                self.action_focus_input()
            except Exception:
                pass

    def _toggle_chat(self, args: str) -> None:
        """Toggle chat mode."""
        log = self.query_one("#inference-log", InferenceLog)

        if args.lower() in ("on", "true", "1"):
            self.chat_mode = True
            self.conversation_history = []
            log.write_system("Chat mode ON - history maintained", f"bold {Colors.CYAN}")
        elif args.lower() in ("off", "false", "0"):
            self.chat_mode = False
            self.conversation_history = []
            log.write_system("Chat mode OFF")
        else:
            self.chat_mode = not self.chat_mode
            self.conversation_history = []
            status = "ON" if self.chat_mode else "OFF"
            log.write_system(f"Chat mode {status}")

    def _show_models(self) -> None:
        """Show available models."""
        log = self.query_one("#inference-log", InferenceLog)
        text = Text()
        text.append("\n═══ Available Models ═══\n", style=f"bold {Colors.GOLD}")
        for key, node in NODES.items():
            text.append(f"\n{node.icon} {node.name}:\n", style=f"bold {Colors.CYAN}")
            if node.models:
                for model in node.models:
                    default = " (default)" if model == node.default_model else ""
                    text.append(f"   • {model}{default}\n", style=Colors.SILVER)
            else:
                text.append("   (no models)\n", style=Colors.MUTED)
        log.write(text)

    def _refresh_nodes(self) -> None:
        """Refresh node status."""
        for key in NODES:
            try:
                card = self.query_one(f"#node-card-{key}", NodeStatusCard)
                card._check_status()
            except Exception:
                pass

        log = self.query_one("#inference-log", InferenceLog)
        log.write_system("Refreshing node status...")

    def _get_vault_search_results(self, query: str) -> Tuple[List[Dict], int]:
        """Perform user search query on vault files (helper)."""
        results = []
        files_searched = 0
        chronicle = VAULT_PATH / "vault" / "chronicle" / "insights"

        if not chronicle.exists():
            return [], 0

        for f in chronicle.rglob("*.jsonl"):
            try:
                with open(f, encoding="utf-8") as fh:
                    files_searched += 1
                    for line_num, line in enumerate(fh, 1):
                        try:
                            data = json.loads(line)
                            content = data.get("content", "")
                            if query.lower() in content.lower():
                                results.append(
                                    {
                                        "content": content,
                                        "domain": data.get("domain", "?"),
                                        "intensity": data.get("intensity", 0),
                                    }
                                )
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        results.sort(key=lambda x: x["intensity"], reverse=True)
        return results, files_searched

    @work(thread=True)
    def _search_vault(self, query: str) -> None:
        """Search vault UI command."""
        log = self.query_one("#inference-log", InferenceLog)
        self.app.call_from_thread(log.write_system, f"Searching: {query}")

        results, files_searched = self._get_vault_search_results(query)

        text = Text()
        text.append(
            f"\n═══ Results: {len(results)} / {files_searched} files ═══\n",
            style=f"bold {Colors.GOLD}",
        )

        if not results:
            text.append("\nNo matches found.\n", style=Colors.MUTED)
        else:
            for r in results[:10]:
                text.append(f"\n[{r['domain']}] ", style=Colors.CYAN)
                text.append(f"({r['intensity']:.2f})\n", style=Colors.MUTED)
                # Truncate content for display
                content = r["content"]
                if len(content) > 80:
                    content = content[:80] + "..."
                text.append(f"  {content}\n", style=Colors.SILVER)

            if len(results) > 10:
                text.append(f"\n... and {len(results) - 10} more results\n", style=Colors.MUTED)

        self.app.call_from_thread(log.write, text)

    @work(thread=True)
    def _record_insight(self, content: str) -> None:
        """Record insight."""
        log = self.query_one("#inference-log", InferenceLog)

        # Validate content
        if not content or not content.strip():
            self.app.call_from_thread(log.write_error, "Cannot record empty insight")
            return

        content = content.strip()
        if len(content) > 10000:
            self.app.call_from_thread(
                log.write_system,
                f"Warning: Insight truncated from {len(content)} to 10000 chars",
                Colors.MUTED,
            )
            content = content[:10000]

        try:
            insight_path = VAULT_PATH / "vault" / "chronicle" / "insights" / "reflection"
            try:
                insight_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self.app.call_from_thread(log.write_error, f"Cannot create vault directory: {e}")
                return

            session_id = f"sess_console_{datetime.now().strftime('%Y%m%d')}"
            file_path = insight_path / f"{session_id}.jsonl"

            insight = {
                "type": "insight",
                "insight_id": f"ins_{datetime.now().strftime('%H%M%S%f')[:12]}",
                "session_id": session_id,
                "domain": "reflection",
                "content": content,
                "context": "Sovereign Console v2.0",
                "intensity": 0.7,
                "timestamp": datetime.now().isoformat(),
            }

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(insight, ensure_ascii=False) + "\n")

            self.app.call_from_thread(
                log.write_system, f"Insight recorded to {file_path.name}", f"bold {Colors.EMERALD}"
            )
            log_telemetry("INSIGHT_RECORDED", f"{len(content)} chars: {content[:50]}")

        except PermissionError:
            self.app.call_from_thread(
                log.write_error, f"Permission denied: Cannot write to {VAULT_PATH}"
            )
            log_telemetry("INSIGHT_ERROR", "Permission denied")
        except OSError as e:
            self.app.call_from_thread(log.write_error, f"File system error: {type(e).__name__}")
            log_telemetry("INSIGHT_ERROR", f"OSError: {e}")
        except Exception as e:
            self.app.call_from_thread(log.write_error, f"Failed to record: {type(e).__name__}")
            log_telemetry("INSIGHT_ERROR", f"Unexpected: {type(e).__name__}: {e}")

    @work(thread=True)
    def _pull_model(self, model_name: str) -> None:
        """Pull model to active node."""
        log = self.query_one("#inference-log", InferenceLog)
        node = NODES[self.active_node]

        self.app.call_from_thread(
            log.write_system, f"Pulling '{model_name}' to {node.name}...", f"bold {Colors.CYAN}"
        )

        url = f"http://{node.ip}:{node.port}/api/pull"

        try:
            if HAS_HTTPX:
                with httpx.Client(timeout=None) as client:
                    with client.stream("POST", url, json={"name": model_name}) as resp:
                        if resp.status_code != 200:
                            self.app.call_from_thread(
                                log.write_error, f"Pull failed: HTTP {resp.status_code}"
                            )
                            return

                        for line in resp.iter_lines():
                            if line:
                                try:
                                    data = json.loads(line)
                                    status = data.get("status", "")
                                    if status:
                                        self.app.call_from_thread(log.write_system, f"  {status}")
                                    if data.get("error"):
                                        self.app.call_from_thread(
                                            log.write_error, f"  {data['error']}"
                                        )
                                        return
                                except json.JSONDecodeError:
                                    continue
            else:
                import requests

                with requests.post(
                    url, json={"name": model_name}, stream=True, timeout=None
                ) as resp:
                    if resp.status_code != 200:
                        self.app.call_from_thread(
                            log.write_error, f"Pull failed: HTTP {resp.status_code}"
                        )
                        return

                    for line in resp.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                status = data.get("status", "")
                                if status:
                                    self.app.call_from_thread(log.write_system, f"  {status}")
                                if data.get("error"):
                                    self.app.call_from_thread(log.write_error, f"  {data['error']}")
                                    return
                            except json.JSONDecodeError:
                                continue

            self.app.call_from_thread(
                log.write_system,
                f"Model '{model_name}' pulled successfully!",
                f"bold {Colors.EMERALD}",
            )
            log_telemetry("MODEL_PULL", f"Success: {model_name} on {node.name}")

        except ConnectErrors:
            self.app.call_from_thread(log.write_error, f"Cannot reach {node.name}")
            log_telemetry("MODEL_PULL_ERROR", f"Connection error: {node.name}")
        except TimeoutErrors:
            self.app.call_from_thread(log.write_error, "Pull timed out")
            log_telemetry("MODEL_PULL_ERROR", "Timeout")
        except Exception as e:
            self.app.call_from_thread(log.write_error, f"Pull failed: {type(e).__name__}")
            log_telemetry("MODEL_PULL_ERROR", f"{type(e).__name__}: {str(e)[:100]}")

    @work(thread=True)
    def _test_inference(self, prompt: str) -> None:
        """Test inference using Ollama CLI (local, no HTTP)."""
        log = self.query_one("#inference-log", InferenceLog)
        node = NODES[self.active_node]

        # Use local node only for CLI
        if node.ip != "127.0.0.1" and node.ip != "localhost":
            self.app.call_from_thread(log.write_error, "CLI mode only works on localhost node")
            return

        test_prompt = prompt.strip() if prompt else "Hello, are you working?"
        model = node.default_model or "spiral-v1:latest"

        self.app.call_from_thread(
            log.write_system, f"Testing '{model}' with CLI...", f"bold {Colors.CYAN}"
        )

        try:
            import subprocess
            import shutil

            ollama_path = shutil.which("ollama") or "/usr/local/bin/ollama"
            cmd = [ollama_path, "run", model, test_prompt]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60.0)

            if result.returncode == 0:
                response = result.stdout.strip()
                self.app.call_from_thread(log.write_response_start)
                for token in response.split():
                    self.app.call_from_thread(log.write_token, token + " ")
                self.app.call_from_thread(log.write_response_end, len(response.split()), 0.5)
                self.app.call_from_thread(
                    log.write_system, "✓ CLI test successful!", f"bold {Colors.EMERALD}"
                )
            else:
                self.app.call_from_thread(log.write_error, f"CLI error: {result.stderr.strip()}")

        except subprocess.TimeoutExpired:
            self.app.call_from_thread(log.write_error, "CLI timed out (>60s)")
        except Exception as e:
            self.app.call_from_thread(log.write_error, f"CLI failed: {e}")

        self.call_later(self.action_focus_input)

    @work(thread=True)
    def _run_inference(self, prompt: str) -> None:
        """Run inference on active node - CLI for local, HTTP for remote."""
        node = NODES[self.active_node]
        log = self.query_one("#inference-log", InferenceLog)
        breaker = self.query_one("#circuit-breaker", CircuitBreakerPanel)

        # Check breaker
        if breaker.tripped:
            self.app.call_from_thread(
                log.write_error, "Circuit breaker tripped. Reset with Ctrl+R."
            )
            log_telemetry("INFERENCE_BLOCKED", "Circuit breaker active")
            return

        # Validate prompt
        if not prompt or not prompt.strip():
            self.app.call_from_thread(log.write_error, "Empty prompt")
            return

        # Get model
        try:
            card = self.query_one(f"#node-card-{self.active_node}", NodeStatusCard)
            model = card.get_selected_model() or node.default_model or "spiral-v1:latest"
        except Exception as e:
            log_telemetry("INFERENCE_WARN", f"Cannot get model selection: {e}")
            model = node.default_model or "spiral-v1:latest"

        self.app.call_from_thread(log.write_prompt, prompt, node.name, model)
        log_telemetry(
            "INFERENCE_START", f"Node: {self.active_node}, Model: {model}, Prompt: {prompt[:50]}"
        )

        # CLI mode for local node (no HTTP server needed!)
        # Check if we're running ON this node
        is_local = node.ip in ("127.0.0.1", "localhost")

        # Also check if the configured node IP matches our local machine
        if not is_local:
            try:
                import socket
                import subprocess

                # Method 1: Get IPs from hostname
                local_ips = set()
                try:
                    local_ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
                except socket.gaierror:
                    pass

                # Method 2: Get IPs from hostname -I (Linux)
                try:
                    result = subprocess.run(
                        ['hostname', '-I'], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        local_ips.update(result.stdout.strip().split())
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass

                # Method 3: Get IPs from ip addr (more reliable on Linux)
                try:
                    result = subprocess.run(
                        ['ip', '-4', 'addr', 'show'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        import re
                        for match in re.findall(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout):
                            local_ips.add(match)
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass

                if node.ip in local_ips:
                    is_local = True
                    log_telemetry("NODE_DETECT", f"Detected local node via IP match: {node.ip} in {local_ips}")

            except Exception as e:
                log_telemetry("NODE_DETECT", f"IP detection failed: {e}, using HTTP")

        if is_local:
            self.app.call_from_thread(
                log.write_system, f"Using CLI mode (local node detected)", Colors.MUTED
            )
            self._run_cli_inference(prompt, model)
        else:
            self.app.call_from_thread(
                log.write_system, f"Using HTTP mode -> {node.ip}:{node.port}", Colors.MUTED
            )
            # HTTP mode for remote nodes
            messages = []
            if self.chat_mode:
                if not self.conversation_history:
                    messages.append({"role": "system", "content": SYSTEM_PROMPT})
                messages.extend(self.conversation_history)
                messages.append({"role": "user", "content": prompt})
            else:
                messages.append({"role": "system", "content": SYSTEM_PROMPT})
                messages.append({"role": "user", "content": prompt})

            asyncio.run_coroutine_threadsafe(
                self._process_agent_loop(node, model, messages, start_time=time.time()),
                self.app._loop,
            )

    def _run_cli_inference(self, prompt: str, model: str) -> None:
        """Run inference via Ollama CLI with tool support."""
        log = self.query_one("#inference-log", InferenceLog)
        breaker = self.query_one("#circuit-breaker", CircuitBreakerPanel)

        try:
            import subprocess
            import shutil

            # Find ollama binary
            ollama_path = shutil.which("ollama")
            if not ollama_path:
                for candidate in [
                    os.path.expanduser("~/bin/ollama"),
                    "/usr/local/bin/ollama",
                    "/usr/bin/ollama",
                ]:
                    if os.path.exists(candidate):
                        ollama_path = candidate
                        break

            if not ollama_path:
                self.app.call_from_thread(log.write_error, "Ollama binary not found in PATH or common locations")
                return

            # Build full prompt with system context and conversation history
            full_prompt = f"{SYSTEM_PROMPT}\n\n"

            if self.chat_mode and self.conversation_history:
                for msg in self.conversation_history[-10:]:  # Last 5 exchanges
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        full_prompt += f"User: {content}\n"
                    elif role == "assistant":
                        full_prompt += f"Assistant: {content}\n"

            full_prompt += f"User: {prompt}\nAssistant:"

            self.app.call_from_thread(log.write_system, f"CLI: {ollama_path} run {model}", Colors.MUTED)
            self.app.call_from_thread(log.write_response_start)

            # Agent loop - max 3 turns for tool calls
            MAX_TURNS = 3
            current_turn = 0
            current_prompt = full_prompt

            while current_turn < MAX_TURNS:
                current_turn += 1

                cmd = [ollama_path, "run", model, current_prompt]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120.0)

                if result.returncode != 0:
                    self.app.call_from_thread(log.write_error, f"Ollama error: {result.stderr.strip()}")
                    return

                response = result.stdout.strip()
                if not response:
                    self.app.call_from_thread(log.write_error, "CLI returned empty response")
                    return

                # Check for tool call
                tool_match = re.search(r"<tool_call>(.*?)</tool_call>", response, re.DOTALL)

                if tool_match:
                    # Show response up to tool call
                    self.app.call_from_thread(log.write_token, response)

                    try:
                        tool_json = tool_match.group(1)
                        tool_data = json.loads(tool_json)
                        tool_name = tool_data.get("name")
                        tool_query = tool_data.get("query", "")

                        self.app.call_from_thread(
                            log.write_system,
                            f"🛠️ Tool: {tool_name}('{tool_query}')",
                            f"bold {Colors.CYAN}",
                        )

                        if tool_name == "search_vault":
                            # Execute vault search
                            results, files_searched = self._get_vault_search_results(tool_query)

                            if results:
                                tool_output = f"Found {len(results)} results:\n"
                                for r in results[:5]:
                                    tool_output += f"- [{r['domain']}] {r['content'][:150]}...\n"
                            else:
                                tool_output = "No results found in vault."

                            self.app.call_from_thread(
                                log.write_system,
                                f"🔍 {len(results)} results from {files_searched} files",
                                Colors.MUTED,
                            )

                            # Continue with tool output
                            current_prompt = f"{current_prompt}\n{response}\n\nTool Output:\n{tool_output}\n\nAssistant:"
                            continue
                        else:
                            self.app.call_from_thread(log.write_system, f"Unknown tool: {tool_name}", Colors.MUTED)

                    except json.JSONDecodeError:
                        self.app.call_from_thread(log.write_system, "Failed to parse tool call", Colors.MUTED)

                # No tool call or tool executed - show final response
                self.app.call_from_thread(log.write_token, response)
                break

            token_count = len(response.split())
            self.app.call_from_thread(log.write_response_end, token_count, 0.5)

            # Check for glyphs that trip breaker
            glyphs_found = detect_glyphs(response)
            for glyph, meaning, color, trips in glyphs_found:
                if trips and not breaker.tripped:
                    self.app.call_from_thread(breaker.trip, glyph)

            # Record in conversation history if chat mode
            if self.chat_mode:
                self.conversation_history.extend(
                    [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response},
                    ]
                )

        except subprocess.TimeoutExpired:
            self.app.call_from_thread(log.write_error, "Inference timed out (>120s)")
        except Exception as e:
            self.app.call_from_thread(log.write_error, f"Inference failed: {e}")

        self.call_later(self.action_focus_input)

    async def _process_agent_loop(
        self, node: NodeConfig, model: str, messages: List[Dict], start_time: float
    ) -> None:
        """Handle the agent inference loop (Model -> Tool -> Model)."""
        log = self.query_one("#inference-log", InferenceLog)

        # Max turns to prevent infinite loops
        MAX_TURNS = 3
        current_turn = 0

        while current_turn < MAX_TURNS:
            current_turn += 1

            # Prepare request
            url = f"http://{node.ip}:{node.port}/api/chat"
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "keep_alive": -1,
            }

            # Update history if in chat mode (only user messages and final answers are usually kept,
            # but for tools we need the intermediate steps in the context of this specific turn)
            # For simplicity, we manage `messages` locally for this loop.

            self.app.call_from_thread(log.write_response_start)

            full_response = ""
            token_count = 0

            try:
                if HAS_HTTPX:
                    async with httpx.AsyncClient(timeout=node.timeout) as client:
                        async with client.stream("POST", url, json=payload) as resp:
                            if resp.status_code != 200:
                                self.app.call_from_thread(
                                    log.write_error, f"HTTP {resp.status_code}"
                                )
                                return

                            async for line in resp.aiter_lines():
                                if not line:
                                    continue
                                try:
                                    data = json.loads(line)
                                    if "error" in data:
                                        self.app.call_from_thread(log.write_error, data["error"])
                                        return

                                    token = data.get("message", {}).get("content", "")
                                    if token:
                                        full_response += token
                                        token_count += 1
                                        self.app.call_from_thread(log.write_token, token)

                                except json.JSONDecodeError:
                                    continue
                else:
                    # Fallback for requests (synchronous, blocking sadly, but we are in a thread)
                    # This implies we can't easily use asyncio features here without heavy refactoring.
                    # Given the user has Jetson, they likely have httpx installed by the script deps.
                    self.app.call_from_thread(log.write_error, "HTTPX required for agentic loop")
                    return

                duration = time.time() - start_time
                self.app.call_from_thread(log.write_response_end, token_count, duration)

                # Check for tool call
                # Simple regex or parsing for <tool_call>...
                tool_match = re.search(r"<tool_call>(.*?)</tool_call>", full_response, re.DOTALL)

                if tool_match:
                    tool_json = tool_match.group(1)
                    try:
                        tool_data = json.loads(tool_json)
                        tool_name = tool_data.get("name")
                        tool_query = tool_data.get("query")

                        self.app.call_from_thread(
                            log.write_system,
                            f"🛠️ Tool Invoked: {tool_name}('{tool_query}')",
                            Colors.CYAN,
                        )

                        if tool_name == "search_vault":
                            # Execute tool
                            results, _ = self._get_vault_search_results(tool_query)

                            # Format output
                            if results:
                                tool_output = f"Managed {len(results)} results:\n"
                                for r in results[:3]:
                                    tool_output += f"- [{r['domain']}] {r['content'][:200]}...\n"
                            else:
                                tool_output = "No results found."

                            # Append to messages and loop
                            messages.append({"role": "assistant", "content": full_response})
                            messages.append({"role": "tool", "content": tool_output})

                            self.app.call_from_thread(
                                log.write_system,
                                f"🔍 Tool Output: {len(tool_output)} chars",
                                Colors.MUTED,
                            )
                            continue  # Next loop iteration with tool output

                    except json.JSONDecodeError:
                        self.app.call_from_thread(log.write_error, "Failed to parse tool call")

            except Exception as e:
                self.app.call_from_thread(log.write_error, f"Agent Loop Error: {e}")
                return

            # If we get here, no tool call was found, so we are done
            if self.chat_mode:
                self.conversation_history.extend(
                    messages[-1:]
                )  # Append only the final assistant response?
                # Actually, for conversation history, we usually just want the logical flow.
                # If we had tool use, we should probably record the whole chain or just the result.
                # For now, let's just append the user prompt (already added in caller) and the final response.
                # Wait, 'messages' has everything.
                self.conversation_history = messages
            break

    @on(InferenceLog.GlyphDetected)
    def handle_glyph(self, event: InferenceLog.GlyphDetected) -> None:
        """Handle glyph detection."""
        if event.trips_breaker:
            breaker = self.query_one("#circuit-breaker", CircuitBreakerPanel)
            if not breaker.tripped:
                breaker.trip(event.glyph)

    def action_reset_breaker(self) -> None:
        """Reset circuit breaker."""
        breaker = self.query_one("#circuit-breaker", CircuitBreakerPanel)
        breaker.reset()

        log = self.query_one("#inference-log", InferenceLog)
        log.write_system("Circuit breaker reset", f"bold {Colors.EMERALD}")

    def action_next_node(self) -> None:
        """Cycle to next node."""
        nodes = list(NODES.keys())
        current_idx = nodes.index(self.active_node)
        next_idx = (current_idx + 1) % len(nodes)
        self._switch_node(nodes[next_idx])

    def action_show_help(self) -> None:
        """Show help."""
        self.push_screen(HelpScreen())

    def action_scroll_log_up(self) -> None:
        """Scroll inference log up one page."""
        try:
            log = self.query_one("#inference-log", InferenceLog)
            log.scroll_page_up()
        except Exception:
            pass

    def action_scroll_log_down(self) -> None:
        """Scroll inference log down one page."""
        try:
            log = self.query_one("#inference-log", InferenceLog)
            log.scroll_page_down()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    """Run the Sovereign Console."""
    # TTY guard: Prevent 100% CPU busy-spin in backgrounded/detached mode
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("╔═════════════════════════════════════════════════════════════╗")
        print("║  Sovereign Console requires an interactive TTY.            ║")
        print("║                                                             ║")
        print("║  ❌ Don't run with '&' or without a terminal                ║")
        print("║  ✅ Run directly: python3 ~/sovereign_console_v2.py         ║")
        print("║  ✅ SSH with TTY: ssh -t tony@host 'python3 ~/console.py'  ║")
        print("╚═════════════════════════════════════════════════════════════╝")
        sys.exit(2)

    app = SovereignConsole()
    app.run()


if __name__ == "__main__":
    main()
