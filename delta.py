import itertools


class StringDeltaCompressor(object):
    '''
    Compress sequences of constant-length strings by encoding fragments that
     need to be replaced. The data is tab-separated:
        {skip_1}\t{str_1}\t{skip_2}\t{str_2}...
    Or, alternatively:
        {match_len}\t{mismatch_str}\t...
    Input cannot contain tabs.
    '''

    def __init__(self, key, minmatch=4, verify=False):
        self.key = key
        self.minmatch = minmatch
        self.last = ''
        self.verify = verify

    def handle(self, data):
        text = data[self.key]

        assert '\t' not in text
        assert len(text) >= len(self.last)

        if text == self.last:
            data[self.key + '_delta'] = ''
            return

        buf = ''
        in_match = True
        mismatch_begin = 0
        mismatch_emitted = False
        match_begin = 0
        offset = 0

        instructions = []

        def emit(offset, pos, leng):
            if leng == 0:
                return ''
            return '%d\t%s\t' % (pos - offset, text[pos:pos+leng])

        # find mismatches
        for n, (a, b) in enumerate(itertools.izip_longest(text, self.last, fillvalue=None)):
            if in_match:
                if a != b:
                    in_match = False
                    if n - match_begin >= self.minmatch:
                        buf += emit(offset, mismatch_begin, match_begin - mismatch_begin)
                        offset = match_begin
                        mismatch_begin = n
            else:
                if a == b:
                    in_match = True
                    match_begin = n

        # emit last match
        if not in_match:
            buf += emit(offset, mismatch_begin, n - mismatch_begin + 1)
        elif mismatch_begin < match_begin:
            buf += emit(offset, mismatch_begin, match_begin - mismatch_begin)

        buf = buf[:-1]  # strip trailing tab

        if self.verify:
            #print buf.replace('\t', '`').replace('\n','\\')
            assert self.decode(self.last, buf) == text
            try:
                assert len(buf) <= len(text) + 3
            except AssertionError:
                import os
                print repr((self.last, text))
                os._exit(0)

        self.last = text
        data[self.key + '_delta'] = buf

    def decode(self, prev, delta):
        if delta == '':
            return prev

        ins = delta.split('\t')
        data = prev
        pos = 0
        while ins:
            pos += int(ins.pop(0))
            fragment = ins.pop(0)
            data = data[:pos] + fragment + data[pos+len(fragment):]
            pos += len(fragment)

        return data

if __name__ == '__main__':
    comp = StringDeltaCompressor('d', verify=True)
    for a in ('abcde', 'bbcde'):
        comp.handle({'d':a})