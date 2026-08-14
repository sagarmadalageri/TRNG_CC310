#!/usr/bin/env python3
"""Capture hex-encoded hardware RNG bytes from cc310_capture.ino over serial,
decode to raw binary, and save for NIST SP800-22 testing.

Usage:
    python capture_trng.py --port COM16 --out random.bin --bytes 1000000
"""

import argparse
import sys

import serial


def open_port(port: str, baud: int) -> serial.Serial:
    try:
        return serial.Serial(port, baud, timeout=5)
    except serial.SerialException as exc:
        msg = str(exc)
        print(f"ERROR: could not open {port}: {exc}")
        if "denied" in msg.lower() or "PermissionError" in msg:
            print(
                "That port looks locked by another program - close the Arduino "
                "IDE's Serial Monitor (or any other terminal holding the port) "
                "and try again."
            )
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Serial port, e.g. COM12")
    parser.add_argument("--out", required=True, help="Output raw binary file")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--bytes", type=int, default=250_000, help="Number of raw bytes to capture"
    )
    args = parser.parse_args()

    ser = open_port(args.port, args.baud)
    written = 0
    dropped = 0  # lines discarded as truncated/corrupted (reported at the end)

    with ser, open(args.out, "wb") as out:
        print("Waiting for '# BEGIN' ... (press the board's reset button now if nothing happens)")
        while True:
            line = ser.readline()
            if not line:
                continue
            if b"# BEGIN" in line:
                break

        print(f"Capturing up to {args.bytes} bytes to {args.out} ...")
        while written < args.bytes:
            raw = ser.readline()
            if not raw:
                continue  # read timeout, just keep waiting

            text = raw.decode("ascii", errors="ignore").strip()
            if not text:
                continue
            if text.startswith("#"):
                if "END" in text:
                    break
                continue  # other banner/comment line

            # Each line is one self-contained chunk of hex. A truncated line is
            # dropped whole rather than being stitched to its neighbour: carrying
            # a leftover nibble across lines would shift every subsequent byte by
            # 4 bits, silently corrupting the stream instead of losing one chunk.
            if len(text) % 2 != 0:
                dropped += 1
                continue

            try:
                chunk = bytes.fromhex(text)
            except ValueError:
                dropped += 1
                continue  # a corrupted line - drop it rather than crash

            remaining = args.bytes - written
            if len(chunk) > remaining:
                chunk = chunk[:remaining]
            out.write(chunk)
            written += len(chunk)
            print(f"\r{written}/{args.bytes} bytes", end="", flush=True)

    print(f"\nDone. Wrote {written} bytes to {args.out}")
    if dropped:
        print(
            f"WARNING: dropped {dropped} truncated/corrupted line(s). The data "
            f"written is byte-aligned and valid, but is short of the requested "
            f"{args.bytes} bytes. Lower CHUNK_BYTES in the sketch if this "
            f"happens often."
        )


if __name__ == "__main__":
    sys.exit(main())
