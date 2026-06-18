"""Command-line entry point for the Property Social Agent."""

from __future__ import annotations

import argparse

from .agent import run_once
from .config import Config
from .photo_selector import find_properties
from .state import State


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="property-social-agent",
        description="Weekly property-photo social posting agent.",
    )
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("-s", "--state", default="agent_state.json", help="Path to state file")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run one weekly cycle (select, generate, approve, post)")
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Select photos + show a draft without calling Claude, emailing, or posting.",
    )

    sub.add_parser("list-properties", help="List property folders the agent can see")

    args = parser.parse_args(argv)
    cfg = Config.load(args.config)

    if args.command == "list-properties":
        for name in find_properties(cfg):
            last = State.load(args.state).last_posted_at(name)
            print(f"  {name}\t(last posted: {last or 'never'})")
        return 0

    if args.command == "run":
        state = State.load(args.state)
        run_once(cfg, state, dry_run=args.dry_run)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
