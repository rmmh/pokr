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

static struct sprite *find_sprite(uint8_t *needle, struct sprite *haystack, int n_sprites) {
    int i;
    for (i = 0; i < n_sprites; ++i) {
        uint8_t *sprite_color = haystack[i].image;
        uint8_t *screen_color = needle;
        while (screen_color - needle < haystack[i].width * kSpriteY) {
            if (*screen_color++ != *sprite_color++)
                goto next_sprite;
        }
        return haystack + i;
        next_sprite:;
    }

    return NULL;
}

int identify_sprites(uint8_t *image, struct sprite *sprites, int n_sprites, struct sprite_match *matched, int max_matches) {
    /*
    Identify sprites using fuzzy palette pattern matching
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
            uint8_t screen_tile[7 * 14];
            uint8_t *screen_out = screen_tile;
            uint8_t color_palette[MAX_PALETTE_SIZE] = {0};
            int n_colors = 0;
            int sp_x, sp_y;
            for (sp_x = 0; sp_x < kSpriteX; ++sp_x) {
                for (sp_y = 0; sp_y < kSpriteY; ++sp_y) {
                    int color = SP_PIX(x + sp_x, y + sp_y);
                    if (!color_palette[color]) {
                        color_palette[color] = ++n_colors;
                    }
                    *screen_out++ = color_palette[color] - 1;
                }
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
                matched[match_count].id = sprite->id;
                matched[match_count].text = sprite->text;
                matched[match_count].space = 0;

                if (!found) {
                    found = 1;
                    //printf("y:%d ", y);
                }

                if (lastX != -1 && x > lastX + 3) {
                    //putchar(' ');
                    matched[match_count].space = 1;
                }

                if (++match_count >= max_matches) {
                    return match_count;
                }


                //printf("%s", sprite->code);
                x += sprite->width - 1;
                lastX = x;
            }
            next_x:;
        }
        if (found) {
            y += 13;
            //printf("\n");
        }
    }
    //printf("considered: %d\n", considered);

    return match_count;
    //printf("\n");
}
