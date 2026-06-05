from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from model_machine.bus import require_byte


@dataclass(frozen=True)
class IOEvent:
    port: int
    value: int


@dataclass
class IOUnit:
    input_values: list[int] | None = None
    input_ports: dict[int, int] = field(default_factory=dict)
    outputs: list[IOEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        values = self.input_values or []
        self._queue = deque(require_byte(value, "input") for value in values)

    def read(self, port: int) -> int:
        checked_port = require_byte(port, "port")
        if self._queue:
            return self._queue.popleft()
        return require_byte(self.input_ports.get(checked_port, 0), "input")

    def write(self, port: int, value: int) -> None:
        self.outputs.append(IOEvent(require_byte(port, "port"), require_byte(value, "output")))
