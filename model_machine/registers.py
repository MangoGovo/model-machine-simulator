from __future__ import annotations

from dataclasses import dataclass, field

from model_machine.bus import require_byte


@dataclass
class RegisterFile:
    r: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    pc: int = 0
    ar: int = 0
    ir: int = 0
    a: int = 0
    b: int = 0
    fz: int = 0
    fc: int = 0

    def get_reg(self, index: int) -> int:
        self._check_index(index)
        return self.r[index]

    def set_reg(self, index: int, value: int) -> None:
        self._check_index(index)
        self.r[index] = require_byte(value, f"R{index}")

    def snapshot(self) -> dict[str, int]:
        return {
            "R0": self.r[0],
            "R1": self.r[1],
            "R2": self.r[2],
            "R3": self.r[3],
            "PC": self.pc,
            "AR": self.ar,
            "IR": self.ir,
            "A": self.a,
            "B": self.b,
            "FZ": self.fz,
            "FC": self.fc,
        }

    @staticmethod
    def _check_index(index: int) -> None:
        if index not in {0, 1, 2, 3}:
            raise IndexError("register index must be 0..3")
