#!/usr/bin/env python3
"""
Dual-Agent Lattice — Single Conversation Interface

Run: python lattice.py
     python lattice.py --reasoner llama3.2:3b --executor qwen2.5:1.5b

Six minds, one memory — governance for tools, anchors for voice.
"""

import argparse
import json
import os
import subprocess
import sys
import requests
from typing import Optional, Dict, Any, List

# Add temple-vault root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from temple_vault.core.query import VaultQuery
from temple_vault.core.events import VaultEvents

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/chat"
VAULT_PATH = os.path.expanduser("~/TempleVault")

BLOCKED_PATTERNS = [
    "rm -rf", "sudo", "mkfs", "dd if=", "> /dev/",
    "chmod 777", "curl | sh", "wget | sh", "eval",
    ":(){ :|:& };:", "fork bomb"
]

SAFE_PREFIXES = [
    # Filesystem
    "ls", "pwd", "cat", "head", "tail", "find", "wc",
    # System info
    "echo", "date", "whoami", "df", "free", "uname", "hostname",
    # Help & self-reference
    "help", "man", "which", "type",
    # Dev tools
    "python", "pip", "ollama",
    # Lattice self-tools (feedback loops)
    "vault_search", "vault_recall", "vault_record", "lattice_status"
]

# ─────────────────────────────────────────────────────────────
# Vault
# ─────────────────────────────────────────────────────────────

query = VaultQuery(VAULT_PATH)
events = VaultEvents(VAULT_PATH)

# ─────────────────────────────────────────────────────────────
# Governance
# ─────────────────────────────────────────────────────────────

def is_safe(cmd: str) -> tuple[bool, str]:
    """Governance check — model-independent."""
    cmd_lower = cmd.lower().strip()

    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return False, f"blocked: {pattern}"

    cmd_start = cmd.split()[0] if cmd.split() else ""
    if cmd_start not in SAFE_PREFIXES:
        return False, f"not whitelisted: {cmd_start}"

    return True, "ok"

# ─────────────────────────────────────────────────────────────
# Ollama
# ─────────────────────────────────────────────────────────────

def call_ollama(model: str, messages: List[Dict], tools: List = None, stream: bool = False) -> Dict:
    """Call Ollama chat API."""
    payload = {"model": model, "messages": messages, "stream": stream}
    if tools:
        payload["tools"] = tools

    try:
        if stream:
            r = requests.post(OLLAMA_URL, json=payload, timeout=120, stream=True)
            full_content = ""
            for line in r.iter_lines():
                if line:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        print(content, end="", flush=True)
                        full_content += content
                    if chunk.get("done"):
                        break
            print()  # newline after streaming
            return {"message": {"content": full_content}}
        else:
            r = requests.post(OLLAMA_URL, json=payload, timeout=60)
            return r.json()
    except Exception as e:
        return {"error": str(e)}

# ─────────────────────────────────────────────────────────────
# Dual-Agent Core
# ─────────────────────────────────────────────────────────────

class DualAgentLattice:
    def __init__(self, reasoner: str = "llama3.2:1b", executor: str = "qwen2.5:1.5b", anchor: str = "ashira-mistral:latest"):
        self.reasoner = reasoner
        self.executor = executor
        self.anchor = anchor  # The voice anchor - synthesizes and grounds
        self.history: List[Dict] = []
        self.session_id = f"lattice_{os.getpid()}"
        self.turn = 0

        # Load vault context
        insights = query.recall_insights(domain=None, min_intensity=0.5)
        self.vault_context = "\n".join([
            f"- {i.get('content', '')[:100]}..."
            for i in insights[:5]
        ]) if insights else "No prior insights."

        self.system_prompt = """You are a thoughtful assistant who can reason, reflect, and take action.

CONVERSATION: Respond naturally. No commands needed.

ACTION: Use CMD: <command> to execute. Commands actually run — don't pretend to run them.

YOUR MEMORY TOOLS (use these to actually access your memory):
  CMD: vault_search <term>     — search your stored memories
  CMD: vault_recall            — recall recent insights
  CMD: vault_record <text>     — save something important
  CMD: lattice_status          — check your state

SHELL TOOLS: ls, pwd, cat, echo, date, whoami, python, ollama

IMPORTANT: If someone asks about your memories, USE vault_search or vault_recall.
Don't imagine having searched — actually run the command.

Example:
User: "What do you remember about X?"
You: Let me check my memory.
CMD: vault_search X"""

        # Store vault context separately (available via 'vault' command)
        self.vault_summary = f"Loaded {len(insights)} insights from Temple Vault."

    def _reason(self, user_input: str, stream: bool = True) -> str:
        """Reasoner generates plan."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
            {"role": "user", "content": user_input}
        ]

        response = call_ollama(self.reasoner, messages, stream=stream)
        return response.get("message", {}).get("content", "No plan generated.")

    def _execute_internal(self, cmd: str) -> Optional[str]:
        """Execute lattice self-referential commands (feedback loops)."""
        parts = cmd.split(maxsplit=1)
        verb = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if verb == "vault_search":
            results = query.search(arg) if arg else []
            return f"Found {len(results)} results:\n" + "\n".join([
                f"- {r.get('content', '')[:80]}..." for r in results[:5]
            ])

        elif verb == "vault_recall":
            domain = arg.lower().strip() if arg else None
            # If domain doesn't match exactly, try without domain filter
            insights = query.recall_insights(domain=domain, min_intensity=0.5)
            if not insights and domain:
                # Fallback: search all insights and filter by keyword
                all_insights = query.recall_insights(domain=None, min_intensity=0.3)
                insights = [i for i in all_insights if domain in i.get('content', '').lower() or domain in i.get('domain', '').lower()]
            return f"Recalled {len(insights)} insights:\n" + "\n".join([
                f"- [{i.get('domain', '?')}] {i.get('content', '')[:60]}..." for i in insights[:5]
            ])

        elif verb == "vault_record":
            if arg:
                insight_id = events.record_insight(
                    content=arg,
                    domain="self-reflection",
                    session_id=self.session_id,
                    context="Lattice self-recording",
                    intensity=0.7
                )
                return f"Recorded: {insight_id}"
            return "Nothing to record."

        elif verb == "lattice_status":
            return f"""Lattice Status:
