from __future__ import annotations

from dataclasses import dataclass, field

from model_machine.alu import ALU
from model_machine.bus import Bus
from model_machine.control_unit import ControlUnit, RunResult
from model_machine.io_unit import IOUnit
from model_machine.loader import LoadRecord, MicroProgramRecord
from model_machine.memory import Memory
from model_machine.registers import RegisterFile


@dataclass
class ModelMachine:
    input_values: list[int] | None = None
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
        )

    def load_records(self, records: list[LoadRecord]) -> None:
        for record in records:
            self.memory.write(record.address, record.value)

    def load_microprogram_records(self, records: list[MicroProgramRecord]) -> None:
        self.microprogram.clear()
        for record in records:
            self.microprogram[record.address] = record.value

    def run(self, max_steps: int = 10000, stop_on_output: bool = True) -> RunResult:
        return self.control.run(max_steps=max_steps, stop_on_output=stop_on_output)
