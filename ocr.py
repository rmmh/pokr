#!/usr/bin/env python

import sys
import time 
import thread
import Queue

import cv2
import numpy

preview = '--show' in sys.argv

if preview:
    cv2.namedWindow("Stream", cv2.WINDOW_AUTOSIZE)
    cv2.namedWindow("Game", cv2.WINDOW_AUTOSIZE)

class SpriteIdentifier(object):
    def __init__(self):
        tiles = cv2.cvtColor(cv2.imread("red_tiles.png"), cv2.COLOR_BGR2GRAY) < 128
        #tiles.show()
        tile_text = '''
ABCDEFGHIJKLMNOP
QRSTUVWXYZ():;[]
abcdefghijklmnop
qrstuvwxyzedlstv


'PM-  ?!.   }>
$*./, 0123456789
|_:*





  %01234567= |@
   |# _# #_#|##
        '''.strip()

        self.tile_map = {}

        for y, line in enumerate(tile_text.splitlines()):
            for x, char in enumerate(line):
                sprite = self.sprite_to_int(tiles, x, y)
                if char == ' ' or sprite == 0:
                    continue
                self.tile_map[sprite] = char

    def sprite_to_int(self, image, left, top):
        bits = (image[top*8:top*8+8, left*8:left*8+8]).flat
        out = 0
        for n,bit in enumerate(bits):
            if bit: 
                out |= 1<<(63-n)
        return out

    def screen_to_text(self, screen):
        if preview:
            cv2.imshow("Game", screen)
            cv2.waitKey(1)
        screen = screen < 128
        out = ''
        for y in range(18):
            for x in range(20):
                out += self.tile_map.get(self.sprite_to_int(screen, x, y), ' ')
            out += '\n'
        return out

identifier = SpriteIdentifier()

def extract_screen(raw):
    screen_x, screen_y = 8, 41
    screen = raw[screen_y:screen_y+432, screen_x:screen_x+480]
    screen = cv2.resize(screen, (160, 144))
    return screen

def test_corpus():
    import os
    for fn in os.listdir('corpus'):
        print '#' * 20 + ' ' + fn
        print
        print identifier.screen_to_text(extract_screen(cv2.cvtColor(cv2.imread('corpus/' + fn), cv2.COLOR_BGR2GRAY)))

#test_corpus()


cv = cv2.VideoCapture('/dev/stdin')

frame_queue = Queue.Queue(120)

def grab_frames():
    while True:
        cv.grab()
        success, frame = cv.retrieve()
        if success:
            try:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                frame_queue.put(frame, block=False, timeout=1.)
            except Queue.Full:
                continue

def process_frames():
    print '\x1b[2J'
    last_text = ''
    cur = time.time()
    while True:
        prev = cur
        cur = time.time()
        frame = frame_queue.get()
        if preview:
            cv2.imshow('Stream', frame)
        screen = extract_screen(frame)
        text = identifier.screen_to_text(screen)
        if text != last_text:
            print '\x1B[H'
            print text
            last_text = text
        qsize = frame_queue.qsize()
        #print '%s     ' % qsize
        if qsize < 60:
            time.sleep(max(0, 1/60. - (cur - prev) + 1/600.*(60-qsize)))

thread.start_new_thread(grab_frames, ())
thread.start_new_thread(process_frames, ())

while True:
    time.sleep(1)
