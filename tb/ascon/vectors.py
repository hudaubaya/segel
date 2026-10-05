"""Pemuat vektor uji resmi Ascon (diunduh `make ascon-vectors`, lihat docs/ascon.md).

Direktori diambil dari env ASCON_VECTORS (default .cache/ascon-vectors di root repo):

  acvp/Ascon-AEAD128-SP800-232/internalProjection.json   NIST ACVP-Server
  acvp/Ascon-XOF128-SP800-232/internalProjection.json
  ascon-c/LWC_AEAD_KAT_128_128.txt                         KAT ascon-c
  ascon-c/LWC_XOF_KAT_128_512.txt

Semua panjang dikembalikan dalam BIT. Berkas yang tidak ada adalah galat (bukan skip):
test vektor resmi harus selalu jalan.
"""

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VEC_DIR = os.environ.get("ASCON_VECTORS", os.path.join(REPO_ROOT, ".cache", "ascon-vectors"))


def _path(*p):
    path = os.path.join(VEC_DIR, *p)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} tidak ada; jalankan `make ascon-vectors`")
    return path


def _h(s):
    return bytes.fromhex(s)


def acvp_aead():
    """[dict]: tg, tc, direction, key, nonce, second_key|None, ad, ad_bits, pt, pt_bits,
    ct, tag, tag_bits, passed (dekripsi: apakah tag harus diterima)."""
    with open(_path("acvp", "Ascon-AEAD128-SP800-232", "internalProjection.json")) as f:
        d = json.load(f)
    out = []
    for g in d["testGroups"]:
        for t in g["tests"]:
            out.append(dict(
                tg=g["tgId"], tc=t["tcId"], direction=g["direction"],
                key=_h(t["key"]), nonce=_h(t["nonce"]),
                second_key=_h(t["secondKey"]) if "secondKey" in t else None,
                ad=_h(t["ad"]), ad_bits=t["adLen"], pt=_h(t["pt"]), pt_bits=t["payloadLen"],
                ct=_h(t["ct"]), tag=_h(t["tag"]), tag_bits=t["tagLen"],
                passed=t.get("testPassed", True), reason=t.get("reason", "")))
    return out


def acvp_xof():
    """[dict]: tc, msg, msg_bits, md, out_bits."""
    with open(_path("acvp", "Ascon-XOF128-SP800-232", "internalProjection.json")) as f:
        d = json.load(f)
    return [dict(tc=t["tcId"], msg=_h(t["msg"]), msg_bits=t["len"], md=_h(t["md"]),
                 out_bits=t["outLen"])
            for g in d["testGroups"] for t in g["tests"]]


def _kat(name):
    recs, r = [], {}
    with open(_path("ascon-c", name)) as f:
        for line in f:
            line = line.strip()
            if not line:
                if r:
                    recs.append(r)
                r = {}
                continue
            k, _, v = line.partition("=")
            r[k.strip()] = v.strip()
    if r:
        recs.append(r)
    return recs


def kat_aead():
    """[dict]: count, key, nonce, ad, pt, ct (tanpa tag), tag (128 bit)."""
    out = []
    for r in _kat("LWC_AEAD_KAT_128_128.txt"):
        ct = _h(r["CT"])
        out.append(dict(count=int(r["Count"]), key=_h(r["Key"]), nonce=_h(r["Nonce"]),
                        ad=_h(r["AD"]), pt=_h(r["PT"]), ct=ct[:-16], tag=ct[-16:]))
    return out


def kat_xof():
    """[dict]: count, msg, md (512 bit)."""
    return [dict(count=int(r["Count"]), msg=_h(r["Msg"]), md=_h(r["MD"]))
            for r in _kat("LWC_XOF_KAT_128_512.txt")]
