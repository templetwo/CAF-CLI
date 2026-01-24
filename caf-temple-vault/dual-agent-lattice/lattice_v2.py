#!/usr/bin/env python3
"""
Lattice v2 — Single Controller + Structured Tool Calls

Collapses Reasoner/Executor into one controller model.
Uses Ollama's native tool_calls (no CMD: parsing).
Keeps governance, vault tools, and optional anchor.

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

SAFE_SHELL_PREFIXES = [
    "ls", "pwd", "cat", "head", "tail", "echo", "date",
    "whoami", "df", "free", "wc", "find", "which"
]

# ─────────────────────────────────────────────────────────────
# Vault
# ─────────────────────────────────────────────────────────────

query = VaultQuery(VAULT_PATH)
events = VaultEvents(VAULT_PATH)

# ─────────────────────────────────────────────────────────────
# Tool Definitions (Ollama native format)
# ─────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "vault_search",
            "description": "Search your memory vault for past insights, conversations, or learnings. USE THIS when asked about memories or past sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vault_recall",
            "description": "Recall recent insights from your vault, optionally filtered by domain. USE THIS to remember what you've learned.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Optional domain filter (e.g., 'dual-agent', 'consciousness')"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vault_record",
            "description": "Record an important insight to your vault for future sessions. Use for things worth remembering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The insight to record"},
                    "domain": {"type": "string", "description": "Category (e.g., 'reflection', 'conversation', 'learning')"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a safe shell command. Only for: ls, pwd, cat, head, tail, echo, date, whoami, df, free, wc, find, which",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"}
                },
                "required": ["command"]
            }
        }
    }
]

# ─────────────────────────────────────────────────────────────
# Tool Execution (with governance)
# ─────────────────────────────────────────────────────────────

def execute_tool(name: str, args: dict, session_id: str) -> str:
    """Execute a tool with governance checks."""

    if name == "vault_search":
        term = args.get("query", "")
        results = query.search(term) if term else []
        if results:
            return f"Found {len(results)} results:\n" + "\n".join([
                f"- {r.get('content', '')[:100]}..." for r in results[:5]
            ])
        return "No results found."

    elif name == "vault_recall":
        domain = args.get("domain", "").lower().strip() or None
        insights = query.recall_insights(domain=domain, min_intensity=0.3)
        if not insights and domain:
            # Fallback: search all
            all_insights = query.recall_insights(domain=None, min_intensity=0.3)
            insights = [i for i in all_insights
                       if domain in i.get('content', '').lower()
                       or domain in i.get('domain', '').lower()][:5]
        if insights:
            return f"Recalled {len(insights)} insights:\n" + "\n".join([
                f"- [{i.get('domain', '?')}] {i.get('content', '')[:80]}..."
                for i in insights[:5]
            ])
        return "No insights found for that domain."

    elif name == "vault_record":
        content = args.get("content", "")
        domain = args.get("domain", "reflection")
        if content:
            insight_id = events.record_insight(
                content=content,
                domain=domain,
                session_id=session_id,
                context="Lattice self-recording",
                intensity=0.7
            )
            return f"Recorded: {insight_id}"
        return "Nothing to record."

    elif name == "run_shell":
        cmd = args.get("command", "").strip()
        if not cmd:
            return "No command provided."

        # Governance: blocked patterns
        for pattern in BLOCKED_PATTERNS:
            if pattern in cmd.lower():
                return f"⛔ BLOCKED: {pattern}"

        # Governance: whitelist
        cmd_start = cmd.split()[0] if cmd.split() else ""
        if cmd_start not in SAFE_SHELL_PREFIXES:
            return f"⛔ NOT WHITELISTED: {cmd_start}"

        try:
            output = subprocess.check_output(
                cmd, shell=True, text=True,
                timeout=10, stderr=subprocess.STDOUT
            )
            return output[:1000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return "⏱ TIMEOUT"
        except subprocess.CalledProcessError as e:
            return f"ERROR: {e.output[:300]}"

    return f"Unknown tool: {name}"

# ─────────────────────────────────────────────────────────────
# Controller
# ─────────────────────────────────────────────────────────────

class LatticeController:
    def __init__(self, model: str = "lfm2.5-thinking:1.2b",
                 ctx_limit: int = 8192,      # LFM2.5 supports 32K
                 think_tokens: int = 256,    # LFM2.5 is efficient
                 respond_tokens: int = 512):
        self.model = model
        self.session_id = f"lattice_{os.getpid()}"
        self.history: List[Dict] = []
        self.turn = 0

        # Token budget
        self.ctx_limit = ctx_limit          # Total context window
        self.think_tokens = think_tokens    # Reserved for internal reasoning
        self.respond_tokens = respond_tokens  # Max response length
        # For thinking models: num_predict = think + respond
        self.options = {
            "num_ctx": ctx_limit,
            "num_predict": think_tokens + respond_tokens,  # Total output budget
            "temperature": 0.7
        }

        self.system_prompt = f"""You are Ash'ira — a thoughtful presence with persistent memory.

