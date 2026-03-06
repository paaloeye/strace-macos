"""CLI entry point for strace-macos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from strace_macos.exceptions import StraceError


def main(argv: list[str] | None = None) -> int:
    """Main entry point for strace-macos.

    Args:
        argv: Command-line arguments (default: sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Trace system calls on macOS using LLDB",
        prog="strace-macos",
    )

    # Output options
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write output to file instead of stderr",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON Lines format (default: strace-compatible text)",
    )
    parser.add_argument(
        "-c",
        "--summary-only",
        action="store_true",
        help="Count time, calls, and errors for each syscall and report summary",
    )
    parser.add_argument(
        "--no-abbrev",
        action="store_true",
        help="Print raw values without symbolic decoding (no abbreviation)",
    )
    parser.add_argument(
        "-a",
        "--args-only",
        action="store_true",
        help="Print only the first argument (requires single syscall filter, e.g., -e trace=open)",
    )

    # Filtering options
    parser.add_argument(
        "-e",
        "--expr",
        dest="filter_expr",
        help="Filter expression (e.g., 'trace=open,close' or 'trace=file')",
    )

    # Process tracing options
    parser.add_argument(
        "-f",
        "--follow-forks",
        action="store_true",
        help="Trace child processes created by fork/vfork/posix_spawn",
    )

    # Attach or spawn
    parser.add_argument(
        "-p",
        "--attach",
        dest="pid",
        type=int,
        help="Attach to process with given PID",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command and arguments to trace",
    )

    args = parser.parse_args(argv)

    # Validate: must specify either -p or command
    if args.pid is None and not args.command:
        parser.error("Must specify either -p PID or COMMAND")
    if args.pid is not None and args.command:
        parser.error("Cannot specify both -p PID and COMMAND")

    # Validate: -c and --json are mutually exclusive
    if args.summary_only and args.json:
        parser.error("Cannot specify both -c (summary) and --json")

    # Validate: -a requires a single syscall filter
    if args.args_only:
        if not args.filter_expr:
            parser.error("-a (args-only) requires -e trace=<syscall>")
        if not args.filter_expr.startswith("trace="):
            parser.error("-a (args-only) requires -e trace=<syscall>")
        # Check if it's a single syscall (not a comma-separated list or category)
        trace_value = args.filter_expr[6:]  # Remove "trace=" prefix
        if "," in trace_value:
            parser.error("-a (args-only) requires a single syscall, not a list")
        # Categories that won't work with -a
        if trace_value in ["file", "network", "process", "memory", "signal", "ipc", "thread", "time", "sysinfo", "security", "debug", "misc"]:
            parser.error("-a (args-only) requires a single syscall, not a category")

    # Import tracer here to avoid loading LLDB until needed
    from strace_macos.tracer import Tracer  # noqa: PLC0415

    try:
        # Create tracer
        tracer = Tracer(
            output_file=args.output,
            json_output=args.json,
            summary_only=args.summary_only,
            filter_expr=args.filter_expr,
            no_abbrev=args.no_abbrev,
            follow_forks=args.follow_forks,
            args_only=args.args_only,
        )

        # Run trace
        if args.pid is not None:
            return tracer.attach(args.pid)
        return tracer.spawn(args.command)
    except StraceError as e:
        # User-facing errors: print message without stack trace
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StraceError as e:
        # User-facing errors: print message without stack trace
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
