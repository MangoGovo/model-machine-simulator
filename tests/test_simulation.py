import tempfile
import unittest
from pathlib import Path

from model_machine.simulation import parse_input_values, run_simulation


class SimulationTest(unittest.TestCase):
    def test_parse_input_values_accepts_commas_and_repeated_values(self) -> None:
        self.assertEqual(parse_input_values(["08,04", "0A"]), [0x08, 0x04, 0x0A])

    def test_run_simulation_renders_cli_and_gui_shared_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / "program.txt"
            program.write_text(
                """
                00 20
                01 00
                02 21
                03 00
                04 34
                05 40
                06 50
                """,
                encoding="utf-8",
            )

            output = run_simulation(
                program,
                input_values=[0x2A, 0x3B],
                max_steps=100,
            )

        self.assertIn("Stopped: output after 3 instruction(s)", output)
        self.assertIn("port 40 <- 3B", output)


if __name__ == "__main__":
    unittest.main()
