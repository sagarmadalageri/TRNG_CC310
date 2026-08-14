#!/usr/bin/env python3
"""NIST SP800-22 Rev 1a statistical test suite for random bit sequences.

Implements: Frequency (Monobit), Block Frequency, Runs, Longest Run of Ones,
Binary Matrix Rank, DFT/Spectral, Non-overlapping Template Matching, Maurer's
Universal Statistical, Serial, Approximate Entropy, Cumulative Sums (forward
and reverse), Random Excursions, Random Excursions Variant.

Usage:
    python sp800_22.py random.bin

Reads the file as raw bytes, unpacks to a bit array (MSB first per byte),
runs all applicable tests, and prints a table of p-values with a PASS/FAIL
verdict (alpha = 0.01). Tests that produce more than one p-value internally
(Serial, Cumulative Sums, Random Excursions, Random Excursions Variant) show
the worst (minimum) p-value in the table; the row only passes if every
sub-p-value passes.
"""

import math
import sys

import numpy as np
from scipy.special import erfc, gammaincc
from scipy.stats import norm

ALPHA = 0.01


def bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


# ---------------------------------------------------------------------------
# 1. Frequency (Monobit) Test
# ---------------------------------------------------------------------------
def frequency_test(bits):
    n = len(bits)
    s = np.sum(2 * bits.astype(np.int64) - 1)
    s_obs = abs(s) / math.sqrt(n)
    p = erfc(s_obs / math.sqrt(2))
    return [p]


# ---------------------------------------------------------------------------
# 2. Block Frequency Test
# ---------------------------------------------------------------------------
def block_frequency_test(bits, m=128):
    n = len(bits)
    N = n // m
    if N == 0:
        return [1.0]
    blocks = bits[: N * m].reshape(N, m)
    pi = np.sum(blocks, axis=1) / m
    chi_sq = 4 * m * np.sum((pi - 0.5) ** 2)
    p = gammaincc(N / 2.0, chi_sq / 2.0)
    return [p]


# ---------------------------------------------------------------------------
# 3. Runs Test
# ---------------------------------------------------------------------------
def runs_test(bits):
    n = len(bits)
    pi = np.sum(bits) / n
    if abs(pi - 0.5) >= (2.0 / math.sqrt(n)):
        return [0.0]
    v_obs = 1 + np.sum(bits[1:] != bits[:-1])
    p = erfc(
        abs(v_obs - 2 * n * pi * (1 - pi)) / (2 * math.sqrt(2 * n) * pi * (1 - pi))
    )
    return [p]


# ---------------------------------------------------------------------------
# 4. Test for the Longest Run of Ones in a Block
# ---------------------------------------------------------------------------
def longest_run_test(bits):
    n = len(bits)
    if n < 128:
        return [1.0]
    if n < 6272:
        m, k = 8, 3
        pi = [0.2148, 0.3672, 0.2305, 0.1875]
        bounds = [1, 2, 3]  # v<=1, v=2, v=3, v>=4
    elif n < 750000:
        m, k = 128, 5
        pi = [0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124]
        bounds = [4, 5, 6, 7, 8]  # v<=4,5,6,7,8,v>=9
    else:
        m, k = 10000, 6
        pi = [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]
        bounds = [10, 11, 12, 13, 14, 15]  # v<=10,11,12,13,14,15,v>=16

    N = n // m
    if N == 0:
        return [1.0]
    counts = [0] * (k + 1)
    for i in range(N):
        block = bits[i * m : (i + 1) * m]
        longest = 0
        cur = 0
        for b in block:
            if b:
                cur += 1
                longest = max(longest, cur)
            else:
                cur = 0
        idx = k
        for j, bound in enumerate(bounds):
            if longest <= bound:
                idx = j
                break
        counts[idx] += 1

    chi_sq = sum(
        (counts[i] - N * pi[i]) ** 2 / (N * pi[i]) for i in range(k + 1)
    )
    p = gammaincc(k / 2.0, chi_sq / 2.0)
    return [p]


# ---------------------------------------------------------------------------
# 5. Binary Matrix Rank Test
# ---------------------------------------------------------------------------
def _gf2_rank(matrix):
    m = matrix.copy().astype(np.uint8)
    rows, cols = m.shape
    rank = 0
    for col in range(cols):
        pivot = None
        for r in range(rank, rows):
            if m[r, col]:
                pivot = r
                break
        if pivot is None:
            continue
        m[[rank, pivot]] = m[[pivot, rank]]
        for r in range(rows):
            if r != rank and m[r, col]:
                m[r] ^= m[rank]
        rank += 1
        if rank == rows:
            break
    return rank


