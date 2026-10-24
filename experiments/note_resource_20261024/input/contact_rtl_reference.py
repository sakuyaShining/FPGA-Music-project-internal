import random

from contact_contract import ContactLedger


INPUTS = [
    ('rst_n', 1), ('on_valid', 1), ('on_contact', 5), ('on_generation', 8),
    ('on_note', 7), ('on_velocity', 8), ('on_glide', 18), ('on_layers', 4),
    ('release_valid', 1), ('release_token', 32), ('move_valid', 1), ('move_token', 32),
    ('move_position', 12), ('retire_valid', 1), ('retire_token', 32),
    ('finish_valid', 1), ('finish_token', 32), ('finish_groups', 32), ('event_ready', 1),
    ('response_valid', 1), ('response_token', 32), ('response_code', 3),
    ('response_groups', 32), ('response_layers', 4), ('response_map', 20),
    ('reply_ready', 1), ('query_contact', 5),
]
OUTPUTS = [
    ('on_ready', 1), ('release_ready', 1), ('event_valid', 1), ('event_on', 1),
    ('event_serial', 31), ('event_token', 32), ('event_note', 7), ('event_velocity', 8),
    ('event_glide', 18), ('event_layers', 4), ('cancel_valid', 1), ('cancel_token', 32),
    ('response_ready', 1), ('reply_valid', 1), ('reply_on', 1), ('reply_token', 32),
    ('reply_groups', 32), ('reply_code', 3), ('reply_layers', 4), ('reply_map', 20),
    ('reply_contact', 5), ('reply_generation', 8), ('expression_valid', 1),
    ('expression_token', 32), ('expression_groups', 32), ('expression_layers', 4),
    ('expression_position', 12), ('query_held', 1), ('query_token', 32),
    ('query_groups', 32), ('query_layers', 4), ('query_map', 20),
    ('epoch_exhausted', 1), ('protocol_error', 1),
]


def pack(fields, values):
    result = 0
    for name, width in fields:
        result = result << width | (int(values.get(name, 0)) & ((1 << width)-1))
    return result


def unpack(fields, value):
    result = {}
    for name, width in reversed(fields):
        result[name] = value & ((1 << width)-1)
        value >>= width
    return result


