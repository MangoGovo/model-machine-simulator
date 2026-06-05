from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ProgramLoadError(ValueError):
    pass


@dataclass(frozen=True)
class LoadRecord:
    address: int
    value: int
    line_no: int
    source: str


@dataclass(frozen=True)
class MicroProgramRecord:
    address: int
    value: int
    line_no: int
    source: str


def parse_u8(token: str, name: str = "value", line_no: int | None = None) -> int:
    text = token.strip()
    if not text:
        raise _error(f"empty {name}", line_no)

    try:
        if text.lower().endswith("h"):
            value = int(text[:-1], 16)
        elif text.lower().startswith("0x"):
            value = int(text, 16)
        elif (
            text.lower().startswith("0b")
            and len(text) > 2
            and all(char in "01" for char in text[2:])
        ):
            value = int(text, 2)
        elif len(text) == 8 and all(char in "01" for char in text):
            value = int(text, 2)
        else:
            value = int(text, 16)
    except ValueError as exc:
        raise _error(f"invalid {name} {token!r}", line_no) from exc

    if not 0 <= value <= 0xFF:
        raise _error(f"{name} {token!r} is outside 00H..FFH", line_no)
    return value


def parse_u24(token: str, name: str = "value", line_no: int | None = None) -> int:
    text = token.strip()
    if not text:
        raise _error(f"empty {name}", line_no)

    try:
        if text.lower().endswith("h"):
            value = int(text[:-1], 16)
        elif text.lower().startswith("0x"):
            value = int(text, 16)
        elif (
            text.lower().startswith("0b")
            and len(text) > 2
            and all(char in "01" for char in text[2:])
        ):
            value = int(text, 2)
        elif len(text) == 24 and all(char in "01" for char in text):
            value = int(text, 2)
        else:
            value = int(text, 16)
    except ValueError as exc:
        raise _error(f"invalid {name} {token!r}", line_no) from exc

    if not 0 <= value <= 0xFFFFFF:
        raise _error(f"{name} {token!r} is outside 000000H..FFFFFFH", line_no)
    return value


def parse_program_text(text: str) -> list[LoadRecord]:
    records: list[LoadRecord] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        clean = raw_line.split(";", 1)[0].strip()
        if not clean:
            continue

        tokens = clean.replace(",", " ").split()
        marker = tokens[0].upper()
        if marker in {"$M", "M", "SM"}:
            continue
        if marker in {"$P", "P", "SP"}:
            if len(tokens) < 3:
                raise _error("$P line must contain address and value", line_no)
            address_token, value_token = tokens[1], tokens[2]
        else:
            if len(tokens) < 2:
                raise _error("line must contain address and value", line_no)
            address_token, value_token = tokens[0], tokens[1]

        address = parse_u8(address_token, "address", line_no)
        value = parse_u8(value_token, "value", line_no)
        records.append(LoadRecord(address=address, value=value, line_no=line_no, source=raw_line))
    return records


def parse_microprogram_text(text: str) -> list[MicroProgramRecord]:
    records: list[MicroProgramRecord] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        clean = raw_line.split(";", 1)[0].strip()
        if not clean:
            continue

        tokens = clean.replace(",", " ").split()
        marker = tokens[0].upper()
        if marker in {"$P", "P", "SP"}:
            continue
        if marker in {"$M", "M", "SM"}:
            if len(tokens) < 3:
                raise _error("$M line must contain address and value", line_no)
            address_token, value_token = tokens[1], tokens[2]
        else:
            if len(tokens) < 2:
                raise _error("line must contain address and value", line_no)
            address_token, value_token = tokens[0], tokens[1]

        address = parse_u8(address_token, "microaddress", line_no)
        value = parse_u24(value_token, "microinstruction", line_no)
        records.append(
            MicroProgramRecord(address=address, value=value, line_no=line_no, source=raw_line)
        )
    return records


def load_program_file(path: str | Path) -> list[LoadRecord]:
    program_path = Path(path)
    return parse_program_text(program_path.read_text(encoding="utf-8"))


def load_microprogram_file(path: str | Path) -> list[MicroProgramRecord]:
    microprogram_path = Path(path)
    return parse_microprogram_text(microprogram_path.read_text(encoding="utf-8"))


def _error(message: str, line_no: int | None) -> ProgramLoadError:
    if line_no is None:
        return ProgramLoadError(message)
    return ProgramLoadError(f"line {line_no}: {message}")
