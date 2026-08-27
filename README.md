# TRNG — CryptoCell CC310 Hardware Random Number Generator

Generates true random numbers from the ARM CryptoCell-310 on a Seeed XIAO
nRF52840 and validates them against the NIST SP800-22 statistical test suite.

**Result: all 13 tests pass on 7,948,288 bits of raw CC310 output.**

## How it works

The nRF52840 carries a dedicated hardware security block, the ARM
CryptoCell-310, whose true random number generator derives entropy from
physical noise in the silicon rather than from an algorithm. That noise seeds
a CTR_DRBG (NIST SP800-90A) which is continuously reseeded from the hardware
source.

An Arduino sketch pulls random bytes from it via the `CRYS_RND` API, hex-encodes
them, and streams them over USB serial between `# BEGIN` and `# END` markers. A
Python script decodes the stream into a raw binary file, and a second script
runs the SP800-22 battery against that file.

### The mandatory `SaSi_LibInit()` step

Getting CC310 working hinges on one detail that costs a lot of time if missed.
The CryptoCell hardware must be brought up with `SaSi_LibInit()` **before** any
`CRYS_*` call. The `Adafruit_nRFCrypto` library does this inside its top-level
`nRFCrypto.begin()`:

```cpp
VERIFY_ERROR(SaSi_LibInit(), false);   // brings up the CC310 hardware
VERIFY( Random.begin() );              // then CRYS_RndInit()
```

If you instead construct an `nRFCrypto_Random` yourself and call its `begin()`
directly, `SaSi_LibInit()` never runs. `CRYS_RndInit()` still returns success
(it only does software-side setup), but the first `CRYS_RND_GenerateVector()`
call then **blocks forever**, polling CryptoCell hardware that was never
powered up. The failure looks like a dead board: no serial output, no USB
enumeration, and it survives a reset.

So: always go through `nRFCrypto.begin()`, then `nRFCrypto.Random.generate()`.

## Documents

**Technical report** — background, architecture, the `SaSi_LibInit()` root
cause, suite validation and full results.
[PDF](docs/TRNG_report.pdf) (7 pages) · [HTML](docs/TRNG_report.html)

**Engineering log** — every approach attempted, each defect found, and how it
was resolved. Includes the two occasions where the evidence was read wrongly
and what corrected them.
[PDF](docs/TRNG_engineering_log.pdf) (8 pages) · [HTML](docs/TRNG_engineering_log.html)

## Project layout

```
trng_project/
  cc310_capture/cc310_capture.ino   Arduino sketch — streams raw CC310 output
  capture_trng.py                   Captures the serial stream to a raw .bin file
  sp800_22.py                       NIST SP800-22 suite (13 tests, numpy/scipy)
  make_reference_data.py            Known-good/known-bad data for validating the suite
  cc310_random_1mb.bin              993,536-byte capture — main result
  cc310_random.bin                  250,000-byte capture — independent confirmation

  cc310_rngclass/                   Optional: CC310 as a NoiseSource feeding the
                                    Southern Storm RNGClass pool (see note below)
docs/                               Report and engineering log
```

## Requirements

