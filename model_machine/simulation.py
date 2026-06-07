from __future__ import annotations

from pathlib import Path

from model_machine.loader import (
    ProgramLoadError,
    load_microprogram_file,
    load_program_file,
    parse_combined_text,
    parse_u8,
)
from model_machine.machine import ModelMachine


def parse_input_values(values: list[str] | None) -> list[int]:
    tokens: list[str] = []
    for value in values or ["00"]:
        tokens.extend(token for token in value.replace(",", " ").split() if token)

    if not tokens:
        raise ProgramLoadError("at least one input byte is required")
    return [parse_u8(token, f"input {index}") for index, token in enumerate(tokens, start=1)]


def format_registers(snapshot: dict[str, int]) -> str:
    ordered = ["R0", "R1", "R2", "R3", "PC", "AR", "IR", "MPC", "MIR", "A", "B", "FZ", "FC"]
    parts: list[str] = []
    for name in ordered:
        value = snapshot[name]
        if name in {"FZ", "FC"}:
            parts.append(f"{name}={value}")
        elif name == "MIR":
            parts.append(f"{name}={value:06X}")
        else:
            parts.append(f"{name}={value:02X}")
    return " ".join(parts)


def format_changes(before: dict[str, int], after: dict[str, int]) -> str:
    ordered = ["R0", "R1", "R2", "R3", "PC", "AR", "IR", "MPC", "MIR", "A", "B", "FZ", "FC"]
    changes = []
    for name in ordered:
        if before[name] != after[name]:
            if name in {"FZ", "FC"}:
                changes.append(f"{name}:{before[name]}->{after[name]}")
            elif name == "MIR":
                changes.append(f"{name}:{before[name]:06X}->{after[name]:06X}")
            else:
                changes.append(f"{name}:{before[name]:02X}->{after[name]:02X}")
    return " ".join(changes) if changes else "no register changes"


def render_trace(traces) -> list[str]:
    lines: list[str] = []
    for trace in traces:
        operands = " ".join(f"{value:02X}" for value in trace.operands)
        byte_text = f"{trace.opcode:02X}" if not operands else f"{trace.opcode:02X} {operands}"
        lines.append(f"{trace.step:04d} PC={trace.pc:02X} BYTES={byte_text:<8} {trace.mnemonic}")
        lines.extend(f"  {micro_op}" for micro_op in trace.micro_ops)
        if trace.memory_writes:
            writes = " ".join(
                f"MEM[{addr:02X}]:{old:02X}->{new:02X}"
                for addr, old, new in trace.memory_writes
            )
            lines.append(f"  {writes}")
        if trace.outputs:
            outputs = " ".join(f"OUT[{port:02X}]<-{value:02X}" for port, value in trace.outputs)
            lines.append(f"  {outputs}")
        lines.append(f"  {format_changes(trace.before, trace.after)}")
    return lines


def render_dump(machine: ModelMachine, start: int, end: int) -> list[str]:
    lines = [f"Memory[{start:02X}:{end:02X}]:"]
    cells = machine.memory.dump(start, end)
    line_parts: list[str] = []
    for index, (addr, value) in enumerate(cells, start=1):
        line_parts.append(f"{addr:02X}:{value:02X}")
        if index % 8 == 0:
            lines.append("  " + " ".join(line_parts))
            line_parts.clear()
    if line_parts:
        lines.append("  " + " ".join(line_parts))
    return lines


def run_simulation(
    program: str | Path | None = None,
    *,
    input_values: list[int],
    microprogram: str | Path | None = None,
    combined_text: str | None = None,
    max_steps: int = 10000,
    trace: bool = False,
    dump_ranges: list[tuple[int, int]] | None = None,
) -> str:
    if combined_text is not None:
        records, micro_records = parse_combined_text(combined_text)
    elif program is not None:
        records = load_program_file(program)
        micro_records = load_microprogram_file(microprogram) if microprogram is not None else []
    else:
        raise ValueError("either program or combined_text must be provided")

    machine = ModelMachine(input_values=input_values, execution_mode="direct" if micro_records else "indexed")
    machine.load_records(records)
    if micro_records:
        machine.load_microprogram_records(micro_records)

    result = machine.run(max_steps=max_steps, stop_on_output=True)

    lines: list[str] = []
    if trace:
        lines.extend(render_trace(result.traces))

    if micro_records:
        lines.append(f"Microprogram: {len(micro_records)} instruction(s) loaded")
    lines.append(f"Stopped: {result.reason} after {result.steps} instruction(s)")
    lines.append("Registers:")
    lines.append("  " + format_registers(machine.registers.snapshot()))

    lines.append("OUT:")
    if machine.io.outputs:
        for event in machine.io.outputs:
            lines.append(f"  port {event.port:02X} <- {event.value:02X}")
    else:
        lines.append("  <none>")

    for start, end in dump_ranges or [(0x60, 0x70)]:
        lines.extend(render_dump(machine, start, end))

    return "\n".join(lines) + "\n"
