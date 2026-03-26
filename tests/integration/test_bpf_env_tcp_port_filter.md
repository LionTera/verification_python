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
ldb [23]
jeq #6, jt 0, jf 2
ldb [37]
jeq #80, jt 1, jf 0
ret #0
ret #1
```

## Program Meaning

1. Load the IPv4 protocol byte from offset `23`
2. If protocol is not TCP (`6`), jump to reject
3. Load the low byte of the TCP destination port from offset `37`
4. If that byte is `80` (`0x50`), jump to accept
5. Otherwise reject

## What It Verifies

- absolute packet byte loads work
- conditional jumps work
- multi-instruction control flow works
- protocol filtering works
- destination-port filtering works for the current packet set

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