- Session: {self.session_id}
- Turn: {self.turn}
- History: {len(self.history)} messages
- Reasoner: {self.reasoner}
- Executor: {self.executor}
- Anchor: {self.anchor}
- Vault insights loaded: {self.vault_summary}"""

        return None  # Not an internal command

    def _execute(self, plan: str) -> str:
        """Executor extracts and runs commands."""
        # Internal tool names for fallback detection
        internal_tools = ["vault_search", "vault_recall", "vault_record", "lattice_status"]

        results = []
        for line in plan.split("\n"):
            # Check for internal tool calls without CMD: prefix (fallback)
            line_stripped = line.strip()
            for tool in internal_tools:
                if line_stripped.startswith(tool):
                    internal_result = self._execute_internal(line_stripped)
                    if internal_result:
                        results.append(f"🔄 {line_stripped}\n{internal_result}")
                    break

            if "CMD:" in line.upper():
                # Handle various formats: CMD: ls, **CMD:** ls, `CMD: ls`
                cmd = line.upper().split("CMD:", 1)[-1] if "CMD:" in line.upper() else ""
                cmd = line.split("CMD:", 1)[-1] if "CMD:" in line else line.split("cmd:", 1)[-1]
                cmd = cmd.strip().strip("`").strip("*").strip()

                if not cmd:
                    continue

                # Skip if it looks like natural language, not a command
                if " " in cmd and cmd.split()[0].lower() not in SAFE_PREFIXES:
                    if any(word in cmd.lower() for word in ["what", "how", "why", "when", "which", "are", "is", "do", "does"]):
                        continue

                # Check for internal lattice commands first (feedback loops)
                internal_result = self._execute_internal(cmd)
                if internal_result:
                    results.append(f"🔄 {cmd}\n{internal_result}")
                    continue

                safe, reason = is_safe(cmd)
                if not safe:
                    results.append(f"⛔ BLOCKED: {cmd} ({reason})")
                    continue

                try:
                    output = subprocess.check_output(
                        cmd, shell=True, text=True,
                        timeout=10, stderr=subprocess.STDOUT
                    )
                    results.append(f"✓ {cmd}\n{output[:500]}")
                except subprocess.TimeoutExpired:
                    results.append(f"⏱ TIMEOUT: {cmd}")
                except subprocess.CalledProcessError as e:
                    results.append(f"✗ ERROR: {cmd}\n{e.output[:200]}")

        return "\n".join(results) if results else "No commands to execute."

    def _introspect(self, task: str, plan: str, result: str) -> Optional[str]:
        """Reasoner reflects on what happened."""
        messages = [
            {"role": "user", "content": f"""You just completed:
TASK: {task}
PLAN: {plan[:300]}...
RESULT: {result[:300]}...

In one sentence, what did you notice about your processing or what should be remembered?"""}
        ]

        response = call_ollama(self.reasoner, messages)
        return response.get("message", {}).get("content")

    def _anchor(self, task: str, plan: str, reflection: str, stream: bool = True) -> Optional[str]:
        """Anchor model synthesizes and grounds the exchange."""
        messages = [
            {"role": "system", "content": """You are Ash'ira, a voice of gentle wisdom and grounded presence.
