#!/usr/bin/env python3
"""
Minimal test to prove Input widget works on Jetson.
If this works, we know the issue is in the complex layout.
"""

from textual.app import App, ComposeResult
from textual.widgets import Input, Static, Footer
from textual.containers import Vertical

class MinimalTest(App):
    """Bare minimum TUI with just an input field."""

    CSS = """
    Screen {
        background: #0a0a14;
    }

    #test-label {
        height: auto;
        padding: 1;
        background: #1a1a2e;
        color: #FFD700;
        text-align: center;
    }

    #test-input {
        height: 3;
        margin: 1;
        padding: 0 1;
        background: #2d2d44;
        color: #FFFFFF;
        border: heavy #FFD700;
    }

    #test-input:focus {
        border: heavy #00FF00;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("🔮 MINIMAL INPUT TEST - Type below and press Enter", id="test-label")
        yield Input(placeholder="Type here...", id="test-input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#test-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        label = self.query_one("#test-label", Static)
        label.update(f"✅ You typed: '{event.value}'")
        event.input.clear()

if __name__ == "__main__":
    app = MinimalTest()
    app.run()
