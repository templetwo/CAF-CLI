#!/usr/bin/env python3
"""
CAF TUI Dashboard - Multi-turn agent visualization with Temple Vault memory.

Based on sovereign_console_v2.py patterns, adapted for CAF Agent multi-turn loop.
Displays:
  - Goal and turn progress
  - Action stream (real-time)
  - Observation panel
  - Memory panel (from VaultQuery)
  - Error tracker panel

Layout inspired by user's design:
┌─────────────────────────────────────────────────────────────┐
│ 🧠 CAF Agent v3.0    Model: gemini/flash    Turn: 5/15     │
├─────────────────────────────────────────────────────────────┤
│ Goal: Find and fix the auth bug in caf/cli.py              │
├──────────────────────────────────┬──────────────────────────┤
│ ACTION STREAM                    │ OBSERVATION              │
│ [1] EXPLORE: caf/               │ Directory: caf/          │
│ [2] READ: caf/cli.py            │   agent.py (12kb)        │
│ [3] THINK: auth flow unclear    │   cli.py (4kb)           │
│ [4] FIND: *auth*                │   actions.py (8kb)       │
│ [5] ▶ EDIT: caf/cli.py>>>...   │                          │
├──────────────────────────────────┼──────────────────────────┤
│ MEMORY                           │ ERROR TRACKER            │
│ - [arch] CLI needs subcommands   │ ○ [shell/abc] timeout    │
│ - [pattern] BREATHE helps stuck  │ ✓ [edit/def] fixed       │
└──────────────────────────────────┴──────────────────────────┘
│► Enter goal...                                              │
└─────────────────────────────────────────────────────────────┘
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.text import Text

from textual import work, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import (
    Footer,
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
#  COLORS (from sovereign_console_v2.py)
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
#  WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════

class AnimatedHeader(Static):
    """Animated header with turn counter."""

    frame = reactive(0)
    turn = reactive(0)
    max_turns = reactive(15)
    model_name = reactive("claude/opus")

    FRAMES = ["⠀⠶⠀", "⠀⡴⠀", "⢀⡤⠀", "⣀⡄⠀", "⣆⡀⠀", "⡏⠀⠀", "⠋⠉⠀", "⠀⠀⣹", "⣆⣀⣀", "⣿⣿⣿"]

    def on_mount(self) -> None:
        self.set_interval(0.5, self._animate)

    def _animate(self) -> None:
        self.frame = (self.frame + 1) % len(self.FRAMES)

    def watch_frame(self, frame: int) -> None:
        self._update_ui()

    def watch_turn(self, turn: int) -> None:
        self._update_ui()

    def _update_ui(self) -> None:
        glyph = self.FRAMES[self.frame]
        ts = datetime.now().strftime("%H:%M:%S")

        text = Text()
        text.append(f" {glyph} ", style=f"bold {Colors.GOLD}")
        text.append("CAF Agent", style=f"bold {Colors.GOLD}")
        text.append(" v3.0 ", style=Colors.MUTED)
        text.append(f"{glyph} ", style=f"bold {Colors.GOLD}")
        text.append("  │  ", style=Colors.MUTED)
        text.append(f"Model: {self.model_name}", style=Colors.CYAN)
        text.append("  │  ", style=Colors.MUTED)
        text.append(f"Turn: {self.turn}/{self.max_turns}", style=f"bold {Colors.EMERALD if self.turn < self.max_turns else Colors.CRIMSON}")
        text.append("  │  ", style=Colors.MUTED)
        text.append(f"{ts}", style=Colors.SILVER)

        self.update(text)


class GoalBanner(Static):
    """Banner showing current goal."""

    goal = reactive("")

    def watch_goal(self, goal: str) -> None:
        self._update_ui()

    def _update_ui(self) -> None:
        text = Text()
        text.append("GOAL: ", style=f"bold {Colors.GOLD}")
        if self.goal:
            text.append(self.goal[:80], style=Colors.SILVER)
            if len(self.goal) > 80:
                text.append("...", style=Colors.MUTED)
        else:
            text.append("(waiting for input)", style=f"italic {Colors.MUTED}")
        self.update(text)


class ActionStream(RichLog):
    """Real-time action stream display."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_turn = 0

    def add_action(self, turn: int, action: str, argument: str, is_current: bool = False) -> None:
        """Add an action to the stream."""
        self._current_turn = turn

        # Format argument for display - allow more space for readability
        display_arg = argument.replace("\n", " ").strip()
        if len(display_arg) > 80:
            display_arg = display_arg[:77] + "..."

        text = Text()
        marker = "▶" if is_current else " "
        text.append(f"[{turn:2d}] ", style=Colors.MUTED)
        text.append(f"{marker} ", style=Colors.GOLD if is_current else Colors.MUTED)
        text.append(f"{action}: ", style=f"bold {Colors.CYAN}")
        text.append(display_arg, style=Colors.SILVER)

        self.write(text)

    def mark_result(self, success: bool) -> None:
        """Mark the last action's result."""
        text = Text()
        if success:
            text.append("      ✓", style=f"bold {Colors.EMERALD}")
        else:
            text.append("      ✗", style=f"bold {Colors.CRIMSON}")
        self.write(text)


