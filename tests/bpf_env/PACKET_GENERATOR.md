# Packet Generator

## Purpose

This helper provides a reusable way to describe packet inputs for BPF tests without hardcoding every packet inline in each test.

File:

- [`packet_generator.py`](C:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/packet_generator.py)

## What It Provides

- `PacketSpec`
  - declarative packet description
- `build_packet(spec)`
  - converts a `PacketSpec` into raw bytes
- `derive_packet(base, **changes)`
  - clone-and-modify helper for variants
- `packet_stream(specs)`
  - build a named sequence of packets
- `random_packet_stream(...)`
  - deterministic random TCP/UDP traffic generation
- `generate_configurable_packet_stream(...)`
  - configurable packet generation with protocol/error selection and optional field randomization

## Example

```python
from tests.bpf_env.packet_generator import PacketSpec, build_packet, derive_packet, packet_stream

base = PacketSpec(
    l4="tcp",
    dst_port=0x5678,
    payload=bytes.fromhex("deadbeef"),
    name="tcp_accept",
)

tcp_accept = build_packet(base)
tcp_reject = build_packet(derive_packet(base, dst_port=0x56BB, name="tcp_reject"))
udp_reject = build_packet(derive_packet(base, l4="udp", name="udp_reject"))
```

## Do Existing Tests Need To Change?

No.

The current tests can keep using:

- `make_tcp_packet(...)`
- `make_udp_packet(...)`

unchanged.

The generator is additive. It gives you a cleaner way to build packet sequences in new tests or when refactoring older tests.

## When To Use It

Use the generator when:

- a test needs many packet variants
- you want a named packet sequence
- you want deterministic random traffic from one seed
- you want selected fields randomized while keeping the run reproducible
- you want test inputs described as data rather than handwritten packet calls

Use the existing packet builders when:

- a test only needs one or two simple packets
- inline `make_tcp_packet(...)` is already clear enough

## User-Selected Randomization

The configurable generator accepts a comma-separated field list that tells it what to randomize.

Example:

```bash
python -m tests.bpf_env.packet_generator \
  --unique-packets 10 \
  --protocol-mode 3 \
  --error-level 2 \
  --seed 0x1234 \
  --randomize-fields ttl,dscp_ecn,payload_len,payload_bytes,tcp_flags \
  --show-limit 10
```

The detailed field list, valid value ranges, and filtering implications are documented in:

- [PACKET_RANDOMIZATION_GUIDE.md](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/docs_md/PACKET_RANDOMIZATION_GUIDE.md)
