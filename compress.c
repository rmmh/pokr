#include <stdint.h>
#include <stdio.h>

void pack2bpp(uint8_t *in, uint8_t *out) {
    /*
    Repack input into a series of 8x8 blocks so it compresses better --
    GameBoy sprites are 8x8, so the transposition allows repetition to
    be encoded once, instead of split over multiple lines.

    Input: 144x166=23040 byte buffer with values in [0, 3]
    Output: 144*166/4=5760 byte buffer of each 8x8 sprite (2bpp, 16 bytes each)
    */

    int x, y, n;

    for (y = 0; y < 18; y++) {
        for (x = 0; x < 20; x++) {
            for (n = 0; n < 8; ++n) {
                int ind = (y * 8 + n) * 160 + x * 8;
                *out++ = in[ind] | (in[ind+1] << 2) | (in[ind+2] << 4) | (in[ind+3] << 6);
                ind += 4;
                *out++ = in[ind] | (in[ind+1] << 2) | (in[ind+2] << 4) | (in[ind+3] << 6);
            }
        }
    }
}
