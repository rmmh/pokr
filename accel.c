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

struct color_stat {
    int color, count, sum, squaresum;
};

#define SP_PIX(x, y) image[(y)+(x)*160]
#define WITHIN(a, b, bounds) ((a) > (b) - (bounds) && (a) < (b) + (bounds))

inline float compute_sigma(struct color_stat *stat) {
    float mean = (float)stat->sum / stat->count;
    float meansquare = (float)stat->squaresum / stat->count;
    return sqrt(meansquare - mean * mean);
}

void identify_sprites(uint8_t *image, sprite_t *sprites, sp_match_t *matched, int max_matches) {
    /*
    Identify sprites using fuzzy palette pattern matching
    */
    int x, y;
    int n_matched = 0;
    const int kTolerance = 5;
    const int kSpriteX = 7;
    const int kSpriteY = 15;
    for (y = 1; y < 160 - kSpriteY; ++y) {
        int found = 0;
        for (x = 0; x < 240 - kSpriteX; ++x) {
            // skip if it's not solid above
            int off;
            int prev = SP_PIX(x, y - 1);
            for (off = 1; off < kSpriteX; ++off) {
                int cur = SP_PIX(x + off, y - 1);
                if (!WITHIN(cur, prev, kTolerance)) {
                    goto next_x;
                }
            }

            // skip if it's a solid line on the left
            int count = 0;
            prev = SP_PIX(x, y);
            for (off = 1; off < kSpriteY; ++off) {
                int cur = SP_PIX(x + off, y - 1);
                if (!WITHIN(cur, prev, kTolerance)) {
                    goto next_x;
                }
                if (SP_PIX(x, y + off) == prev) {
                    count++;
                } else {
                    break;
                }
            }
            if (count == 15)
                goto next_x;


            // extract tile
            uint8_t screen_tile[7 * 15];
            int sp_x, sp_y;
            for (sp_x = 0; sp_x < kSpriteX; ++sp_x) {
                for (sp_y = 0; sp_y < kSpriteY; ++sp_y) {
                    screen_tile[sp_x * kSpriteY + sp_y] = SP_PIX(x + sp_x, y + sp_y);
                }
            }

            // skip low-variance tiles
            {
                int sum = 0;
                int squaresum = 0;
                int ind;
                for (ind = 0; ind < sizeof(screen_tile); ++ind) {
                    int color = screen_tile[ind];
                    squaresum += color * color;
                    sum += color;
                }

                int var = squaresum/128 - (sum/128) * (sum/128);

                if (var < 1500) {
                    goto next_x;
                }
            }


            sprite_t *cur_sprite = sprites;
            for (cur_sprite = sprites; cur_sprite->id != -1; ++cur_sprite) {
                struct color_stat palette_stats[MAX_PALETTE_SIZE];
                memset(&palette_stats, 0, sizeof(palette_stats));
                uint8_t *sprite_color = cur_sprite->image;
                uint8_t *screen_color = screen_tile;
                int ind;
                int mismatch = 0;
                for (ind = 0; ind < cur_sprite->width * kSpriteY; ++ind) {
                    int color = *screen_color;
                    struct color_stat *stat = &palette_stats[*sprite_color];
                    if (!stat->count) {
                        stat->color = color;
                    } else {
                        if (stat->color > (color + kTolerance) || stat->color < (color - kTolerance)) {
                            mismatch++;
                            if (mismatch > cur_sprite->width - 2)
                                goto next_sprite;
                        }
                    }
                    stat->count++;
                    /*
                    stat->sum += color;
                    stat->squaresum += color * color;
                    */
                    sprite_color++;
                    screen_color++;
                }

                if (WITHIN(palette_stats[0].color, palette_stats[1].color, kTolerance)
                    || WITHIN(palette_stats[1].color, palette_stats[2].color, kTolerance)
                    || WITHIN(palette_stats[0].color, palette_stats[2].color, kTolerance)) {
                    continue;
                }

                /*

                struct color_stat tot = {0};
                float sigma_total = 0.0f;
                struct color_stat *stat = palette_stats;
                for (stat = palette_stats; stat->count; ++stat) {
                    sigma_total += compute_sigma(stat);
                    tot.count += stat->count;
                    tot.sum += stat->sum;
                    tot.squaresum += stat->squaresum;
                }

                // skip low-variance tiles
                /*
                if (compute_sigma(&tot) < 5.0) {
                    continue;
                }
                */

                //if (sigma_total < 3.0)
                {
                    if (!found) {
                        printf("y:%d ", y);
                    }
                    putchar(cur_sprite->code);
                    found = 1;
                    //printf("%c x:%d y:%d c:%d sp.id:%d sp.w:%d sigma_total:%.3f\n", cur_sprite->code, x, y, tot.count, cur_sprite->id, cur_sprite->width, sigma_total);
                    x += cur_sprite->width - 1;
                    break;
                }
                next_sprite:;
            }
            next_x:;
        }
        if (found) {
            y += 14;
            printf("\n");
        }
    }
    //printf("\n");
}
