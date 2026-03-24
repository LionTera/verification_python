def make_tcp_packet():
    # Ethernet + IPv4 + TCP minimal example
    eth = bytes.fromhex(
        "001122334455"  # dst mac
        "66778899aabb"  # src mac
        "0800"          # ethertype IPv4
    )

    ip = bytes([
        0x45, 0x00,             # version/ihl, dscp
        0x00, 0x28,             # total length
        0x00, 0x01,             # identification
        0x00, 0x00,             # flags/frag
        0x40,                   # ttl
        0x06,                   # protocol = TCP
        0x00, 0x00,             # checksum
        192, 168, 1, 10,        # src ip
        192, 168, 1, 20,        # dst ip
    ])

    tcp = bytes([
        0x1F, 0x90,             # src port 8080
        0x00, 0x50,             # dst port 80
        0x00, 0x00, 0x00, 0x01, # seq
        0x00, 0x00, 0x00, 0x00, # ack
        0x50, 0x02,             # data offset, SYN
        0x72, 0x10,             # window
        0x00, 0x00,             # checksum
        0x00, 0x00,             # urgent
    ])

    return eth + ip + tcp


def make_zero_program(n_words=4):
    return [0] * n_words