class Adapter:
    def __init__(self, source=0, serial_bits=31, initial_serial=0):
        self.ledger = ContactLedger(source=source, serial_bits=serial_bits, initial_serial=initial_serial)
        self.reset()

    def reset(self):
        self.ledger.reset()
        self.phase = 'idle'
        self.event = None
        self.reply = None
        self.reply_register = {}
        self.error = False

    def evaluate(self, inputs):
        ledger = self.ledger
        event = self.event
        outputs = dict.fromkeys((name for name, width in OUTPUTS), 0)
        outputs.update(self.reply_register)
        outputs.update(reply_valid=self.reply is not None, protocol_error=self.error,
                       epoch_exhausted=ledger.issued == 1 << ledger.serial_bits)
        if event is not None:
            outputs.update(event_on=event.on, event_serial=event.token & 0x7fffffff,
                event_token=event.token, event_note=event.note, event_velocity=event.velocity,
                event_glide=event.glide, event_layers=event.layers, cancel_token=event.token)
        free = self.reply is None or inputs['reply_ready']
        pending_release = self.phase != 'idle' and event.on and inputs['release_token'] == event.token
        outputs['release_ready'] = inputs['rst_n'] and (self.phase == 'idle' and free or pending_release)
        cancel_now = outputs['release_ready'] and inputs['release_valid'] and pending_release
        row = ledger.rows.get(inputs['on_contact'])
        outputs['on_ready'] = inputs['rst_n'] and self.phase == 'idle' and free and not inputs['release_valid'] and not outputs['epoch_exhausted'] and inputs['on_contact'] < ledger.capacity and not (row and row['held']) and inputs['on_layers'] != 0
        outputs['event_valid'] = inputs['rst_n'] and self.phase == 'send'
        outputs['cancel_valid'] = inputs['rst_n'] and self.phase != 'idle' and event.on and (ledger.cancelled or cancel_now)
        valid_code = event is not None and inputs['response_code'] in ((0, 3, 4, 5, 6) if event.on else (1, 3, 4))
        allocated = True
        if event is not None and inputs['response_code'] == 0:
            try:
                ledger.validate_allocation(inputs['response_groups'], inputs['response_layers'], inputs['response_map'], event.layers)
            except ValueError:
                allocated = False
        matched = self.phase == 'wait' and inputs['response_token'] == event.token
        outputs['response_ready'] = inputs['rst_n'] and matched and free and valid_code and (inputs['response_code'] != 0 or allocated and not ledger.cancelled and not cancel_now)
        outputs['_bad_response'] = inputs['response_valid'] and (not matched or not valid_code or inputs['response_code'] == 0 and not allocated)
        moving = ledger.row_for_token(inputs['move_token'])
        motion = ledger.move(inputs['move_token'], inputs['move_position'])
        if motion:
            groups, layers = motion['groups'], motion['layers']
            completed = inputs['finish_groups'] if inputs['finish_valid'] and inputs['finish_token'] == inputs['move_token'] and not inputs['finish_groups'] & ~groups else 0
            groups &= ~completed
            for layer in range(4):
                if layers >> layer & 1 and completed >> ((moving['mapping'] >> (5*layer)) & 31) & 1:
                    layers &= ~(1 << layer)
            outputs.update(expression_groups=groups, expression_layers=layers)
            outputs['expression_valid'] = inputs['rst_n'] and inputs['move_valid'] and groups != 0 and not (inputs['retire_valid'] and inputs['retire_token'] == inputs['move_token']) and not (outputs['release_ready'] and inputs['release_valid'] and inputs['release_token'] == inputs['move_token'])
        outputs.update(expression_token=inputs['move_token'], expression_position=inputs['move_position'])
        row = ledger.rows.get(inputs['query_contact'])
        if row:
            outputs.update(query_held=row['held'], query_token=row['token'], query_groups=row['groups'], query_layers=row['layers'], query_map=row['mapping'])
        return outputs

    def step(self, inputs):
        if not inputs['rst_n']:
            self.reset()
        before = self.evaluate(inputs)
        if not inputs['rst_n']:
            return before
        if before['_bad_response']:
            self.error = True
        if self.reply and inputs['reply_ready']:
            self.reply = None
        prior_phase = self.phase
        new_contact = None
        if inputs['release_valid'] and before['release_ready']:
            released = self.ledger.release(inputs['release_token'])
            if prior_phase == 'idle' and released is not None:
                self.event = released
                self.phase = 'send'
        elif inputs['on_valid'] and before['on_ready']:
            glide = inputs['on_glide'] & ((1 << 18)-1)
            glide = glide-(1 << 18) if glide & (1 << 17) else glide
            self.event = self.ledger.press(inputs['on_contact'], inputs['on_generation'], inputs['on_note'], inputs['on_velocity'], glide, inputs['on_layers'])
            self.phase = 'send'
            new_contact = inputs['on_contact']
        if prior_phase == 'send' and inputs['event_ready']:
            self.phase = 'wait'
        elif prior_phase == 'wait' and inputs['response_valid'] and before['response_ready']:
            self.reply = self.ledger.complete(inputs['response_token'], inputs['response_code'], inputs['response_groups'], inputs['response_layers'], inputs['response_map'])
            self.reply_register = dict(reply_on=self.reply.event.on, reply_token=self.reply.event.token,
                reply_groups=self.reply.groups, reply_code=self.reply.code, reply_layers=self.reply.layers,
                reply_map=self.reply.mapping, reply_contact=self.reply.event.contact, reply_generation=self.reply.event.generation)
            self.phase = 'idle'
        retired = set()
        if inputs['retire_valid']:
            row = self.ledger.row_for_token(inputs['retire_token'])
            if row is not None and row is not self.ledger.rows.get(new_contact):
                self.ledger.retire(inputs['retire_token'])
                retired.add(inputs['retire_token'])
        if inputs['finish_valid'] and inputs['finish_token'] not in retired:
            row = self.ledger.row_for_token(inputs['finish_token'])
            if row is not None and row is not self.ledger.rows.get(new_contact):
                try:
                    self.ledger.natural_end(inputs['finish_token'], inputs['finish_groups'])
                except ValueError:
                    self.error = True
        return before


