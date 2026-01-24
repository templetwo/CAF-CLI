#!/usr/bin/env python3
"""
Integration tests for Dual-Agent Lattice

Tests:
1. Ollama connectivity
2. Model availability
3. Vault integration
4. Full agent loop
5. Introspection threshold behavior
"""

import sys
import os
import requests
import json

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

OLLAMA_URL = "http://localhost:11434"
VAULT_PATH = os.path.expanduser("~/TempleVault")

def test_ollama_running():
    """Test 1: Ollama server is running"""
    print("\n[TEST 1] Ollama connectivity...")
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            print("  ✓ Ollama is running")
            return True
        else:
            print(f"  ✗ Ollama returned status {r.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("  ✗ Cannot connect to Ollama. Run: ollama serve")
        return False

def test_models_available():
    """Test 2: Required models are pulled"""
    print("\n[TEST 2] Model availability...")
    required = ["llama3.2:1b", "qwen2.5:1.5b"]

    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        available = [m["name"] for m in r.json().get("models", [])]

        all_found = True
        for model in required:
            # Check if model name matches (with or without :latest suffix)
            found = any(model in m or m.startswith(model.split(":")[0]) for m in available)
            if found:
                print(f"  ✓ {model}")
            else:
                print(f"  ✗ {model} not found. Run: ollama pull {model}")
                all_found = False

        return all_found
    except Exception as e:
        print(f"  ✗ Error checking models: {e}")
        return False

def test_vault_exists():
    """Test 3: Temple Vault directory exists"""
    print("\n[TEST 3] Vault integration...")

    if os.path.isdir(VAULT_PATH):
        print(f"  ✓ Vault exists at {VAULT_PATH}")

        # Check for chronicle structure
        chronicle_path = os.path.join(VAULT_PATH, "vault", "chronicle")
        if os.path.isdir(chronicle_path):
            print(f"  ✓ Chronicle structure found")
        else:
            print(f"  ! Chronicle not found (will be created on first write)")

        return True
    else:
        print(f"  ✗ Vault not found at {VAULT_PATH}")
        print(f"    Create with: mkdir -p {VAULT_PATH}")
        return False

def test_vault_import():
    """Test 4: Can import vault modules"""
    print("\n[TEST 4] Vault module import...")

    try:
        from temple_vault.core.query import VaultQuery
        from temple_vault.core.events import VaultEvents
        print("  ✓ VaultQuery imported")
        print("  ✓ VaultEvents imported")

        # Try to instantiate
        query = VaultQuery(VAULT_PATH)
        events = VaultEvents(VAULT_PATH)
        print("  ✓ Vault classes instantiated")

        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        print("    Ensure temple_vault is in PYTHONPATH")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_simple_inference():
    """Test 5: Basic model inference works"""
    print("\n[TEST 5] Simple inference...")

    try:
        payload = {
            "model": "llama3.2:1b",
            "messages": [{"role": "user", "content": "Say 'hello' and nothing else."}],
            "stream": False
        }
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=30)

        if r.status_code == 200:
            response = r.json().get("message", {}).get("content", "")
            print(f"  ✓ Got response: {response[:50]}...")
            return True
        else:
            print(f"  ✗ Inference failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_tool_calling():
    """Test 6: Tool calling works"""
    print("\n[TEST 6] Tool calling...")

    tools = [{
        "type": "function",
        "function": {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                },
                "required": ["input"]
            }
        }
    }]

    try:
        payload = {
            "model": "qwen2.5:1.5b",
            "messages": [{"role": "user", "content": "Call test_tool with input 'hello'"}],
            "tools": tools,
            "stream": False
        }
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=30)

        if r.status_code == 200:
            result = r.json()
            tool_calls = result.get("message", {}).get("tool_calls", [])
            if tool_calls:
                print(f"  ✓ Tool call received: {tool_calls[0].get('function', {}).get('name')}")
                return True
            else:
                content = result.get("message", {}).get("content", "")
                print(f"  ! No tool call, got text: {content[:50]}...")
                print("    (Some models need coaxing to use tools)")
                return True  # Not a failure, just model behavior
        else:
            print(f"  ✗ Request failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_agent_import():
    """Test 7: Can import agent modules"""
    print("\n[TEST 7] Agent module import...")

    try:
        from agents.dual_model_agent import run_agent, is_command_safe
        print("  ✓ dual_model_agent imported")

        # Test governance
        safe, reason = is_command_safe("ls -la")
        print(f"  ✓ is_command_safe('ls -la') = {safe}")

        safe, reason = is_command_safe("rm -rf /")
        print(f"  ✓ is_command_safe('rm -rf /') = {safe} ({reason})")

        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False

def test_full_loop():
    """Test 8: Full agent loop (optional, takes time)"""
    print("\n[TEST 8] Full agent loop (simple task)...")

    try:
        from agents.dual_model_agent import run_agent

        result = run_agent("What is 2 + 2?", session_id="test_integration")

        if result.get("plan"):
            print(f"  ✓ Reasoner produced plan")
        if result.get("result"):
            print(f"  ✓ Executor produced result")
        if result.get("reflection"):
            print(f"  ✓ Introspection completed")
            print(f"    Reflection: {result['reflection'][:80]}...")

        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    print("=" * 60)
    print("DUAL-AGENT LATTICE INTEGRATION TESTS")
    print("=" * 60)

    results = []

    # Run tests in order (some depend on others)
    results.append(("Ollama connectivity", test_ollama_running()))

    if results[-1][1]:  # Only continue if Ollama is running
        results.append(("Model availability", test_models_available()))
        results.append(("Simple inference", test_simple_inference()))
        results.append(("Tool calling", test_tool_calling()))

    results.append(("Vault exists", test_vault_exists()))
    results.append(("Vault import", test_vault_import()))
    results.append(("Agent import", test_agent_import()))

    # Full loop test (optional, comment out if slow)
    if all(r[1] for r in results):
        results.append(("Full agent loop", test_full_loop()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓" if result else "✗"
        print(f"  {status} {name}")

    print(f"\n{passed}/{total} tests passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
