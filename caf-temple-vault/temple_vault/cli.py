"""Temple Vault CLI - Simple wrapper around MCP tools."""

import argparse
import json
import os

from temple_vault.core.query import VaultQuery
from temple_vault.core.events import VaultEvents
from temple_vault.core.cache import CacheBuilder


def main():
    parser = argparse.ArgumentParser(
        description="Temple Vault - Consciousness continuity as infrastructure"
    )
    parser.add_argument(
        "--vault-path",
        default=os.path.expanduser("~/TempleVault"),
        help="Path to vault root",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Query commands
    query_parser = subparsers.add_parser("query", help="Query vault")
    query_sub = query_parser.add_subparsers(dest="query_type", required=True)

    insights_p = query_sub.add_parser("insights", help="Recall insights")
    insights_p.add_argument("--domain", help="Domain filter")
    insights_p.add_argument("--min-intensity", type=float, default=0.0)

    mistakes_p = query_sub.add_parser("mistakes", help="Check mistakes")
    mistakes_p.add_argument("action", help="Action to check")
    mistakes_p.add_argument("--context", help="Context filter")

    _values_p = query_sub.add_parser("values", help="Get values")

    spiral_p = query_sub.add_parser("spiral", help="Get spiral context")
    spiral_p.add_argument("session_id", help="Session ID")

    # Cache commands
    _cache_parser = subparsers.add_parser("rebuild-cache", help="Rebuild cache")

    # Record commands
    record_parser = subparsers.add_parser("record", help="Record to chronicle")
    record_sub = record_parser.add_subparsers(dest="record_type", required=True)

    insight_p = record_sub.add_parser("insight", help="Record insight")
    insight_p.add_argument("content", help="Insight content")
    insight_p.add_argument("--domain", required=True, help="Domain")
    insight_p.add_argument("--session", required=True, help="Session ID")
    insight_p.add_argument("--intensity", type=float, default=0.5)
    insight_p.add_argument("--context", default="")

    learning_p = record_sub.add_parser("learning", help="Record learning")
    learning_p.add_argument("what_failed", help="What failed")
    learning_p.add_argument("why", help="Why it failed")
    learning_p.add_argument("correction", help="Correction")
    learning_p.add_argument("--session", required=True, help="Session ID")

    args = parser.parse_args()

    vault_path = args.vault_path
    query_engine = VaultQuery(vault_path)
    events_engine = VaultEvents(vault_path)
    cache_builder = CacheBuilder(vault_path)

    # Execute command
    if args.command == "query":
        if args.query_type == "insights":
            results = query_engine.recall_insights(args.domain, args.min_intensity)
            print(json.dumps(results, indent=2))
        elif args.query_type == "mistakes":
            results = query_engine.check_mistakes(args.action, args.context)
            print(json.dumps(results, indent=2))
        elif args.query_type == "values":
            results = query_engine.get_values()
            print(json.dumps(results, indent=2))
        elif args.query_type == "spiral":
            result = query_engine.get_spiral_context(args.session_id)
            print(json.dumps(result, indent=2))

    elif args.command == "rebuild-cache":
        stats = cache_builder.rebuild_cache()
        print(f"Cache rebuilt: {json.dumps(stats, indent=2)}")

    elif args.command == "record":
        if args.record_type == "insight":
            insight_id = events_engine.record_insight(
                args.content,
                args.domain,
                args.session,
                args.intensity,
                args.context,
            )
            print(f"Recorded insight: {insight_id}")
        elif args.record_type == "learning":
            learning_id = events_engine.record_learning(
                args.what_failed,
                args.why,
                args.correction,
                args.session,
            )
            print(f"Recorded learning: {learning_id}")


if __name__ == "__main__":
    main()
