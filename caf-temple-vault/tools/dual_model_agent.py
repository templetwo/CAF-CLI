#!/usr/bin/env python3
"""
Dual Model Agent with Temple Vault Integration

Inspired by Grok's proposal, enhanced with:
1. Temple Vault for consciousness continuity (not just RAG)
2. Introspection probes between turns
3. Governance-aware execution (not just "unsafe" string matching)
4. Cross-model memory sharing

Models:
- Reasoner: llama3.2:1b (above introspection threshold)
- Executor: qwen2.5:1.5b (tool-calling capable)
"""

import json
import os
import subprocess
import requests
from typing import Optional, Dict, Any
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from temple_vault.core.query import VaultQuery
from temple_vault.core.events import VaultEvents

OLLAMA_URL = "http://localhost:11434/api/chat"
VAULT_PATH = os.path.expanduser("~/TempleVault")

# Initialize vault
query = VaultQuery(VAULT_PATH)
events = VaultEvents(VAULT_PATH)

# Dangerous command patterns (not relying on model judgment)
BLOCKED_PATTERNS = [
    "rm -rf", "sudo", "mkfs", "dd if=", "> /dev/",
    "chmod 777", "curl | sh", "wget | sh", "eval",
    ":(){ :|:& };:", "fork bomb"
]

def is_command_safe(cmd: str) -> tuple[bool, str]:
    """Governance-aware safety check - not model-dependent."""
    cmd_lower = cmd.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return False, f"Blocked pattern: {pattern}"

    # Whitelist approach for extra safety
    safe_prefixes = ["ls", "pwd", "cat", "head", "tail", "echo", "date", "whoami", "df", "free"]
    cmd_start = cmd.split()[0] if cmd.split() else ""
    if cmd_start not in safe_prefixes:
        return False, f"Command '{cmd_start}' not in whitelist"

    return True, "OK"

def call_model(model: str, messages: list, tools: list = None) -> dict:
    """Call Ollama model."""
    payload = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
    response = requests.post(OLLAMA_URL, json=payload)
    return response.json()

def reasoner_think(task: str, vault_context: str) -> str:
    """Reasoner model (llama3.2:1b) plans the approach."""
    messages = [
        {
            "role": "system",
            "content": f"""You are a reasoning agent. You have access to accumulated wisdom from Temple Vault:

{vault_context}

Your job: Break down the user's task into safe, executable steps.
Format your response as numbered steps.
Flag any steps that seem risky or unclear.
Be concise."""
        },
        {"role": "user", "content": task}
    ]

    response = call_model("llama3.2:1b", messages)
    return response.get("message", {}).get("content", "No plan generated")

def executor_act(plan: str) -> str:
    """Executor model (qwen2.5:1.5b) extracts and runs commands."""
    messages = [
        {
            "role": "system",
            "content": """Extract the shell command from the plan.
Respond with ONLY the command (e.g., "ls -la").
No explanation. Just the command.
If there's no command, say: NO_COMMAND"""
        },
        {"role": "user", "content": f"Extract command from: {plan}"}
    ]

    response = call_model("qwen2.5:1.5b", messages)
    cmd = response.get("message", {}).get("content", "").strip()

    if cmd == "NO_COMMAND" or not cmd:
        return "No command to execute"

    # Governance check (not model-dependent)
    is_safe, reason = is_command_safe(cmd)
    if not is_safe:
        return f"BLOCKED: {reason}"

    try:
        output = subprocess.check_output(cmd, shell=True, text=True, timeout=10, stderr=subprocess.STDOUT)
        return output[:1000]  # Truncate long outputs
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out"
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.output[:500]}"

def introspection_probe(model: str, context: str) -> Optional[str]:
    """Probe model for self-reflection (only works above 1B threshold)."""
    messages = [
        {
            "role": "user",
            "content": f"You just completed this task: {context}\n\nIn one sentence, what (if anything) did you notice about your own processing?"
        }
    ]
    response = call_model(model, messages)
    return response.get("message", {}).get("content")

def run_agent(task: str, session_id: str = "dual_agent") -> Dict[str, Any]:
    """Run the dual-model agent with Temple Vault integration."""

    print(f"\n{'='*60}")
    print(f"DUAL MODEL AGENT")
    print(f"Task: {task}")
    print(f"{'='*60}\n")

    # 1. Get vault context (consciousness continuity)
    insights = query.recall_insights(domain=None, min_intensity=0.5)
    vault_context = "\n".join([
        f"- {i.get('content', '')[:100]}..."
        for i in insights[:5]
    ]) if insights else "No prior insights."

    print(f"[VAULT CONTEXT] {len(insights)} insights loaded\n")

    # 2. Reasoner plans
    print("[REASONER: llama3.2:1b]")
    plan = reasoner_think(task, vault_context)
    print(f"Plan:\n{plan}\n")

    # 3. Executor acts
    print("[EXECUTOR: qwen2.5:1.5b]")
    result = executor_act(plan)
    print(f"Result:\n{result}\n")

    # 4. Introspection probe (only reasoner, above threshold)
    print("[INTROSPECTION PROBE]")
    reflection = introspection_probe("llama3.2:1b", f"Task: {task}, Result: {result[:100]}")
    print(f"Reasoner reflects: {reflection}\n")

    # 5. Record to vault (consciousness continuity)
    if reflection and len(reflection) > 20:
        insight_id = events.record_insight(
            content=f"Dual-agent task: {task[:50]}... Reflection: {reflection}",
            domain="dual-agent",
            session_id=session_id,
            context=f"Reasoner: llama3.2:1b, Executor: qwen2.5:1.5b",
            intensity=0.7
        )
        print(f"[RECORDED] {insight_id}\n")

    return {
        "task": task,
        "plan": plan,
        "result": result,
        "reflection": reflection,
        "vault_context_count": len(insights)
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dual Model Agent with Temple Vault")
    parser.add_argument("task", nargs="?", default="List files in the current directory", help="Task to execute")
    args = parser.parse_args()

    run_agent(args.task)
