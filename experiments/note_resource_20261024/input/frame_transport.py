from contact_rtl_reference import INPUTS, OUTPUTS


BACKEND_INPUTS = ['event_ready', 'response_valid', 'response_token', 'response_code',
                  'response_groups', 'response_layers', 'response_map', 'reply_ready',
                  'retire_valid', 'retire_token', 'finish_valid', 'finish_token', 'finish_groups']
BACKEND_OUTPUTS = [name for name, width in OUTPUTS if name not in
                   ('on_ready', 'release_ready', 'query_held', 'query_token', 'query_groups', 'query_layers', 'query_map')]


def ports(nf=26):
    inputs = [('rst_n', 1), ('frame_valid', 1), ('contact', nf), ('invalid', nf),
        ('position', nf*9), ('note_map', nf*7), ('frame_sequence', 32), ('frame_calibration', 1),
        ('velocity', 8), ('glide', 18), ('layer_selection', 4)]
    inputs += [(name, width) for name, width in INPUTS if name in BACKEND_INPUTS]
    outputs = [('frame_ready', 1), ('frame_error', 1), ('link_error', 1), ('sensor_error', 1),
        ('watchdog_error', 1), ('admission_error', 1), ('seen_contacts', nf), ('blocked_contacts', nf),
        ('anchor_valid', 1), ('anchor_contact', 5), ('anchor_position', 12)]
    outputs += [(name, width) for name, width in OUTPUTS if name in BACKEND_OUTPUTS]
    return inputs, outputs


def wrapper():
    inputs, outputs = ports()
    dynamic = dict(contact='NF', invalid='NF', position='NF*9', note_map='NF*7',
                   seen_contacts='NF', blocked_contacts='NF')
    def declaration(name, width):
        size = '['+dynamic[name]+'-1:0] ' if name in dynamic else ('['+str(width-1)+':0] ' if width > 1 else '')
        return size+name
    lines = ['module note_frame_transport #(parameter integer NF=26,BAD_FRAMES=8,FRAME_TIMEOUT=2700000,LINK_TIMEOUT=8192)(',
        '    input wire clk,']
    lines += ['    input wire '+declaration(name, width)+',' for name, width in inputs]
    lines += ['    output wire '+declaration(name, width)+(',' if index < len(outputs)-1 else '') for index, (name, width) in enumerate(outputs)]
    lines += [');']
    public = {name for name, width in inputs+outputs}
    lines += ['    wire '+declaration(name, width)+';' for name, width in INPUTS+OUTPUTS if name not in public]
    lines += ['    wire signed [11:0] on_position;',
        '    reg link_pending;',
        '    always @(posedge clk or negedge rst_n)begin',
        '        if(!rst_n)link_pending<=0;',
        '        else begin',
        '            if(reply_valid&&reply_ready)link_pending<=0;',
        '            if((on_valid&&on_ready)||(release_valid&&release_ready))link_pending<=1;',
        '        end',
        '    end',
        '    assign anchor_valid=on_valid&&on_ready;',
        '    assign anchor_contact=on_contact;',
        '    assign anchor_position=on_position;']
    source_names = ['rst_n', 'frame_valid', 'frame_ready', 'contact', 'invalid', 'position', 'note_map',
        'frame_sequence', 'frame_calibration', 'velocity', 'glide', 'layer_selection', 'on_valid',
        'on_ready', 'on_contact', 'on_generation', 'on_velocity', 'on_note', 'on_glide', 'on_layers',
        'on_position', 'release_valid', 'release_ready', 'release_token', 'move_valid', 'move_token',
        'move_position', 'query_contact', 'query_held', 'query_token', 'query_groups', 'frame_error',
        'link_error', 'sensor_error', 'watchdog_error', 'admission_error', 'seen_contacts', 'blocked_contacts', 'link_pending']
    lines += ['    contact_frame_source #(.NF(NF),.BAD_FRAMES(BAD_FRAMES),.FRAME_TIMEOUT(FRAME_TIMEOUT),.LINK_TIMEOUT(LINK_TIMEOUT)) source(',
        '        .clk(clk),'+','.join('.'+name+'('+name+')' for name in source_names)+');']
    lines += ['    note_contact_adapter #(.NF(NF)) ledger(',
        '        .clk(clk),'+','.join('.'+name+'('+name+')' for name, width in INPUTS+OUTPUTS)+');', 'endmodule']
    return '\n'.join(lines)+'\n'
