# `test_bpf_env_tcp_port_filter`

## Purpose

Verify a real multi-instruction BPF filter that inspects packet fields and branches.

## Packets Under Test

Accepted case:

- Ethernet + IPv4 + TCP
- destination port `80`

Rejected cases:

- Ethernet + IPv4 + TCP with destination port `443`
- Ethernet + IPv4 + UDP with destination port `80`

## Program Under Test

```text
ldb [protocol_offset]
jeq #6, jt 0, jf 2
ldb [dst_port_low_byte_offset]
jeq #80, jt 1, jf 0
ret #0
ret #1
```

## Program Meaning

1. Probe the DUT to discover which byte offset exposes the IPv4 protocol byte
2. Probe the DUT to discover which byte offset exposes the TCP destination-port low byte
3. Load the discovered IPv4 protocol byte
2. If protocol is not TCP (`6`), jump to reject
3. Load the discovered low byte of the TCP destination port
4. If that byte is `80` (`0x50`), jump to accept
5. Otherwise reject

## What It Verifies

- absolute packet byte loads work
- conditional jumps work
- multi-instruction control flow works
- protocol filtering works
- destination-port filtering works for the current packet set
- the test adapts to the RTL's actual packet-byte mapping instead of assuming software-standard offsets

## Expected Result

For TCP destination port `80`:

- `returned == True`
- `accepted == True`
- `ret_value == 1`

For TCP destination port `443`:

- `returned == True`
- `accepted == False`
- `ret_value == 0`

For UDP destination port `80`:

- `returned == True`
- `accepted == False`
- `ret_value == 0`

## Notes

This test intentionally probes packet-field offsets using small `ldb [k]; ret a` programs before running the final filter.

Reason:

- this RTL does not expose packet bytes at exactly the same offsets a software BPF implementation would assume
- probing avoids hardcoding an offset that is wrong for the hardware datapath
