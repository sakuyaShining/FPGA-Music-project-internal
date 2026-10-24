import random


def signed(value, width):
    value &= (1 << width) - 1
    return value - (1 << width) if value & (1 << (width - 1)) else value


def render(context, layer, partial, definition, custom, notes, tilts, weights):
    ratio = (definition >> 32) & 65535
    amplitude = (definition >> 24) & 255
    envelope_parameters = definition & ((1 << 23) - 1)
    envelope = definition >> 48 if custom else 0
    frequency = notes[context['note']] * ratio
    spectrum = 255 if context['pad'] >> partial & 1 else context['spectrum'][partial]
    if not custom:
        amplitude = spectrum if context['replace'] else min(255, amplitude + spectrum)
    tilt_weight = max(64, tilts[(context['tilt'] >> 4) * 16 + partial] & 511)
    amplitude = min(255, (amplitude * tilt_weight) >> 8)
    weight = weights[layer * 256 + (context['velocity'] >> 4) * 16 + partial] & 511
    delta = ((weight - 256) * context['scale']) >> 8
    weight = max(0, min(511, delta + 256))
    if partial < 3:
        weight = max(weight, 64)
    amplitude = min(255, (amplitude * weight) >> 8)
    amplitude = (amplitude * context['velocity']) >> 8
    if frequency >> 31:
        amplitude = 0
    if context['artic'] and context['artic_mask'] >> partial & 1:
        decay = max(0, context['strike_k'] - ((partial * context['curve']) >> 4))
        sustain = context['sustain'] << 11 if partial < 4 else 0
        envelope_parameters = (sustain << 7) | (context['strike_m'] << 5) | decay
        envelope &= ~(15 << 11)
    return [(frequency >> 8) & 0xffffff, amplitude, envelope_parameters, envelope, context['glide'] & 0x3ffff]


def generate(notes, presets, tilts, weights, count=256, seed=20261024):
    generator = random.Random(seed)
    commands, expected = [], []
    definitions = [None] * 4
    query_index = 0
    enabled = []
    commands.append('1 0 0')
    for context_index in range(count):
        slots = []
        if context_index == 32:
            slots = [0, 2]
        elif context_index == 64:
            slots = [1, 3]
        elif context_index >= 96 and context_index % 16 == 0:
            slots = [context_index // 16 % 4]
        for slot in slots:
            words = []
            for partial in range(16):
                ratio = generator.choice([64, 128, 256, 512, 716, 1536, 4096, 32768, 65535])
                amplitude = generator.randrange(256)
                parameters = (generator.randrange(32769) << 7) | (generator.randrange(1, 4) << 5) | generator.randrange(32)
                envelope = (1 << 35) | (generator.randrange(16) << 31) | (generator.randrange(1, 32769) << 15)
                envelope |= (generator.randrange(16) << 11) | (generator.randrange(16) << 7) | (generator.randrange(1, 4) << 5) | generator.randrange(32)
                word = (envelope << 48) | (ratio << 32) | (amplitude << 24) | parameters
                commands.append('0 %d %d %022x' % (slot, partial, word))
                words.append(word)
                if partial == 5:
                    commands.append('1 %d 0' % slot)
            commands.append('1 %d 1' % slot)
            definitions[slot] = words
        spectrum = [generator.randrange(256) for partial in range(16)]
        if context_index in (0, 4, 5):
            spectrum = [0] * 16
        for partial, amplitude in enumerate(spectrum):
            commands.append('2 %d %d' % (partial, amplitude))
        commands.append('3 15 %d' % spectrum[15])
        context = dict(note=generator.randrange(128), velocity=generator.randrange(256), glide=generator.randrange(-114688, 131072),
            tilt=generator.randrange(256), bias=generator.randrange(-512,512), gain=generator.randrange(256), scale=generator.randrange(512),
            replace=generator.randrange(2), pad=generator.randrange(65536), artic=generator.randrange(2), artic_mask=generator.randrange(65536),
            strike_m=generator.randrange(1,4), strike_k=generator.randrange(32), curve=generator.randrange(16), sustain=generator.randrange(16), spectrum=spectrum)
        if context_index in (0, 4, 5):
            context.update(note=60, velocity=255 if context_index == 0 else 0x50, tilt=0x70, scale=256, replace=0, pad=0, artic=0)
        if context_index == 5:
            context['scale'] = 511
        if context_index == 1:
            context.update(velocity=0, scale=511)
        if context_index == 2:
            context.update(note=127, velocity=255)
        token = context_index + 1 | ((context_index % 2) << 31)
        commands.append('4 %08x %d %d %05x %d %d %d %d %d %04x %d %04x %d %d %d %d' % (
            token, context['note'], context['velocity'], context['glide'] & 0x3ffff, context['tilt'], context['bias'], context['gain'], context['scale'],
            context['replace'], context['pad'], context['artic'], context['artic_mask'], context['strike_m'], context['strike_k'], context['curve'], context['sustain']))
        if context_index == 0:
            commands.append('7')
        enabled.append([slot for slot, words in enumerate(definitions) if words is not None])
        for layer in range(4):
            for partial in range(16):
                commands.append('5 %d %d %d %d' % (layer, partial, generator.randrange(4), generator.randrange(8)))
                definition = definitions[layer][partial] if definitions[layer] is not None else presets[layer * 16 + partial]
                payload = render(context, layer, partial, definition, definitions[layer] is not None, notes, tilts, weights)
                expected.append([query_index, token, query_index & 255, layer, partial] + payload)
                query_index += 1
                if layer == 1 and partial == 15:
                    commands.append('3 5 %d' % generator.randrange(256))
        commands.append('6')
    return commands, expected, dict(contexts=count, queries=query_index, enabled_history=enabled)
