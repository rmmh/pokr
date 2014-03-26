void pack2bpp(uint8_t *in, uint8_t *out);

struct sprite {
    uint8_t image[98]; // 7 * 14
    int id;
    char text[5];
    int width;
};

struct sprite_match {
	int x;
	int y;
	int id;
	char *text;
	int space;
};

void translate_bytes(uint8_t *image, int len, uint8_t *table);

int identify_sprites(uint8_t *image, struct sprite *sprites, int n_sprites, struct sprite_match *matched, int max_matches);
