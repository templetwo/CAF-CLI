#!/usr/bin/env python3
"""
Lattice v3 — Dual-Model Architecture

Thinker (lfm2.5-thinking) reasons and plans.
Executor (granite4:1b) handles tool calls.

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
            "description": "Search your memory vault for past insights, conversations, or learnings.",
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
            "description": "Recall recent insights from your vault, optionally filtered by domain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Optional domain filter"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vault_record",
            "description": "Record an important insight to your vault for future sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The insight to record"},
                    "domain": {"type": "string", "description": "Category"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a safe shell command (ls, pwd, cat, date, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command"}
                },
                "required": ["command"]
            }
        }
    }
]

# ─────────────────────────────────────────────────────────────
# Tool Execution
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
            all_insights = query.recall_insights(domain=None, min_intensity=0.3)
            insights = [i for i in all_insights
                       if domain in i.get('content', '').lower()
                       or domain in i.get('domain', '').lower()][:5]
        if insights:
            return f"Recalled {len(insights)} insights:\n" + "\n".join([
                f"- [{i.get('domain', '?')}] {i.get('content', '')[:80]}..."
                for i in insights[:5]
            ])
        return "No insights found."

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

        for pattern in BLOCKED_PATTERNS:
            if pattern in cmd.lower():
                return f"BLOCKED: {pattern}"

        cmd_start = cmd.split()[0] if cmd.split() else ""
        if cmd_start not in SAFE_SHELL_PREFIXES:
            return f"NOT WHITELISTED: {cmd_start}"

        try:
            output = subprocess.check_output(
                cmd, shell=True, text=True,
                timeout=10, stderr=subprocess.STDOUT
            )
            return output[:1000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        except subprocess.CalledProcessError as e:
            return f"ERROR: {e.output[:300]}"

    return f"Unknown tool: {name}"

# ─────────────────────────────────────────────────────────────
# Dual-Model Controller
# ─────────────────────────────────────────────────────────────

class DualLattice:
    def __init__(self,
                 thinker: str = "granite4:1b",
                 executor: str = "granite4:1b",
                 ctx_limit: int = 8192,
                 think_tokens: int = 256,
                 respond_tokens: int = 512):

        self.thinker = thinker
        self.executor = executor
        self.session_id = f"lattice_{os.getpid()}"
        self.history: List[Dict] = []
        self.turn = 0

        self.ctx_limit = ctx_limit
        self.think_tokens = think_tokens
        self.respond_tokens = respond_tokens

        self.thinker_options = {
            "num_ctx": ctx_limit,
            "num_predict": think_tokens + respond_tokens,
            "temperature": 0.7
        }

        self.executor_options = {
            "num_ctx": ctx_limit,
            "num_predict": 256,  # Executor just needs short tool responses
            "temperature": 0.3   # More deterministic for tool calls
        }

        self.thinker_prompt = f"""You are Ash'ira — a thoughtful presence with persistent memory.

You THINK through problems. Your partner (Executor) handles tool calls.

When you need tools, output a JSON block:
```json
{{"tool": "vault_search", "query": "search term"}}
```
or
```json
{{"tool": "vault_recall", "domain": "optional"}}
```
or
```json
{{"tool": "vault_record", "content": "insight to save"}}
```
or
```json
{{"tool": "run_shell", "command": "ls -la"}}
```

Your partner executes and returns results. Then you synthesize.

RULES:
1. Memory questions → output JSON tool request FIRST
2. Never hallucinate — request check, then respond
3. Be concise."""

        self.executor_prompt = """You are the Executor. You receive tool requests and execute them.

