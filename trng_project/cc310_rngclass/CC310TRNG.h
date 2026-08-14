#ifndef CC310_TRNG_h
#define CC310_TRNG_h

#include <NoiseSource.h>
#include "Adafruit_nRFCrypto.h"   // provides nRFCrypto (wraps CRYS_RND)

// Feeds the CC310's hardware TRNG (via CRYS_RND) into the Crypto
// library's global RNG pool as a noise source.
class CC310NoiseSource : public NoiseSource
{
public:
    CC310NoiseSource();
    virtual ~CC310NoiseSource();

    bool begin();

    // NoiseSource declares both of these pure-virtual, so both must be
    // overridden or the class stays abstract and will not compile.
    bool calibrating() const override;
    void stir() override;

private:
    bool _begun;
};

extern CC310NoiseSource CC310TRNG;

#endif
