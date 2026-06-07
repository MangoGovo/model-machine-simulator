from __future__ import annotations

from dataclasses import dataclass, field

from model_machine.alu import ALU
from model_machine.bus import Bus
from model_machine.control_unit import ControlUnit, RunResult
from model_machine.io_unit import IOUnit
from model_machine.loader import LoadRecord, MicroProgramRecord
from model_machine.microcode import decode_microprogram
from model_machine.memory import Memory
from model_machine.registers import RegisterFile


def _detect_execution_mode(records: list[LoadRecord]) -> str:
    memory_map = {record.address: record.value for record in records}
    values = set(memory_map.values())
    if 0x61 in values and 0x51 in values:
        return "course"
    pc = 0
    visited: set[int] = set()

    while pc in memory_map and pc not in visited:
        visited.add(pc)
        opcode = memory_map[pc]
        group = opcode & 0xF0

        if group in {0x40, 0x90, 0xA0}:
            return "direct"
        if group == 0xB0 and opcode != 0xB0:
            return "direct"

        if group in {0x20, 0x30, 0x60, 0xB0, 0xC0, 0xD0, 0xE0, 0xF0}:
            pc = (pc + 2) & 0xFF
        else:
            pc = (pc + 1) & 0xFF

    return "indexed"


@dataclass
class ModelMachine:
    input_values: list[int] | None = None
    execution_mode: str = "indexed"
    memory: Memory = field(default_factory=Memory)
    registers: RegisterFile = field(default_factory=RegisterFile)
    bus: Bus = field(default_factory=Bus)
    alu: ALU = field(default_factory=ALU)
    microprogram: dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.io = IOUnit(input_values=self.input_values)
        self.control = ControlUnit(
            memory=self.memory,
            registers=self.registers,
            bus=self.bus,
            alu=self.alu,
            io=self.io,
            microprogram=self.microprogram,
            execution_mode=self.execution_mode,
        )

    def load_records(self, records: list[LoadRecord]) -> None:
        if not self.microprogram:
            detected_mode = _detect_execution_mode(records)
            self.execution_mode = detected_mode
            self.control.execution_mode = detected_mode
        for record in records:
            self.memory.write(record.address, record.value)

    def load_microprogram_records(self, records: list[MicroProgramRecord]) -> None:
        self.microprogram.clear()
        for record in records:
            self.microprogram[record.address] = record.value
        decoded = decode_microprogram(self.microprogram)
        self.control.microprogram = decoded
        self.registers.mpc = 0
        self.registers.mir = 0
        if self.execution_mode != "course":
            self.execution_mode = "direct"
            self.control.execution_mode = "direct"

    def run(self, max_steps: int = 10000, stop_on_output: bool = True) -> RunResult:
        return self.control.run(max_steps=max_steps, stop_on_output=stop_on_output)
