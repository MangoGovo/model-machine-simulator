from __future__ import annotations

from dataclasses import dataclass, field

from model_machine.alu import ALU, ALUResult
from model_machine.bus import Bus
from model_machine.io_unit import IOUnit
from model_machine.memory import Memory
from model_machine.registers import RegisterFile


class IllegalInstructionError(RuntimeError):
    pass


@dataclass
class InstructionTrace:
    step: int
    pc: int
    opcode: int
    operands: list[int]
    mnemonic: str
    micro_ops: list[str]
    before: dict[str, int]
    after: dict[str, int]
    memory_writes: list[tuple[int, int, int]] = field(default_factory=list)
    outputs: list[tuple[int, int]] = field(default_factory=list)
    halted: bool = False


@dataclass
class RunResult:
    reason: str
    steps: int
    traces: list[InstructionTrace]


class ControlUnit:
    def __init__(
        self,
        memory: Memory,
        registers: RegisterFile,
        bus: Bus,
        alu: ALU,
        io: IOUnit,
    ) -> None:
        self.memory = memory
        self.registers = registers
        self.bus = bus
        self.alu = alu
        self.io = io
        self.halted = False

    def run(self, max_steps: int = 10000, stop_on_output: bool = True) -> RunResult:
        traces: list[InstructionTrace] = []
        reason = "max_steps"
        for step_index in range(max_steps):
            trace = self.step(step_index)
            traces.append(trace)
            if trace.halted:
                reason = "halted"
                break
            if stop_on_output and trace.outputs:
                reason = "output"
                break
        return RunResult(reason=reason, steps=len(traces), traces=traces)

    def step(self, step_index: int = 0) -> InstructionTrace:
        if self.halted:
            raise RuntimeError("machine is halted")

        regs = self.registers
        before = regs.snapshot()
        start_pc = regs.pc
        operands: list[int] = []
        micro_ops: list[str] = []
        memory_writes: list[tuple[int, int, int]] = []

        regs.ar = self._transfer("PC", "AR", regs.pc, micro_ops)
        opcode = self.memory.read(regs.ar)
        regs.ir = self._transfer(f"MEM[{regs.ar:02X}]", "IR", opcode, micro_ops)
        regs.pc = (regs.pc + 1) & 0xFF
        micro_ops.append(f"PC<-{regs.pc:02X}")

        group = opcode & 0xF0
        low = opcode & 0x0F
        dest = low & 0x03
        src = (low >> 2) & 0x03
        mnemonic = ""
        halted = False
        output_start = len(self.io.outputs)

        if group == 0x00:
            mnemonic = self._binary_alu("ADD", dest, src, self.alu.add, micro_ops)
        elif group == 0x10:
            mnemonic = self._binary_alu("AND", dest, src, self.alu.bit_and, micro_ops)
        elif group == 0x20:
            port = self._fetch_operand(operands, micro_ops)
            value = self.io.read(port)
            regs.set_reg(dest, self._transfer(f"IN[{port:02X}]", f"R{dest}", value, micro_ops))
            mnemonic = f"IN R{dest},{port:02X}H"
        elif group == 0x30:
            port = self._fetch_operand(operands, micro_ops)
            value = regs.get_reg(src)
            self.io.write(port, value)
            micro_ops.append(f"R{src}->OUT[{port:02X}] ({value:02X})")
            mnemonic = f"OUT {port:02X}H,R{src}"
        elif opcode == 0x50:
            mnemonic = "HLT"
            halted = True
            self.halted = True
            micro_ops.append("HALT")
        elif group == 0x60:
            immediate = self._fetch_operand(operands, micro_ops)
            regs.set_reg(dest, self._transfer("operand", f"R{dest}", immediate, micro_ops))
            mnemonic = f"LDI R{dest},{immediate:02X}H"
        elif group == 0x70:
            mnemonic = self._unary_alu("INC", dest, self.alu.inc, micro_ops)
        elif group == 0x80:
            mnemonic = self._binary_alu("SUB", dest, src, self.alu.sub, micro_ops)
        elif group in {0xB0, 0xE0}:
            target = self._fetch_operand(operands, micro_ops)
            regs.pc = self._transfer("operand", "PC", target, micro_ops)
            mnemonic = f"JMP {target:02X}H"
        elif group == 0xC0:
            offset = self._fetch_operand(operands, micro_ops)
            base = regs.get_reg(src)
            addr = (base + offset) & 0xFF
            regs.ar = self._transfer(f"R{src}+{offset:02X}H", "AR", addr, micro_ops)
            value = self.memory.read(regs.ar)
            regs.set_reg(dest, self._transfer(f"MEM[{regs.ar:02X}]", f"R{dest}", value, micro_ops))
            mnemonic = f"LAD R{dest},[R{src}],{offset:02X}H"
        elif group == 0xD0:
            address = self._fetch_operand(operands, micro_ops)
            value = regs.get_reg(dest)
            old = self.memory.read(address)
            self.memory.write(address, value)
            memory_writes.append((address, old, value))
            micro_ops.append(f"R{dest}->MEM[{address:02X}] ({value:02X})")
            mnemonic = f"STA {address:02X}H,R{dest}"
        elif opcode == 0xF0:
            target = self._fetch_operand(operands, micro_ops)
            taken = bool(regs.fz or regs.fc)
            if taken:
                regs.pc = self._transfer("operand", "PC", target, micro_ops)
            else:
                micro_ops.append("BZC not taken")
            mnemonic = f"BZC {target:02X}H"
        else:
            raise IllegalInstructionError(f"unknown opcode {opcode:02X}H at {start_pc:02X}H")

        outputs = [(event.port, event.value) for event in self.io.outputs[output_start:]]
        return InstructionTrace(
            step=step_index,
            pc=start_pc,
            opcode=opcode,
            operands=operands,
            mnemonic=mnemonic,
            micro_ops=micro_ops,
            before=before,
            after=regs.snapshot(),
            memory_writes=memory_writes,
            outputs=outputs,
            halted=halted,
        )

    def _fetch_operand(self, operands: list[int], micro_ops: list[str]) -> int:
        regs = self.registers
        regs.ar = self._transfer("PC", "AR", regs.pc, micro_ops)
        value = self.memory.read(regs.ar)
        operands.append(value)
        micro_ops.append(f"MEM[{regs.ar:02X}]->operand ({value:02X})")
        regs.pc = (regs.pc + 1) & 0xFF
        micro_ops.append(f"PC<-{regs.pc:02X}")
        return value

    def _binary_alu(self, name: str, dest: int, src: int, operation, micro_ops: list[str]) -> str:
        regs = self.registers
        regs.a = self._transfer(f"R{dest}", "A", regs.get_reg(dest), micro_ops)
        regs.b = self._transfer(f"R{src}", "B", regs.get_reg(src), micro_ops)
        result = operation(regs.a, regs.b)
        self._commit_alu_result(dest, result, micro_ops)
        return f"{name} R{dest},R{src}"

    def _unary_alu(self, name: str, dest: int, operation, micro_ops: list[str]) -> str:
        regs = self.registers
        regs.a = self._transfer(f"R{dest}", "A", regs.get_reg(dest), micro_ops)
        result = operation(regs.a)
        self._commit_alu_result(dest, result, micro_ops)
        return f"{name} R{dest}"

    def _commit_alu_result(self, dest: int, result: ALUResult, micro_ops: list[str]) -> None:
        regs = self.registers
        regs.set_reg(dest, self._transfer("ALU", f"R{dest}", result.value, micro_ops))
        regs.fz = result.zero
        regs.fc = result.carry
        micro_ops.append(f"FZ<-{regs.fz} FC<-{regs.fc}")

    def _transfer(self, source: str, target: str, value: int, micro_ops: list[str]) -> int:
        self.bus.drive(source, value)
        byte = self.bus.read()
        self.bus.clear()
        micro_ops.append(f"{source}->{target} ({byte:02X})")
        return byte
