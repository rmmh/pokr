#!/usr/bin/env python

import os
import re
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
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            cv2.namedWindow("Stream", cv2.WINDOW_AUTOSIZE)
            cv2.namedWindow("Game", cv2.WINDOW_AUTOSIZE)
        self.tile_map = self.make_tilemap('crystal_tiles.png')
        self.tile_text = self.make_tile_text('crystal_tiles.txt')


    def make_tile_text(self, fname):
        def make_wide(x):
            if not wide or len(x.strip()) < 2:
                return x[0]
            elif 's' in flags:
                return x[1] + x
            else:
                return x[0] + x

        out = {}
        for line in open(fname):
            m = re.match('([0-9A-F]+)([a-z]*):(.*)', line)
            if m:
                offset = int(m.group(1), 16)
                flags = m.group(2)
                wide = 'w' in flags
                if 'x' in flags:
                    offset += 1024
                letters = m.group(3)
                width = 1 + wide
                for i in xrange(0, len(letters), width):
                    t = letters[i:i+width]
                    if t == ' ':
                        continue
                    out[offset + (i / width)] = make_wide(t)
        return out

    def make_tilemap(self, name):
        path = os.path.abspath(os.path.dirname(__file__)) + '/' + name
        tiles = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2GRAY) < 128

        tile_map = {}

        n = -1
        for y in xrange(len(tiles) / 8):
            for x in xrange(128 / 8):
                n += 1
                sprite = self.sprite_to_int(tiles, x, y)
                if sprite == 0:
                    continue
                if sprite in tile_map:
                    print 'huh', x*8, y*8, tile_map[sprite], sprite
                tile_map[sprite] = n

        return tile_map

    def sprite_to_int(self, image, left, top):
        bits = (image[top*8:top*8+8, left*8:left*8+8]).flat
        out = 0
        for n,bit in enumerate(bits):
            if bit:
                out |= 1<<(63-n)
        return out

    def screen_to_tiles(self, screen):
        screen = screen < 128
        out = []
        for y in range(18):
            for x in range(20):
                sprite = self.sprite_to_int(screen, x, y)
                tile_n = self.tile_map.get(sprite, 0)
                if tile_n == 0:
                    # try inverting it?
                    tile_n = self.tile_map.get((~sprite)&((1<<64)-1), 0)
                if tile_n == 0:
                    tile_n = bin(sprite).count('1') / 8
                out.append(tile_n)
        return out

    def screen_to_text(self, screen):
        tiles = self.screen_to_tiles(screen)
        out_text = ''
        out_dither = ''
        out_full = []
        for n, tile in enumerate(tiles):
            text = self.tile_text.get(tile, None)
            out_full.append(text or tile)
            text = (text or ' ')[0]
            out_text += text
            out_dither += text if text != ' ' else self.tile_text.get(tile + 1024, ' ')[0]
            if n % 20 == 19:
                out_text += '\n'
                out_dither += '\n'
        return out_full, out_text, out_dither

    def stream_to_text(self, frame):
        screen = extract_screen(frame)
        return screen, self.screen_to_text(screen)

    def handle(self, data):
        if self.debug:
            cv2.imshow('Stream', data['frame'])
            cv2.imshow('Screen', data['screen'])
            cv2.waitKey(1)

        full, text, dithered = self.screen_to_text(data['screen'])
        data.update(text=text, dithered=dithered, full=full)

    def test_corpus(self):
        import os
        for fn in os.listdir('corpus'):
            print '#' * 20 + ' ' + fn
            screen, (text, dithered) = self.stream_to_text(cv2.cvtColor(cv2.imread('corpus/' + fn), cv2.COLOR_BGR2GRAY))
            print dithered



class StreamProcessor(object):
    def __init__(self, bufsize=120, ratelimit=True, frame_skip=0, default_handlers=True, debug=False, video_loc=None):
        self.frame_queue = Queue.Queue(bufsize)
        self.ratelimit = ratelimit
        self.frame_skip = frame_skip
        self.handlers = []
        self.video_loc = video_loc
        if default_handlers:
            self.handlers.append(video.ScreenExtractor().handle)
            self.handlers.append(SpriteIdentifier(debug=debug).handle)
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
                    if self.video_loc:
                        print 'stream ended'
                        self.frame_queue.put(None)
                        return
                    print 'failed grabbing frame, reconnecting'
                    break

    def process_frames(self):
        cur = time.time()
        while True:
            prev = cur
            cur = time.time()
            # give a timeout to avoid python Issue #1360:
            # Ctrl-C doesn't kill threads waiting on queues
            frame = self.frame_queue.get(True, 60*60*24)  
            if frame is None:
                return
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
        if self.video_loc:
            return self.video_loc
        while True:
            try:
                streamer = livestreamer.Livestreamer()
                plugin = streamer.resolve_url('http://twitch.tv/twitchplayspokemon')
                streams = plugin.get_streams()
                return streams['source'].url
            except KeyError:
                print 'unable to connect to stream, sleeping 30 seconds...'
                time.sleep(30)

    def run(self):
        thread.start_new_thread(self.grab_frames, ())
        self.process_frames()


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
    import dialog

    class DialogPusher(object):
        def __init__(self):
            self.tracker = dialog.BattleState('blah wants to fight', '')
        def handle(self, text, lines, timestamp):
            print timestamp, repr(self.tracker.annotate(text, lines))


    box_reader = dialog.BoxReader()
    box_reader.add_dialog_handler(DialogPusher().handle)

    debug = '--show' in sys.argv
    proc = StreamProcessor(debug=debug)
    #proc.add_handler(handler_stdout)
    proc.add_handler(LogHandler('text', 'frames.log').handle)
    proc.add_handler(delta.StringDeltaCompressor('dithered', verify=True).handle)
    proc.add_handler(box_reader.handle)
    proc.run()
