"""Model referensi CRC-8 untuk rtl/crc8.

Default-nya CRC-8/SMBUS: poly 0x07, init 0x00, MSB dulu, tanpa refleksi,
tanpa XOR akhir. Check value standar: crc8(b"123456789") == 0xF4.

Jalankan langsung (`python3 model/crc8.py`) untuk self-test.
"""

POLY = 0x07
INIT = 0x00
CHECK = 0xF4  # CRC-8/SMBUS atas b"123456789"


def update(crc: int, byte: int, poly: int = POLY) -> int:
    """Satu langkah: serap satu byte ke register CRC."""
    r = (crc ^ byte) & 0xFF
    for _ in range(8):
        r = ((r << 1) ^ poly) & 0xFF if r & 0x80 else (r << 1) & 0xFF
    return r


def crc8(data: bytes, init: int = INIT, poly: int = POLY) -> int:
    crc = init
    for b in data:
        crc = update(crc, b, poly)
    return crc


# update(s, b) == TABLE[s ^ b]
TABLE = [update(0, i) for i in range(256)]
# TABLE adalah permutasi, jadi setiap state bisa dicapai dari state mana pun
# dalam satu byte: update(s, s ^ TABLE_INV[t]) == t.
TABLE_INV = [0] * 256
for _i, _v in enumerate(TABLE):
    TABLE_INV[_v] = _i


def steer(current: int, target: int) -> int:
    """Byte yang membawa register dari `current` ke `target` dalam satu langkah."""
    return current ^ TABLE_INV[target]


def _self_test() -> None:
    assert crc8(b"123456789") == CHECK, hex(crc8(b"123456789"))
    assert sorted(TABLE) == list(range(256)), "TABLE bukan permutasi"
    for s in range(256):
        for t in (0x00, 0x5A, 0xFF, s):
            assert update(s, steer(s, t)) == t
        for b in range(256):
            assert update(s, b) == TABLE[s ^ b]
    print("model/crc8.py: OK")


if __name__ == "__main__":
    _self_test()
