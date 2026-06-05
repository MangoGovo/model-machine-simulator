from __future__ import annotations

from dataclasses import dataclass


BYTE_MASK = 0xFF


@dataclass(frozen=True)
class ALUResult:
    value: int
    zero: int
    carry: int


class ALU:
    def add(self, left: int, right: int) -> ALUResult:
        raw = left + right
        value = raw & BYTE_MASK
        return ALUResult(value=value, zero=int(value == 0), carry=int(raw > BYTE_MASK))

    def sub(self, left: int, right: int) -> ALUResult:
        raw = left - right
        value = raw & BYTE_MASK
        return ALUResult(value=value, zero=int(value == 0), carry=int(raw < 0))

    def compare(self, left: int, right: int) -> ALUResult:
        raw = left - right
        value = raw & BYTE_MASK
        return ALUResult(value=value, zero=int(value == 0), carry=int(raw < 0))

    def bit_and(self, left: int, right: int) -> ALUResult:
        value = (left & right) & BYTE_MASK
        return ALUResult(value=value, zero=int(value == 0), carry=0)

    def inc(self, value: int) -> ALUResult:
        raw = value + 1
        result = raw & BYTE_MASK
        return ALUResult(value=result, zero=int(result == 0), carry=int(raw > BYTE_MASK))

    def shr(self, value: int) -> ALUResult:
        result = (value >> 1) & BYTE_MASK
        return ALUResult(value=result, zero=int(result == 0), carry=value & 0x01)
