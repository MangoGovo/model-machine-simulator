import unittest

from model_machine.alu import ALU


class ALUTest(unittest.TestCase):
    def setUp(self) -> None:
        self.alu = ALU()

    def test_add_sets_value_and_carry(self) -> None:
        result = self.alu.add(0xFF, 0x01)
        self.assertEqual(result.value, 0x00)
        self.assertEqual(result.zero, 1)
        self.assertEqual(result.carry, 1)

    def test_sub_sets_borrow_as_carry(self) -> None:
        result = self.alu.sub(0x00, 0x01)
        self.assertEqual(result.value, 0xFF)
        self.assertEqual(result.zero, 0)
        self.assertEqual(result.carry, 1)

    def test_and_clears_carry(self) -> None:
        result = self.alu.bit_and(0xF0, 0x0F)
        self.assertEqual(result.value, 0x00)
        self.assertEqual(result.zero, 1)
        self.assertEqual(result.carry, 0)

    def test_inc_wraps_and_sets_flags(self) -> None:
        result = self.alu.inc(0xFF)
        self.assertEqual(result.value, 0x00)
        self.assertEqual(result.zero, 1)
        self.assertEqual(result.carry, 1)


if __name__ == "__main__":
    unittest.main()