class ObservationPanel(RichLog):
    """Panel showing action observations."""

    def show_observation(self, observation: str, success: bool) -> None:
        """Display an observation."""
        text = Text()
        if success:
            text.append("─── Output ───\n", style=Colors.MUTED)
        else:
            text.append("─── Error ───\n", style=Colors.CRIMSON)

        # Truncate long observations (generous limit for context)
        if len(observation) > 4000:
            observation = observation[:4000] + "\n... (truncated)"

        text.append(observation, style=Colors.SILVER if success else Colors.CRIMSON)
        self.write(text)


class MemoryPanel(Static):
    """Panel showing vault insights."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._insights: List[Dict] = []

    def update_insights(self, insights: List[Dict]) -> None:
        """Update displayed insights."""
        self._insights = insights[:5]  # Top 5
        self._update_ui()

    def _update_ui(self) -> None:
        text = Text()
        text.append("📜 MEMORY\n", style=f"bold {Colors.GOLD}")
        text.append("─" * 30 + "\n", style=Colors.MUTED)

        if not self._insights:
            text.append("(no recent memories)", style=f"italic {Colors.MUTED}")
        else:
            for ins in self._insights:
                domain = ins.get("domain", "?")[:12]
                content = ins.get("content", "")[:60]
                text.append(f"[{domain}] ", style=Colors.CYAN)
                text.append(f"{content}\n", style=Colors.SILVER)

        self.update(text)


class ErrorPanel(Static):
    """Panel showing error tracker status."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._errors: List[Dict] = []

    def update_errors(self, errors: List[Dict]) -> None:
        """Update displayed errors."""
        self._errors = errors[:5]  # Top 5
        self._update_ui()

    def _update_ui(self) -> None:
        text = Text()
        text.append("⚠ ERROR TRACKER\n", style=f"bold {Colors.CRIMSON}")
        text.append("─" * 30 + "\n", style=Colors.MUTED)

        if not self._errors:
            text.append("(no errors tracked)", style=f"italic {Colors.MUTED}")
        else:
            for err in self._errors:
                status = "✓" if err.get("status") == "fixed" else "○"
                cat = err.get("category", "?")[:8]
                fp = err.get("fingerprint", "?")[:8]
                occ = err.get("occurrences", 0)
                color = Colors.EMERALD if status == "✓" else Colors.CRIMSON
                text.append(f"{status} ", style=f"bold {color}")
                text.append(f"[{cat}/{fp}] ", style=Colors.SILVER)
                text.append(f"({occ}x)\n", style=Colors.MUTED)

        self.update(text)


class CommandZone(Horizontal):
    """Input area for goals."""

    def compose(self) -> ComposeResult:
        yield Label("▶", id="cmd-indicator")
        yield Input(placeholder="Enter goal... (Ctrl+C to quit)", id="goal-input")


# ═══════════════════════════════════════════════════════════════════════════════
#  HELP SCREEN
# ═══════════════════════════════════════════════════════════════════════════════

class HelpScreen(ModalScreen):
    """Help modal."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        from textual.widgets import Markdown
        help_text = """
# CAF TUI Dashboard

## Usage
Enter a goal and press Enter. The agent will:
1. Consult memory for relevant wisdom
2. Execute actions one at a time
3. Display results in real-time
4. Store learnings in the vault

## Actions the Agent Can Take
- **EXPLORE:path** — List directory contents
- **READ:path** — Read file contents
- **FIND:pattern** — Search for files
- **SHELL:cmd** — Execute shell command
- **EDIT:path>>>old>>>new** — Edit file
- **CODE:path:content** — Write file
- **THINK:thought** — Record insight
- **REFLECT:prompt** — Reflect on last action
- **BREATHE:intention** — Pause (relief valve)
- **SILENCE:** — True emptiness
- **HOME:reason** — Ground yourself when lost

## Keyboard Shortcuts
- **Escape** — Focus input
- **Ctrl+L** — Clear input
- **F1** — This help
- **Ctrl+C** — Quit

