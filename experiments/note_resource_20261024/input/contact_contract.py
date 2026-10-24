from dataclasses import dataclass


@dataclass(frozen=True)
class ContactEvent:
    on: bool
    token: int
    contact: int
    generation: int
    note: int
    velocity: int
    glide: int
    layers: int


@dataclass(frozen=True)
class ContactCancellation:
    token: int


@dataclass(frozen=True)
class ContactReply:
    event: ContactEvent
    code: int
    groups: int
    layers: int
    mapping: int


class ContactLedger:
    def __init__(self, source=0, contacts=26, serial_bits=31, initial_serial=0):
        if source not in (0, 1) or not 1 <= contacts <= 32 or not 1 <= serial_bits <= 31:
            raise ValueError('Invalid logical source capacity')
        if not 0 <= initial_serial < 1 << serial_bits:
            raise ValueError('Invalid initial serial')
        self.source = source
        self.capacity = contacts
        self.serial_bits = serial_bits
        self.initial_serial = initial_serial
        self.reset()

    def reset(self):
        self.rows = {}
        self.pending = None
        self.cancelled = False
        self.next_serial = self.initial_serial
        self.issued = 0

    def press(self, contact, generation, note, velocity, glide, layers):
        if self.pending is not None:
            raise RuntimeError('Complete the outstanding source transaction first')
        if not (0 <= contact < self.capacity and 0 <= generation < 256 and 0 <= note < 128
                and 0 <= velocity < 256 and -(1 << 17) <= glide < 1 << 17 and 0 < layers < 16):
            raise ValueError('Invalid contact payload')
        if contact in self.rows and self.rows[contact]['held']:
            raise RuntimeError('A held contact cannot retrigger, including after retirement')
        if self.issued == 1 << self.serial_bits:
            raise RuntimeError('Serial epoch exhausted; common reset fence required')
        token = self.source << 31 | self.next_serial
        self.next_serial = (self.next_serial+1) % (1 << self.serial_bits)
        self.issued += 1
        event = ContactEvent(True, token, contact, generation, note, velocity, glide, layers)
        self.rows[contact] = dict(token=token, generation=generation, held=True,
                                  groups=0, layers=0, mapping=0, note=note, position=None)
        self.pending = event
        return event

    def row_for_token(self, token):
        return next((row for row in self.rows.values() if row['token'] == token), None)

    def release(self, token):
        row = self.row_for_token(token)
        if row is None or not row['held']:
            return None
        if self.pending is not None and (self.pending.token != token or not self.pending.on):
            raise RuntimeError('Another source transaction is outstanding')
        row['held'] = False
        if self.pending is not None:
            self.cancelled = True
            return ContactCancellation(token)
        contact = next(index for index, candidate in self.rows.items() if candidate is row)
        self.pending = ContactEvent(False, token, contact, row['generation'], row['note'], 0, 0, 0)
        return self.pending

    @staticmethod
    def validate_allocation(groups, layers, mapping, expected_layers):
        if not (0 < groups < 1 << 32 and layers == expected_layers and 0 < layers < 16
                and 0 <= mapping < 1 << 20):
            raise ValueError('Incomplete allocation metadata')
        selected = [(mapping >> (5*layer)) & 31 for layer in range(4) if layers >> layer & 1]
        if len(set(selected)) != len(selected) or sum(1 << group for group in selected) != groups:
            raise ValueError('Layer map does not identify all distinct allocated groups')

    def complete(self, token, code, groups=0, layers=0, mapping=0):
        event = self.pending
        if event is None or token != event.token:
            raise ValueError('Unsolicited or stale completion')
        if code not in ((0, 3, 4, 5, 6) if event.on else (1, 3, 4)):
            raise ValueError('Unexpected completion kind')
        if event.on and code == 0:
            if self.cancelled:
                raise ValueError('Cancelled admission must not consume ALLOCATED')
            self.validate_allocation(groups, layers, mapping, event.layers)
            self.rows[event.contact].update(groups=groups, layers=layers, mapping=mapping)
        elif event.on:
            self.rows[event.contact].update(groups=0, layers=0, mapping=0)
        reply = ContactReply(event, code, groups, layers, mapping)
        self.pending = None
        self.cancelled = False
        return reply

    def retire(self, token):
        row = self.row_for_token(token)
        if row is not None:
            row.update(groups=0, layers=0, mapping=0)

    def natural_end(self, token, groups):
        row = self.row_for_token(token)
        if row is None:
            return
        if groups == 0 or groups & ~row['groups']:
            raise ValueError('Invalid natural-completion mask')
        row['groups'] &= ~groups
        for layer in range(4):
            if row['layers'] >> layer & 1 and groups >> ((row['mapping'] >> (5*layer)) & 31) & 1:
                row['layers'] &= ~(1 << layer)

    def move(self, token, position):
        row = self.row_for_token(token)
        if row is None or not row['held'] or row['groups'] == 0:
            return None
        row['position'] = position
        return dict(token=token, groups=row['groups'], layers=row['layers'], position=position)
