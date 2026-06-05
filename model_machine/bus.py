from __future__ import annotations

from dataclasses import dataclass


def require_byte(value: int, name: str = "value") -> int:
    if not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not 0 <= value <= 0xFF:
        raise ValueError(f"{name} must be in range 00H..FFH")
    return value


@dataclass
class Bus:
    source: str | None = None
    value: int | None = None

    def drive(self, source: str, value: int) -> int:
        byte = require_byte(value)
        self.source = source
        self.value = byte
        return byte

    def read(self) -> int:
        if self.value is None:
            raise RuntimeError("bus has no value")
        return self.value

    def clear(self) -> None:
        self.source = None
        self.value = None
