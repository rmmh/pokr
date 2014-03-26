#!/usr/bin/env python

# an example consumer of the pokr module, used by poke.ifies.com
import sys; sys.path += ['..']  # hack to let us import it as a module from the same directory

import json
import time

import pokr
import redis


r = redis.Redis()

class FilteredPrinter(object):
    def printer(self, data):
        if data['dithered_delta'] == '':
            return
        data.pop('frame')
        data.pop('screen')
        r.publish('pokemon.streams.frames', json.dumps(data))
        print data['timestamp'], '%5d'%len(data['dithered_delta'])

class DialogPusher(object):
    def handle(self, text, data):
        timestamp = data['timestamp']
        print timestamp, text
        r.publish('pokemon.streams.dialog', json.dumps({'time': timestamp, 'text': text}))

class TSD(object):
    def __init__(self):
        self.last = ''
        self.lasts = 0
    def timestamp_printer(self, data):
        ts = data['timestamp']
        tss = data['timestamp_s']
        if ts != self.last:
            self.last = ts
            if tss != self.lasts + 1:
                print 'wtf, discontinuity', '#' * 50
            self.lasts = tss
            print ts


box_reader = pokr.BoxReader()
box_reader.add_dialog_handler(DialogPusher().handle)

proc = pokr.StreamProcessor()
proc.add_handler(TSD().timestamp_printer)
#proc.add_handler(pokr.ScreenCompressor(fname='frames/frames.%y%m%d-%H%M.raw.gz').handle)
#proc.add_handler(pokr.StringDeltaCompressor('dithered').handle)
proc.add_handler(box_reader.handle)
#proc.add_handler(FilteredPrinter().printer)
#proc.add_handler(pokr.LogHandler('text', 'frames.log').handle)
proc.run()
