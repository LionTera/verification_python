# BPF Integration Report

## Result

| Field | Value |
| --- | --- |
| Cycles | `41` |
| Returned | `True` |
| Accepted | `True` |
| Return Value | `0x00000001` |
| CSV Trace | `reports/bpf_packet_header_probe.csv` |

## Packet

- Length: `58` bytes
- Raw bytes: `aabbccddeeff11223344556608004500002c1234400040065a310a010203c00002631234567801020304a1b2c3d45012100061900000deadbeef`

### Ethernet

| Field | Value |
| --- | --- |
| Destination MAC | `aa:bb:cc:dd:ee:ff` |
| Source MAC | `11:22:33:44:55:66` |
| EtherType | `0x0800` |

### IPv4

| Field | Value |
| --- | --- |
| Version | `4` |
| Header Length | `20` bytes |
| Total Length | `44` bytes |
| TTL | `64` |
| Protocol | `6` |
| Source IP | `10.1.2.3` |
| Destination IP | `192.0.2.99` |

### TCP

| Field | Byte Range | Value |
| --- | --- | --- |
| Source Port | `0-1` | `4660` |
| Destination Port | `2-3` | `22136` |
| Sequence Number | `4-7` | `16909060` |
| Acknowledgment Number | `8-11` | `2712847316` |
| Header Length | `12[7:4]` | `20` bytes |
| Flags | `13` | `ACK,SYN` (`0x12`) |
| Window | `14-15` | `4096` |
| Checksum | `16-17` | `0x6190` |
| Urgent Pointer | `18-19` | `0` |
| Payload Length | `20+` | `4` bytes |

### Packet Memory Words

| PRAM Address | Packet Byte Range | 32-bit Word | Raw Bytes |
| --- | --- | --- | --- |
| `0x0000` | `0-3` | `0xaabbccdd` | `aabbccdd` |
| `0x0004` | `4-7` | `0xeeff1122` | `eeff1122` |
| `0x0008` | `8-11` | `0x33445566` | `33445566` |
| `0x000c` | `12-15` | `0x08004500` | `08004500` |
| `0x0010` | `16-19` | `0x002c1234` | `002c1234` |
| `0x0014` | `20-23` | `0x40004006` | `40004006` |
| `0x0018` | `24-27` | `0x5a310a01` | `5a310a01` |
| `0x001c` | `28-31` | `0x0203c000` | `0203c000` |
| `0x0020` | `32-35` | `0x02631234` | `02631234` |
| `0x0024` | `36-39` | `0x56780102` | `56780102` |
| `0x0028` | `40-43` | `0x0304a1b2` | `0304a1b2` |
| `0x002c` | `44-47` | `0xc3d45012` | `c3d45012` |
| `0x0030` | `48-51` | `0x10006190` | `10006190` |
| `0x0034` | `52-55` | `0x0000dead` | `0000dead` |
| `0x0038` | `56-57` | `0xbeef0000` | `beef` |

## BPF Program

| Index | Raw | Assembly | Details |
| --- | --- | --- | --- |
| `0` | `0x0006000000000001` | `ret #1` | `RET_K (code=0x06, jt=0, jf=0, k=0x00000001)` |
