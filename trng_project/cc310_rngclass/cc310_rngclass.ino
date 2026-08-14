// CC310 wired into the Southern Storm Crypto library's RNGClass pool as a
// NoiseSource, then streamed out via RNG.rand().
//
// IMPORTANT - what this actually measures:
// RNGClass does not pass hardware bytes through. It folds whatever a
// NoiseSource supplies into a ChaCha20 state and returns ChaCha20 keystream
// (see RNG.cpp: ChaCha::hashCore(stream, block, RNG_ROUNDS)). So SP800-22 run
// against this output is testing ChaCha20, not the CC310 - a software CSPRNG
// will pass these tests even when fed a poor entropy source. Use
// cc310_capture.ino, which streams raw CRYS_RND output, when the goal is to
// evaluate the hardware itself. This sketch exists to demonstrate the
// NoiseSource integration.
//
// Output format (# BEGIN / hex lines / # END) matches the other sketches, so
// capture_trng.py and sp800_22.py work unchanged.

#include <bluefruit.h>
#include <Crypto.h>
#include <RNG.h>
#include "CC310TRNG.h"

#define TOTAL_BYTES 250000UL
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

    Serial.println("# CC310 -> NoiseSource -> RNGClass (ChaCha20 pool) output");

    Bluefruit.begin();

    Serial.println("# step: calling CC310TRNG.begin() [nRFCrypto.begin]");
    Serial.flush();
    bool ok = CC310TRNG.begin();
    Serial.print("# step: CC310TRNG.begin() returned ");
    Serial.println(ok ? "PASS" : "FAIL");

    if (!ok) {
        Serial.println("# ABORT - CC310TRNG.begin() failed");
        while (true) {
            delay(1000);
        }
    }

    RNG.begin("CC310 TRNG 1.0");
    RNG.addNoiseSource(CC310TRNG);
    Serial.println("# step: RNG pool initialised, noise source registered");

    // Let the pool fill from the CC310 before drawing from it.
    Serial.println("# step: waiting for RNG.available(48)");
    Serial.flush();
    unsigned long start = millis();
    while (!RNG.available(48) && (millis() - start) < 15000) {
        RNG.loop();
        delay(1);
    }
    Serial.print("# step: RNG.available(48) = ");
    Serial.print(RNG.available(48) ? "true" : "false");
    Serial.print(" after ");
    Serial.print(millis() - start);
    Serial.println(" ms");

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

    RNG.rand(raw, n);      // ChaCha20 keystream, stirred from CC310 noise
    RNG.loop();            // keep stirring fresh CC310 bytes into the pool

    char *p = hexbuf;
    for (uint16_t i = 0; i < n; i++) {
        *p++ = HEXCHARS[raw[i] >> 4];
        *p++ = HEXCHARS[raw[i] & 0x0F];
    }
    Serial.write((const uint8_t *)hexbuf, (size_t)(n * 2));
    Serial.write('\n');

    bytes_sent += n;
}
