#!/usr/bin/env python

import sys

from PIL import Image
import numpy
import cv2

class SpriteIdentifier(object):
    def __init__(self):
        tiles = Image.open("red_tiles.png").convert('1', dither=Image.NONE)
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
        if isinstance(image, numpy.ndarray):
            bits = (image[top*8:top*8+8, left*8:left*8+8]).flat
            out = 0
            for n,bit in enumerate(bits):
                if bit: 
                    out |= 1<<(63-n)
            return out

        top *= 8
        left *= 8
        out = 0
        for y in range(top, top+8):
            for x in range(left, left+8):
                out <<= 1
                p = image.getpixel((x, y))
                if p in (0, (0, 0, 0)):
                    out |= 1
        return out

    def screen_to_text(self, screen):
        out = ''
        for y in range(18):
            for x in range(20):
                out += self.tile_map.get(self.sprite_to_int(screen, x, y), ' ')
            out += '\n'
        return out

identifier = SpriteIdentifier()


def extract_screen(raw):
    screen_x, screen_y = 8, 41
    screen = raw.crop((screen_x, screen_y, screen_x + 480, screen_y + 432))
    screen = screen.resize((160, 144)).convert('1', dither=Image.NONE)
    return screen

def extract_screen_from_array(raw):
    screen_x, screen_y = 8, 41
    screen = raw[screen_y:screen_y+432, screen_x:screen_x+480]
    screen = cv2.resize(screen, (160, 144))
    return screen

def test_corpus():
    import os
    for fn in os.listdir('corpus'):
        print '#' * 20 + ' ' + fn
        print
        print identifier.screen_to_text(extract_screen(Image.open('corpus/' + fn)))

#test_corpus()

import time 
cv = cv2.VideoCapture('/dev/stdin')
print '\x1b[2J'
last_text = ''
n = 0
start = time.time()
while True:
    n += 1
    cv.grab()
    success, frame = cv.retrieve()
    screen2 = extract_screen_from_array(frame)
    #Image.fromarray(screen2).show()
    text = identifier.screen_to_text(cv2.cvtColor(screen2, cv2.COLOR_BGR2GRAY) < 128)
    if text != last_text:
        print '\x1B[H'
        #print n, n/(time.time()-start)
        print text
    last_text = text