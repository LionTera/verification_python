# `test_bpf_env_accept_reject`

## Purpose

Verify the simplest accept/reject behavior of the DUT using classic BPF return instructions.

## Packet Under Test

- Ethernet + IPv4 + TCP SYN packet
- source port `1234`
- destination port `80`

## Programs Under Test

Accept path:

```text
ret #1
```

Reject path:

```text
ret #0
```

## What It Verifies

- `RET_K` executes correctly
- non-zero return values map to accept
- zero return values map to reject
- both paths reach `bpf_return`

## Expected Result

For `ret #1`:

- `returned == True`
- `accepted == True`
- `ret_value == 1`

For `ret #0`:

- `returned == True`
- `accepted == False`
- `ret_value == 0`
