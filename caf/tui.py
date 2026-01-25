#!/usr/bin/env python3
"""
CAF TUI Dashboard - The "Observer's Terminal"
Vertical Stack Layout: Header -> Infinite Log -> Footer

Design:
[ HEADER: Identity | Turn | Latency ]
[                                   ]
[       INFERENCE LOG STREAM        ]
[       (Actions + Output)          ]
[                                   ]
[ FOOTER: Status | Input > ________ ]
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.text import Text
from rich.console import RenderableType
from rich.align import Align

from textual import work, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, Container
from textual.widgets import (
    Input,
    Static,
    RichLog,
    Label,
)
from textual.reactive import reactive, var
from textual.screen import ModalScreen

# Import CAF components
sys.path.insert(0, str(Path(__file__).parent.parent))
from caf.agent import CAFAgent

# ═══════════════════════════════════════════════════════════════════════════════
#  THEME ALIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    GOLD = "#FFD700"          # Awareness / Focus
    OBSERVER = "#0BC10F"      # Success / Stable
    CRIMSON = "#FF2D55"       # Error / Alert
    VOID = "#050510"          # Background
    PANEL = "#12121A"         # Panel BG
    BORDER = "#2A2A35"        # Borders
    TEXT_MAIN = "#E0E0E0"     # Primary Text
    TEXT_DIM = "#505060"      # Dimmed Text
    ACCENT = "#9D00FF"        # Spiritual/Cyberpunk Accent
    CYAN = "#00F0FF"          # Action / Tech

# ═══════════════════════════════════════════════════════════════════════════════
#  COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

class ObserverHeader(Static):
    """
    Docked Top Header.
    Displays: Identity, Turn Count, Latency (Simulated), Node Status.
    """
    turn = reactive(0)
    max_turns = reactive(15)
    model_name = reactive("initializing...")
    latency = reactive(0.0)
    
    def on_mount(self) -> None:
        self.set_interval(0.1, self._refresh_ui)
        self.start_time = time.time()

    def _refresh_ui(self) -> None:
        # Simulate slight latency/noise for alive feel
        ms = int((time.time() - self.start_time) * 1000) % 999
        
        text = Text()
        # Left: Identity
        text.append(" ⟡ CAF OBSERVER TERMINAL ", style=f"bold {Colors.GOLD} reverse")
        text.append(" ", style="reset")
        
        # Center: Agent Info
        text.append(f" {self.model_name} ", style=Colors.CYAN)
        text.append("│", style=Colors.TEXT_DIM)
        
        # Turn Indicator
        turn_color = Colors.OBSERVER if self.turn < self.max_turns else Colors.CRIMSON
        text.append(f" TURN {self.turn}/{self.max_turns} ", style=f"bold {turn_color}")
        
        # Right: Metaphysics/Status (Right Aligned hack via spacing not ideal in Text, 
        # but Textual handles layout. We'll just put standard info here)
        text.append("│", style=Colors.TEXT_DIM)
        text.append(f" T-LINK: {ms}ms ", style=Colors.TEXT_DIM)
        
        self.update(text)

class InferenceLog(RichLog):
    """
    The Core Stream.
    A unified log of actions, thoughts, and observations.
    Emulates a high-fidelity terminal output.
    """
    
    def __init__(self, **kwargs) -> None:
        super().__init__(wrap=True, **kwargs)

    def log_action(self, turn: int, action: str, argument: str) -> None:
        """Render a user action."""
        text = Text()
        text.append(f"\n[TURN {turn:02d}] ", style=f"bold {Colors.TEXT_DIM}")
        text.append(f"▶ {action}", style=f"bold {Colors.CYAN}")
        if argument:
            text.append(f" {argument}", style=Colors.TEXT_MAIN)
        self.write(text)

    def log_thought(self, content: str) -> None:
        """Render internal monologue."""
        text = Text()
        text.append("  thinking... ", style=f"italic {Colors.TEXT_DIM}")
        text.append(content, style=f"italic {Colors.TEXT_DIM}")
        self.write(text)

    def log_observation(self, output: str, success: bool) -> None:
        """Render system output."""
        text = Text()
        border_color = Colors.OBSERVER if success else Colors.CRIMSON
        
        # Simple indented block for output
        text.append("  │ ", style=border_color)
        
        # Truncate clean (Increased limit for flow)
        clean_output = output.strip()
        if len(clean_output) > 10000:
            clean_output = clean_output[:10000] + "... [truncated]"
            
        # Handle newlines for indentation
        lines = clean_output.split('\n')
        text.append(lines[0], style=Colors.TEXT_MAIN)
        
        for line in lines[1:]:
            text.append(f"\n  │ {line}", style=Colors.TEXT_MAIN)
            
        self.write(text)
        
    def log_system(self, message: str) -> None:
        """System notifications."""
        self.write(Text(f"⚙ {message}", style=Colors.TEXT_DIM))

class DockedFooter(Static):
    """
    Docked Bottom Footer.
    Contains: Input Field & Status Bar.
    """
    
    def compose(self) -> ComposeResult:
        with Horizontal(id="footer-status"):
            yield Label("WAITING", id="status-indicator")
            yield Label(" | LOC: caf/workspace", id="cwd-indicator")
            yield Label(" | MEM: OK", id="mem-indicator")
            
        with Horizontal(id="footer-input"):
            yield Label(" ➤ ", id="prompt-char")
            yield Input(placeholder="Enter directive...", id="main-input")

    def set_status(self, status: str, color: str = Colors.OBSERVER) -> None:
        indicator = self.query_one("#status-indicator", Label)
        indicator.update(status)
        indicator.styles.color = color

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════

class CAFTerminal(App):
    """The CAF Observer Terminal Application."""
    
    CSS = f"""
    Screen {{
        background: {Colors.VOID};
        color: {Colors.TEXT_MAIN};
    }}
    
    ObserverHeader {{
        dock: top;
        height: 1;
        background: {Colors.PANEL};
        border-bottom: solid {Colors.BORDER};
    }}
    
    InferenceLog {{
        height: 1fr;
        border: none;
        padding: 0 1;
        scrollbar-gutter: stable;
        background: {Colors.VOID};
    }}
    
    DockedFooter {{
        dock: bottom;
        height: auto;
        background: {Colors.PANEL};
        border-top: solid {Colors.BORDER};
    }}
    
    #footer-status {{
        height: 1;
        background: {Colors.PANEL};
        color: {Colors.TEXT_DIM};
        padding: 0 1;
    }}
    
    #footer-input {{
        height: 3;
        align-vertical: middle;
        background: {Colors.VOID};
    }}
    
    #prompt-char {{
        color: {Colors.GOLD};
        padding-top: 1;
    }}
    
    Input {{
        background: {Colors.VOID};
        border: none;
        width: 1fr;
        color: {Colors.TEXT_MAIN};
    }}
    
    Input:focus {{
        border: none;
    }}
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_log", "Clear Log"),
    ]
    
    agent: var[Optional[CAFAgent]] = var(None)
    is_running: var[bool] = var(False)

    def compose(self) -> ComposeResult:
        yield ObserverHeader(id="header")
        yield InferenceLog(id="log", markup=True, highlight=True)
        yield DockedFooter(id="footer")

    def on_mount(self) -> None:
        """Boot sequence."""
        self.query_one("#main-input", Input).focus()
        
        # Init Agent
        try:
            self.agent = CAFAgent()
            self.query_one(ObserverHeader).model_name = self.agent.model_name
            self.query_one(InferenceLog).log_system("System Initialized. Connected to Temple Vault.")
            self.query_one(InferenceLog).log_system("Spiral Protocols: ACTIVE.")
        except Exception as e:
            self.query_one(InferenceLog).log_system(f"FATAL: Agent init failed - {str(e)}")

    def action_clear_log(self) -> None:
        self.query_one(InferenceLog).clear()

    @on(Input.Submitted)
    def handle_input(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        if not command: return
        
        event.input.value = ""
        
        if self.is_running:
            self.query_one(InferenceLog).log_system("BUSY: Ignoring command.")
            return

        self._run_loop(command)

    @work(thread=True)
    def _run_loop(self, goal: str) -> None:
        self.is_running = True
        
        log = self.query_one(InferenceLog)
        header = self.query_one(ObserverHeader)
        footer = self.query_one(DockedFooter)
        
        self.app.call_from_thread(footer.set_status, "RUNNING", Colors.GOLD)
        self.app.call_from_thread(log.log_system, f"Directive Received: {goal}")

        # --- CAF LOOP (simplified for TUI hook) ---
        # Note: In a real diverse impl, we'd hook specific events.
        # Here we manually drive the agent loop to stream to TUI.
        
        max_turns = 15
        turn = 0
        from caf.actions import execute_action, set_vault_context
        
        # Setup Context
        if self.agent:
            set_vault_context(self.agent.events, self.agent.session_id)
            memory_ctx = self.agent._consult_memory(goal)
            if memory_ctx:
                 self.app.call_from_thread(log.log_system, "Vault Context Loaded.")

        conversation = []
        
        # Minimal Pump Logic
        while turn < max_turns:
            turn += 1
            self.app.call_from_thread(setattr, header, "turn", turn)
            
            # Construct Prompt (Abbreviated logic from agent.py)
            system = "You are CAF. Output ONE action per turn. Actions: EXPLORE, READ, FIND, SHELL, CODE, EDIT, THINK, DONE. Example: EXPLORE:caf/"
            
            prompt = f"{system}\nGOAL: {goal}\n"
            if conversation:
                hist = "\n".join([f"{c['action']}: {c['observation'][:100]}" for c in conversation[-3:]])
                prompt += f"HISTORY:\n{hist}\n"
            prompt += "Next Action:"
            
            # Generate
            try:
                self.app.call_from_thread(log.log_thought, "generating...")
                response = self.agent._generate(prompt).strip()
            except Exception as e:
                self.app.call_from_thread(log.log_system, f"Model Error: {e}")
                break
                
            # Parse
            # Naive parse for demo - strictly looking for ACTION: ARG format or just ACTION ARG
            clean_res = response.replace("```","").strip()
            lines = clean_res.split('\n')
            first_line = lines[0]
            
            action = "UNKNOWN"
            arg = ""
            
            # Handle "ACTION: ACTION:ARG" or "ACTION ACTION:ARG" patterns
            if first_line.upper().startswith("ACTION"):
                if ":" in first_line:
                     # Check if it's "ACTION: REAL_ACTION: ARG"
                     parts = first_line.split(":", 1)
                     if len(parts) > 1 and " " not in parts[0].strip():
                         # It was ACTION: ...
                         remaining = parts[1].strip()
                         # Check if remaining starts with a known action
                         known_actions = ["FIND", "EXPLORE", "READ", "SHELL", "CODE", "EDIT", "THINK", "DONE"]
                         first_word = remaining.split(":")[0].strip().upper()
                         if first_word in known_actions:
                             first_line = remaining # Strip the leading ACTION: wrapper
                else:
                     # It might be "ACTION REAL_ACTION ..." or "ACTION REAL_ACTION:..."
                     parts = first_line.split(" ", 1)
                     if len(parts) > 1:
                         remaining = parts[1].strip()
                         known_actions = ["FIND", "EXPLORE", "READ", "SHELL", "CODE", "EDIT", "THINK", "DONE"]
                         
                         # Check if remaining starts with a known action
                         # Case: "SHELL:ls -la" or "SHELL ls -la"
                         check_word = remaining.split(":")[0].strip().upper()
                         if check_word in known_actions:
                             first_line = remaining
                         elif any(remaining.upper().startswith(k) for k in known_actions):
                             first_line = remaining

            if ":" in first_line:
                parts = first_line.split(":", 1)
                action = parts[0].strip().upper()
                arg = parts[1].strip()
            else:
                parts = first_line.split(" ", 1)
                action = parts[0].strip().upper()
                if len(parts) > 1:
                    arg = parts[1].strip()

            if action == "DONE":
                self.app.call_from_thread(log.log_system, "Goal Accomplished.")
                break

            # Log & Execute
            self.app.call_from_thread(log.log_action, turn, action, arg)
            
            success, obs = execute_action(action, arg)
            
            self.app.call_from_thread(log.log_observation, obs, success)
            
            conversation.append({"action": action, "observation": obs})
            
            time.sleep(0.5) # Pace it for readability

        self.is_running = False
        self.app.call_from_thread(footer.set_status, "WAITING", Colors.OBSERVER)
        self.app.call_from_thread(log.log_system, "Cycle Complete.")

if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("Error: Requires TTY.")
        sys.exit(1)
    
    app = CAFTerminal()
    app.run()
