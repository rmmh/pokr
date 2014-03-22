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
        self.sprites = ffi.new('sprite_t[]', len(sprites) + 1)
        for sprite_n, (sprite_id, sprite_buf) in enumerate(sprites):
            sprite = self.sprites[sprite_n]
            sprite.id = sprite_id
            sprite.code = sprite_text.get(sprite_id, '#')
            sprite.width = max(3, len(sprite_buf) / 15)
            sprite.image = sprite_buf
        self.sprites[len(sprites)].id = -1
        #print repr(list(self.sprites[0].image[0:128]))

    def identify(self, screen):
        #return []
        max_matches = 128
        results = ffi.new('sp_match_t[]', max_matches)
        pimage = ffi.cast('uint8_t *', screen.flatten(order='F').ctypes.data)
        C.identify_sprites(pimage, self.sprites, results, max_matches)
        return []


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