def binary_matrix_rank_test(bits, m_dim=32, q_dim=32):
    n = len(bits)
    block_size = m_dim * q_dim
    N = n // block_size
    if N < 1:
        return [1.0]
    full = 0
    minus_one = 0
    for i in range(N):
        block = bits[i * block_size : (i + 1) * block_size].reshape(m_dim, q_dim)
        r = _gf2_rank(block)
        if r == m_dim:
            full += 1
        elif r == m_dim - 1:
            minus_one += 1
    rest = N - full - minus_one
    p_full, p_minus1, p_rest = 0.2888, 0.5776, 0.1336
    chi_sq = (
        (full - N * p_full) ** 2 / (N * p_full)
        + (minus_one - N * p_minus1) ** 2 / (N * p_minus1)
        + (rest - N * p_rest) ** 2 / (N * p_rest)
    )
    p = math.exp(-chi_sq / 2.0)
    return [p]


# ---------------------------------------------------------------------------
# 6. Discrete Fourier Transform (Spectral) Test
# ---------------------------------------------------------------------------
def dft_test(bits):
    n = len(bits)
    x = 2 * bits.astype(np.float64) - 1
    fft = np.fft.fft(x)
    m = np.abs(fft[: n // 2])
    t = math.sqrt(math.log(1.0 / 0.05) * n)
    n0 = 0.95 * n / 2.0
    n1 = np.sum(m < t)
    d = (n1 - n0) / math.sqrt(n * 0.95 * 0.05 / 4.0)
    p = erfc(abs(d) / math.sqrt(2))
    return [p]


# ---------------------------------------------------------------------------
# 7. Non-overlapping Template Matching Test
# ---------------------------------------------------------------------------
def non_overlapping_template_test(bits, template=(0, 0, 0, 0, 0, 0, 0, 0, 1), n_blocks=8):
    n = len(bits)
    m = len(template)
    template = np.array(template, dtype=np.uint8)
    big_m = n // n_blocks
    if big_m <= m:
        return [1.0]
    mu = (big_m - m + 1) / (2.0 ** m)
    var = big_m * (1.0 / (2.0 ** m) - (2.0 * m - 1) / (2.0 ** (2 * m)))

    w = []
    for i in range(n_blocks):
        block = bits[i * big_m : (i + 1) * big_m]
        count = 0
        j = 0
        limit = big_m - m + 1
        while j < limit:
            if np.array_equal(block[j : j + m], template):
                count += 1
                j += m
            else:
                j += 1
        w.append(count)

    chi_sq = sum((wi - mu) ** 2 / var for wi in w)
    p = gammaincc(n_blocks / 2.0, chi_sq / 2.0)
    return [p]


# ---------------------------------------------------------------------------
# 8. Maurer's Universal Statistical Test
# ---------------------------------------------------------------------------
_UNIVERSAL_TABLE = {
    6: (5.2177052, 2.954),
    7: (6.1962507, 3.125),
    8: (7.1836656, 3.238),
    9: (8.1764248, 3.311),
    10: (9.1723243, 3.356),
    11: (10.170032, 3.384),
    12: (11.168765, 3.401),
    13: (12.168070, 3.410),
    14: (13.167693, 3.416),
    15: (14.167488, 3.419),
    16: (15.167379, 3.421),
}


def universal_test(bits):
    n = len(bits)
    if n < 387840:
        return [1.0]
    l_candidates = [
        (387840, 6),
        (904960, 7),
        (2097152, 8),
        (4654080, 9),
        (10 ** 7, 10),
    ]
    L = 6
    for threshold, l_val in l_candidates:
        if n >= threshold:
            L = l_val
    if L not in _UNIVERSAL_TABLE:
        return [1.0]
    expected, variance = _UNIVERSAL_TABLE[L]
    Q = 10 * (2 ** L)
    K = n // L - Q
    if K <= 0:
        return [1.0]

    bit_str = bits[: (Q + K) * L]
    blocks = bit_str.reshape(Q + K, L)
    powers = 2 ** np.arange(L - 1, -1, -1)
    values = blocks.dot(powers)

    table = np.zeros(2 ** L, dtype=np.int64)
    for i in range(Q):
        table[values[i]] = i + 1

    total = 0.0
    for i in range(Q, Q + K):
        v = values[i]
        total += math.log2(i + 1 - table[v])
        table[v] = i + 1

    fn = total / K
    c = 0.7 - 0.8 / L + (4 + 32.0 / L) * (K ** (-3.0 / L)) / 15.0
    sigma = c * math.sqrt(variance / K)
    stat = (fn - expected) / (math.sqrt(2) * sigma)
    p = erfc(abs(stat))
    return [p]


# ---------------------------------------------------------------------------
# 9. Serial Test
# ---------------------------------------------------------------------------
def _psi_sq(bits, m):
    n = len(bits)
    if m <= 0:
        return 0.0
    extended = np.concatenate([bits, bits[: m - 1]])
    powers = 2 ** np.arange(m - 1, -1, -1)
    windows = np.lib.stride_tricks.sliding_window_view(extended, m)
    values = windows.dot(powers)
    counts = np.bincount(values, minlength=2 ** m)
    return (2.0 ** m / n) * np.sum(counts.astype(np.float64) ** 2) - n


def serial_test(bits, m=16):
    n = len(bits)
    if m < 2 or 2 ** m > n:
        m = max(2, int(math.log2(n)) - 3)
    psi_m = _psi_sq(bits, m)
    psi_m1 = _psi_sq(bits, m - 1)
    psi_m2 = _psi_sq(bits, m - 2) if m >= 2 else 0.0

    delta1 = psi_m - psi_m1
    delta2 = psi_m - 2 * psi_m1 + psi_m2

    p1 = gammaincc(2.0 ** (m - 2), delta1 / 2.0)
    p2 = gammaincc(2.0 ** (m - 3), delta2 / 2.0)
    return [p1, p2]


# ---------------------------------------------------------------------------
# 10. Approximate Entropy Test
# ---------------------------------------------------------------------------
def _phi(bits, m):
    n = len(bits)
    extended = np.concatenate([bits, bits[: m - 1]])
    powers = 2 ** np.arange(m - 1, -1, -1)
    windows = np.lib.stride_tricks.sliding_window_view(extended, m)
    values = windows.dot(powers)
    counts = np.bincount(values, minlength=2 ** m)
    c = counts.astype(np.float64) / n
    nz = c[c > 0]
    return np.sum(nz * np.log(nz))


def approximate_entropy_test(bits, m=10):
    n = len(bits)
    if 2 ** (m + 1) > n:
        m = max(2, int(math.log2(n)) - 3)
    phi_m = _phi(bits, m)
    phi_m1 = _phi(bits, m + 1)
    ap_en = phi_m - phi_m1
    chi_sq = 2 * n * (math.log(2) - ap_en)
    p = gammaincc(2.0 ** (m - 1), chi_sq / 2.0)
    return [p]


# ---------------------------------------------------------------------------
# 11. Cumulative Sums (Cusum) Test - forward and reverse
# ---------------------------------------------------------------------------
def _cusum_p(x, n):
    z = int(np.max(np.abs(np.cumsum(x))))
    if z == 0:
        return 1.0

    def norm_cdf(v):
        return norm.cdf(v)

    total = 0.0
    start = int(math.floor((-n / z + 1) / 4))
    end = int(math.floor((n / z - 1) / 4))
    for k in range(start, end + 1):
        total += norm_cdf(((4 * k + 1) * z) / math.sqrt(n)) - norm_cdf(
            ((4 * k - 1) * z) / math.sqrt(n)
        )
    sum1 = total

    total = 0.0
    start = int(math.floor((-n / z - 3) / 4))
    end = int(math.floor((n / z - 1) / 4))
    for k in range(start, end + 1):
        total += norm_cdf(((4 * k + 3) * z) / math.sqrt(n)) - norm_cdf(
            ((4 * k + 1) * z) / math.sqrt(n)
        )
    sum2 = total

    p = 1 - sum1 + sum2
    return max(0.0, min(1.0, p))


def cumulative_sums_test(bits):
    n = len(bits)
    x = 2 * bits.astype(np.float64) - 1
    p_forward = _cusum_p(x, n)
    p_backward = _cusum_p(x[::-1], n)
    return [p_forward, p_backward]


# ---------------------------------------------------------------------------
# 12 & 13. Random Excursions (and Variant) Tests
# ---------------------------------------------------------------------------
def _random_walk_cycles(bits):
    x = 2 * bits.astype(np.int64) - 1
    s = np.concatenate([[0], np.cumsum(x)])  # s[0] = 0 start; no forced end zero
    zero_idx = np.where(s == 0)[0]
    cycles = [s[zero_idx[i] : zero_idx[i + 1] + 1] for i in range(len(zero_idx) - 1)]
    return s, cycles


def random_excursions_test(bits):
    s, cycles = _random_walk_cycles(bits)
    j = len(cycles)
    if j < 500:
        return [1.0]  # not enough cycles for a meaningful result

    states = [-4, -3, -2, -1, 1, 2, 3, 4]
    p_values = []
    for x in states:
        counts = [0] * 6  # visits == 0,1,2,3,4,>=5
        for cyc in cycles:
            v = int(np.sum(cyc == x))
            counts[min(v, 5)] += 1

        ax = abs(x)
        pi = [1 - 1.0 / (2 * ax)]
        for k in range(1, 5):
            pi.append((1.0 / (4 * ax * ax)) * (1 - 1.0 / (2 * ax)) ** (k - 1))
        pi.append((1.0 / (2 * ax)) * (1 - 1.0 / (2 * ax)) ** 4)

        chi_sq = sum((counts[k] - j * pi[k]) ** 2 / (j * pi[k]) for k in range(6))
        p = gammaincc(2.5, chi_sq / 2.0)
        p_values.append(p)
    return p_values


def random_excursions_variant_test(bits):
    s, cycles = _random_walk_cycles(bits)
    j = len(cycles)
    if j < 500:
        return [1.0]

    interior = s[1:]  # exclude only the leading S_0 = 0 boundary
    states = list(range(-9, 0)) + list(range(1, 10))
    p_values = []
    for x in states:
        xi = int(np.sum(interior == x))
        p = erfc(abs(xi - j) / math.sqrt(2.0 * j * (4 * abs(x) - 2)))
        p_values.append(p)
    return p_values


# ---------------------------------------------------------------------------
TESTS = [
    ("Frequency (Monobit)", frequency_test),
    ("Block Frequency", block_frequency_test),
    ("Runs", runs_test),
    ("Longest Run of Ones", longest_run_test),
    ("Binary Matrix Rank", binary_matrix_rank_test),
    ("Discrete Fourier Transform", dft_test),
    ("Non-overlapping Template Matching", non_overlapping_template_test),
    ("Maurer's Universal Statistical", universal_test),
    ("Serial", serial_test),
    ("Approximate Entropy", approximate_entropy_test),
    ("Cumulative Sums", cumulative_sums_test),
    ("Random Excursions", random_excursions_test),
    ("Random Excursions Variant", random_excursions_variant_test),
]


def run_suite(bits, verbose=True):
    """Runs all tests, returns (all_pass, results) where results is a list of
    (name, worst_p_value, n_sub_values, passed)."""
    results = []
    name_w = max(len(name) for name, _ in TESTS)
    if verbose:
        print(f"{'Test':<{name_w}}  {'p-value':>10}  Result")
        print("-" * (name_w + 26))

    all_pass = True
    for name, fn in TESTS:
        try:
            p_values = fn(bits)
        except Exception as exc:  # noqa: BLE001
            if verbose:
                print(f"{name:<{name_w}}  {'ERROR':>10}  ({exc})")
            all_pass = False
            results.append((name, None, 0, False))
            continue

        worst = min(p_values)
        passed = worst >= ALPHA
        all_pass &= passed
        results.append((name, worst, len(p_values), passed))
        if verbose:
            verdict = "PASS" if passed else "FAIL"
            extra = (
                f"  ({len(p_values)} sub-values, worst shown)"
                if len(p_values) > 1
                else ""
            )
            print(f"{name:<{name_w}}  {worst:>10.6f}  {verdict}{extra}")

    if verbose:
        print("-" * (name_w + 26))
        print("OVERALL:", "PASS" if all_pass else "FAIL", f"(alpha = {ALPHA})")

    return all_pass, results


def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <random.bin>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read()

    bits = bytes_to_bits(data)
    n = len(bits)
    print(f"Loaded {len(data)} bytes ({n} bits) from {path}\n")

    run_suite(bits)


if __name__ == "__main__":
    main()
