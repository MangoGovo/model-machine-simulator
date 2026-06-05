from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from model_machine.loader import ProgramLoadError, parse_u8
from model_machine.simulation import parse_input_values, run_simulation


class SimulatorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Model Machine Simulator")
        self.minsize(860, 620)

        self.program_var = tk.StringVar()
        self.microprogram_var = tk.StringVar()
        self.input_var = tk.StringVar(value="08,04")
        self.max_steps_var = tk.StringVar(value="10000")
        self.dump_var = tk.StringVar(value="60:70")
        self.trace_var = tk.BooleanVar(value=False)

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root.columnconfigure(1, weight=1)
        root.rowconfigure(6, weight=1)

        self._add_file_row(root, 0, "Machine program", self.program_var)
        self._add_file_row(root, 1, "Microprogram", self.microprogram_var)

        ttk.Label(root, text="Input bytes").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(root, textvariable=self.input_var).grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=(8, 0)
        )

        ttk.Label(root, text="Max steps").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(root, textvariable=self.max_steps_var, width=16).grid(
            row=3, column=1, sticky="w", pady=(8, 0)
        )

        ttk.Label(root, text="Dump ranges").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(root, textvariable=self.dump_var).grid(
            row=4, column=1, sticky="ew", pady=(8, 0)
        )
        ttk.Checkbutton(root, text="Trace", variable=self.trace_var).grid(
            row=4, column=2, sticky="e", pady=(8, 0)
        )

        actions = ttk.Frame(root)
        actions.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 8))
        ttk.Button(actions, text="Run", command=self._run).pack(side="left")
        ttk.Button(actions, text="Clear", command=self._clear_output).pack(side="left", padx=(8, 0))

        self.output = tk.Text(root, wrap="none", font=("Menlo", 12), height=24)
        self.output.grid(row=6, column=0, columnspan=3, sticky="nsew")

        y_scroll = ttk.Scrollbar(root, orient="vertical", command=self.output.yview)
        y_scroll.grid(row=6, column=3, sticky="ns")
        self.output.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(root, orient="horizontal", command=self.output.xview)
        x_scroll.grid(row=7, column=0, columnspan=3, sticky="ew")
        self.output.configure(xscrollcommand=x_scroll.set)

    def _add_file_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky="ew", padx=(8, 8), pady=(0, 8)
        )
        ttk.Button(parent, text="Browse", command=lambda: self._browse(variable)).grid(
            row=row, column=2, sticky="e", pady=(0, 8)
        )

    def _browse(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Select text file",
            filetypes=(("Text files", "*.txt"), ("All files", "*")),
        )
        if path:
            variable.set(path)

    def _run(self) -> None:
        try:
            program = self._required_path(self.program_var.get(), "machine program")
            microprogram = self._optional_path(self.microprogram_var.get())
            max_steps = self._parse_max_steps()
            dump_ranges = self._parse_dump_ranges()
            output = run_simulation(
                program,
                input_values=parse_input_values([self.input_var.get()]),
                microprogram=microprogram,
                max_steps=max_steps,
                trace=self.trace_var.get(),
                dump_ranges=dump_ranges,
            )
        except Exception as exc:
            messagebox.showerror("Simulation error", str(exc))
            return

        self._set_output(output)

    def _required_path(self, value: str, name: str) -> Path:
        if not value.strip():
            raise ValueError(f"{name} file is required")
        return Path(value.strip())

    def _optional_path(self, value: str) -> Path | None:
        text = value.strip()
        return Path(text) if text else None

    def _parse_max_steps(self) -> int:
        try:
            max_steps = int(self.max_steps_var.get().strip())
        except ValueError as exc:
            raise ValueError("max steps must be an integer") from exc
        if max_steps <= 0:
            raise ValueError("max steps must be positive")
        return max_steps

    def _parse_dump_ranges(self) -> list[tuple[int, int]] | None:
        text = self.dump_var.get().strip()
        if not text:
            return None

        ranges: list[tuple[int, int]] = []
        for index, token in enumerate(text.replace(",", " ").split(), start=1):
            if ":" not in token:
                raise ValueError(f"dump range {index} must be START:END")
            start_text, end_text = token.split(":", 1)
            try:
                start = parse_u8(start_text, f"dump range {index} start")
                end = parse_u8(end_text, f"dump range {index} end")
            except ProgramLoadError as exc:
                raise ValueError(str(exc)) from exc
            if start > end:
                raise ValueError(f"dump range {index} start must be <= end")
            ranges.append((start, end))
        return ranges

    def _set_output(self, text: str) -> None:
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)

    def _clear_output(self) -> None:
        self.output.delete("1.0", tk.END)


def launch_gui() -> None:
    app = SimulatorApp()
    app.mainloop()