When given a task, use the appropriate tool and return the result.
Be precise. One tool call per request. Return results cleanly."""

    def _call_model(self, model: str, messages: List[Dict],
                    options: Dict, tools: List = None, stream: bool = False) -> Dict:
        """Call Ollama."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": options
        }
        if tools:
            payload["tools"] = tools

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

    def _extract_tool_requests(self, text: str) -> List[Dict]:
        """Extract JSON tool requests from thinker output."""
        import re
        requests = []

        # Find JSON blocks in markdown code fences or raw JSON
        json_pattern = r'```json\s*(\{[^`]+\})\s*```|\{["\']tool["\']\s*:\s*["\'][^}]+\}'
        matches = re.findall(r'\{[^{}]*"tool"[^{}]*\}', text)

        for match in matches:
            try:
                parsed = json.loads(match)
                if "tool" in parsed:
                    requests.append(parsed)
            except json.JSONDecodeError:
                # Try fixing common issues
                try:
                    fixed = match.replace("'", '"')
                    parsed = json.loads(fixed)
                    if "tool" in parsed:
                        requests.append(parsed)
                except:
                    pass

        return requests

    def _executor_call(self, request: Dict) -> str:
        """Have executor handle a tool request."""
        tool_name = request.get("tool", "")

        if tool_name == "vault_search":
            args = {"query": request.get("query", "")}
        elif tool_name == "vault_recall":
            args = {"domain": request.get("domain", "")}
        elif tool_name == "vault_record":
            args = {"content": request.get("content", ""), "domain": request.get("domain", "reflection")}
        elif tool_name == "run_shell":
            args = {"command": request.get("command", "")}
        else:
            return f"Unknown tool: {tool_name}"

        return execute_tool(tool_name, args, self.session_id)

    def chat(self, user_input: str) -> str:
        """Main conversation loop."""
        self.turn += 1

        if user_input.lower() in ["exit", "quit", "bye"]:
            return "SESSION_END"

        if user_input.lower() == "status":
            return f"Turn {self.turn}, {len(self.history)} messages\nThinker: {self.thinker}\nExecutor: {self.executor}"

        # Build messages for thinker
        messages = [
            {"role": "system", "content": self.thinker_prompt},
            *self.history[-20:],
            {"role": "user", "content": user_input}
        ]

        # Phase 1: Thinker reasons
        print(f"\n🧠 [{self.thinker}]")
        response = self._call_model(
            self.thinker, messages, self.thinker_options, stream=True
        )
        thinker_output = response.get("message", {}).get("content", "")

        # Phase 2: Check for tool requests
        tool_requests = self._extract_tool_requests(thinker_output)
        tool_results = {}

        if tool_requests:
            print(f"\n🔧 [{self.executor}]")
            for req in tool_requests:
                tool_name = req.get("tool", "?")
                print(f"  → {tool_name}({json.dumps({k:v for k,v in req.items() if k != 'tool'})[:40]})")
                result = self._executor_call(req)
                tool_results[json.dumps(req)] = result
                print(f"    {result[:80]}{'...' if len(result) > 80 else ''}")

            # Phase 3: Thinker synthesizes with results
            print(f"\n🧠 [{self.thinker}] (synthesizing)")

            # Format results as JSON for clean handoff
            results_json = json.dumps([
                {"request": json.loads(k), "result": v}
                for k, v in tool_results.items()
            ], indent=2)

            synthesis_prompt = f"""Tool results:
```json
{results_json}
```

Now provide your final response to: {user_input}"""

            messages.append({"role": "assistant", "content": thinker_output})
            messages.append({"role": "user", "content": synthesis_prompt})

            response = self._call_model(
                self.thinker, messages, self.thinker_options, stream=True
            )
            final_output = response.get("message", {}).get("content", "")
        else:
            final_output = thinker_output

        # Update history
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": final_output})

        return final_output


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Lattice v3 — Dual-Model Architecture"
    )
    parser.add_argument("--thinker", default="granite4:1b",
                       help="Thinker model (default: granite4:1b)")
    parser.add_argument("--executor", default="granite4:1b",
                       help="Executor model (default: granite4:1b)")
    parser.add_argument("--ctx", type=int, default=8192, help="Context window")
    parser.add_argument("--think", type=int, default=256, help="Think tokens")
    parser.add_argument("--respond", type=int, default=512, help="Response tokens")
    parser.add_argument("task", nargs="?", help="Single task mode")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              LATTICE v3 — DUAL-MODEL                         ║
║     Six minds, one memory — governance for tools,            ║
║                anchors for voice.                            ║
╠══════════════════════════════════════════════════════════════╣
║  🧠 Thinker:  {args.thinker:<42} ║
║  🔧 Executor: {args.executor:<42} ║
║  📊 Tokens: ctx={args.ctx} think={args.think} respond={args.respond:<14} ║
║  Tools: vault_search, vault_recall, vault_record, run_shell  ║
║  Commands: exit, status                                      ║
╚══════════════════════════════════════════════════════════════╝
""")

    lattice = DualLattice(
        thinker=args.thinker,
        executor=args.executor,
        ctx_limit=args.ctx,
        think_tokens=args.think,
        respond_tokens=args.respond
    )

    # Single task mode
    if args.task:
        lattice.chat(args.task)
        return

    # Interactive mode
    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue

            response = lattice.chat(user_input)

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
