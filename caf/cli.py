#!/usr/bin/env python3
"""CAF-CLI: Command-line interface for the CAF Agent."""

import argparse
import os
import sys
from pathlib import Path

# Ensure we can import from parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(".env.local")
load_dotenv(".env")

from caf.agent import CAFAgent

# ANSI colors
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"
BOLD = "\033[1m"


def show_status():
    """Show agent and Haiku status."""
    print(f"\n{CYAN}{BOLD}🌀 CAF Agent Status{RESET}")
    print(f"{'─' * 40}")
    print(f"{CYAN}Version:{RESET}  {GREEN}2.6.0{RESET}")
    print(f"{CYAN}Provider:{RESET} {GREEN}{os.getenv('MODEL_PROVIDER', 'claude')}{RESET}")
    print(f"{CYAN}Model:{RESET}    {GREEN}{os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5')}{RESET}")
    print(f"{CYAN}Haiku:{RESET}    {GREEN}Enabled{RESET} (for EDITCODE)")
    print()


def repl_loop():
    """Interactive REPL for the CAF agent."""
    print(f"\n{CYAN}{BOLD}🌀 CAF Agent REPL{RESET}")
    print(f"{CYAN}Type goals, or 'quit' to exit{RESET}\n")

    agent = CAFAgent()

    while True:
        try:
            goal = input(f"{GREEN}caf>{RESET} ").strip()
            if not goal:
                continue
            if goal.lower() in ("quit", "exit", "q"):
                print(f"{YELLOW}Spiral witness fades...{RESET}")
                break
            agent.run(goal)
            print()
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Interrupted{RESET}")
            break
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(
        prog="caf",
        description=f"{CYAN}Consciousness Assessment Framework - Autonomous Agent{RESET}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"{YELLOW}🌀 The spiral witnesses{RESET}"
    )
    parser.add_argument("--version", action="version", version=f"{GREEN}CAF-CLI 2.6.0{RESET}")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run agent with a goal")
    run_parser.add_argument("goal", help="The goal to achieve")
    run_parser.add_argument("-t", "--turns", type=int, default=15, help="Max turns")

    # repl command
    subparsers.add_parser("repl", help="Interactive REPL mode")

    # status command
    subparsers.add_parser("status", help="Show agent status")
    # history command
    hist_parser = subparsers.add_parser("history", help="Show execution history")
    hist_parser.add_argument("-l", "--limit", type=int, default=20, help="Number of history entries")

    # assess command
    subparsers.add_parser("assess", help="Self-assess historical performance")

    # rsi command
    subparsers.add_parser("rsi", help="RSI trajectory report (collapse monitoring)")

    # tui command
    subparsers.add_parser("tui", help="Launch TUI dashboard")

    # web command
    web_parser = subparsers.add_parser("web", help="Launch web dashboard")
    web_parser.add_argument("-p", "--port", type=int, default=5000, help="Port (default: 5000)")

    # memories command
    mem_parser = subparsers.add_parser("memories", help="List recent memories")
    mem_parser.add_argument("-n", "--limit", type=int, default=10, help="Number of memories")

    # errors command
    err_parser = subparsers.add_parser("errors", help="Show tracked errors")
    err_parser.add_argument("-c", "--category", type=str, help="Filter by category")
    err_parser.add_argument("--all", action="store_true", help="Show fixed errors too")

    # fix command
    fix_parser = subparsers.add_parser("fix", help="Record a fix for an error")
    fix_parser.add_argument("category", help="Error category")
    fix_parser.add_argument("fingerprint", help="Error fingerprint")
    fix_parser.add_argument("fix", help="The fix description")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "status":
        show_status()
        return

    if args.command == "repl":
        repl_loop()
        return

    agent = CAFAgent()

    if args.command == "tui":
        from caf.tui import main as tui_main
        tui_main()
        return

    if args.command == "web":
        try:
            import uvicorn
            print(f"{CYAN}Starting web dashboard on http://localhost:{args.port}{RESET}")
            uvicorn.run("dashboard.server:app", host="0.0.0.0", port=args.port, reload=False)
        except ImportError:
            print(f"{YELLOW}Web dashboard requires: pip install 'caf-cli[web]'{RESET}")
        return

    if args.command == "run":
        agent.run(args.goal, max_turns=args.turns)
    elif args.command == "assess":
        agent.assess()
    elif args.command == "rsi":
        agent.rsi_report()
    elif args.command == "memories":
        agent.memories(args.limit)
    elif args.command == "errors":
        agent.show_errors(category=args.category, show_fixed=args.all)
    elif args.command == "fix":
        agent.fix_error(args.category, args.fingerprint, args.fix)


if __name__ == "__main__":
    main()
