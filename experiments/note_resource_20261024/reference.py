import random


class ResourceModel:
    def __init__(self, ticket_width=3):
        self.notes = {}
        self.serials = [None, None]
        self.ticket = 0
        self.ticket_mask = (1 << ticket_width) - 1
        self.protocol_error = 0

    def used(self):
        return sum(note['groups'] for note in self.notes.values())

    def snapshot(self):
        return [self.used(), 0, len(self.notes), self.protocol_error], [
            [token, note['groups'], note['layers'], note['mapping'], int(note['released'])]
            for token, note in self.notes.items()]

    def apply(self, command):
        kind, token, layers, groups = (command[name] for name in ('kind', 'token', 'layers', 'groups'))
        cancel = command.get('cancel', 0)
        works = []
        response = [3, token, 0, 0, 0]

        def work(operation, key, note):
            works.append([operation, self.ticket, key, note['groups'], note['layers'], note['mapping']])
            self.ticket = (self.ticket + 1) & self.ticket_mask

        def finish():
            if works and command.get('wrong_ack', 0):
                self.protocol_error = 1
            snapshot, entries = self.snapshot()
            return dict(works=works, response=response, snapshot=snapshot, entries=entries)

        if kind == 3 or kind == 0 and layers == 0:
            response[0] = 4
            return finish()
        note = self.notes.get(token)
        if kind == 0:
            if note is not None:
                response = [5, token, note['groups'], note['layers'], note['mapping']]
                return finish()
            source, serial = token >> 31, token & 0x7fffffff
            previous = self.serials[source]
            delta = (serial - previous) & 0x7fffffff if previous is not None else 1
            if delta == 0 or delta >= 0x40000000:
                return finish()
            self.serials[source] = serial
            response[0] = 6
            if cancel in (1, 6):
                return finish()
            needed = layers.bit_count() if hasattr(int, 'bit_count') else bin(layers).count('1')
            while 32 - bin(self.used()).count('1') < needed or len(self.notes) == 32:
                victim = next((key for key, value in self.notes.items() if value['released']), next(iter(self.notes)))
                work(1, victim, self.notes[victim])
                del self.notes[victim]
                if cancel == 2:
                    return finish()
            free = iter(group for group in range(32) if not self.used() >> group & 1)
            mapping, mask = 0, 0
            for layer in range(4):
                if layers >> layer & 1:
                    group = next(free)
                    mapping |= group << (layer * 5)
                    mask |= 1 << group
            note = dict(groups=mask, layers=layers, mapping=mapping, released=False)
            work(2, token, note)
            if cancel == 3:
                work(1, token, note)
                return finish()
            work(3, token, note)
            if cancel in (4, 5):
                work(1, token, note)
                return finish()
            self.notes[token] = note
            response = [0, token, mask, layers, mapping]
        elif note is not None and kind == 1:
            if not note['released']:
                work(0, token, note)
            note['released'] = True
            response = [1, token, note['groups'], note['layers'], note['mapping']]
        elif note is not None and kind == 2:
            if groups == 0:
                response[0] = 4
            elif groups & note['groups'] == 0:
                pass
            elif groups & ~note['groups']:
                response[0] = 4
            else:
                note['groups'] &= ~groups
                for layer in range(4):
                    if note['layers'] >> layer & 1 and groups >> ((note['mapping'] >> (layer * 5)) & 31) & 1:
                        note['layers'] &= ~(1 << layer)
                response = [2, token, groups, note['layers'], note['mapping']]
                if note['groups'] == 0:
                    del self.notes[token]
        return finish()


def scenarios(seed=20261024, random_count=700):
    generator = random.Random(seed)
    model = ResourceModel()
    counters = [0x7ffffff4, 0x7ffffff6]
    commands, expected, issued = [], [], []

    def push(kind, token, layers=0, groups=0, cancel=0, label=''):
        command = dict(kind=kind, token=token, layers=layers, groups=groups, cancel=cancel,
                       ready_delay=generator.randrange(4), done_delay=generator.randrange(1, 5),
                       response_delay=generator.randrange(2, 6), wrong_ack=(1+len(commands)//7%3) if len(commands)%7==0 else 0, label=label)
        commands.append(command)
        expected.append(model.apply(command))
        return token

    def note(layers=1, cancel=0, source=None, label=''):
        source = len(issued) % 2 if source is None else source
        token = source << 31 | counters[source]
        counters[source] = (counters[source] + 1) & 0x7fffffff
        issued.append(token)
        return push(0, token, layers=layers, cancel=cancel, label=label)

    def drain():
        for token, value in list(model.notes.items()):
            push(2, token, groups=value['groups'], label='natural-complete')

    def fill():
        while bin(model.used()).count('1') < 32:
            note(label='fill-shared-pool')

    push(0, 0, label='invalid-zero-layers')
    push(3, 0, label='invalid-operation')
    first = [note(mask, label='one-to-four-layers') for mask in (1, 3, 7, 15)]
    push(0, first[0], layers=15, label='duplicate-live-on')
    push(1, first[1], label='off-retains-tail-resources')
    push(1, first[1], label='duplicate-off')
    partial = model.notes[first[2]]['groups'] & -model.notes[first[2]]['groups']
    push(2, first[2], groups=partial, label='partial-natural-completion')
    push(2, first[2], groups=0, label='invalid-empty-completion')
    push(2, first[2], groups=partial, label='stale-completion')
    drain()
    push(0, first[0], layers=1, label='retired-on-replay')
    fill()
    for token in list(model.notes)[-2:]:
        push(1, token, label='young-released-tails')
    note(15, label='tails-before-old-held-and-multiple-victims')
    for mask in (1, 3, 7, 15):
        fill()
        note(mask, label='full-pool-one-to-four-layers')
    for cancel in (1, 2, 3, 4, 5, 6):
        fill()
        note(15, cancel=cancel, label='cancel-stage-' + str(cancel))
    push(1, first[0], label='late-off-no-replacement-kill')
    push(2, first[0], groups=0xffffffff, label='late-finish-no-replacement-kill')
    drain()
    anchor = note(label='long-held-order-anchor')
    for iteration in range(400):
        token = note(label='ticket-and-source-serial-wrap')
        push(1, token, label='off-tail-not-free')
        push(2, token, groups=model.notes[token]['groups'], label='natural-finish')
    fill()
    note(15, label='oldest-anchor-after-many-ticket-wraps')
    assert anchor not in model.notes
    for iteration in range(random_count):
        choice = generator.random()
        active = list(model.notes)
        if choice < .48:
            note(generator.randrange(1, 16), cancel=generator.choice([0, 0, 0, 0, 1, 2, 3, 4, 5, 6]), label='random-on')
        elif choice < .67 and active:
            push(1, generator.choice(active), label='random-off')
        elif choice < .87 and active:
            token = generator.choice(active)
            mask = model.notes[token]['groups']
            groups = mask if generator.randrange(2) else mask & -mask
            push(2, token, groups=groups, label='random-natural-finish')
        elif issued:
            token = generator.choice(issued)
            push(generator.randrange(3), token, layers=generator.randrange(1, 16), groups=0x80000000, label='random-repeat-or-stale')
    drain()
    return commands, expected
