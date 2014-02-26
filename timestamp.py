import difflib
import re
import numpy

class TimestampRecognizer(object):
    # these represent number of set pixels in each column
    col_to_char = {
       'DGGEEDEJGDD': '0',
       'BBDJJJJBBB': '1',
       'EHHGGEGHGEE': '2',
       'BEEEEEGJHEE': '3',
       'DEEEGEJJJBB': '4',
       'GHHEEEEHHDD': '5',
       'GJJEEEEHHDD': '6',
       'DDDEGGEGEDD': '7',
       'EJJEEEEJJEE': '8',
       'DHHEEEEJJGG': '9',
       'DDDDDDDDKK': 'd',
       'KKBBBBGE': 'h',
       'HHBBHGBBBGG': 'm',
       'DDEEEEEEBB': 's'
    }

    def __init__(self):
        self.last = '0d0h0m0s'

    def handle(self, data):
        x1, x2, y1, y2 = 232, 231+147, 9, 9 + 25
        timestamp = data['frame'][y1:y2, x1:x2]
        col_sum = (timestamp > 150).sum(axis=0)
        col_str = (col_sum *.5 + ord('A')).astype(numpy.int8).tostring()
        strings = re.split(r'A*', col_str)
        try:
            self.last = self.convert(strings)
        except IndexError:
            pass # no close match
        finally:
            days, hours, minutes, seconds = map(int, re.split('[dhms]', self.last)[:-1])
            data['timestamp'] = self.last
            data['timestamp_s'] = ((days * 24 + hours) * 60 + minutes) * 60 + seconds

    def convert(self, strings):
        col_to_char = self.col_to_char

        def match(x):
            if x in col_to_char:
                return col_to_char[x]
            close = difflib.get_close_matches(x, col_to_char, cutoff=.6)
            return col_to_char[close[0]]

        return ''.join(match(x) for x in strings if x)
