"""Validasi golden model (model/ascon.py) terhadap seluruh vektor resmi, tanpa RTL.

  python3 tb/ascon/check_model.py        (dari root, setelah `make ascon-vectors`)

Keluar 0 kalau semua cocok. Dijalankan oleh `make test-ascon-model`.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "model"))
sys.path.insert(0, os.path.dirname(__file__))

import ascon as A  # noqa: E402
import vectors as V  # noqa: E402


def main():
    bad = 0

    n = 0
    for t in V.acvp_aead():
        n += 1
        if t["direction"] == "encrypt":
            ct, tag = A.aead_encrypt(t["key"], t["nonce"], t["ad"], t["pt"], t["ad_bits"],
                                     t["pt_bits"], t["tag_bits"], t["second_key"])
            ok = ct == t["ct"] and tag == t["tag"]
        else:
            pt = A.aead_decrypt(t["key"], t["nonce"], t["ad"], t["ct"], t["tag"], t["ad_bits"],
                                t["pt_bits"], t["tag_bits"], t["second_key"])
            ok = (pt == t["pt"]) if t["passed"] else (pt is None)
        if not ok:
            bad += 1
            print(f"FAIL ACVP AEAD tg{t['tg']} tc{t['tc']}")
    print(f"ACVP Ascon-AEAD128-SP800-232: {n} vektor")

    n = 0
    for t in V.acvp_xof():
        n += 1
        if A.xof(t["msg"], t["out_bits"], t["msg_bits"]) != t["md"]:
            bad += 1
            print(f"FAIL ACVP XOF tc{t['tc']}")
    print(f"ACVP Ascon-XOF128-SP800-232: {n} vektor")

    n = 0
    for t in V.kat_aead():
        n += 1
        ct, tag = A.aead_encrypt(t["key"], t["nonce"], t["ad"], t["pt"])
        pt = A.aead_decrypt(t["key"], t["nonce"], t["ad"], t["ct"], t["tag"])
        if ct != t["ct"] or tag != t["tag"] or pt != t["pt"]:
            bad += 1
            print(f"FAIL KAT AEAD Count {t['count']}")
    print(f"KAT ascon-c LWC_AEAD_KAT_128_128: {n} vektor")

    n = 0
    for t in V.kat_xof():
        n += 1
        if A.xof(t["msg"], 512) != t["md"]:
            bad += 1
            print(f"FAIL KAT XOF Count {t['count']}")
    print(f"KAT ascon-c LWC_XOF_KAT_128_512: {n} vektor")

    print(("PASS" if bad == 0 else f"FAIL ({bad} gagal)") + " golden model vs vektor resmi")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
