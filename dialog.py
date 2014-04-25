import itertools
import re

def is_subsequence(a, b):
    b_pos = 0
    try:  # http://stackoverflow.com/a/3673735/3694
        for char in a:
            if char == ' ':
                continue
            b_pos = b.index(char, b_pos) + 1
        return True
    except ValueError:
        return False

def dist_merge(s1, s2):
    '''
    Calculate edit distance between two strings and what their
    'merged' value should be. This reduces errors when
    noise makes a character unrecognizable.
    '''
    if is_subsequence(s1, s2):
        return 0, s2

    #print 'dist_merge', repr(s1), `s2`
    s2_pos = 0
    for c in s1:
        if c == ' ':
            continue
    dist = 0
    out = ''
    for a, b in itertools.izip_longest(s1, s2, fillvalue=' '):
        if a != ' ' and a != b:
            dist += 1
        if b != ' ':
            out += b
        else:
            out += a
    return dist, out


class BoxReader(object):
    '''Find each dialog box in the text version of the screen'''

    def __init__(self, max_dist=3):
        self.last = ''
        self.lastline = ''
        self.group = []
        self.lastgroup = []
        self.dialog_handlers = []
        self.max_dist = max_dist
        self.continued = 0
        self.last_lines = None
        self.out = open('dialog_raw.txt', 'a')

    def add_dialog_handler(self, handler):
        self.dialog_handlers.append(handler)

    def handle_dialog(self, data, text):
        #print 'handle_dialog', repr(text), self.continued

        if text == '':  # dialog disappeared
            if self.last:
                self.group.append(self.last)
            if self.group and self.lastgroup and self.group[0] == self.lastgroup[-1]:
                # some screen effects make us lose the dialog temporarily
                # prevent duplicate lines this way
                self.group = []
            if self.group:
                out = ['']
                for el in self.group:
                    for line in el.splitlines():
                        if not line:
                            continue
                        if 'FIGHT BAG' in line:
                            continue
                        if 'POKEMON RUN' in line:
                            continue
                        dist, merged = dist_merge(out[-1], line)
                        if dist < self.max_dist:
                            out[-1] = merged
                        else:
                            out.append(line)
                out = ' '.join(out).strip()
                out = re.sub(r'\s+', ' ', out)
                out = re.sub(r'- ', '', out)
                if out.strip():
                    for handler in self.dialog_handlers:
                        handler(out, data)
                self.lastgroup = self.group
                self.group = []
            self.last = text
            return
        if text.strip() in ('', self.last.strip()):
            return
        dist, merged = dist_merge(self.last, text)
        if dist < self.max_dist:
            self.last = merged
        else:
            #print self.last.replace('\n', '`'), '--', text.replace('\n', '`')
            if self.last != self.lastline:
                self.group.append(self.last)
                self.last = text

    def handle(self, data):
        def conv_tile_or_text(t):
            if isinstance(t, int):
                return ' '
            if len(t) == 1:
                return t
            return t[1:]

        lines = data['text']

        if lines != self.last_lines:
            if lines:
                self.out.write(data['timestamp'] + ' ' + str(lines) + '\n')
            self.last_lines = lines

        texts = []
        lines = [ x for x in lines if len(x[3]) > 1 ]

        if len(lines) >= 1 and lines[0][0] in (120, 121) and lines[0][1] < 39:
            texts = [ x[3] for x in lines ]

        self.handle_dialog(data, '\n'.join(texts) if len(texts) >= 1 else '')
