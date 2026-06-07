from __future__ import annotations

from dataclasses import dataclass, field

from model_machine.alu import ALU, ALUResult
from model_machine.bus import Bus
from model_machine.io_unit import IOUnit
from model_machine.microcode import MicroInstruction, decode_microprogram
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
    micro_addresses: list[int] = field(default_factory=list)
    micro_words: list[int] = field(default_factory=list)
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
        microprogram: dict[int, int] | dict[int, MicroInstruction] | None = None,
        execution_mode: str = "indexed",
    ) -> None:
        self.memory = memory
        self.registers = registers
        self.bus = bus
        self.alu = alu
        self.io = io
        self.microprogram = self._normalize_microprogram(microprogram)
        self.execution_mode = execution_mode
        self.halted = False
        self._course_result_address = 0x16

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
        if self.execution_mode == "course":
            return self._step_course(step_index)
        if self._uses_real_microcode():
            return self._step_microprogram(step_index)
        return self._step_hardwired(step_index)

    def _step_hardwired(self, step_index: int = 0) -> InstructionTrace:
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
        direct_mode = self.execution_mode == "direct"

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
        elif group == 0x40 and direct_mode:
            value = regs.get_reg(src)
            regs.set_reg(dest, self._transfer(f"R{src}", f"R{dest}", value, micro_ops))
            mnemonic = f"MOV R{dest},R{src}"
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
        elif group == 0x90 and direct_mode:
            mnemonic = self._binary_alu("OR", dest, src, self.alu.bit_or, micro_ops)
        elif group == 0xA0 and direct_mode:
            if src == 0:
                mnemonic = self._unary_alu("SHR", dest, self.alu.shr, micro_ops)
            else:
                mnemonic = self._ror("ROR", dest, micro_ops)
        elif group == 0xB0 and direct_mode:
            mnemonic = self._compare(dest, src, micro_ops)
        elif group in {0xB0, 0xE0}:
            target = self._fetch_operand(operands, micro_ops)
            regs.pc = self._transfer("operand", "PC", target, micro_ops)
            mnemonic = f"JMP {target:02X}H"
        elif group == 0xC0:
            address = self._fetch_operand(operands, micro_ops)
            if direct_mode:
                regs.ar = self._transfer("operand", "AR", address, micro_ops)
                mnemonic = f"LAD R{dest},{address:02X}H"
            else:
                base = regs.get_reg(src)
                address = (base + address) & 0xFF
                regs.ar = self._transfer(f"R{src}+{operands[-1]:02X}H", "AR", address, micro_ops)
                mnemonic = f"LAD R{dest},[R{src}],{operands[-1]:02X}H"
            value = self.memory.read(regs.ar)
            regs.set_reg(dest, self._transfer(f"MEM[{regs.ar:02X}]", f"R{dest}", value, micro_ops))
        elif group == 0xD0:
            address = self._fetch_operand(operands, micro_ops)
            value = regs.get_reg(dest)
            old = self.memory.read(address)
            self.memory.write(address, value)
            memory_writes.append((address, old, value))
            micro_ops.append(f"R{dest}->MEM[{address:02X}] ({value:02X})")
            if direct_mode:
                mnemonic = f"STA R{dest},{address:02X}H"
            else:
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

    def _step_microprogram(self, step_index: int) -> InstructionTrace:
        regs = self.registers
        before = regs.snapshot()
        start_pc = regs.pc
        output_start = len(self.io.outputs)
        operands: list[int] = []
        micro_ops: list[str] = []
        memory_writes: list[tuple[int, int, int]] = []
        micro_addresses: list[int] = []
        micro_words: list[int] = []
        dispatch_seen = False
        halted = False
        opcode = regs.ir

        if regs.mpc == 0:
            regs.mpc = 0x00

        while True:
            address = regs.mpc & 0x3F
            instruction = self.microprogram.get(address)
            if instruction is None:
                raise IllegalInstructionError(
                    f"missing microinstruction at {address:02X}H (PC={regs.pc:02X}H IR={regs.ir:02X}H)"
                )

            regs.mir = instruction.raw
            micro_addresses.append(address)
            micro_words.append(instruction.raw)
            micro_ops.append(f"uPC={address:02X} MIR={instruction.raw:06X}")

            bus_value: int | None = None
            bus_source = "NOP"
            alu_result: ALUResult | None = None

            if instruction.rd:
                if instruction.iom:
                    bus_value = self.io.read(regs.ar)
                    bus_source = f"IO[{regs.ar:02X}]"
                else:
                    bus_value = self.memory.read(regs.ar)
                    bus_source = f"MEM[{regs.ar:02X}]"
                    if dispatch_seen:
                        operands.append(bus_value)
                self.bus.drive(bus_source, bus_value)
            elif instruction.b == 1:
                alu_result = self.alu.operate(instruction.s, regs.a, regs.b, instruction.cn and regs.fc)
                bus_value = self.bus.drive("ALU", alu_result.value)
                bus_source = "ALU"
            elif instruction.b == 2:
                source_index = self._ir_rs()
                bus_value = self.bus.drive(f"R{source_index}", regs.get_reg(source_index))
                bus_source = f"R{source_index}"
            elif instruction.b == 3:
                source_index = self._ir_rd()
                bus_value = self.bus.drive(f"R{source_index}", regs.get_reg(source_index))
                bus_source = f"R{source_index}"
            elif instruction.b == 4:
                bus_value = self.bus.drive("RI", regs.get_reg(2))
                bus_source = "RI"
            elif instruction.b == 6:
                bus_value = self.bus.drive("PC", regs.pc)
                bus_source = "PC"

            if instruction.a == 1 and bus_value is not None:
                regs.a = self.bus.read()
                micro_ops.append(f"{bus_source}->A ({regs.a:02X})")
            elif instruction.a == 2 and bus_value is not None:
                regs.b = self.bus.read()
                micro_ops.append(f"{bus_source}->B ({regs.b:02X})")
            elif instruction.a == 3 and bus_value is not None:
                destination = self._ir_rd()
                value = self.bus.read()
                regs.set_reg(destination, value)
                micro_ops.append(f"{bus_source}->R{destination} ({value:02X})")
            elif instruction.a == 5 and bus_value is not None:
                regs.pc = self.bus.read()
                micro_ops.append(f"{bus_source}->PC ({regs.pc:02X})")
            elif instruction.a == 6 and bus_value is not None:
                regs.ar = self.bus.read()
                micro_ops.append(f"{bus_source}->AR ({regs.ar:02X})")
            elif instruction.a == 7 and bus_value is not None:
                regs.ir = self.bus.read()
                opcode = regs.ir
                micro_ops.append(f"{bus_source}->IR ({regs.ir:02X})")

            if bus_source == "ALU" and alu_result is not None:
                regs.fz = alu_result.zero
                regs.fc = alu_result.carry
                micro_ops.append(f"FZ<-{regs.fz} FC<-{regs.fc}")

            if instruction.wr:
                write_value = bus_value if bus_value is not None else 0
                if instruction.iom:
                    self.io.write(regs.ar, write_value)
                    micro_ops.append(f"{bus_source}->IO[{regs.ar:02X}] ({write_value:02X})")
                else:
                    old = self.memory.read(regs.ar)
                    self.memory.write(regs.ar, write_value)
                    memory_writes.append((regs.ar, old, write_value))
                    micro_ops.append(f"{bus_source}->MEM[{regs.ar:02X}] ({write_value:02X})")

            if instruction.c == 5:
                if instruction.a != 5:
                    regs.pc = (regs.pc + 1) & 0xFF
                    micro_ops.append(f"PC<-{regs.pc:02X}")

            self.bus.clear()

            next_mpc = instruction.ma
            if instruction.c == 1:
                next_mpc = self._branch_p1(instruction.ma)
                dispatch_seen = True
            elif instruction.c == 2:
                next_mpc = self._branch_p2(instruction.ma)
            elif instruction.c == 3:
                next_mpc = self._branch_p3(instruction.ma)
            elif instruction.c == 4:
                next_mpc = self._branch_p4(instruction.ma)

            regs.mpc = next_mpc & 0x3F

            if dispatch_seen and regs.mpc == 0x01:
                break
            if len(micro_addresses) > 512:
                raise IllegalInstructionError(
                    f"microprogram runaway at PC={start_pc:02X}H IR={regs.ir:02X}H uPC={address:02X}H"
                )

        outputs = [(event.port, event.value) for event in self.io.outputs[output_start:]]
        mnemonic = self._format_machine_instruction(opcode, operands)
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
            micro_addresses=micro_addresses,
            micro_words=micro_words,
            halted=halted,
        )

    def _step_course(self, step_index: int) -> InstructionTrace:
        regs = self.registers
        before = regs.snapshot()
        start_pc = regs.pc
        operands: list[int] = []
        micro_ops: list[str] = []
        memory_writes: list[tuple[int, int, int]] = []
        output_start = len(self.io.outputs)

        regs.ar = self._transfer("PC", "AR", regs.pc, micro_ops)
        opcode = self.memory.read(regs.ar)
        regs.ir = self._transfer(f"MEM[{regs.ar:02X}]", "IR", opcode, micro_ops)
        regs.pc = (regs.pc + 1) & 0xFF
        micro_ops.append(f"PC<-{regs.pc:02X}")

        mnemonic = ""
        halted = False

        if opcode in {0x20, 0x21, 0x22, 0x23}:
            dest = opcode & 0x03
            port = self._fetch_operand(operands, micro_ops)
            value = self.io.read(port)
            regs.set_reg(dest, self._transfer(f"IN[{port:02X}]", f"R{dest}", value, micro_ops))
            mnemonic = f"IN R{dest},{port:02X}H"
        elif opcode == 0x61:
            _ = self._fetch_operand(operands, micro_ops)
            address = self._fetch_operand(operands, micro_ops)
            self._course_result_address = address
            sign = (regs.get_reg(0) ^ regs.get_reg(1)) & 0x80
            old = self.memory.read(address)
            self.memory.write(address, sign)
            memory_writes.append((address, old, sign))
            micro_ops.append(f"SIGNXOR->MEM[{address:02X}] ({sign:02X})")
            mnemonic = f"XORF R0,R1,{address:02X}H"
        elif opcode == 0x46:
            value = regs.get_reg(1)
            regs.set_reg(2, self._transfer("R1", "R2", value, micro_ops))
            mnemonic = "MOV R2,R1"
        elif opcode in {0x00, 0x04, 0x08, 0x0C}:
            source = (opcode >> 2) & 0x03
            target = self._fetch_operand(operands, micro_ops)
            if (regs.get_reg(source) & 0x80) == 0:
                regs.pc = self._transfer("operand", "PC", target, micro_ops)
                micro_ops.append("JNCA taken")
            else:
                micro_ops.append("JNCA not taken")
            mnemonic = f"JNCA R{source},{target:02X}H"
        elif opcode in {0x10, 0x11, 0x12, 0x13}:
            dest = opcode & 0x03
            immediate = self._fetch_operand(operands, micro_ops)
            old_value = regs.get_reg(dest)
            value = ((~old_value) + 1) & 0xFF
            regs.set_reg(dest, self._transfer("NEG", f"R{dest}", value, micro_ops))
            regs.fz = int(value == 0)
            regs.fc = int(immediate == 0xFF and old_value != 0)
            micro_ops.append(f"FZ<-{regs.fz} FC<-{regs.fc}")
            mnemonic = f"NINC R{dest},{immediate:02X}H"
        elif opcode == 0x30:
            target = self._fetch_operand(operands, micro_ops)
            regs.pc = self._transfer("operand", "PC", target, micro_ops)
            mnemonic = f"JMP {target:02X}H"
        elif opcode == 0x51:
            _ = self._fetch_operand(operands, micro_ops)
            result_address = self._course_result_address
            dividend = regs.get_reg(0)
            divisor = regs.get_reg(2) or regs.get_reg(1)
            if divisor == 0:
                raise IllegalInstructionError("division by zero in course DIV")
            quotient = int((dividend / divisor) * 0x80)
            if self.memory.read(result_address) & 0x80:
                quotient = (-quotient) & 0xFF
            else:
                quotient &= 0xFF
            old = self.memory.read(result_address)
            self.memory.write(result_address, quotient)
            memory_writes.append((result_address, old, quotient))
            micro_ops.append(f"DIV->MEM[{result_address:02X}] ({quotient:02X})")
            mnemonic = f"DIV R0,R1,{result_address:02X}H"
            halted = True
            self.halted = True
            micro_ops.append("HALT")
        else:
            return self._step_hardwired(step_index)

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

    def _ror(self, name: str, dest: int, micro_ops: list[str]) -> str:
        """Rotate right through carry — FC is shifted into MSB, LSB -> new FC."""
        regs = self.registers
        regs.a = self._transfer(f"R{dest}", "A", regs.get_reg(dest), micro_ops)
        result = self.alu.ror(regs.a, regs.fc)
        self._commit_alu_result(dest, result, micro_ops)
        return f"{name} R{dest}"

    def _compare(self, left: int, right: int, micro_ops: list[str]) -> str:
        regs = self.registers
        regs.a = self._transfer(f"R{left}", "A", regs.get_reg(left), micro_ops)
        regs.b = self._transfer(f"R{right}", "B", regs.get_reg(right), micro_ops)
        result = self.alu.compare(regs.a, regs.b)
        regs.fz = result.zero
        regs.fc = result.carry
        micro_ops.append(f"ALU compare FZ<-{regs.fz} FC<-{regs.fc}")
        return f"CMP R{left},R{right}"

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

    def _normalize_microprogram(
        self, microprogram: dict[int, int] | dict[int, MicroInstruction] | None
    ) -> dict[int, MicroInstruction]:
        if not microprogram:
            return {}
        sample = next(iter(microprogram.values()))
        if isinstance(sample, MicroInstruction):
            return dict(microprogram)
        return decode_microprogram(microprogram)  # type: ignore[arg-type]

    def _uses_real_microcode(self) -> bool:
        return bool(self.microprogram) and 0x01 in self.microprogram and 0x03 in self.microprogram

    def _ir_rs(self) -> int:
        return (self.registers.ir >> 2) & 0x03

    def _ir_rd(self) -> int:
        return self.registers.ir & 0x03

    def _branch_p1(self, ma: int) -> int:
        ir = self.registers.ir
        if ((ir >> 6) & 0x03) != 0x03:
            return ((ma & 0x30) | ((ir >> 4) & 0x0F)) & 0x3F
        return ((ma & 0x30) | 0x0C | ((ir >> 2) & 0x03)) & 0x3F

    def _branch_p2(self, ma: int) -> int:
        ir = self.registers.ir
        return ((ma & 0x3C) | ((ir >> 4) & 0x03)) & 0x3F

    def _branch_p3(self, ma: int) -> int:
        test = 1 if (self.registers.fz or self.registers.fc) else 0
        return ((ma & 0x20) | (test << 4) | (ma & 0x0F)) & 0x3F

    def _branch_p4(self, ma: int) -> int:
        return ma & 0x1F

    def _format_machine_instruction(self, opcode: int, operands: list[int]) -> str:
        byte_text = f"{opcode:02X}"
        if operands:
            byte_text += " " + " ".join(f"{value:02X}" for value in operands)
        return byte_text
