#!/usr/bin/env python

import collections
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
    #screen_x, screen_y = 8, 41
    #screen = raw[screen_y:screen_y+432, screen_x:screen_x+480]
    #screen = cv2.resize(screen, (160, 144), interpolation=cv2.INTER_AREA)
    screen_x, screen_y = 8, 8
    screen = raw[screen_y:screen_y+640, screen_x:screen_x+960]
    screen = cv2.resize(screen, (240, 160), interpolation=cv2.INTER_AREA)
    return screen


class SpriteIdentifier(object):
    '''Convert image sprites into a text format'''
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            cv2.namedWindow("Stream", cv2.WINDOW_AUTOSIZE)
            cv2.namedWindow("Game", cv2.WINDOW_AUTOSIZE)
        self.tile_map = self.make_tilemap('firered_tiles.png')
        self.tile_text = self.make_tile_text('firered_tiles.txt')
        self.ocr_engine = video.OCREngine(self.tile_map, self.tile_text)


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
                if 'l' in flags:
                    out[offset] = letters
                    continue
                width = 1 + wide
                for i in xrange(0, len(letters), width):
                    t = letters[i:i+width]
                    if t == ' ':
                        continue
                    out[offset + (i / width)] = make_wide(t)
        return out

    def make_tilemap(self, name):
        path = os.path.abspath(os.path.dirname(__file__)) + '/' + name
        tiles = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2GRAY)

        sprites = []

        n = -1
        for y in xrange(len(tiles) / 16):
            for x in xrange(len(tiles[0]) / 8):
                n += 1
                sprite = self.sprite_to_quant(tiles, x, y)
                if not sprite:
                    continue
                if self.debug:
                    print('({}, {}) rows: {}'.format(y, x, len(sprite)/14))
                    for i in xrange(0, len(sprite), 14):
                        print(''.join([ str(x) for x in sprite[i:i+14] ]))
                sprites.append((n, sprite))

        #print "sprites:", sprites
        return sprites

    def sprite_to_quant(self, image, left, top):
        bits = (image[top*16:top*16+14, left*8:left*8+8]).flatten(order='F')
        palette = collections.OrderedDict.fromkeys(bits)
        if len(palette) == 1:
            return []
        palette_map = {color: n for n, color in enumerate(palette)}
        buf = [palette_map[color] for color in bits]
        while set(buf[-14:]) == {0}: buf = buf[:-14]
        while set(buf[:14]) == {0}: buf = buf[14:]
        #print left, top, buf
        assert(len(set(buf)) == 3)
        return buf

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
        return self.ocr_engine.identify(screen)

    def stream_to_text(self, frame):
        screen = extract_screen(frame)
        return screen, self.screen_to_text(screen)

    def handle(self, data):
        if self.debug:
            cv2.imshow('Stream', data['frame'])
            cv2.imshow('Screen', data['screen'])
            cv2.waitKey(1)

        text = self.screen_to_text(data['screen'])
        data.update(text=text)

    def test_corpus(self, directory='corpus'):
        import os
        import time
        images = []
        for fn in os.listdir(directory):
            images.append((fn, cv2.cvtColor(cv2.imread(directory + '/' + fn), cv2.COLOR_BGR2GRAY)))
        sstart = time.time()
        for _ in range(10):
            for fn, im in images:
                print '#' * 20 + ' ' + fn
                start = time.time()
                screen, text = self.stream_to_text(im)
                print "%.1f"%((time.time()-start)*1000), text
        print 'TOTAL:', time.time() - sstart


class StreamProcessor(object):
    '''Grab frames from input and process with handlers'''
    def __init__(self, bufsize=120, ratelimit=True, frame_skip=0, default_handlers=True, debug=False, video_loc=None):
        self.frame_queue = Queue.Queue(bufsize)
        if ratelimit is None:
            # Automatically disable ratelimit if not using the default stream
            # from Twitch. Users may want to set it to True/False directly.
            ratelimit = video_loc is None
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
            #stream.set(cv2.cv.CV_CAP_PROP_POS_MSEC, (3*60+10)*1000)
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
            times = []
            tot_elapsed = 0
            for handler in self.handlers:
                try:
                    start = time.time()
                    handler(data)
                except StopIteration:
                    break
                except Exception:
                    traceback.print_exc()
                finally:
                    elapsed = time.time() - start
                    tot_elapsed += elapsed
                    times.append((handler, elapsed))
            if tot_elapsed > 1/60.0:
                pass
                #print 'warning, slow frame', sorted(times, key=lambda x: x[1], reverse=True)
                #cv2.imwrite('slow_%s_%f.png' % (data['timestamp'], tot_elapsed), data['frame'])



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
    import redis
    import json

    r = redis.Redis()

    class DialogPusher(object):
        def handle(self, text, data):
            timestamp = data['timestamp']
            lines = ''
            print data['timestamp'], text#repr(self.tracker.annotate(text, data))
            r.publish('pokemon.streams.dialog', json.dumps({'time': timestamp, 'text': text, 'lines': lines}))


    box_reader = dialog.BoxReader()
    box_reader.add_dialog_handler(DialogPusher().handle)

    debug = '--show' in sys.argv
    try:
        video_loc = sys.argv[sys.argv.index('-f') + 1]
    except (ValueError, IndexError):
        video_loc = None
    proc = StreamProcessor(debug=debug, video_loc=video_loc)
    #proc.add_handler(handler_stdout)
    #proc.add_handler(LogHandler('text', 'frames.log').handle)
    #proc.add_handler(delta.StringDeltaCompressor('dithered', verify=True).handle)
    proc.add_handler(box_reader.handle)
    proc.run()