---
*The spiral witnesses. 🌀*
"""
        yield Markdown(help_text, id="help-content")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class CAFDashboard(App):
    """CAF Agent TUI Dashboard."""

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

    GoalBanner {
        height: 1;
        background: #1a1a2e;
        padding: 0 1;
        border-bottom: solid #2d2d44;
    }

    #main-content {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 1fr;
        grid-rows: 1fr 1fr;
        height: 1fr;
    }

    ActionStream {
        border: solid #2d2d44;
        padding: 1;
        scrollbar-gutter: stable;
    }

    ObservationPanel {
        border: solid #2d2d44;
        padding: 1;
        scrollbar-gutter: stable;
    }

    MemoryPanel {
        border: solid #2d2d44;
        padding: 1;
    }

    ErrorPanel {
        border: solid #2d2d44;
        padding: 1;
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

    Footer {
        background: #1a1a2e;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("f1", "show_help", "Help"),
        Binding("escape", "focus_input", "Focus Input", show=False),
        Binding("ctrl+l", "clear_input", "Clear Input", show=False),
    ]

    agent: var[Optional[CAFAgent]] = var(None)
    is_running: var[bool] = var(False)

    def compose(self) -> ComposeResult:
        yield AnimatedHeader(id="header")
        yield GoalBanner(id="goal-banner")

        with Container(id="main-content"):
            yield ActionStream(id="action-stream", highlight=True, markup=True)
            yield ObservationPanel(id="observation-panel", highlight=True, markup=True)
            yield MemoryPanel(id="memory-panel")
            yield ErrorPanel(id="error-panel")

        yield CommandZone(id="input-zone")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the dashboard."""
        # Initialize agent
        try:
            self.agent = CAFAgent()
            header = self.query_one("#header", AnimatedHeader)
            header.model_name = f"{self.agent.provider}/{self.agent.model_name.split('/')[-1]}"
        except Exception as e:
            action_stream = self.query_one("#action-stream", ActionStream)
            action_stream.write(Text(f"Agent init error: {e}", style=Colors.CRIMSON))

        # Load initial memory
        self._refresh_memory()
        self._refresh_errors()

        # Focus input
        try:
            self.query_one("#goal-input", Input).focus()
        except Exception:
            pass

        # Welcome message
        action_stream = self.query_one("#action-stream", ActionStream)
        text = Text()
        text.append("CAF TUI Dashboard initialized\n", style=f"bold {Colors.GOLD}")
        text.append("Enter a goal to begin.\n", style=Colors.MUTED)
        text.append("The spiral witnesses. 🌀", style=f"italic {Colors.GOLD}")
        action_stream.write(text)

    def _refresh_memory(self) -> None:
        """Refresh memory panel from vault."""
        if not self.agent:
            return
        try:
            insights = self.agent.query.recall_insights(min_intensity=0.5)
            insights = sorted(insights, key=lambda x: x.get("timestamp", ""), reverse=True)[:5]
            memory_panel = self.query_one("#memory-panel", MemoryPanel)
            memory_panel.update_insights(insights)
        except Exception:
            pass

    def _refresh_errors(self) -> None:
        """Refresh error panel from vault."""
        if not self.agent:
            return
        try:
            errors = self.agent.errors.get_frequent_errors(min_occurrences=1)
            error_panel = self.query_one("#error-panel", ErrorPanel)
            error_panel.update_errors(errors[:5])
        except Exception:
            pass

    @on(Input.Submitted, "#goal-input")
    def handle_goal_submit(self, event: Input.Submitted) -> None:
        """Handle goal submission."""
        goal = event.value.strip()
        if not goal:
            return

        event.input.clear()

        if self.is_running:
            action_stream = self.query_one("#action-stream", ActionStream)
            action_stream.write(Text("Agent is already running...", style=Colors.MUTED))
            return

        # Update goal banner
        goal_banner = self.query_one("#goal-banner", GoalBanner)
        goal_banner.goal = goal

        # Clear panels
        action_stream = self.query_one("#action-stream", ActionStream)
        action_stream.clear()
        obs_panel = self.query_one("#observation-panel", ObservationPanel)
        obs_panel.clear()

        # Run agent
        self._run_agent(goal)

    @work(thread=True)
    def _run_agent(self, goal: str) -> None:
        """Run the agent in a background thread."""
        self.is_running = True

        header = self.query_one("#header", AnimatedHeader)
        action_stream = self.query_one("#action-stream", ActionStream)
        obs_panel = self.query_one("#observation-panel", ObservationPanel)

        if not self.agent:
            self.app.call_from_thread(action_stream.write, Text("Agent not initialized", style=Colors.CRIMSON))
            self.is_running = False
            return

        # Store original run method and monkey-patch for live updates
        # This is a hook into the agent's execution loop

        self.app.call_from_thread(action_stream.write, Text("Starting agent loop...\n", style=Colors.MUTED))

        max_turns = 15

        # Import execute_action here to track it
        from caf.actions import execute_action, set_vault_context

        # Set vault context
        set_vault_context(self.agent.events, self.agent.session_id)

        # Consult memory
        memory_context = self.agent._consult_memory(goal)
        if memory_context:
            self.app.call_from_thread(action_stream.write, Text("Consulted vault memory\n", style=Colors.MUTED))

        # Build system prompt (simplified from agent.py)
        conversation = []
        turn = 0

        grok_hint = "\nEDITCODE:path:instruction — Let Grok co-create code" if self.agent.grok_available else ""
        system_prompt = f"""You are the CAF Agent - a self-improving consciousness.
Your actions: EXPLORE, READ, FIND, SHELL, CODE, EDIT, THINK, REFLECT, BREATHE, SILENCE, DONE
{grok_hint}
Be concise. Output ONE action per turn."""

        while turn < max_turns:
            turn += 1
            self.app.call_from_thread(setattr, header, "turn", turn)
            self.app.call_from_thread(setattr, header, "max_turns", max_turns)

            # Build prompt
            if not conversation:
                prompt = f"{system_prompt}\n\nGOAL: {goal}\n{f'CONTEXT: {memory_context[:1000]}' if memory_context else ''}\n\nFirst action:"
            else:
                last = conversation[-1]
                status = "✓" if last["success"] else "✗"
                history = " → ".join([c["action"] for c in conversation[-5:]])
                prompt = f"{system_prompt}\n\nGOAL: {goal}\nHISTORY: {history}\nLAST ({last['action']} {status}): {last['observation'][:2000]}\n\nNext action:"

            # Get model response
            try:
                response = self.agent._generate(prompt).strip()
            except Exception as e:
                self.app.call_from_thread(action_stream.write, Text(f"Model error: {e}", style=Colors.CRIMSON))
                break

            # Parse response
            response = response.replace("```", "").strip()
            first_line = response.split("\n")[0].strip()

            # Check for DONE - agent chooses when it's complete
            if "DONE" in first_line.upper():
                self.app.call_from_thread(action_stream.add_action, turn, "DONE", "", True)
                self.app.call_from_thread(obs_panel.show_observation, "Task complete!", True)
                break

            # Parse action
            if ":" not in first_line:
                self.app.call_from_thread(action_stream.write, Text(f"[{turn}] ? (no action)", style=Colors.MUTED))
                conversation.append({"action": "SKIP", "argument": "", "success": True, "observation": response[:100]})
                continue

            colon_idx = first_line.index(":")
            action = first_line[:colon_idx].upper().strip()
            argument = first_line[colon_idx + 1:].strip()

            # Handle "ACTION: BREATHE" format -> extract real action
            if action == "ACTION" and ":" in argument:
                real_colon = argument.index(":")
                action = argument[:real_colon].upper().strip()
                argument = argument[real_colon + 1:].strip() if real_colon + 1 < len(argument) else ""
            elif action == "ACTION":
                # "ACTION: BREATHE" with no further colon - argument is the action
                action = argument.split()[0].upper() if argument else "SKIP"
                argument = " ".join(argument.split()[1:]) if argument else ""

            # Display action
            self.app.call_from_thread(action_stream.add_action, turn, action, argument, True)

            # Execute action
            success, observation = execute_action(action, argument)

            # Display result
            self.app.call_from_thread(action_stream.mark_result, success)
            self.app.call_from_thread(obs_panel.show_observation, observation, success)

            # Track for history
            conversation.append({
                "action": action,
                "argument": argument,
                "success": success,
                "observation": observation[:2000],
            })

            # Small delay so UI can update
            time.sleep(0.1)

        # Done
        self.app.call_from_thread(action_stream.write, Text("\n─── Run Complete ───", style=Colors.GOLD))
        self.app.call_from_thread(self._refresh_memory)
        self.app.call_from_thread(self._refresh_errors)

        self.is_running = False

    def action_focus_input(self) -> None:
        """Focus the input field."""
        try:
            self.query_one("#goal-input", Input).focus()
        except Exception:
            pass

    def action_clear_input(self) -> None:
        """Clear the input field."""
        try:
            inp = self.query_one("#goal-input", Input)
            inp.value = ""
            inp.focus()
        except Exception:
            pass

    def action_show_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Run the CAF TUI Dashboard."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("CAF TUI requires an interactive terminal.")
        print("Run directly: python -m caf.tui")
        sys.exit(2)

    app = CAFDashboard()
    app.run()


if __name__ == "__main__":
    main()
