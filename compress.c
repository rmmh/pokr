#include <stdint.h>
#include <stdio.h>

void pack2bpp(uint8_t *in, uint8_t *out) {
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
