#!/usr/bin/env python3
"""
Capture RAW binary CC310 hardware TRNG bytes over serial
and save them directly to a binary file.

The Arduino firmware waits for the host to send 'S'.
After receiving 'S', the board starts generating raw
random bytes.

Usage:
    python capture_trng.py --port /dev/cu.usbmodem1101 --out random.bin --bytes 250000
"""

import argparse
import sys
import time

import serial


def open_port(port: str, baud: int) -> serial.Serial:
    try:
        return serial.Serial(
            port,
            baud,
            timeout=1
        )

    except serial.SerialException as exc:
        print(f"ERROR: could not open {port}: {exc}")

        if "busy" in str(exc).lower():
            print(
                "The serial port is busy. "
                "Close Arduino Serial Monitor or any other "
                "program using the board."
            )

        sys.exit(1)


def main():

    # --------------------------------------------------------
    # Command-line arguments
    # --------------------------------------------------------

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--port",
        required=True,
        help="Serial port"
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Output raw binary file"
    )

    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Serial baud rate"
    )

    parser.add_argument(
        "--bytes",
        type=int,
        default=250_000,
        help="Number of raw bytes to capture"
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Open serial port
    # --------------------------------------------------------

    ser = open_port(
        args.port,
        args.baud
    )

    written = 0

    try:

        # ----------------------------------------------------
        # Allow USB serial connection to settle
        # ----------------------------------------------------

        time.sleep(1)

        # ----------------------------------------------------
        # Clear old data
        # ----------------------------------------------------

        ser.reset_input_buffer()

        # ----------------------------------------------------
        # Tell Arduino to START
        # Arduino firmware waits for character 'S'
        # ----------------------------------------------------

        print("Sending START command to CC310...")

        ser.write(b"S")
        ser.flush()

        print(
            f"Capturing {args.bytes:,} raw bytes..."
        )

        # ----------------------------------------------------
        # Open output file in binary mode
        # ----------------------------------------------------

        with open(args.out, "wb") as out:

            while written < args.bytes:

                remaining = (
                    args.bytes - written
                )

                # Read only the amount still required
                chunk = ser.read(
                    min(4096, remaining)
                )

                # No data received yet
                if not chunk:
                    continue

                # Write RAW bytes directly
                out.write(chunk)

                written += len(chunk)

                # Display progress
                print(
                    f"\rCaptured "
                    f"{written:,}/{args.bytes:,} bytes",
                    end="",
                    flush=True
                )

    except KeyboardInterrupt:

        print(
            "\nCapture stopped by user."
        )

    except serial.SerialException as exc:

        print(
            f"\nERROR: serial communication failed: {exc}"
        )

        sys.exit(1)

    finally:

        ser.close()

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print(
        f"\nDone. Wrote {written:,} bytes "
        f"to {args.out}"
    )


if __name__ == "__main__":
    main()