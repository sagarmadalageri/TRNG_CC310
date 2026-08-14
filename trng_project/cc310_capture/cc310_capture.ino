// Streams RAW CC310 (CryptoCell-310) hardware TRNG output over serial.
//
// CC310 bring-up: the CryptoCell hardware must be initialized with
// SaSi_LibInit() before any CRYS_* call. Adafruit_nRFCrypto does this inside
// its top-level nRFCrypto.begin(). Constructing an nRFCrypto_Random and
// calling its begin() directly skips SaSi_LibInit(), so CRYS_RndInit()
// returns success but the first CRYS_RND_GenerateVector() blocks forever on
// un-powered hardware. Always go through nRFCrypto.begin().
//
// Throughput notes: the CC310 is not the bottleneck, the serial formatting is.
// Bytes are pulled in large chunks and hex-encoded by table lookup into a
// buffer that is pushed with a single Serial.write() per chunk. Using
// Serial.print(b, HEX) per byte instead runs the print formatter 1M+ times
// and is many times slower.
//
// Output format: # BEGIN, then hex lines, then # END - consumed by
// capture_trng.py and tested with sp800_22.py.

#include <bluefruit.h>
#include "Adafruit_nRFCrypto.h"

// 128 bytes -> 256 hex chars + newline per line. Large enough that the print
// path is not the bottleneck, small enough that a single bulk write fits the
// USB CDC TX buffer; 256-byte chunks (513-char lines) overflowed it and cost
// roughly one truncated line per 90,000 bytes.
#define TOTAL_BYTES 1000000UL
#define CHUNK_BYTES 128

static const char HEXCHARS[] = "0123456789abcdef";

static uint8_t  raw[CHUNK_BYTES];
static char     hexbuf[CHUNK_BYTES * 2 + 1];
static uint32_t bytes_sent = 0;
static bool     streaming = false;

void setup() {
    pinMode(LED_RED, OUTPUT);
    digitalWrite(LED_RED, HIGH);

    Serial.begin(115200);
    while (!Serial) {
        delay(10);
    }

    Serial.println("# CC310 (CryptoCell-310) hardware TRNG dump - raw CRYS_RND output");

    Bluefruit.begin();

    Serial.println("# step: calling nRFCrypto.begin() [SaSi_LibInit + CRYS_RndInit]");
    Serial.flush();
    bool ok = nRFCrypto.begin();
    Serial.print("# step: nRFCrypto.begin() returned ");
    Serial.println(ok ? "PASS" : "FAIL");

    if (!ok) {
        Serial.println("# ABORT - nRFCrypto.begin() failed");
        while (true) {
            delay(1000);
        }
    }

    digitalWrite(LED_RED, LOW);
    Serial.println("# BEGIN");
    streaming = true;
}

void loop() {
    if (!streaming) {
        return;
    }

    if (bytes_sent >= TOTAL_BYTES) {
        Serial.println("# END");
        streaming = false;
        while (true) {
            delay(1000);
        }
    }

    uint32_t remaining = TOTAL_BYTES - bytes_sent;
    uint16_t n = (remaining < CHUNK_BYTES) ? (uint16_t)remaining : CHUNK_BYTES;

    if (!nRFCrypto.Random.generate(raw, n)) {
        Serial.println("# generate() returned FAIL");
        delay(1000);
        return;
    }

    // Table-lookup hex encode, then one bulk write.
    char *p = hexbuf;
    for (uint16_t i = 0; i < n; i++) {
        *p++ = HEXCHARS[raw[i] >> 4];
        *p++ = HEXCHARS[raw[i] & 0x0F];
    }
    Serial.write((const uint8_t *)hexbuf, (size_t)(n * 2));
    Serial.write('\n');

    bytes_sent += n;
}
