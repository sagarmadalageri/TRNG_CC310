#!/usr/bin/env python3
"""Generate reference datasets to validate sp800_22.py before touching real
hardware data: known-good, known-bad, biased, and weak-PRNG samples."""

import os

import numpy as np

N_BYTES = 250_000
N_BITS = N_BYTES * 8


def write(name, data: bytes):
    path = os.path.join(os.path.dirname(__file__), name)
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {len(data)} bytes -> {name}")


def make_urandom():
    return os.urandom(N_BYTES)


def make_all_zero():
    return bytes(N_BYTES)


def make_biased(p_one=0.70):
    rng = np.random.default_rng()
    bits = rng.choice([0, 1], size=N_BITS, p=[1 - p_one, p_one]).astype(np.uint8)
    return np.packbits(bits).tobytes()


def make_weak_lcg():
    # glibc-style LCG constants; take the low byte of each state, which is
    # notoriously short-period/non-random for power-of-two-modulus LCGs.
    a, c, m_mod = 1103515245, 12345, 2 ** 31
    x = 12345  # fixed seed for reproducibility
    out = bytearray(N_BYTES)
    for i in range(N_BYTES):
        x = (a * x + c) % m_mod
        out[i] = x & 0xFF
    return bytes(out)


if __name__ == "__main__":
    write("ref_urandom.bin", make_urandom())
    write("ref_allzero.bin", make_all_zero())
    write("ref_biased70.bin", make_biased())
    write("ref_weak_lcg.bin", make_weak_lcg())
