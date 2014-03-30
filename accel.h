void pack2bpp(uint8_t *in, uint8_t *out);

struct sprite {
    uint32_t image[7];
    int id;
    char text[5];
    int width;
};

struct sprite_match {
	int x;
	int y;
	struct sprite *sp;
	int space;
};

struct sprite_matches {
	int cap, len;
	struct sprite_match m[128];
};

void translate_bytes(uint8_t *image, int len, uint8_t *table);

int identify_sprites(uint8_t *image, struct sprite *sprites, int n_sprites, struct sprite_match *matched, int max_matches);

int merge_sprites(struct sprite_match *a, int a_count, struct sprite_match *b, int b_count, struct sprite_match *dest, int dest_count, int *overlap_out);