- Seeed XIAO nRF52840 (or Sense variant)
- Arduino IDE, or [arduino-cli](https://arduino.github.io/arduino-cli/), with the
  **Seeed nRF52 Boards** package installed (board manager URL:
  `https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json`)
- Python 3 with `pyserial`, `numpy`, `scipy`

```
pip install pyserial numpy scipy
```

## Usage

**1. Flash the sketch**

Open `trng_project/cc310_capture/cc310_capture.ino` in Arduino IDE, select
Board > Seeed nRF52 Boards > Seeed XIAO nRF52840 (Sense), select the port, and
upload. Or via arduino-cli:

```
arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840Sense cc310_capture
arduino-cli upload -p COM16 --fqbn Seeeduino:nrf52:xiaonRF52840Sense cc310_capture
```

The sketch streams 1,000,000 bytes as hex text, then stops. Change
`TOTAL_BYTES` in the sketch to adjust.

**2. Capture**

Close any other program holding the serial port (e.g. the Arduino Serial
Monitor), then:

```
python capture_trng.py --port COM16 --out random.bin --bytes 1000000
```

Reset the board first (or re-flash it) so the capture starts from a fresh
`# BEGIN`.

**3. Run the test suite**

```
python sp800_22.py random.bin
```

Prints a p-value table and a PASS/FAIL verdict per test at alpha = 0.01.

## Results

### 1 MB capture

`cc310_random_1mb.bin` is a 993,536-byte / 7,948,288-bit capture of raw
`CRYS_RND` output, transferred in about 18 seconds:

```
Test                                  p-value  Result
-----------------------------------------------------------
Frequency (Monobit)                  0.505782  PASS
Block Frequency                      0.476197  PASS
Runs                                 0.127776  PASS
Longest Run of Ones                  0.188890  PASS
Binary Matrix Rank                   0.125504  PASS
Discrete Fourier Transform           0.919110  PASS
Non-overlapping Template Matching    0.805184  PASS
Maurer's Universal Statistical       0.584228  PASS
Serial                               0.028721  PASS  (2 sub-values, worst shown)
Approximate Entropy                  0.882174  PASS
Cumulative Sums                      0.430308  PASS  (2 sub-values, worst shown)
Random Excursions                    0.024265  PASS  (8 sub-values, worst shown)
Random Excursions Variant            0.074681  PASS  (18 sub-values, worst shown)
-----------------------------------------------------------
OVERALL: PASS (alpha = 0.01)
```

The capture is a few thousand bytes short of the requested 1,000,000: under
sustained streaming the USB CDC link occasionally loses a whole line. That
costs samples but does not bias them — `capture_trng.py` decodes each line
independently and discards any line that is truncated or non-hex, so every
byte written is byte-aligned and valid. (An earlier version stitched a
leftover nibble onto the next line, which shifted all following bytes by 4
bits; that is why it is now dropped instead.) Lower `CHUNK_BYTES` in the
sketch if you need the count to land exactly.

### 250 KB capture — independent confirmation

`cc310_random.bin`, taken from a separate reset, also passes all 13 tests;
worst p-value 0.219608. Reproducibility across independent captures matters
more than any single run.

## Interpreting results

A p-value >= 0.01 passes; the p-value is not a quality score (0.02 and 0.98
pass equally well). The suite runs ~40 individual p-value comparisons in
total (some tests, like Random Excursions Variant, produce many sub-values).
At alpha = 0.01, true randomness still has roughly a 1-in-3 chance of one
spurious single-test failure on any given run — that's what alpha = 0.01
means, not a defect. A single narrow failure doesn't mean anything by
itself; recapture and re-run. Multiple failures, or the same test failing
across repeated fresh captures, is the real signal.

## Validating the test suite itself

`make_reference_data.py` generates four reference datasets so the suite's
correctness can be checked before trusting it on real hardware data:

- `os.urandom` (2,000,000 bits) — should pass all tests
- all-zero bytes — should fail nearly every test
- a 70%-biased bit stream — should fail nearly every test
- a weak LCG (low byte of a glibc-style generator) — should fail at least
  the spectral (DFT) test

Run `python make_reference_data.py` then `python sp800_22.py <file>` on each
to reproduce this check.

## Note on `cc310_rngclass/`

This variant wires the CC310 into the Southern Storm `RNGClass` entropy pool
as a `NoiseSource`. It works and passes all 13 tests, but those figures are
**not** cited as hardware evidence and no dataset from it is included here.

`RNGClass` does not pass hardware bytes through: it folds them into a ChaCha20
state and returns keystream. A software stream cipher passes SP800-22 even
when fed a poor entropy source, so testing its output measures ChaCha20 rather
than the CryptoCell. All hardware figures above come from raw `CRYS_RND`
output via `cc310_capture`.
