from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from model_machine.loader import ProgramLoadError, parse_u8
from model_machine.simulation import parse_input_values, run_simulation


class SimulatorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("模型机仿真器")
        self.minsize(860, 720)

        self.input_var = tk.StringVar(value="08,04")
        self.max_steps_var = tk.StringVar(value="10000")
        self.dump_var = tk.StringVar(value="60:70")
        self.trace_var = tk.BooleanVar(value=False)

        self._build_ui()

    # ---- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=0)
        root.rowconfigure(0, weight=1)  # program text area
        root.rowconfigure(6, weight=1)  # output text area

        # Row 0: program input label
        ttk.Label(
            root,
            text="程序  —  $M = 微程序 / 控制存储器,  $P = 机器程序 / 主存",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        # Row 1: editable text area
        self.program_text = tk.Text(
            root,
            wrap="none",
            font=("Menlo", 12),
            height=16,
            undo=True,
        )
        self.program_text.grid(
            row=1, column=0, columnspan=3, sticky="nsew", pady=(0, 4)
        )

        program_y_scroll = ttk.Scrollbar(
            root, orient="vertical", command=self.program_text.yview
        )
        program_y_scroll.grid(row=1, column=3, sticky="ns", pady=(0, 4))
        self.program_text.configure(yscrollcommand=program_y_scroll.set)

        # Row 2: Import / Clear buttons
        btn_frame = ttk.Frame(root)
        btn_frame.grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        ttk.Button(
            btn_frame, text="导入文件", command=self._import_file
        ).pack(side="left")
        ttk.Button(
            btn_frame, text="清空", command=self._clear_program_text
        ).pack(side="left", padx=(8, 0))

        # Row 3: Input bytes
        ttk.Label(root, text="输入字节").grid(
            row=3, column=0, sticky="w", pady=(0, 0)
        )
        ttk.Entry(root, textvariable=self.input_var).grid(
            row=3, column=1, columnspan=2, sticky="ew", pady=(0, 0)
        )

        # Row 4: Max steps
        ttk.Label(root, text="最大步数").grid(
            row=4, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(
            root, textvariable=self.max_steps_var, width=16
        ).grid(row=4, column=1, sticky="w", pady=(8, 0))

        # Row 5: Dump ranges + Trace
        ttk.Label(root, text="内存转储范围").grid(
            row=5, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(root, textvariable=self.dump_var).grid(
            row=5, column=1, sticky="ew", pady=(8, 0)
        )
        ttk.Checkbutton(
            root, text="指令跟踪", variable=self.trace_var
        ).grid(row=5, column=2, sticky="e", pady=(8, 0))

        # Row 6: Run / Clear output
        actions = ttk.Frame(root)
        actions.grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=(12, 8)
        )
        ttk.Button(actions, text="运行", command=self._run).pack(
            side="left"
        )
        ttk.Button(
            actions, text="清空输出", command=self._clear_output
        ).pack(side="left", padx=(8, 0))

        # Row 7: output area
        self.output = tk.Text(
            root, wrap="none", font=("Menlo", 12), height=20
        )
        self.output.grid(
            row=7, column=0, columnspan=3, sticky="nsew"
        )

        out_y_scroll = ttk.Scrollbar(
            root, orient="vertical", command=self.output.yview
        )
        out_y_scroll.grid(row=7, column=3, sticky="ns")
        self.output.configure(yscrollcommand=out_y_scroll.set)

        out_x_scroll = ttk.Scrollbar(
            root, orient="horizontal", command=self.output.xview
        )
        out_x_scroll.grid(
            row=8, column=0, columnspan=3, sticky="ew"
        )
        self.output.configure(xscrollcommand=out_x_scroll.set)

    # ---- actions -----------------------------------------------------------

    def _import_file(self) -> None:
        path = filedialog.askopenfilename(
            title="选择程序文件",
            filetypes=(("文本文件", "*.txt"), ("所有文件", "*")),
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("文件错误", str(exc))
            return
        self.program_text.delete("1.0", tk.END)
        self.program_text.insert(tk.END, content)

    def _clear_program_text(self) -> None:
        self.program_text.delete("1.0", tk.END)

    def _run(self) -> None:
        program_content = self.program_text.get("1.0", tk.END).strip()
        if not program_content:
            messagebox.showerror("输入错误", "请输入程序内容")
            return

        try:
            max_steps = self._parse_max_steps()
            dump_ranges = self._parse_dump_ranges()
            output = run_simulation(
                combined_text=program_content,
                input_values=parse_input_values([self.input_var.get()]),
                max_steps=max_steps,
                trace=self.trace_var.get(),
                dump_ranges=dump_ranges,
            )
        except Exception as exc:
            messagebox.showerror("仿真错误", str(exc))
            return

        self._set_output(output)

    def _parse_max_steps(self) -> int:
        try:
            max_steps = int(self.max_steps_var.get().strip())
        except ValueError as exc:
            raise ValueError("最大步数必须为整数") from exc
        if max_steps <= 0:
            raise ValueError("最大步数必须为正数")
        return max_steps

    def _parse_dump_ranges(self) -> list[tuple[int, int]] | None:
        text = self.dump_var.get().strip()
        if not text:
            return None

        ranges: list[tuple[int, int]] = []
        for index, token in enumerate(
            text.replace(",", " ").split(), start=1
        ):
            if ":" not in token:
                raise ValueError(
                    f"转储范围 {index} 必须为 起始:结束 格式"
                )
            start_text, end_text = token.split(":", 1)
            try:
                start = parse_u8(start_text, f"转储范围 {index} 起始")
                end = parse_u8(end_text, f"转储范围 {index} 结束")
            except ProgramLoadError as exc:
                raise ValueError(str(exc)) from exc
            if start > end:
                raise ValueError(
                    f"转储范围 {index} 起始必须 <= 结束"
                )
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
