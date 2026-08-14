#include "CC310TRNG.h"
#include <string.h>

CC310NoiseSource CC310TRNG;

CC310NoiseSource::CC310NoiseSource()
    : _begun(false)
{
}

CC310NoiseSource::~CC310NoiseSource()
{
    if (_begun) {
        nRFCrypto.end();
    }
}

bool CC310NoiseSource::begin()
{
    // Must go through the top-level nRFCrypto.begin(), which runs
    // SaSi_LibInit() to power up the CryptoCell hardware and only then
    // CRYS_RndInit(). Calling nRFCrypto_Random::begin() on its own skips
    // SaSi_LibInit(): CRYS_RndInit() still reports success, but the first
    // CRYS_RND_GenerateVector() blocks forever on uninitialized hardware.
    _begun = nRFCrypto.begin();
    return _begun;
}

bool CC310NoiseSource::calibrating() const
{
    // CC310 is a certified DRBG: it is either up (after begin()) or it is
    // not. There is no ring-oscillator-style warm-up period to wait out.
    return false;
}

void CC310NoiseSource::stir()
{
    if (!_begun && !begin()) {
        return;   // CC310 not ready yet, try again next stir()
    }

    uint8_t buf[32];
    if (nRFCrypto.Random.generate(buf, sizeof(buf))) {
        // CRYS_RND is a certified DRBG seeded from a real hardware entropy
        // source, so - unlike a ring oscillator - we can credit it with full
        // entropy for the bytes it hands back.
        output(buf, sizeof(buf), sizeof(buf) * 8);
    }

    memset(buf, 0, sizeof(buf));   // don't leave key-grade bytes on the stack
}
