import csv
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class BpfCycle:
    cycle: int
    bpf_start: int
    bpf_return: int
    bpf_active: int
    bpf_accept: int
    bpf_reject: int
    bpf_ret_value: int
    bpf_mmap_addr: int
    bpf_mmap_wdata: int
    bpf_mmap_wr: int
    bpf_pram_waddr: int
    bpf_pram_wdata: int
    bpf_pram_wr: int
    bpf_packet_len: int


class BpfPythonTB:
    # IMPORTANT:
    # BPF_START_ADDR is used by the Verilog TB but its numeric value is not shown
    # in tb_bpf.v directly. Set it here once you locate it in the package/include files.
    BPF_START_ADDR = 0

    def __init__(self, dut):
        self.dut = dut
        self.trace = []

    def init_signals(self):
        d = self.dut

        d.bpf_start        @= 0
        d.bpf_packet_len   @= 0
        d.bpf_packet_loss  @= 0

        d.bpf_mmap_addr    @= 0
        d.bpf_mmap_wdata   @= 0
        d.bpf_mmap_wr      @= 0
        d.bpf_mmap_rd      @= 0

        d.bpf_pram_waddr   @= 0
        d.bpf_pram_wdata   @= 0
        d.bpf_pram_wr      @= 0
        d.bpf_pram_raddr   @= 0

        d.bpf_pram_bank_rx   @= 0
        d.bpf_pram_bank_bpf  @= 0
        d.bpf_pram_bank_tx   @= 0

        d.sim_eval_combinational()

    def log_cycle(self, cycle):
        d = self.dut
        self.trace.append(BpfCycle(
            cycle=cycle,
            bpf_start=int(d.bpf_start),
            bpf_return=int(d.bpf_return),
            bpf_active=int(d.bpf_active),
            bpf_accept=int(d.bpf_accept),
            bpf_reject=int(d.bpf_reject),
            bpf_ret_value=int(d.bpf_ret_value),
            bpf_mmap_addr=int(d.bpf_mmap_addr),
            bpf_mmap_wdata=int(d.bpf_mmap_wdata),
            bpf_mmap_wr=int(d.bpf_mmap_wr),
            bpf_pram_waddr=int(d.bpf_pram_waddr),
            bpf_pram_wdata=int(d.bpf_pram_wdata),
            bpf_pram_wr=int(d.bpf_pram_wr),
            bpf_packet_len=int(d.bpf_packet_len),
        ))

    def dump_trace_csv(self, path):
        if not self.trace:
            return
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=asdict(self.trace[0]).keys())
            writer.writeheader()
            for row in self.trace:
                writer.writerow(asdict(row))

    def load_program(self, instructions, start_addr=0):
        # Mirrors the Verilog TB approach:
        # each 64-bit instruction is written as two 32-bit MMAP writes.
        d = self.dut

        for i, inst in enumerate(instructions):
            low  = inst & 0xffffffff
            high = (inst >> 32) & 0xffffffff

            d.bpf_mmap_addr  @= start_addr + (i << 1)
            d.bpf_mmap_wdata @= low
            d.bpf_mmap_wr    @= 1
            d.sim_tick()

            d.bpf_mmap_addr  @= start_addr + (i << 1) + 1
            d.bpf_mmap_wdata @= high
            d.bpf_mmap_wr    @= 1
            d.sim_tick()

        d.bpf_mmap_wr @= 0

        # Enable bit + start address, same style as Verilog TB.
        d.bpf_mmap_addr  @= self.BPF_START_ADDR
        d.bpf_mmap_wdata @= 0x80000000 | start_addr
        d.bpf_mmap_wr    @= 1
        d.sim_tick()
        d.bpf_mmap_wr    @= 0

    def load_packet(self, packet_bytes: bytes):
        # Mirrors Verilog init_packet_mem:
        # packet is written as 32-bit words with byte swap
        d = self.dut

        for addr in range(0, len(packet_bytes), 4):
            chunk = packet_bytes[addr:addr+4]
            while len(chunk) < 4:
                chunk += b'\x00'

            # same byte ordering idea as the Verilog TB
            word = (chunk[3] << 24) | (chunk[2] << 16) | (chunk[1] << 8) | chunk[0]

            d.bpf_pram_waddr @= addr
            d.bpf_pram_wdata @= word
            d.bpf_pram_wr    @= 1
            d.sim_tick()

        d.bpf_pram_wr @= 0

    def start(self, packet_len):
        d = self.dut
        d.bpf_packet_len @= packet_len
        d.bpf_start      @= 1
        d.sim_tick()
        d.bpf_start      @= 0
        d.sim_eval_combinational()

    def run_until_return(self, max_cycles=1000):
        d = self.dut
        cycle = 0

        while not int(d.bpf_return):
            self.log_cycle(cycle)
            d.sim_tick()
            cycle += 1
            if cycle >= max_cycles:
                raise RuntimeError("Timeout waiting for bpf_return")

        self.log_cycle(cycle)
        return cycle

    def print_summary(self):
        d = self.dut
        print("\n[BPF SUMMARY]")
        print("  bpf_return   =", int(d.bpf_return))
        print("  bpf_active   =", int(d.bpf_active))
        print("  bpf_accept   =", int(d.bpf_accept))
        print("  bpf_reject   =", int(d.bpf_reject))
        print("  bpf_ret_value=", hex(int(d.bpf_ret_value)))
