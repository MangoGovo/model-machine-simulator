import tempfile
import unittest
from pathlib import Path

from model_machine.loader import (
    ProgramLoadError,
    load_microprogram_file,
    load_program_file,
    parse_microprogram_text,
    parse_program_text,
    parse_u8,
    parse_u24,
)


class LoaderTest(unittest.TestCase):
    def test_parse_program_text_supports_manual_hex_and_binary(self) -> None:
        records = parse_program_text(
            """
            $P 00 20 ; IN R0,00H
            01 0F
            00000010 01100001
            $M 00 000001 ; ignored by machine-program loader
            """
        )

        self.assertEqual(
            [(record.address, record.value) for record in records],
            [(0x00, 0x20), (0x01, 0x0F), (0x02, 0x61)],
        )

    def test_parse_u8_accepts_common_notations(self) -> None:
        self.assertEqual(parse_u8("70H"), 0x70)
        self.assertEqual(parse_u8("0x70"), 0x70)
        self.assertEqual(parse_u8("01110000"), 0x70)
        self.assertEqual(parse_u8("70"), 0x70)

    def test_parse_microprogram_text_supports_24_bit_control_words(self) -> None:
        records = parse_microprogram_text(
            """
            $P 00 20 ; ignored by microprogram loader
            $M 00 000001 ; NOP
            $M 1A 05B201 ; A-B
            """
        )

        self.assertEqual(
            [(record.address, record.value) for record in records],
            [(0x00, 0x000001), (0x1A, 0x05B201)],
        )

    def test_parse_u24_accepts_common_notations(self) -> None:
        self.assertEqual(parse_u24("000001"), 0x000001)
        self.assertEqual(parse_u24("0x05B201"), 0x05B201)

    def test_invalid_value_reports_line_number(self) -> None:
        with self.assertRaisesRegex(ProgramLoadError, "line 1"):
            parse_program_text("$P 00 100")

    def test_load_program_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "program.txt"
            path.write_text("$P 00 50\n", encoding="utf-8")
            records = load_program_file(path)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].address, 0x00)
        self.assertEqual(records[0].value, 0x50)

    def test_load_microprogram_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "microprogram.txt"
            path.write_text("$M 00 000001\n", encoding="utf-8")
            records = load_microprogram_file(path)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].address, 0x00)
        self.assertEqual(records[0].value, 0x000001)


if __name__ == "__main__":
    unittest.main()
