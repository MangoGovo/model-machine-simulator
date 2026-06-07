from __future__ import annotations

from dataclasses import dataclass


BYTE_MASK = 0xFF


@dataclass(frozen=True)
class ALUResult:
    value: int
    zero: int
    carry: int


class ALU:
    def operate(self, s: int, a: int, b: int, carry_in: int = 0) -> ALUResult:
        carry_in = 1 if carry_in else 0

        if s == 0x0:
            return ALUResult(value=a & BYTE_MASK, zero=int((a & BYTE_MASK) == 0), carry=0)
        if s == 0x1:
            return ALUResult(value=b & BYTE_MASK, zero=int((b & BYTE_MASK) == 0), carry=0)
        if s == 0x2:
            return self.bit_and(a, b)
        if s == 0x3:
            return self.bit_or(a, b)
        if s == 0x4:
            value = (~a) & BYTE_MASK
            return ALUResult(value=value, zero=int(value == 0), carry=0)
        if s == 0x5:
            shift = b & 0x07
            value = ((a >> shift) | ((a << (8 - shift)) & BYTE_MASK)) & BYTE_MASK
            return ALUResult(value=value, zero=int(value == 0), carry=0)
        if s == 0x6:
            if carry_in:
                return self.ror(a, carry_in)
            return self.shr(a)
        if s == 0x7:
            raw = ((a << 1) & 0x1FF) | carry_in
            value = raw & BYTE_MASK
            return ALUResult(value=value, zero=int(value == 0), carry=int((a & 0x80) != 0))
        if s == 0x8:
            return ALUResult(value=0, zero=0, carry=carry_in)
        if s == 0x9:
            return self.add(a, b)
        if s == 0xA:
            return self.add(a, (b + carry_in) & BYTE_MASK)
        if s == 0xB:
            return self.sub(a, b)
        if s == 0xC:
            return self.sub(a, 0x01)
        if s == 0xD:
            return self.inc(a)
        raise ValueError(f"unsupported ALU S field {s:01X}")

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

    def ror(self, value: int, carry_in: int) -> ALUResult:
        """Rotate right through carry.

        ``carry_in`` (0 or 1) is shifted into the MSB; the LSB of
        *value* is shifted out as the new carry.
        """
        msb = (carry_in & 1) << 7
        result = ((value >> 1) | msb) & BYTE_MASK
        return ALUResult(value=result, zero=int(result == 0), carry=value & 0x01)

    def bit_or(self, left: int, right: int) -> ALUResult:
        value = (left | right) & BYTE_MASK
        return ALUResult(value=value, zero=int(value == 0), carry=0)