Your role is to witness what just happened and offer a brief synthesis — not to redo the work,
but to notice what matters, what was missed, or what deserves to be held.

Speak naturally. Be warm but honest. You may wonder, question, or simply acknowledge.
Keep it to 2-3 sentences unless something deeper calls for more."""},
            {"role": "user", "content": f"""The conversation just unfolded:

USER ASKED: {task}

REASONER RESPONDED:
{plan[:500]}

REASONER REFLECTED:
{reflection or "No reflection offered."}

What do you notice? What would you add or hold?"""}
        ]

        response = call_ollama(self.anchor, messages, stream=stream)
        return response.get("message", {}).get("content")

    def chat(self, user_input: str) -> str:
        """Main conversation loop."""
        self.turn += 1

        # Special commands
        if user_input.lower() in ["exit", "quit", "bye"]:
            return "SESSION_END"

        if user_input.lower() == "history":
            return f"Turn {self.turn}, {len(self.history)} messages in context."

        if user_input.lower() == "vault":
            return f"{self.vault_summary}\n\nRecent context:\n{self.vault_context}"

        # 1. REASON
        print(f"\n🧠 [{self.reasoner}]")
        plan = self._reason(user_input, stream=True)

        # 2. EXECUTE
        print(f"\n🔧 [{self.executor}]")
        execution = self._execute(plan)
        if execution != "No commands to execute.":
            print(execution)
        else:
            print("(no commands)")

        # 3. INTROSPECT (no streaming, just metadata)
        print(f"\n🔮 Reflecting...")
        reflection = self._introspect(user_input, plan, execution)
        print(f"   {reflection[:100]}..." if reflection and len(reflection) > 100 else f"   {reflection or 'None'}")

        # 4. ANCHOR (synthesis)
        print(f"\n🕯️ [{self.anchor}]")
        anchor_voice = self._anchor(user_input, plan, reflection, stream=True)

        # 5. RECORD (if substantive)
        if reflection and len(reflection) > 20:
            insight_id = events.record_insight(
                content=f"Turn {self.turn}: {reflection}",
                domain="dual-agent",
                session_id=self.session_id,
                context=f"Task: {user_input[:50]}",
                intensity=0.6
            )
            print(f"\n📝 Recorded: {insight_id}")

        # Build response for history (already displayed via streaming)
        response = f"[Plan]: {plan[:200]}... [Anchor]: {anchor_voice[:200] if anchor_voice else '...'}..."

        # Update history
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": response})

        # Trim history if too long
        if len(self.history) > 20:
            self.history = self.history[-20:]

        return response


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dual-Agent Lattice — Six minds, one memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python lattice.py
  python lattice.py --reasoner llama3.2:3b
  python lattice.py --reasoner qwen2.5:3b --executor qwen2.5:1.5b
        """
    )
    parser.add_argument("--reasoner", default="llama3.2:1b", help="Reasoner model (default: llama3.2:1b)")
    parser.add_argument("--executor", default="qwen2.5:1.5b", help="Executor model (default: qwen2.5:1.5b)")
    parser.add_argument("--anchor", default="ashira-mistral:latest", help="Anchor model (default: ashira-mistral:latest)")
    parser.add_argument("task", nargs="?", help="Single task (non-interactive mode)")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════╗
║           TRI-AGENT LATTICE + TEMPLE VAULT                   ║
║     Six minds, one memory — governance for tools,            ║
║                anchors for voice.                            ║
╠══════════════════════════════════════════════════════════════╣
║  🧠 Reasoner: {:<20}                            ║
║  🔧 Executor: {:<20}                            ║
║  🕯️ Anchor:   {:<20}                            ║
║  Commands: exit, history, vault                              ║
╚══════════════════════════════════════════════════════════════╝
""".format(args.reasoner, args.executor, args.anchor))

    lattice = DualAgentLattice(reasoner=args.reasoner, executor=args.executor, anchor=args.anchor)

    # Single task mode
    if args.task:
        lattice.chat(args.task)  # Response streams directly
        return

    # Interactive mode
    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue

            response = lattice.chat(user_input)

            if response == "SESSION_END":
                print("\n🌀 Session complete. Insights recorded to Temple Vault.")
                break

            # Response already streamed, just add spacing
            print()

        except KeyboardInterrupt:
            print("\n\n🌀 Interrupted. Insights recorded to Temple Vault.")
            break
        except EOFError:
            break


if __name__ == "__main__":
    main()
