#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include <memory.h>

#include "accel.h"

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

#define MAX_PALETTE_SIZE 16

const int kSpriteX = 7;
const int kSpriteY = 14;

#define SP_PIX(x, y) image[(y)+(x)*160]

void translate_bytes(uint8_t *image, int len, uint8_t *table) {
    int i;
    for (i = 0; i < len; ++i) {
        image[i] = table[image[i]];
    }
}

static struct sprite *find_sprite(uint32_t *needle, struct sprite *haystack, int n_sprites) {
    int low = 0, high = n_sprites;

    /* binary search to find a match */
    while (low + 1 < high) {
        int mid = (low + high) / 2;
        int dir = memcmp(needle, haystack[mid].image, sizeof(*needle) * haystack[mid].width);
        if (dir == 0) {
            return &haystack[mid];
        } else if (dir < 0) {
            high = mid;
        } else if (dir > 0) {
            low = mid;
        }
    }
    return NULL;
}

int identify_sprites(uint8_t *image, struct sprite *sprites, int n_sprites, struct sprite_match *matched, int max_matches) {
    /*
    Identify sprites using palette pattern matching
    */
    int x, y;

    int considered = 0;
    int match_count = 0;

    for (y = 1; y < 160 - kSpriteY; ++y) {
        int found = 0;
        int lastX = -1;
        for (x = 0; x < 240 - kSpriteX; ++x) {
            // skip if it's not solid above
            ///*
            int off;
            int prev = SP_PIX(x, y - 1);
            for (off = 1; off < kSpriteX; ++off) {
                if (SP_PIX(x + off, y - 1) != prev) {
                    x += off;
                    goto next_x;
                }
            }
            //*/

            // skip if it's a solid line on the left
            int count = 0;
            prev = SP_PIX(x, y);
            for (off = 1; off < kSpriteY; ++off) {
                if (SP_PIX(x, y + off) == prev) {
                    count++;
                } else {
                    break;
                }
            }
            if (count == 13) {
                goto next_x;
            }
            //*/

            // extract tile
            uint32_t screen_tile[7];
            uint8_t color_palette[MAX_PALETTE_SIZE] = {0};
            int n_colors = 0;
            int sp_x, sp_y;
            for (sp_x = 0; sp_x < kSpriteX; ++sp_x) {
                uint32_t col = 0;
                for (sp_y = 0; sp_y < kSpriteY; ++sp_y) {
                    int color = SP_PIX(x + sp_x, y + sp_y);
                    if (!color_palette[color]) {
                        color_palette[color] = ++n_colors;
                    }
                    col = (color_palette[color] - 1) | (col << 2);
                }
                screen_tile[sp_x] = col;
            }

            if (n_colors != 3) {
                continue;
            }

            considered++;

            if (0 && y == 137) {
                for (off = 0; off < sizeof(screen_tile); ++off) printf("%c", "01234"[screen_tile[off]]);
                printf("\n");
            }

            struct sprite *sprite = find_sprite(screen_tile, sprites, n_sprites);
            if (sprite) {
                matched[match_count].x = x;
                matched[match_count].y = y;
                matched[match_count].sp = sprite;
                matched[match_count].space = 0;

                if (!found) {
                    found = 1;
                }

                if (lastX != -1 && x > lastX + 3) {
                    matched[match_count].space = 1;
                }

                if (++match_count >= max_matches) {
                    return match_count;
                }

                x += sprite->width - 1;
                lastX = x;
            }
            next_x:;
        }
        if (found) {
            y += 13;
        }
    }

    return match_count;
}

/* try to combine two different sprite match structures into one, aborting if they have two sprites with the same positions and different ids
   this improves noise tolerance  */
int merge_sprites(struct sprite_match *a, int a_count, struct sprite_match *b, int b_count, struct sprite_match *dest, int dest_count, int *overlap_out) {
    int overlap = 0;
    int ind_a = 0, ind_b = 0, ind_dest = 0;
    while (ind_a < a_count && ind_b < b_count && ind_dest < dest_count && a[ind_a].sp && b[ind_b].sp) {
        int diff = a[ind_a].y - b[ind_b].y;
        if (!diff)
            diff = a[ind_a].x - b[ind_b].x;

        if (diff < 0) {
            dest[ind_dest++] = a[ind_a++];
        } else if (diff > 0) {
            dest[ind_dest++] = b[ind_b++];
        } else {
            if (a[ind_a].sp != b[ind_b].sp) {
                *overlap_out = 0;
                return 0;
            }
            overlap++;
            dest[ind_dest++] = a[ind_a];
            ind_a++;
            ind_b++;
        }
    }
    while (b[ind_b].sp && ind_dest < dest_count && ind_b < b_count) {
        dest[ind_dest++] = b[ind_b++];
    }
    while (a[ind_a].sp && ind_dest < dest_count && ind_a < a_count) {
        dest[ind_dest++] = a[ind_a++];
    }

    int lastX = -1;
    int lastY = -1;

    int i;
    for (i = 0; i < ind_dest; ++i) {
        dest[i].space = 0;
        if (lastY == dest[i].y && lastX != -1 && dest[i].x > lastX + 3) {
            dest[i].space = 1;
        }
        lastY = dest[i].y;
        lastX = dest[i].x + dest[i].sp->width - 1;
    }

    *overlap_out = overlap;
    return ind_dest;
}
