import itertools
import re

def dist_merge(s1, s2):
    '''
    Calculate edit distance between two strings and what their
    'merged' value should be. This reduces errors when
    noise makes a character unrecognizable.
    '''
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
                        dist, merged = dist_merge(out[-1], line)
                        if dist < self.max_dist:
                            out[-1] = merged
                        else:
                            out.append(line)
                out = ' '.join(out).strip()
                out = re.sub(r'\s+', ' ', out)
                out = re.sub(r'- ', '', out)
                for handler in self.dialog_handlers:
                    handler(out, data)
                self.lastgroup = self.group
                self.group = []
            self.last = text
            return
        text = text.replace(' ' * 18 + '\n', '')
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

        if len(lines) >= 1 and lines[0][0] == 121:
            self.handle_dialog(data, '\n'.join(text for y, text in lines))
        else:
            self.handle_dialog(data, '')