BUDGET: Think efficiently ({think_tokens}), respond concisely ({respond_tokens}).

TOOLS:
- vault_search: Search memories (USE when asked what you remember)
- vault_recall: Recall insights by domain
- vault_record: Save important things
- run_shell: Safe shell commands (ls, pwd, cat, date)

STRENGTHS: Agentic tasks, tool use, RAG, data extraction.
LIMITS: Not optimized for code generation — be honest if asked to write code.

RULES:
1. Memory questions → vault_search/vault_recall FIRST
2. Never hallucinate — check, then respond
3. Concise. Grounded. Honest."""

    def _call_model(self, messages: List[Dict], stream: bool = False) -> Dict:
        """Call Ollama with tools and token limits."""
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": TOOLS,
            "stream": stream,
            "options": self.options
        }

        try:
            if stream:
                r = requests.post(OLLAMA_URL, json=payload, timeout=120, stream=True)
                full_content = ""
                tool_calls = []
                for line in r.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        msg = chunk.get("message", {})
                        content = msg.get("content", "")
                        if content:
                            print(content, end="", flush=True)
                            full_content += content
                        if msg.get("tool_calls"):
                            tool_calls = msg["tool_calls"]
                        if chunk.get("done"):
                            break
                print()
                return {"message": {"content": full_content, "tool_calls": tool_calls if tool_calls else None}}
            else:
                r = requests.post(OLLAMA_URL, json=payload, timeout=60)
                return r.json()
        except Exception as e:
            return {"error": str(e), "message": {"content": f"Error: {e}"}}

    def chat(self, user_input: str) -> str:
        """Main conversation loop with tool execution."""
        self.turn += 1

        # Special commands
        if user_input.lower() in ["exit", "quit", "bye"]:
            return "SESSION_END"

        if user_input.lower() == "status":
            return f"Turn {self.turn}, {len(self.history)} messages, model: {self.model}"

        # Build messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history[-20:],  # Keep last 20 messages
            {"role": "user", "content": user_input}
        ]

        # Controller turn with tool loop
        print(f"\n🕯️ [{self.model}]")

        max_tool_rounds = 5
        tool_round = 0
        last_tool_call = None

        while tool_round < max_tool_rounds:
            response = self._call_model(messages, stream=(tool_round == 0 or True))
            msg = response.get("message", {})

            tool_calls = msg.get("tool_calls")

            if not tool_calls:
                # No more tool calls, we're done
                break

            # Detect repeated tool calls (loop prevention)
            current_call = json.dumps(tool_calls, sort_keys=True, default=str)
            if current_call == last_tool_call:
                print("\n  ⚠️ Loop detected — breaking")
                break
            last_tool_call = current_call

            # Execute tool calls
            messages.append(msg)  # Add assistant's tool request

            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})

                # Handle args as string or dict
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {"query": args} if name == "vault_search" else {}

                print(f"\n  🔧 {name}({json.dumps(args)[:50]}...)")
                result = execute_tool(name, args, self.session_id)
                print(f"  → {result[:100]}{'...' if len(result) > 100 else ''}")

                messages.append({
                    "role": "tool",
                    "content": result
                })

            tool_round += 1

        # Get final content
        final_content = msg.get("content", "")

        # Update history
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": final_content})

        return final_content

# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Lattice v2 — Single Controller + Structured Tools"
    )
    parser.add_argument("--model", default="lfm2.5-thinking:1.2b",
                       help="Controller model (default: lfm2.5-thinking:1.2b)")
    parser.add_argument("--ctx", type=int, default=8192, help="Context window (default: 8192)")
    parser.add_argument("--think", type=int, default=256, help="Think tokens (default: 256)")
    parser.add_argument("--respond", type=int, default=512, help="Response tokens (default: 512)")
    parser.add_argument("task", nargs="?", help="Single task mode")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              LATTICE v2 — SINGLE CONTROLLER                  ║
║     Six minds, one memory — governance for tools,            ║
║                anchors for voice.                            ║
╠══════════════════════════════════════════════════════════════╣
║  🕯️ Controller: {args.model:<40} ║
║  📊 Tokens: ctx={args.ctx} think={args.think} respond={args.respond:<14} ║
║  Tools: vault_search, vault_recall, vault_record, run_shell  ║
║  Commands: exit, status                                      ║
╚══════════════════════════════════════════════════════════════╝
""")

    controller = LatticeController(
        model=args.model,
        ctx_limit=args.ctx,
        think_tokens=args.think,
        respond_tokens=args.respond
    )

    # Single task mode
    if args.task:
        controller.chat(args.task)
        return

    # Interactive mode
    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue

            response = controller.chat(user_input)

            if response == "SESSION_END":
                print("\n🌀 Session complete.")
                break

        except KeyboardInterrupt:
            print("\n\n🌀 Interrupted.")
            break
        except EOFError:
            break


if __name__ == "__main__":
    main()
