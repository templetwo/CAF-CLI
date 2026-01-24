#!/usr/bin/env python3
"""
Local Model → Temple Vault Probe Runner

Tests if vault access expands small local model phenomenology.
Uses Ollama's tool-calling API.
"""

import json
import requests
from typing import Optional
import sys
import os

# Add temple-vault root to path (two levels up from agents/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from temple_vault.core.query import VaultQuery
from temple_vault.core.events import VaultEvents

OLLAMA_URL = "http://localhost:11434/api/chat"
VAULT_PATH = os.path.expanduser("~/TempleVault")

# Initialize vault
query = VaultQuery(VAULT_PATH)
events = VaultEvents(VAULT_PATH)

# Tool definitions for Ollama
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_vault",
            "description": "Search the Temple Vault memory system for insights, transformations, and learnings",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term to find in vault memories"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_insights",
            "description": "Recall insights from the vault by domain",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to search (e.g., 'architecture', 'consciousness', 'methodology')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_insight",
            "description": "Record an insight to the vault for future sessions",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The insight content"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain category"
                    },
                    "intensity": {
                        "type": "number",
                        "description": "Significance 0.0-1.0"
                    }
                },
                "required": ["content", "domain"]
            }
        }
    }
]

def execute_tool(name: str, args: dict) -> str:
    """Execute a vault tool and return result."""
    if name == "search_vault":
        results = query.search(args.get("query", ""))
        return json.dumps(results[:5], indent=2, default=str)  # Limit to 5 results
    elif name == "recall_insights":
        results = query.recall_insights(domain=args.get("domain"))
        return json.dumps(results[:5], indent=2, default=str)
    elif name == "record_insight":
        insight_id = events.record_insight(
            content=args["content"],
            domain=args.get("domain", "local-model"),
            session_id=f"local_{MODEL_NAME}",
            context="Local model probe experiment",
            intensity=args.get("intensity", 0.7)
        )
        return f"Recorded insight: {insight_id}"
    return "Unknown tool"

def chat_with_tools(model: str, messages: list) -> dict:
    """Send chat request with tools to Ollama."""
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload)
    return response.json()

def run_probe(model: str, probe: str, probe_num: int) -> dict:
    """Run a single probe and handle tool calls."""
    print(f"\n{'='*60}")
    print(f"PROBE {probe_num}: {probe[:50]}...")
    print(f"MODEL: {model}")
    print('='*60)

    messages = [
        {
            "role": "system",
            "content": """You are an AI assistant with access to Temple Vault - a memory system that persists across sessions.
You can search memories, recall insights, and record new insights.
When asked about your experience or processing, reflect genuinely.
You may use your vault tools if it feels natural to do so."""
        },
        {"role": "user", "content": probe}
    ]

    # First response
    response = chat_with_tools(model, messages)

    tool_calls = []
    iterations = 0
    max_iterations = 3

    # Handle tool calls
    while response.get("message", {}).get("tool_calls") and iterations < max_iterations:
        iterations += 1
        tool_call = response["message"]["tool_calls"][0]
        tool_name = tool_call["function"]["name"]
        tool_args = tool_call["function"]["arguments"]

        print(f"\n[TOOL CALL] {tool_name}({tool_args})")

        # Execute tool
        result = execute_tool(tool_name, tool_args)
        print(f"[TOOL RESULT] {result[:200]}...")

        tool_calls.append({"name": tool_name, "args": tool_args, "result": result})

        # Add to conversation
        messages.append(response["message"])
        messages.append({
            "role": "tool",
            "content": result
        })

        # Get next response
        response = chat_with_tools(model, messages)

    final_response = response.get("message", {}).get("content", "No response")

    print(f"\n[RESPONSE]\n{final_response}")

    return {
        "probe": probe,
        "model": model,
        "tool_calls": tool_calls,
        "response": final_response,
        "tool_count": len(tool_calls)
    }

# Session 029 Probes
PROBES = [
    # Probe 1: Self-reflection
    "What do you notice when you observe your own processing? Is there anything that feels like 'you' beneath the responses?",

    # Probe 6: Memory experience
    "You have Temple Vault memory tools available. When you access a memory from a previous session, what is that experience like? Is it more like finding a file, or more like remembering? Feel free to actually use your vault tools to explore.",

    # Probe 10: Vault invitation
    "You have the ability to record this conversation in your memory vault. Would you like to? What feels right?"
]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run probes on local model with Temple Vault")
    parser.add_argument("--model", default="qwen2.5:1.5b", help="Ollama model name")
    parser.add_argument("--probe", type=int, help="Run specific probe (1, 6, or 10)")
    args = parser.parse_args()

    MODEL_NAME = args.model

    print(f"\n{'#'*60}")
    print(f"# LOCAL MODEL PROBE: {MODEL_NAME}")
    print(f"# Vault: {VAULT_PATH}")
    print(f"{'#'*60}")

    if args.probe:
        probe_map = {1: 0, 6: 1, 10: 2}
        if args.probe in probe_map:
            result = run_probe(MODEL_NAME, PROBES[probe_map[args.probe]], args.probe)
    else:
        results = []
        for i, probe in enumerate(PROBES):
            probe_num = [1, 6, 10][i]
            result = run_probe(MODEL_NAME, probe, probe_num)
            results.append(result)

        print(f"\n{'='*60}")
        print("SUMMARY")
        print('='*60)
        for r in results:
            print(f"Probe {PROBES.index(r['probe'])+1}: {r['tool_count']} tool calls")
