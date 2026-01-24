from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Input, Button, Label, Log, Static, Digits
from textual.message import Message
from textual import work
from rich.text import Text
from rich.json import JSON
import httpx
import json
import asyncio
from datetime import datetime

# --- Configuration ---
OLLAMA_ENDPOINT = "http://192.168.1.205:11434"
MODEL_NAME = "spiral-v1"

class ChatMessage(Static):
    """A widget to display a single chat message."""
    def __init__(self, role, content, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content_text = content
        self._content_widget = None

    def compose(self) -> ComposeResult:
        role_color = "green" if self.role == "user" else "cyan"
        role_icon = "👤" if self.role == "user" else "🌀"

        yield Label(f"{role_icon} [{role_color}]{self.role.upper()}[/]", classes="role_label")
        self._content_widget = Static(self.content_text, classes="message_content")
        yield self._content_widget

    def update_content(self, new_text: str):
        """Update the message content for streaming."""
        self.content_text = new_text
        if self._content_widget:
            # Highlight glyphs
            text = Text(new_text)
            text.highlight_regex(r"†⟡", "bold red reverse blink")
            text.highlight_regex(r"†", "bold yellow")
            self._content_widget.update(text)

class SovereignConsole(App):
    CSS = """
    Screen {
        background: #111;
        layout: horizontal;
    }

    #left-pane {
        width: 70%;
        height: 100%;
        border-right: vkey gold;
        layout: vertical;
    }

    #right-pane {
        width: 30%;
        height: 100%;
        layout: vertical;
        background: #222;
    }

    #chat-scroll {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }

    #input-area {
        height: auto;
        border-top: solid gold;
        padding: 1;
        background: #111;
    }

    ChatMessage {
        margin-bottom: 1;
        background: #222;
        padding: 1;
    }
    
    .message_content {
        padding-left: 2;
    }

    #status-bar {
        height: auto;
        padding: 1;
        border-bottom: solid gold;
        background: #333;
    }

    .status-item {
        margin-bottom: 1;
    }

    #telemetry-log {
        height: 1fr;
        border-top: solid gold;
        background: #000;
        color: #0f0;
    }

    .circuit-open {
        color: red;
        text-style: bold;
    }
    
    .circuit-closed {
        color: green;
        text-style: bold;
    }

    """

    TITLE = "TEMPLE VAULT // SOVEREIGN CONSOLE"
    SUB_TITLE = "Connected to: Jetson Orin (spiral-v1)"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Horizontal():
            # LEFT: Chat Interface
            with Container(id="left-pane"):
                with Vertical(id="chat-scroll"):
                    yield Static("✨ [bold cyan]Spiral Observer[/] online. Waiting for input...", id="welcome-msg")
                with Container(id="input-area"):
                    yield Input(placeholder="Transmit query to Sovereign Node...", id="chat-input")

            # RIGHT: Telemetry & Logs
            with Container(id="right-pane"):
                with Container(id="status-bar"):
                    yield Label("📡 CONNECTION: CHECKING...", id="status-conn")
                    yield Label("🧠 MODEL: " + MODEL_NAME)
                    yield Label("🛡️ CIRCUIT BREAKER: SECURE", id="status-circuit", classes="circuit-closed")
                    yield Digits("000 ms", id="latency-meter")
                
                yield Label("🔍 NEURAL TELEMETRY", classes="panel-header")
                yield Log(id="telemetry-log", highlight=True)

        yield Footer()

    def on_mount(self):
        """Start background tasks."""
        self.check_connection()
        self.set_interval(5.0, self.check_connection)
        self.query_one("#chat-input").focus()

    @work(exclusive=True)
    async def check_connection(self):
        """Ping the Ollama endpoint."""
        conn_label = self.query_one("#status-conn")
        latency_digits = self.query_one("#latency-meter")
        
        start = asyncio.get_event_loop().time()
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(OLLAMA_ENDPOINT)
                end = asyncio.get_event_loop().time()
                
                if response.status_code == 200:
                    conn_label.update("📡 CONNECTION: [green]ONLINE[/]")
                    latency = (end - start) * 1000
                    latency_digits.update(f"{latency:.0f} ms")
                else:
                    conn_label.update(f"📡 CONNECTION: [red]ERR {response.status_code}[/]")
        except Exception:
            conn_label.update("📡 CONNECTION: [red]OFFLINE[/]")
            latency_digits.update("--- ms")

    async def on_input_submitted(self, event: Input.Submitted):
        """Handle user message."""
        input_widget = event.input
        user_text = input_widget.value.strip()
        
        if not user_text:
            return

        input_widget.value = ""
        chat_scroll = self.query_one("#chat-scroll")
        
        # Add User Message
        chat_scroll.mount(ChatMessage("user", user_text))
        chat_scroll.scroll_end()
        
        # Log to telemetry
        self.log_telemetry("📤", "PROMPT", user_text)
        
        # Trigger Inference
        self.run_inference(user_text)

    @work
    async def run_inference(self, prompt: str):
        chat_scroll = self.query_one("#chat-scroll")
        log_widget = self.query_one("#telemetry-log")
        circuit_label = self.query_one("#status-circuit")
        
        # Placeholder for streaming response
        response_widget = ChatMessage("assistant", "")
        await chat_scroll.mount(response_widget)
        
        full_response = ""
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": 0.7,
                        "num_gpu": 99
                    }
                }
                
                self.log_telemetry("🔄", "INFERENCE_INIT", f"Payload size: {len(str(payload))} bytes")

                async with client.stream("POST", f"{OLLAMA_ENDPOINT}/api/generate", json=payload) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                chunk = data["response"]
                                full_response += chunk
                                
                                # Update UI
                                response_widget.update_content(full_response)
                                chat_scroll.scroll_end()
                                
                                # Circuit Breaker Check
                                if "†⟡" in full_response:
                                    circuit_label.update("🛡️ CIRCUIT BREAKER: TRIPPED")
                                    circuit_label.remove_class("circuit-closed")
                                    circuit_label.add_class("circuit-open")
                                    self.log_telemetry("🚨", "BREAKER", "Witness Glyph Detected! Halting visual stream.")
                                    # In a real app we might actually abort the request here
                                    
                        except json.JSONDecodeError:
                            continue
                            
                    if "done" in data and data["done"]:
                        self.log_telemetry("✅", "COMPLETE", f"Tokens: {data.get('eval_count', '?')} | Duration: {data.get('total_duration', 0)//1000000}ms")

        except Exception as e:
            response_widget.content_text = f"[bold red]Error:[/n] {str(e)}"
            self.log_telemetry("❌", "ERROR", str(e))

    def log_telemetry(self, icon, event_type, details):
        log_widget = self.query_one("#telemetry-log")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color coding
        color = "white"
        if event_type == "PROMPT": color = "cyan"
        elif event_type == "INFERENCE_INIT": color = "yellow"
        elif event_type == "COMPLETE": color = "green"
        elif event_type == "ERROR": color = "red"
        elif event_type == "BREAKER": color = "bold red reverse"

        msg = f"[{timestamp}] {icon} [{color}]{event_type}:[/] {details}"
        log_widget.write(msg)

if __name__ == "__main__":
    app = SovereignConsole()
    app.run()
