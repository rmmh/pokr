import gzip
import os
import struct
import time

import cv2
import numpy

import ocr

from cffi import FFI

DATA_DIR = os.path.abspath(os.path.dirname(__file__))

ffi = FFI()
ffi.cdef(open(DATA_DIR + '/accel.h').read())
C = ffi.dlopen(os.path.abspath(os.path.dirname(__file__)) + '/accel.so')


class ScreenExtractor(object):
    def __init__(self, fname=None, debug=False):
        self.last = None
        self.n = 0

    def handle(self, data):
        self.n += 1
        data['screen'] = ocr.extract_screen(data['frame'])
        trunc = data['screen'] >> 6  # / 64 -> values in [0, 3]
        data['changed'] = not numpy.array_equal(trunc, self.last)
        data['frame_n'] = self.n
        if not data['changed']:
            raise StopIteration

        self.last = trunc


class OCREngine(object):
    def __init__(self, sprites, sprite_text):
        self.sprite_text = ''
        self.sprites = ffi.new('struct sprite[]', len(sprites) + 1)
        self.n_sprites = len(sprites)
        sprites.sort(key=lambda (id, buf): buf)
        for sprite_n, (sprite_id, sprite_buf) in enumerate(sprites):
            sprite = self.sprites[sprite_n]
            sprite.id = sprite_id
            text = sprite_text.get(sprite_id, '#')
            sprite.text = text
            sprite.width = max(3, len(sprite_buf) / 14)
            sprite.image = sprite_buf
        self.sprites[len(sprites)].id = -1
        #print repr(list(self.sprites[0].image[0:128]))

        self.map = ffi.new('uint8_t[]', 256)
        #  61 is the dark red of the down arrow on text boxes
        #  Map it to 2 so the OCR engine's 3 color heuristic isn't confused.
        for color, n in ((246, 1), (206, 2), (97, 3), (61, 3)):
            for off in range(-9, 9):
                self.map[color + off] = n

        self.last_image = None

    def identify(self, screen):
        #return []
        max_matches = 128
        image = screen.flatten(order='F')
        pimage = ffi.cast('uint8_t *', image.ctypes.data)
        C.translate_bytes(pimage, 240*160, self.map)
        if numpy.array_equal(image, self.last_image):
            return self.last_out
        self.last_image = image
        results = ffi.new('struct sprite_match[]', max_matches)
        matched = C.identify_sprites(pimage, self.sprites, self.n_sprites, results, max_matches)
        out = []
        lastY = None
        for n in xrange(matched):
            match = results[n]
            if match.y != lastY:
                out += [[match.y, '']]
                lastY = match.y
            out[-1][1] += ' ' * match.space + ffi.string(match.text)
        self.last_out = out
        return out


class ScreenCompressor(object):
    '''
    Experimental compression for very low-bandwidth video streaming.

    Packing each frame as 2bpp as a series of 8x8 blocks (matching the GameBoy
    sprite size), then applying a generic LZ77 compressor (LZ4 performs better
    than DEFLATE) reduces the video stream from >1000kbps to <10kbps (<5MB/hr).
    '''

    FRAME_BYTES = 144 * 160 * 2 / 8

    def __init__(self, fname=None, debug=False):
        self.last = None
        self.fd = None
        if fname:
            self.fd = gzip.GzipFile(time.strftime(fname), "w")
        self.debug = debug
        self.start = time.time()

    def handle(self, data):
        trunc = data['screen'] >> 6  # / 64
        trunc_flat = trunc.flatten()
        ptrunc = ffi.cast("uint8_t *", trunc_flat.ctypes.data)
        pout = ffi.new('uint8_t[]', self.FRAME_BYTES)
        C.pack2bpp(ptrunc, pout)

        if self.fd:
            self.fd.write('+f\xc9q')
            self.fd.write(struct.pack('<LB', data.get('timestamp_s', 0), data['frame_n'] & 0xff))
            self.fd.write(ffi.buffer(pout))
        self.last = trunc

        if self.debug:
            n = data['frame_n']
            if n&0xf==0:
                print '%.3f %.3f' % (n/60., (n/60.) / (time.time() - self.start))
            self.unpack(pout, trunc)
            cv2.imshow('Stream', cv2.resize(trunc * 80, (160 * 4, 144 * 4), interpolation=cv2.INTER_NEAREST))
            cv2.waitKey(1)

    def unpack(self, pout, frame):
        off = 0
        for py in range(18):
            for px in range(20):
                for n in range(8):
                    a = pout[off] | (pout[off + 1] << 8)
                    off += 2
                    for nx in range(8):
                        frame[py*8+n][px*8+nx] = a & 3
                        a >>= 2

if __name__ == '__main__':
    import timestamp

    class SavedStreamProcessor(ocr.StreamProcessor):
        def get_stream_location(self):
            import sys
            if len(sys.argv) > 1:
                return sys.argv[1]
            else:
                return '/home/ryan/games/tpp/stream.flv'

    proc = SavedStreamProcessor(default_handlers=False)
    proc.add_handler(ScreenExtractor().handle)
    proc.add_handler(timestamp.TimestampRecognizer().handle)
    proc.add_handler(ScreenCompressor(debug=True, fname='frames.raw.gz').handle)
    proc.run()
    while True:
        time.sleep(1)  # loop until killed with ctrl-c
