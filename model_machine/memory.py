from __future__ import annotations

from dataclasses import dataclass, field

from model_machine.bus import require_byte


@dataclass
class Memory:
    size: int = 256
    data: bytearray = field(init=False)

    def __post_init__(self) -> None:
        if self.size != 256:
            raise ValueError("this model machine uses exactly 256 bytes of memory")
        self.data = bytearray(self.size)

    def read(self, address: int) -> int:
        return self.data[require_byte(address, "address")]

    def write(self, address: int, value: int) -> None:
        self.data[require_byte(address, "address")] = require_byte(value)

    def dump(self, start: int, end: int) -> list[tuple[int, int]]:
        start_byte = require_byte(start, "start")
        end_byte = require_byte(end, "end")
        if start_byte > end_byte:
            raise ValueError("dump start must be <= end")
        return [(addr, self.data[addr]) for addr in range(start_byte, end_byte + 1)]
