import random

INPUT_FIELDS = [('rst_n',1)] + [(source+'_'+name,width) for source in ('live','score') for name,width in
    [('valid',1),('on',1),('serial',31),('note',7),('velocity',8),('glide',18),('layers',4)]] + [
    ('event_ready',1),('response_valid',1),('response_token',32),('response_groups',32),('response_code',3),
    ('response_layers',4),('response_map',20),('live_response_ready',1),('score_response_ready',1)]
OUTPUT_FIELDS = [('live_ready',1),('score_ready',1),('event_valid',1),('event_on',1),('event_token',32),
    ('event_note',7),('event_velocity',8),('event_glide',18),('event_layers',4),('response_ready',1),
    ('live_response_valid',1),('score_response_valid',1),('routed_token',32),('routed_groups',32),
    ('routed_code',3),('routed_layers',4),('routed_map',20),('protocol_error',1)]


def pack(fields, values):
    packed = 0
    for name, width in fields:
        packed = (packed << width) | (values.get(name,0) & ((1 << width)-1))
    return packed


def unpack(fields, packed):
    values = {}
    for name, width in reversed(fields):
        values[name] = packed & ((1 << width)-1)
        packed >>= width
    return values


class Router:
    def __init__(self):
        self.phase = 'choose'
        self.turn = 0
        self.payload = dict(on=0,token=0,note=0,velocity=0,glide=0,layers=0)
        self.error = 0

    def outputs(self, inputs):
        if not inputs['rst_n']:
            self.__init__()
        source = int(bool(inputs['score_valid'] and (not inputs['live_valid'] or self.turn)))
        match = self.phase == 'reply' and inputs['response_token'] == self.payload['token']
        response_source = self.payload['token'] >> 31
        enabled = inputs['rst_n']
        result = {('event_'+name):value for name,value in self.payload.items()}
        result.update(live_ready=int(enabled and self.phase=='choose' and not source),
            score_ready=int(enabled and self.phase=='choose' and source),
            event_valid=int(enabled and self.phase=='present'),
            response_ready=int(enabled and match and inputs[('score' if response_source else 'live')+'_response_ready']),
            live_response_valid=int(enabled and inputs['response_valid'] and match and not response_source),
            score_response_valid=int(enabled and inputs['response_valid'] and match and response_source),
            protocol_error=self.error)
        for name in ('token','groups','code','layers','map'):
            result['routed_'+name] = inputs['response_'+name]
        return result

    def advance(self, inputs, outputs):
        if not inputs['rst_n']:
            return
        if inputs['response_valid'] and not (self.phase=='reply' and inputs['response_token']==self.payload['token']):
            self.error = 1
        for source, label in enumerate(('live','score')):
            if inputs[label+'_valid'] and outputs[label+'_ready']:
                self.payload = {name:inputs[label+'_'+name] for name in ('on','note','velocity','glide','layers')}
                self.payload['token'] = (source << 31) | inputs[label+'_serial']
                self.turn = 1-source
                self.phase = 'present'
                return
        if outputs['event_valid'] and inputs['event_ready']:
            self.phase = 'reply'
        elif inputs['response_valid'] and outputs['response_ready']:
            self.phase = 'choose'


def generate(cycles=24000, seed=20261024):
    generator = random.Random(seed)
    model = Router()
    serials = [(1 << 31)-17,(1 << 31)-19]
    heads = [None,None]
    reply = None
    delay = 0
    bad_left = 0
    inputs_list, expected = [], []
    coverage = dict(accepted=[0,0],completed=[0,0],sent=0,collisions=0,wrong_responses=0,
                    downstream_stalls=0,response_stalls=0,resets=0,serial_wraps=[0,0])
    for cycle in range(cycles):
        reset = cycle < 3 or cycle % 4000 in (0,1,2)
        if reset:
            heads = [None,None]
            reply = None
            delay = 0
            bad_left = 0
            coverage['resets'] += 1
        inputs = {name:0 for name,width in INPUT_FIELDS}
        inputs.update(rst_n=int(not reset),event_ready=int(cycle%97>24 and generator.randrange(4)!=0),
                      live_response_ready=int(cycle%131>23 and generator.randrange(3)!=0),
                      score_response_ready=int(cycle%137>29 and generator.randrange(3)!=0))
        for source,label in enumerate(('live','score')):
            if heads[source] is None and not reset and generator.randrange(4)!=0:
                previous = serials[source]
                serials[source] = (previous+1) & 0x7fffffff
                if serials[source] < previous:
                    coverage['serial_wraps'][source] += 1
                heads[source] = dict(on=generator.randrange(2),serial=serials[source],note=60 if cycle%5 else generator.randrange(128),
                    velocity=generator.randrange(256),glide=generator.randrange(1<<18),layers=generator.randrange(16))
            if heads[source] is not None:
                inputs[label+'_valid'] = 1
                inputs.update({label+'_'+name:value for name,value in heads[source].items()})
        if reply is not None:
            if delay:
                delay -= 1
            else:
                inputs.update(response_valid=1,**{'response_'+name:value for name,value in reply.items()})
                if bad_left:
                    inputs['response_token'] ^= 0x80000001
                    bad_left -= 1
                    coverage['wrong_responses'] += 1
        elif not reset and model.phase=='choose' and cycle%113==0:
            inputs.update(response_valid=1,response_token=0x12345678)
            coverage['wrong_responses'] += 1
        outputs = model.outputs(inputs)
        if inputs['live_valid'] and inputs['score_valid'] and model.phase=='choose':
            coverage['collisions'] += 1
        for source,label in enumerate(('live','score')):
            if inputs[label+'_valid'] and outputs[label+'_ready']:
                coverage['accepted'][source] += 1
                heads[source] = None
            if outputs[label+'_response_valid'] and inputs[label+'_response_ready']:
                coverage['completed'][source] += 1
        if outputs['event_valid'] and not inputs['event_ready']:
            coverage['downstream_stalls'] += 1
        if (outputs['live_response_valid'] or outputs['score_response_valid']) and not outputs['response_ready']:
            coverage['response_stalls'] += 1
        if inputs['response_valid'] and outputs['response_ready']:
            reply = None
        if outputs['event_valid'] and inputs['event_ready']:
            coverage['sent'] += 1
            token = outputs['event_token']
            reply = dict(token=token,groups=(token*0x9e3779b1)&0xffffffff,code=(token>>3)%7,
                         layers=outputs['event_layers'],map=(token*31337)&0xfffff)
            delay = generator.randrange(1,9)
            bad_left = 3 if coverage['sent']%17==0 else 0
        inputs_list.append(pack(INPUT_FIELDS,inputs))
        expected.append(pack(OUTPUT_FIELDS,outputs))
        model.advance(inputs,outputs)
    return inputs_list, expected, coverage
