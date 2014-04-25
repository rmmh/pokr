import difflib
import re
import numpy

class TimestampRecognizer(object):
    '''
    Extract play time from stream.
    '''

    # these represent number of set pixels in each column
    col_to_char = {
    'HHDCCCCCDHH':   '0',
    'CCKKJBB':       '1',
    'EEEEEEEDDEE':   '2',
    'CCDCDDDDEGG':   '3',
    'EEDDDDKKKBB':   '4',
    'GGEDDDDDEFF':   '5',
    'HHEDDDDDEEE':   '6',
    'BBBBFFHEEEE':   '7',
    'GGEDDDDDEGG':   '8',
    'EEEDDDDDEHH':   '9',
    'DDDCCCCCDII':   'd',
    'IIBBBBBBBEE':   'h',
    'FFBBFFFBBEE':   'm',
    'DDEDDDEDD':     's'
    }

    def __init__(self, debug=False):
        self.debug = debug
        self.timestamp = '0d0h0m0s'
        self.timestamp_s = 0

    def handle(self, data):
        x1, x2, y1, y2 = 970, 970+147, 48, 48 + 32
        timestamp = data['frame'][y1:y2, x1:x2]
        col_sum = (timestamp > 150).sum(axis=0)  # Sum bright pixels in each column
        col_str = (col_sum *.5 + ord('A')).astype(numpy.int8).tostring()  #
        strings = re.split(r'A*', col_str)  # Segment by black columns
        if self.debug:
            print(strings)
            import cv2
            cv2.imshow('timestamp', timestamp)
            cv2.waitKey(0)
        try:
            result = self.convert(strings)
            days, hours, minutes, seconds = map(int, re.split('[dhms]', result)[:-1])
            self.timestamp = result
            self.timestamp_s = ((days * 24 + hours) * 60 + minutes) * 60 + seconds
        except (ValueError, IndexError):
            pass    # invalid timestamp (ocr failed)
        finally:
            data['timestamp'] = self.timestamp
            data['timestamp_s'] = self.timestamp_s

    def convert(self, strings):
        col_to_char = self.col_to_char

        def match(x):
            if x in col_to_char:
                return col_to_char[x]
            close = difflib.get_close_matches(x, col_to_char, cutoff=.6)
            return col_to_char[close[0]]

        return ''.join(match(x) for x in strings if x)
