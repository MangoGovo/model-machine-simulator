from __future__ import annotations

import argparse
import sys
from pathlib import Path

from model_machine.loader import (
    ProgramLoadError,
    load_microprogram_file,
    load_program_file,
    parse_u8,
)
from model_machine.machine import ModelMachine


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


def parse_input_values(values: list[str] | None) -> list[int]:
    tokens: list[str] = []
    for value in values or ["00"]:
        tokens.extend(token for token in value.replace(",", " ").split() if token)

    if not tokens:
        raise ProgramLoadError("at least one input byte is required")
    return [parse_u8(token, f"input {index}") for index, token in enumerate(tokens, start=1)]


def format_registers(snapshot: dict[str, int]) -> str:
    ordered = ["R0", "R1", "R2", "R3", "PC", "AR", "IR", "A", "B", "FZ", "FC"]
    parts: list[str] = []
    for name in ordered:
        value = snapshot[name]
        if name in {"FZ", "FC"}:
            parts.append(f"{name}={value}")
        else:
            parts.append(f"{name}={value:02X}")
    return " ".join(parts)


def format_changes(before: dict[str, int], after: dict[str, int]) -> str:
    ordered = ["R0", "R1", "R2", "R3", "PC", "AR", "IR", "A", "B", "FZ", "FC"]
    changes = []
    for name in ordered:
        if before[name] != after[name]:
            if name in {"FZ", "FC"}:
                changes.append(f"{name}:{before[name]}->{after[name]}")
            else:
                changes.append(f"{name}:{before[name]:02X}->{after[name]:02X}")
    return " ".join(changes) if changes else "no register changes"


def print_trace(machine: ModelMachine, traces) -> None:
    for trace in traces:
        operands = " ".join(f"{value:02X}" for value in trace.operands)
        byte_text = f"{trace.opcode:02X}" if not operands else f"{trace.opcode:02X} {operands}"
        print(f"{trace.step:04d} PC={trace.pc:02X} BYTES={byte_text:<8} {trace.mnemonic}")
        for micro_op in trace.micro_ops:
            print(f"  {micro_op}")
        if trace.memory_writes:
            writes = " ".join(
                f"MEM[{addr:02X}]:{old:02X}->{new:02X}"
                for addr, old, new in trace.memory_writes
            )
            print(f"  {writes}")
        if trace.outputs:
            outputs = " ".join(f"OUT[{port:02X}]<-{value:02X}" for port, value in trace.outputs)
            print(f"  {outputs}")
        print(f"  {format_changes(trace.before, trace.after)}")


def print_dump(machine: ModelMachine, start: int, end: int) -> None:
    print(f"Memory[{start:02X}:{end:02X}]:")
    cells = machine.memory.dump(start, end)
    line_parts: list[str] = []
    for index, (addr, value) in enumerate(cells, start=1):
        line_parts.append(f"{addr:02X}:{value:02X}")
        if index % 8 == 0:
            print("  " + " ".join(line_parts))
            line_parts.clear()
    if line_parts:
        print("  " + " ".join(line_parts))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Complex model machine simulator")
    parser.add_argument("program", type=Path, help="machine instruction text file")
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

    if args.max_steps <= 0:
        parser.error("--max-steps must be positive")

    try:
        input_values = parse_input_values(args.input)
        records = load_program_file(args.program)
        micro_records = (
            load_microprogram_file(args.microprogram) if args.microprogram is not None else []
        )
    except (OSError, ProgramLoadError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    machine = ModelMachine(input_values=input_values)
    machine.load_records(records)
    if micro_records:
        machine.load_microprogram_records(micro_records)

    try:
        result = machine.run(max_steps=args.max_steps, stop_on_output=True)
    except Exception as exc:
        print(f"execution error: {exc}", file=sys.stderr)
        return 1

    if args.trace:
        print_trace(machine, result.traces)

    if micro_records:
        print(f"Microprogram: {len(micro_records)} instruction(s) loaded")
    print(f"Stopped: {result.reason} after {result.steps} instruction(s)")
    print("Registers:")
    print("  " + format_registers(machine.registers.snapshot()))

    print("OUT:")
    if machine.io.outputs:
        for event in machine.io.outputs:
            print(f"  port {event.port:02X} <- {event.value:02X}")
    else:
        print("  <none>")

    dump_ranges = args.dump or [(0x60, 0x70)]
    for start, end in dump_ranges:
        print_dump(machine, start, end)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
