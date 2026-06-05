from __future__ import annotations

import argparse
import sys
from pathlib import Path

from model_machine.loader import ProgramLoadError, parse_u8
from model_machine.simulation import parse_input_values, run_simulation


def parse_dump_range(value: str) -> tuple[int, int]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("dump range must be START:END")
    start_text, end_text = value.split(":", 1)
    try:
        start = parse_u8(start_text, "dump start")
        end = parse_u8(end_text, "dump end")
    except ProgramLoadError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if start > end:
        raise argparse.ArgumentTypeError("dump start must be <= end")
    return start, end


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Complex model machine simulator")
    parser.add_argument("program", type=Path, nargs="?", help="machine instruction text file")
    parser.add_argument("--gui", action="store_true", help="open the Tkinter GUI")
    parser.add_argument(
        "--microprogram",
        type=Path,
        help="microprogram text file containing $M records",
    )
    parser.add_argument(
        "--input",
        action="append",
        help="input byte(s) read by IN; repeat this option or comma-separate values",
    )
    parser.add_argument("--trace", action="store_true", help="print instruction and component trace")
    parser.add_argument(
        "--dump",
        type=parse_dump_range,
        action="append",
        help="dump memory range START:END after execution, for example 60:70",
    )
    parser.add_argument("--max-steps", type=int, default=10000, help="maximum instructions to run")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        from model_machine.gui import launch_gui

        launch_gui()
        return 0

    if args.program is None:
        parser.error("program is required unless --gui is used")

    if args.max_steps <= 0:
        parser.error("--max-steps must be positive")

    try:
        input_values = parse_input_values(args.input)
        output = run_simulation(
            args.program,
            input_values=input_values,
            microprogram=args.microprogram,
            max_steps=args.max_steps,
            trace=args.trace,
            dump_ranges=args.dump,
        )
    except (OSError, ProgramLoadError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"execution error: {exc}", file=sys.stderr)
        return 1

    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
