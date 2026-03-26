# `test_bpf_env_tcp`

## Purpose

Verify that a structured TCP packet can be loaded into packet RAM and processed by the DUT.

## Packet Under Test

- Ethernet + IPv4 + TCP SYN packet
- source port `1234`
- destination port `80`

## Program Under Test

```text
ret #1
```

## What It Verifies

- packet construction helper is valid enough for the DUT
- packet RAM loading works for a normal L2/L3/L4 packet
- the DUT can process a realistic TCP packet

## Expected Result

- `returned == True`
- `accepted == True`
- packet length is at least the minimum Ethernet+IPv4+TCP header size
