#!/usr/bin/env python

import os
import sys
import time
import thread
import traceback
import Queue

import livestreamer
import cv2

import delta
import timestamp
import video


def extract_screen(raw):
    screen_x, screen_y = 8, 41
    screen = raw[screen_y:screen_y+432, screen_x:screen_x+480]
    screen = cv2.resize(screen, (160, 144), interpolation=cv2.INTER_AREA)
    return screen


class SpriteIdentifier(object):
    def __init__(self, preview=False):
        self.preview = preview
        if self.preview:
            cv2.namedWindow("Stream", cv2.WINDOW_AUTOSIZE)
            cv2.namedWindow("Game", cv2.WINDOW_AUTOSIZE)
        self.tile_map = self.make_tilemap('red_tiles')
        self.tile_map_outside = self.make_tilemap('red_tiles_outside')

    def make_tilemap(self, name):
        path = os.path.abspath(os.path.dirname(__file__)) + '/' + name
        tiles = cv2.cvtColor(cv2.imread(path + '.png'), cv2.COLOR_BGR2GRAY) < 128
        tile_text = open(path + '.txt').read()

        tile_map = {}

        for y, line in enumerate(tile_text.splitlines()):
            for x, char in enumerate(line):
                sprite = self.sprite_to_int(tiles, x, y)
                if sprite == 0:
                    continue
                tile_map[sprite] = char

        return tile_map

    def sprite_to_int(self, image, left, top):
        bits = (image[top*8:top*8+8, left*8:left*8+8]).flat
        out = 0
        for n,bit in enumerate(bits):
            if bit:
                out |= 1<<(63-n)
        return out

    def screen_to_text(self, screen):
        screen = screen < 128
        out_text = ''
        out_dither = ''
        for y in range(18):
            for x in range(20):
                sprite = self.sprite_to_int(screen, x, y)
                out_text += self.tile_map.get(sprite, ' ')
                out_dither += self.tile_map.get(sprite, None) or self.tile_map_outside.get(sprite, None) or ' .,:;*@#'[bin(sprite).count('1')/10]
            out_text += '\n'
            out_dither += '\n'
        return out_text, out_dither

    def stream_to_text(self, frame):
        screen = extract_screen(frame)
        return screen, self.screen_to_text(screen)

    def handle(self, data):
        if self.preview:
            cv2.imshow('Stream', data['frame'])
            cv2.imshow('Screen', data['screen'])
            cv2.waitKey(1)

        text, dithered = self.screen_to_text(data['screen'])
        data.update(text=text, dithered=dithered)

    def test_corpus(self):
        import os
        for fn in os.listdir('corpus'):
            print '#' * 20 + ' ' + fn
            screen, (text, dithered) = self.stream_to_text(cv2.cvtColor(cv2.imread('corpus/' + fn), cv2.COLOR_BGR2GRAY))
            print dithered



class StreamProcessor(object):
    def __init__(self, bufsize=120, ratelimit=True, frame_skip=0, default_handlers=True):
        self.frame_queue = Queue.Queue(bufsize)
        self.ratelimit = ratelimit
        self.frame_skip = frame_skip
        self.handlers = []
        if default_handlers:
            self.handlers.append(video.ScreenExtractor().handle)
            self.handlers.append(SpriteIdentifier().handle)
            self.handlers.append(timestamp.TimestampRecognizer().handle)

    def add_handler(self, handler):
        self.handlers.append(handler)

    def grab_frames(self):
        while True:
            stream = cv2.VideoCapture(self.get_stream_location())
            while True:
                stream.grab()
                for _ in range(self.frame_skip):
                    stream.grab()
                success, frame = stream.retrieve()
                if success:
                    try:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        self.frame_queue.put(frame, block=False, timeout=1.)
                    except Queue.Full:
                        continue
                else:
                    print 'failed grabbing frame, reconnecting'
                    break

    def process_frames(self):
        cur = time.time()
        while True:
            prev = cur
            cur = time.time()
            frame = self.frame_queue.get()
            data = {'frame': frame}
            for handler in self.handlers:
                try:
                    handler(data)
                except StopIteration:
                    break
                except Exception:
                    traceback.print_exc()

            qsize = self.frame_queue.qsize()
            if self.ratelimit and qsize < 60:
                # TODO: proper framerate control
                # This hackily slows down processing as we run out of frames
                time.sleep(max(0, 1/60. - (cur - prev) + 1/600.*(60-qsize)))

    def get_stream_location(self):
        streamer = livestreamer.Livestreamer()
        plugin = streamer.resolve_url('http://twitch.tv/twitchplayspokemon')
        streams = plugin.get_streams()
        return streams['source'].url

    def run(self):
        thread.start_new_thread(self.grab_frames, ())
        thread.start_new_thread(self.process_frames, ())


class LogHandler(object):
    def __init__(self, key, fname, rep=None):
        self.key = key
        self.fd = open(fname, 'a')
        self.last = ''
        self.rep = rep or (lambda s: s.replace('\n', '`'))

    def handle(self, data):
        text = data[self.key]
        if text != self.last:
            self.last = text
            self.fd.write(self.rep(text) + data['timestamp'] + '\n')

if __name__ == '__main__':
    #SpriteIdentifier().test_corpus();q

    def handler_stdout(data):
        print '\x1B[H' + data['timestamp'] + ' '*10
        print data['dithered']

    import delta

    debug = '--show' in sys.argv
    identifier = SpriteIdentifier(preview=debug)
    proc = StreamProcessor()
    #proc.add_handler(video.ScreenCompressor().handle)
    proc.add_handler(handler_stdout)
    proc.add_handler(LogHandler('text', 'frames.log').handle)
    proc.add_handler(delta.StringDeltaCompressor('dithered', verify=True).handle)
    proc.run()

    time.sleep(5)

    print '\x1b[2J'
    while True:
        time.sleep(1)  # loop until killed with ctrl-c
