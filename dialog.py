import itertools
import re

def dist_merge(s1, s2):
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
    COORD_DIALOG = (0, 12, 19, 17)
    banned_phrases = (
        'SAVE   \n',

    )

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

    def handle_dialog(self, text, lines, timestamp):
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
                    handler(out, lines, timestamp)
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

        lines = data['full']
        lines = [map(conv_tile_or_text, lines[20 * i : 20 * i + 20]) for i in range(18)]
        timestamp = data['timestamp']
        boxes = []

        for box_y in range(18):
            for box_x in range(20):
                if lines[box_y][box_x] == 'o':
                    # might be a dialog box, trace

                    top_x = box_x + 1
                    while top_x < 20 and lines[box_y][top_x] == '-':
                        top_x += 1
                    if top_x == 20 or lines[box_y][top_x] != 'o':
                        break
                    left_y = box_y + 1
                    while left_y < 18 and lines[left_y][box_x] == '|' and lines[left_y][top_x] == '|':
                        left_y += 1
                    if left_y == 18 or lines[left_y][box_x] != 'o' or lines[left_y][top_x] != 'o':
                        break

                    box = ''
                    for y in xrange(box_y + 1, left_y):
                        for x in xrange(box_x + 1, top_x):
                            box += lines[y][x]
                        box += '\n'
                    boxes.append(((box_x, box_y, top_x, left_y), box))
        for coord, box in boxes:
            if coord == self.COORD_DIALOG:
                self.handle_dialog(box, lines, timestamp)
                break
            else:
                continue
                for banned_phrase in self.banned_phrases:
                    if banned_phrase in box:
                        break
                else:
                    print '%2d %2d %2d %2d' % coord, box.replace('\n', '`')
        else:
            self.handle_dialog('', lines, timestamp)

class BattleState(object):
    re_wild = re.compile(r'Wild (.*) appeared')
    re_trainer = re.compile(r'(.*) wants to fight')
    re_enemy_faint = re.compile(r'Enemy .* fainted')
    re_opponent_level = re.compile(r'@(\d\d)')

    banned_phrases = ('Choose a POKeMON', 'already out', 'Come back', 'OAK:',
            'which POKeMON', 'will to fight', 'catchy tune', 'about to use', 'change POKeMON',
            'no running from', 'Thats too impor')

    STATE_NORMAL = 0
    STATE_WILD_BEATEN = 1

    def __init__(self, start_text, timestamp):
        self.last_hp = (0, 0, 0)
        m_wild = self.re_wild.match(start_text)
        m_trainer = self.re_trainer.match(start_text)
        self.trainer_battle = m_trainer is not None
        if m_trainer:
            self.opponent = m_trainer.group(1)
        else:
            self.opponent = m_wild.group(1)
        self.start_time = timestamp
        self.lines = [(timestamp, start_text)]
        self.state = self.STATE_NORMAL
        self.opponent_level = 0

    def read_hp(self, lines):
        my_hp_bar = ''.join(lines[10][11:18]).split('/')
        my_hp_cur, my_hp_tot = int(my_hp_bar[0]), int(my_hp_bar[1])
        enemy_hp_bar = ''.join(lines[2][2:10])
        if not re.match(r'HPP:([_=1-7]H)*', enemy_hp_bar):
            raise ValueError
        enemy_hp_perc = int(sum(0 if c == '_' else 8 if c == '=' else int(c) for c in enemy_hp_bar[4::2])*100/48.)
        return my_hp_cur, my_hp_tot, enemy_hp_perc

    def read_enemy_level(self, lines):
        try:
            opp_level = lines[1][6:9]
            if opp_level[0] == 'Lv':
                return int(opp_level[1]+opp_level[2])
            return 0
        except ValueError:
            return 0

    def feed(self, text, lines, timestamp):
        if self.state == self.STATE_WILD_BEATEN:
            # our opponent has fainted, but we might have EXP gain lines
            if 'EXP' not in text:
                return True

        text = self.annotate(text, lines)

        for banned in self.banned_phrases:
            if banned in text:
                break
        else:
            self.lines.append((timestamp, text))

        if 'blacked out' in text:
            return True
        if self.trainer_battle:
            if 'for winning' in text:
                return True
        else:
            if 'was caught' in text or 'away' in text:
                return True
            if self.re_enemy_faint.search(text):
                self.state = self.STATE_WILD_BEATEN

    def annotate(self, text, lines):
        if self.re_wild.match(text) or self.re_trainer.match(text):
            self.opponent_level = 0

        if 'sent out' in text:
            level = self.read_enemy_level(lines)
            if level:
                text = re.sub(r'( \S*!)$', r' L%02d\1' % level, text)

        if self.opponent_level == 0:
            self.opponent_level = self.read_enemy_level(lines)
            if self.opponent_level:
                text += ' EnLvl:%d' % self.opponent_level

        try:
            hp = self.read_hp(lines)
        except (ValueError, IndexError):
            hp = self.last_hp

        ext = ''
        if hp != self.last_hp:
            if hp[2] != self.last_hp[2]:
                ext += ' En: %d%% (%d%%)' % (hp[2], hp[2]-self.last_hp[2])
            if hp[0] != self.last_hp[0] and hp[1] == self.last_hp[1]:
                ext += ' Us: %d/%d (%d)' % (hp[0], hp[1], hp[0]-self.last_hp[0])
            self.last_hp = hp
        return text + ext

    def __str__(self):
        out = ''
        if self.trainer_battle:
            out += 'Trainer battle with %s at %s\n' % (self.opponent, self.start_time)
        else:
            out += 'Wild encounter with L%02d %s at %s\n' % (
                self.opponent_level, self.opponent, self.start_time)
        for timestamp, text in self.lines[1:]:
            out += '   %-14s %s\n' % (timestamp, text)
        return out

class BattleTracker(object):
    def __init__(self):
        self.battle = None
        self.battles = []

    def handle_text(self, text, lines, timestamp):
        if self.battle:
            if self.battle.feed(text, lines, timestamp):
                self.battles.append(self.battle)
                self.battle = None
        if 'wants to fight' in text or 'appeared!' in text:
            if self.battle:
                self.battles.append(self.battle)
            self.battle = BattleState(text, timestamp)

    def finalize(self):
        for battle in self.battles[::-1]:
            print battle
            print '\n\n'

if __name__ == '__main__':
    import sys

    reader = BoxReader()
    tracker = BattleTracker()
    reader.add_dialog_handler(tracker.handle_text)
    logs = open(sys.argv[1] if len(sys.argv) > 1 else 'frames.log')
    for line in logs:
        line = line.replace('`', '\n')
        line = line[:line.rindex('\n')]
        if len(line) < 18 * 21:
            # line too short generally means we've hit EOF
            continue
        try:
            data = {'text': line[:line.rindex('\n')+1], 'timestamp': line[line.rindex('\n')+1:]}
            reader.handle(data)
        except IndexError, e:
            print e
            print line
    tracker.finalize()
