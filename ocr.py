#!/usr/bin/env python

import os
import sys
import time
import thread
import traceback
import Queue

import livestreamer
import cv2


class SpriteIdentifier(object):
    def __init__(self, preview=False):
        path = os.path.abspath(os.path.dirname(__file__))
        tiles = cv2.cvtColor(cv2.imread(path + "/red_tiles.png"), cv2.COLOR_BGR2GRAY) < 128
        tile_text = open(path + '/red_tiles.txt').read()

        self.tile_map = {}

        for y, line in enumerate(tile_text.splitlines()):
            for x, char in enumerate(line):
                sprite = self.sprite_to_int(tiles, x, y)
                if char == ' ' or sprite == 0:
                    continue
                self.tile_map[sprite] = char

        self.preview = preview
        if self.preview:
            cv2.namedWindow("Stream", cv2.WINDOW_AUTOSIZE)
            cv2.namedWindow("Game", cv2.WINDOW_AUTOSIZE)

    def sprite_to_int(self, image, left, top):
        bits = (image[top*8:top*8+8, left*8:left*8+8]).flat
        out = 0
        for n,bit in enumerate(bits):
            if bit:
                out |= 1<<(63-n)
        return out

    def screen_to_text(self, screen):
        screen = screen < 128
        out = ''
        for y in range(18):
            for x in range(20):
                out += self.tile_map.get(self.sprite_to_int(screen, x, y), ' ')
            out += '\n'
        return out

    def extract_screen(self, raw):
        screen_x, screen_y = 8, 41
        screen = raw[screen_y:screen_y+432, screen_x:screen_x+480]
        screen = cv2.resize(screen, (160, 144))
        return screen

    def stream_to_text(self, frame):
        screen = self.extract_screen(frame)
        if self.preview:
            cv2.imshow('Stream', frame)
            cv2.imshow("Game", screen)
            cv2.waitKey(1)

        return self.screen_to_text(screen)

    def test_corpus(self):
        import os
        for fn in os.listdir('corpus'):
            print '#' * 20 + ' ' + fn
            print identifier.stream_to_text(cv2.cvtColor(cv2.imread('corpus/' + fn), cv2.COLOR_BGR2GRAY))


class StreamProcessor(object):
    def __init__(self, identifier=None, bufsize=120, ratelimit=True):
        self.frame_queue = Queue.Queue(bufsize)
        self.ratelimit = ratelimit
        self.handlers = []
        if identifier is None:
            identifier = SpriteIdentifier().stream_to_text
        self.identifier = identifier

    def add_handler(self, handler):
        self.handlers.append(handler)

    def grab_frames(self):
        while True:
            self.stream.grab()
            success, frame = self.stream.retrieve()
            if success:
                try:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    self.frame_queue.put(frame, block=False, timeout=1.)
                except Queue.Full:
                    continue

    def process_frames(self):
        tlog = open('frames.txt', 'a')  # tail -f frames.txt | tr '`' '\n'
        last_text = ''
        cur = time.time()
        while True:
            prev = cur
            cur = time.time()
            frame = self.frame_queue.get()
            text = self.identifier(frame)
            if text != last_text:
                data = {'text': text, 'frame': frame}
                last_text = text
                for handler in self.handlers:
                    try:
                        handler(data)
                    except Exception:
                        traceback.print_exc()

            qsize = self.frame_queue.qsize()
            if self.ratelimit and qsize < 60:
                # TODO: proper framerate control
                # This hackily slows down processing as we run out of frames
                time.sleep(max(0, 1/60. - (cur - prev) + 1/600.*(60-qsize)))

    def run(self):
        streamer = livestreamer.Livestreamer()
        plugin = streamer.resolve_url('http://twitch.tv/twitchplayspokemon')
        streams = plugin.get_streams()
        self.stream = cv2.VideoCapture(streams['source'].url)
        thread.start_new_thread(self.grab_frames, ())
        thread.start_new_thread(self.process_frames, ())


if __name__ == '__main__':
    def handler_stdout(data):
        print '\x1B[H'
        print data['text']

    class LogHandler:
        def __init__(self, fname):
            self.fd = open(fname, 'a')

        def handle(self, data):
            self.fd.write(data['text'].replace('\n', '`') + '\n')

    identifier = SpriteIdentifier(preview='--show' in sys.argv)
    proc = StreamProcessor(identifier.stream_to_text)
    proc.add_handler(handler_stdout)
    proc.add_handler(LogHandler('frames.log').handle)
    proc.run()

    time.sleep(5)

    print '\x1b[2J'
    while True:
        time.sleep(1)  # loop until killed with ctrl-c
