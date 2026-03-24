# Suggested BPF Architecture

## Suggested Full Implementation

- Top candidate: **bpf_npu**
- Control: **bpf_control**
- Datapath: **bpf_dp**
- Instruction memory: **bpf_iram**
- Packet memory: **bpf_pram**
- Scratch memory: **bpf_sram**
- ALU helpers: **bpf_div, bpf_mult**

## Suggested Connection Model

- `bpf_control` fetches instructions from `bpf_iram`
- `bpf_control` drives control signals into `bpf_dp`
- `bpf_dp` reads packet-related data from `bpf_pram`
- `bpf_dp` writes or reads scratch/state via `bpf_sram`
- `bpf_dp` likely uses ALU helpers: `bpf_div, bpf_mult`

## Verification Progression

1. Verify control-only behavior on the control module.
2. Verify datapath-only behavior on the datapath module.
3. Verify control + datapath together.
4. Verify packet memory + scratch/SRAM path.
5. Verify full top-level integration.

## Top Candidates Ranking

- `bpf_control` (score=118)
- `bpf_npu` (score=93)
- `bpf_dp` (score=90)
- `bpf_shifter` (score=60)
- `bpf_env` (score=45)
- `bpf_iram` (score=14)
- `bpf_pram` (score=14)
- `bpf_div` (score=12)
- `bpf_mult` (score=12)
- `bpf_sram` (score=12)
