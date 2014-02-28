import gzip
import os
import struct
import time

import cv2
import numpy

from cffi import FFI

ffi = FFI()
ffi.cdef("void pack2bpp(uint8_t *in, uint8_t *out);")
C = ffi.dlopen(os.path.abspath(os.path.dirname(__file__)) + '/compress.so')

import ocr

class SavedStreamProcessor(ocr.StreamProcessor):
    def get_stream_location(self):
        return '/home/ryan/games/tpp/stream.flv'

def pack(frame, pout):
    frame_len = len(frame.flat)
    pframe = ffi.cast("uint8_t *", frame.ctypes.data)
    C.pack2bpp(pframe, pout)

class FrameCompressor(object):
    FRAME_BYTES = 144 * 160 * 2 / 8

    def __init__(self, fname=None, debug=False):
        self.last = None
        self.fd = None
        if fname:
            self.fd = gzip.GzipFile(time.strftime(fname), "w")
        self.n = 0
        self.debug = debug
        self.start = time.time()

    def handle(self, data):
        self.n += 1
        trunc = data['screen'] >> 6  # / 64
        if numpy.array_equal(trunc, self.last):
            return

        pout = ffi.new('uint8_t[]', self.FRAME_BYTES)
        trunc_flat = trunc.flatten()
        pack(trunc_flat, pout)
        if self.fd:
            self.fd.write('+f\xc9q')
            self.fd.write(struct.pack('<LB', data.get('timestamp_s'), self.n & 0xff))
            self.fd.write(ffi.buffer(pout))
        self.last = trunc

        if self.debug:
            if self.n&0xf==0:
                print '%.3f %.3f' % (self.n/60., (self.n/60.) / (time.time() - self.start))
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
    #cv2.namedWindow("Stream", cv2.WINDOW_AUTOSIZE)
    proc = SavedStreamProcessor(default_handlers=False)
    proc.add_handler(ocr.SpriteIdentifier().handle_screen)
    comp = FrameCompressor(debug=True)
    proc.add_handler(comp.handle)
    proc.run()
    while True:
        time.sleep(1)  # loop until killed with ctrl-c