def generate(source=0, serial_bits=31):
    initial = (1 << serial_bits)-3
    model = Adapter(source, serial_bits, initial)
    rng = random.Random(8501+source)
    vectors, expected = [], []
    coverage = dict(ons=0, offs=0, moves=0, cancellations=0, responses=0, event_stalls=0,
                    reply_stalls=0, rejected_responses=0, retire_move_races=0, finish_moves=0)

    def tick(**changes):
        inputs = dict.fromkeys((name for name, width in INPUTS), 0)
        inputs.update(rst_n=1, reply_ready=1, query_contact=changes.get('on_contact', 0))
        inputs.update(changes)
        before = model.step(inputs)
        vectors.append(pack(INPUTS, inputs))
        expected.append(pack(OUTPUTS, before))
        coverage['ons'] += bool(inputs['on_valid'] and before['on_ready'])
        coverage['offs'] += bool(inputs['release_valid'] and before['release_ready'])
        coverage['moves'] += bool(before['expression_valid'])
        coverage['cancellations'] += bool(before['cancel_valid'])
        coverage['responses'] += bool(inputs['response_valid'] and before['response_ready'])
        coverage['event_stalls'] += bool(before['event_valid'] and not inputs['event_ready'])
        coverage['reply_stalls'] += bool(before['reply_valid'] and not inputs['reply_ready'])
        coverage['rejected_responses'] += bool(inputs['response_valid'] and not before['response_ready'])
        coverage['retire_move_races'] += bool(inputs['retire_valid'] and inputs['move_valid'])
        coverage['finish_moves'] += bool(inputs['finish_valid'] and before['expression_valid'])
        return before

    def send():
        for delay in range(rng.randrange(1, 4)):
            tick(on_valid=1, on_contact=25, on_note=rng.randrange(128), on_layers=7)
        tick(event_ready=1)

    def response(token, layers=15, base=0, code=0, **overlap):
        selected = [layer for layer in range(4) if layers >> layer & 1]
        mapping = sum(((base+layer) % 32) << (layer*5) for layer in selected)
        groups = sum(1 << ((base+layer) % 32) for layer in selected)
        fields = dict(response_valid=1, response_token=token, response_code=code,
            response_groups=groups if code == 0 else 0, response_layers=layers if code == 0 else 0,
            response_map=mapping if code == 0 else 0)
        fields.update(overlap)
        tick(**fields)
        return fields

    def on(contact=0, generation=0, layers=15):
        tick(on_valid=1, on_contact=contact, on_generation=generation, on_note=60,
             on_velocity=231, on_glide=-7011, on_layers=layers, query_contact=contact)
        return model.ledger.rows[contact]['token']

    def off(token, **overlap):
        tick(release_valid=1, release_token=token, **overlap)
        send()
        response(token, code=1)
        tick()

    tick(rst_n=0)
    token = on()
    send()
    response(token ^ (1 << 30))
    response(token, layers=3)
    response(token, response_map=0, response_groups=1)
    response(token, code=7)
    response(token)
    for delay in range(4):
        tick(reply_ready=0, on_valid=1, on_contact=1, on_layers=15,
             move_valid=1, move_token=token, move_position=320)
    tick()
    tick(move_valid=1, move_token=token, finish_valid=1, finish_token=token, finish_groups=2)
    tick(move_valid=1, move_token=token, retire_valid=1, retire_token=token)
    for attempt in range(3):
        tick(on_valid=1, on_contact=0, on_layers=15, move_valid=1, move_token=token)
    off(token)
    tick(finish_valid=1, finish_token=token, finish_groups=1)
    tick(rst_n=0)
    token = on()
    send()
    fields = response(token, release_valid=1, release_token=token)
    assert model.phase == 'wait'
    tick(**fields)
    response(token, code=6)
    tick()
    token = on(0, 1)
    tick(release_valid=1, release_token=token)
    send()
    response(token, code=6)
    tick()
    tick(rst_n=0)
    first = None
    count = 270 if serial_bits == 31 else 8
    for generation in range(count):
        token = on(0, generation % 256)
        if first is None:
            first = token
        send()
        response(token, layers=15, base=generation % 28)
        tick(query_contact=0)
        if generation >= 256:
            tick(release_valid=1, release_token=first, move_valid=1, move_token=first)
            tick(retire_valid=1, retire_token=first, finish_valid=1, finish_token=first, finish_groups=1)
        tick(move_valid=1, move_token=token, move_position=rng.randrange(-2048, 2048))
        off(token)
    tick(on_valid=1, on_contact=0, on_layers=15)
    if serial_bits == 31:
        token = model.ledger.rows[0]['token']
        send()
        response(token, code=3)
        tick()
        off(token)
    tick(rst_n=0)
    token = on()
    send()
    response(token)
    tick()
    off(token)
    tick(on_valid=1, on_contact=0, on_generation=1, on_note=62, on_velocity=111,
         on_layers=15, finish_valid=1, finish_token=token, finish_groups=1, query_contact=0)
    token2 = model.ledger.rows[0]['token']
    send()
    response(token2, retire_valid=1, retire_token=token2)
    tick(query_contact=0, move_valid=1, move_token=token2)
    token3 = on(1, 7)
    send()
    response(token3, base=8, finish_valid=1, finish_token=token3, finish_groups=1 << 9)
    tick(query_contact=1, move_valid=1, move_token=token3, move_position=123)
    off(token3, move_valid=1, move_token=token3, move_position=250)
    tick(rst_n=0)
    tick(on_valid=1, on_contact=31, on_layers=15)
    tick(on_valid=1, on_contact=0, on_layers=0)
    for contact in range(26):
        tick(query_contact=contact)
    coverage.update(cycles=len(vectors), generation_wrap=count >= 256,
                    serial_wrap=True, serial_exhaustion=serial_bits < 31,
                    simultaneous_cancel_allocation=True, old_tail_finish_new_on=True)
    return vectors, expected, coverage
