from __future__ import annotations

import unittest
from pathlib import Path

from model_machine.loader import (
    load_program_file,
    parse_combined_text,
    parse_microprogram_text,
    parse_program_text,
)
from model_machine.machine import ModelMachine


ROOT = Path(__file__).resolve().parents[1]


def run_program(text: str, input_value: int = 0x00, stop_on_output: bool = False):
    machine = ModelMachine(input_values=[input_value])
    machine.load_records(parse_program_text(text))
    result = machine.run(max_steps=1000, stop_on_output=stop_on_output)
    return machine, result


def run_microprogram_mode(
    text: str,
    microprogram_text: str = "$M 00 000001\n",
    input_values: list[int] | None = None,
    stop_on_output: bool = False,
):
    machine = ModelMachine(input_values=input_values or [0x00])
    machine.load_records(parse_program_text(text))
    machine.load_microprogram_records(parse_microprogram_text(microprogram_text))
    result = machine.run(max_steps=1000, stop_on_output=stop_on_output)
    return machine, result


class ControlUnitTest(unittest.TestCase):
    def test_arithmetic_and_halt_instructions(self) -> None:
        machine, result = run_program(
            """
            00 60
            01 0F
            02 61
            03 03
            04 14
            05 70
            06 04
            07 84
            08 50
            """
        )

        self.assertEqual(result.reason, "halted")
        self.assertEqual(result.steps, 7)
        self.assertEqual(machine.registers.get_reg(0), 0x04)
        self.assertEqual(machine.registers.fz, 0)
        self.assertEqual(machine.registers.fc, 0)

    def test_bzc_and_jmp_instructions(self) -> None:
        machine, result = run_program(
            """
            00 60
            01 00
            02 10
            03 F0
            04 08
            05 61
            06 FF
            07 50
            08 E0
            09 0B
            0A 50
            0B 61
            0C 2A
            0D 50
            """
        )

        self.assertEqual(result.reason, "halted")
        self.assertEqual(machine.registers.get_reg(1), 0x2A)

    def test_lad_sta_in_out_instructions(self) -> None:
        machine, result = run_program(
            """
            00 62
            01 80
            02 20
            03 00
            04 D0
            05 80
            06 CB
            07 00
            08 3C
            09 40
            0A 50
            """,
            input_value=0x5A,
            stop_on_output=True,
        )

        self.assertEqual(result.reason, "output")
        self.assertEqual(machine.memory.read(0x80), 0x5A)
        self.assertEqual(machine.registers.get_reg(3), 0x5A)
        self.assertEqual(machine.io.outputs[-1].port, 0x40)
        self.assertEqual(machine.io.outputs[-1].value, 0x5A)

    def test_microprogram_mode_supports_direct_lad_mov_shr(self) -> None:
        machine, result = run_microprogram_mode(
            """
            00 60
            01 01
            02 62
            03 80
            04 D2
            05 60
            06 62
            07 11
            08 D2
            09 61
            0A C1
            0B 60
            0C A1
            0D 47
            0E 3C
            0F 40
            10 50
            """,
            stop_on_output=True,
        )

        self.assertEqual(result.reason, "output")
        self.assertEqual(machine.registers.get_reg(1), 0x40)
        self.assertEqual(machine.registers.get_reg(3), 0x40)
        self.assertEqual(machine.io.outputs[-1].value, 0x40)

    def test_microprogram_mode_supports_cmp_bzc(self) -> None:
        machine, result = run_microprogram_mode(
            """
            00 60
            01 05
            02 61
            03 05
            04 B4
            05 F0
            06 0B
            07 62
            08 FF
            09 E0
            0A 0D
            0B 62
            0C 2A
            0D 38
            0E 40
            0F 50
            """,
            stop_on_output=True,
        )

        self.assertEqual(result.reason, "output")
        self.assertEqual(machine.registers.get_reg(2), 0x2A)
        self.assertEqual(machine.io.outputs[-1].value, 0x2A)

    def test_sample_program_results(self) -> None:
        records = load_program_file(ROOT / "programs" / "sum_1_to_x.txt")

        for input_value, expected in [(0x00, 0x00), (0x05, 0x0F), (0x0F, 0x78)]:
            with self.subTest(input=input_value):
                machine = ModelMachine(input_values=[input_value])
                machine.load_records(records)
                result = machine.run(max_steps=1000, stop_on_output=True)

                self.assertEqual(result.reason, "output")
                self.assertEqual(machine.memory.read(0x70), expected)
                self.assertEqual(machine.io.outputs[-1].value, expected)

    def test_combination_program_runs_in_direct_mode_without_explicit_microprogram(self) -> None:
        records = load_program_file(ROOT / "examples" / "combination_number.txt")

        machine = ModelMachine(input_values=[0x05, 0x03], execution_mode="direct")
        machine.load_records(records)
        result = machine.run(max_steps=10000, stop_on_output=True)

        self.assertEqual(result.reason, "output")
        self.assertEqual(machine.io.outputs[-1].value, 0x0A)

    def test_course_microprogram_runs_without_opcode_desync(self) -> None:
        text = (ROOT / "examples" / "signed_division_course.txt").read_text(encoding="utf-8")
        records, micro_records = parse_combined_text(text)

        machine = ModelMachine(input_values=[0xE0, 0x40])
        machine.load_records(records)
        machine.load_microprogram_records(micro_records)
        result = machine.run(max_steps=2000, stop_on_output=False)

        self.assertNotEqual(result.reason, "max_steps")
        self.assertEqual(machine.memory.read(0x16), 0xC0)


if __name__ == "__main__":
    unittest.main()
