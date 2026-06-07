from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MicroInstruction:
    raw: int
    m23: int
    cn: int
    wr: int
    rd: int
    iom: int
    s: int
    a: int
    b: int
    c: int
    ma: int

    @classmethod
    def decode(cls, raw: int) -> "MicroInstruction":
        return cls(
            raw=raw,
            m23=(raw >> 23) & 0x1,
            cn=(raw >> 22) & 0x1,
            wr=(raw >> 21) & 0x1,
            rd=(raw >> 20) & 0x1,
            iom=(raw >> 19) & 0x1,
            s=(raw >> 15) & 0xF,
            a=(raw >> 12) & 0x7,
            b=(raw >> 9) & 0x7,
            c=(raw >> 6) & 0x7,
            ma=raw & 0x3F,
        )


def decode_microprogram(raw_program: dict[int, int]) -> dict[int, MicroInstruction]:
    return {address: MicroInstruction.decode(value) for address, value in raw_program.items()}
