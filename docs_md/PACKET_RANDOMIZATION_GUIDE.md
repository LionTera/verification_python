# Packet Randomization Guide

This guide explains how packet randomization works in the Python BPF verification flow, which fields can be randomized, what values are considered valid, and how those fields are typically filtered by BPF programs.

## Purpose

Randomization is used to create broader stimulus while keeping runs reproducible.

The design goal is:

- same seed + same parameters + same randomization field list = same generated traffic
- different seed = different but still repeatable traffic

The randomization logic lives in:

- [packet_generator.py](/abs/path/c:/Users/Lionn%20Bruckstein/Documents/verification_python/tests/bpf_env/packet_generator.py)

## How Randomization Works

The generator creates a local Python RNG:

```python
rng = random.Random(seed)
```

Every randomized field then draws its values from that RNG in a fixed order.

That means:

- packet 0 always gets the same randomized values for a given seed
- packet 1 always gets the same randomized values for a given seed
- changing the selected fields changes the generated stream, because it changes which RNG draws happen

So reproducibility depends on all of these:

- seed
- protocol mode
- unique packet count
- selected randomization fields

## User Control

Randomization is selected with a comma-separated field list.

Pytest:

```bash
python -m pytest tests/integration/stress/test_bpf_env_configurable_traffic.py -s \
  --bpf-reports \
  --bpf-unique-packets 40 \
  --bpf-protocol-mode 3 \
  --bpf-error-level 2 \
  --bpf-packet-rng-seed 0x1234 \
  --bpf-randomize-fields ttl,dscp_ecn,payload_len,payload_bytes,tcp_flags
```

Standalone generator:

```bash
python -m tests.bpf_env.packet_generator \
  --unique-packets 10 \
  --protocol-mode 3 \
  --error-level 2 \
  --seed 0x1234 \
  --randomize-fields ttl,dscp_ecn,payload_len,payload_bytes,tcp_flags \
  --show-limit 10
```

## Supported Randomization Fields

The current supported field names are:

- `length`
- `payload_len`
- `payload_bytes`
- `ttl`
- `dscp_ecn`
- `src_ip`
- `dst_ip`
- `identification`
- `flags_fragment`
- `src_port`
- `seq`
- `ack`
- `tcp_flags`
- `tcp_window`
- `ip_protocol`

`length` and `payload_len` both mean payload-length randomization. Total packet length changes indirectly because IPv4 total length and frame size are derived from payload size.

## Valid Value Ranges

### `length` / `payload_len`

Meaning:

- random payload length

Current range:

- `0..32` payload bytes

Effect:

- changes payload size
- changes IPv4 total length
- changes final frame length

Typical BPF filtering:

- `ld len`
- compare total packet length indirectly through fixed offsets if your RTL exposes it
- payload-offset checks if packet format is fixed

### `payload_bytes`

Meaning:

- random payload content

Current behavior:

- each payload byte is drawn from `0x00..0xFF`
- payload length stays at the current selected length

Typical BPF filtering:

- `ldb abs` for fixed payload offsets
- `ldxb msh` + `ldb ind` if payload position depends on IPv4 header length

### `ttl`

Meaning:

- IPv4 time-to-live byte

Valid range:

- `1..255`

Typical BPF filtering:

- absolute byte load of the TTL field
- compare with `jeq`, `jgt`, or `jge`

Example filter logic:

- reject packets with `ttl < 64`

### `dscp_ecn`

Meaning:

- full IPv4 DSCP/ECN byte

Valid range:

- `0..255`

Field structure:

- upper 6 bits = DSCP (`0..63`)
- lower 2 bits = ECN (`0..3`)

Typical BPF filtering:

- load the byte
- mask with `and #0xFC` to isolate DSCP
- compare against a DSCP class
- optionally mask with `and #0x03` to isolate ECN

### `src_ip`

Meaning:

- IPv4 source address

Current range:

- deterministic values inside `10.1.x.y`

Typical BPF filtering:

- load source IP bytes/word
- compare against subnet or exact source host

### `dst_ip`

Meaning:

- IPv4 destination address

Current range:

- deterministic values inside `192.168.x.y`

Typical BPF filtering:

- compare against exact host
- compare masked prefix if the program implements subnet logic

### `identification`

Meaning:

- IPv4 identification field

Valid range:

- `0..65535`

Typical BPF filtering:

- two-byte field load
- equality checks or grouping checks

### `flags_fragment`

Meaning:

- full IPv4 flags/fragment-offset field

Current range:

- `0x0000`
- `0x4000`

Current behavior:

- only no-fragment or DF is randomized
- fragment offset remains zero

Reason:

- it keeps packets structurally simple while still varying the field

Typical BPF filtering:

- mask `0x4000` to check DF
- compare whole field if needed

### `src_port`

Meaning:

- TCP/UDP source port

Valid range:

- `1024..65535`

Typical BPF filtering:

- L4 source-port loads
- compare against service ranges or client-port ranges

### `seq`

Meaning:

- TCP sequence number

Valid range:

- `0..0xFFFFFFFF`

Typical BPF filtering:

- 32-bit load
- equality/range checks in specialized tests

### `ack`

Meaning:

- TCP acknowledgment number

Valid range:

- `0..0xFFFFFFFF`

Typical BPF filtering:

- 32-bit load
- usually combined with TCP flag checks

### `tcp_flags`

Meaning:

- TCP control flags byte

Current randomized choices:

- `0x02` = SYN
- `0x10` = ACK
- `0x12` = SYN|ACK
- `0x18` = PSH|ACK
- `0x11` = FIN|ACK
- `0x04` = RST

Typical BPF filtering:

- load TCP flags byte
- use `jset` for bit tests

Example:

- accept only packets with SYN set

### `tcp_window`

Meaning:

- TCP window field

Valid range:

- `512..65535`

Typical BPF filtering:

- 16-bit load
- compare to thresholds or classes

### `ip_protocol`

Meaning:

- IPv4 protocol field for raw `l4="ip"` packets

Current randomized choices:

- `1` = ICMP
- `2` = IGMP
- `6` = TCP
- `17` = UDP
- `47` = GRE

Typical BPF filtering:

- single-byte protocol compare

## How Filtering Relates To Randomization

The important rule is:

- only randomize fields that the current BPF program can still interpret correctly

Examples:

- randomizing `ttl` is safe if the program reads the TTL byte
- randomizing `dscp_ecn` is safe if the program reads the DSCP/ECN byte
- randomizing `tcp_flags` is safe if the program reads the TCP flags byte

The main unsafe class is variable header layout.

Example:

- if IPv4 header length changes, absolute offsets for TCP fields move
- a program using fixed `ldb abs [offset]` for TCP destination port can break
- in that case you need `ldxb msh` and indirect loads

That is why the richer mixed-program tests use:

- `ldxb msh`
- `ldb ind`

instead of relying only on fixed absolute offsets.

## Practical Guidance

Good randomization sets for current configurable traffic tests:

- `ttl,dscp_ecn,payload_len,payload_bytes,tcp_flags`
- `src_ip,dst_ip,src_port,seq,ack`

Good randomization sets for protocol-only or golden-model runs:

- `ttl,dscp_ecn,identification,flags_fragment,payload_len,payload_bytes`

If you want to test filters that depend on variable L3/L4 layout, do not stay with a simple absolute-offset program. Use a more advanced filter program that computes offsets dynamically.
