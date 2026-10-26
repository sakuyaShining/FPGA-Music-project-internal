`timescale 1ns/1ps
module tb_velocity_scaling;
    reg [3:0] vel=0,part=0;
    reg [1:0] slot=0;
    reg [7:0] base=0;
    reg [8:0] vscale=0;
    wire [7:0] actual,legacy;
    vel_shape original(.vel(vel),.slot(slot),.part(part),.base(base),.tilt_bias(10'sd0),.tilt_gain(8'd128),.vscale(vscale),.amp(legacy));
    vel_shape_scaled corrected(.vel(vel),.slot(slot),.part(part),.base(base),.tilt_bias(10'sd0),.tilt_gain(8'd128),.vscale(vscale),.amp(actual));
    reg [11:0] weights[0:1023];
    integer scales[0:7];
    integer address,amplitude,scale_index,raw_weight,delta,weight,expected;
    integer checked=0,default_checked=0,corrected_cases=0;
    initial begin
        $readmemh("vel_wtab.hex",weights);
        scales[0]=0;scales[1]=1;scales[2]=128;scales[3]=255;
        scales[4]=256;scales[5]=257;scales[6]=384;scales[7]=511;
        for(address=0;address<1024;address=address+1)begin
            slot=address/256;vel=(address/16)%16;part=address%16;raw_weight=weights[address]&511;
            for(scale_index=0;scale_index<8;scale_index=scale_index+1)begin
                vscale=scales[scale_index];delta=raw_weight-256;delta=delta*scales[scale_index];delta=delta>>>8;
                weight=delta+256;if(weight<0)weight=0;if(weight>511)weight=511;
                if(part<3&&weight<64)weight=64;
                for(amplitude=0;amplitude<256;amplitude=amplitude+1)begin
                    base=amplitude;expected=(amplitude*weight)>>8;if(expected>255)expected=255;
                    #1;
                    if(actual!==expected[7:0])$fatal(1,"scaled velocity arithmetic mismatch");
                    if(vscale==0||vscale==256)begin
                        if(actual!==legacy)$fatal(1,"default velocity compatibility changed");
                        default_checked=default_checked+1;
                    end
                    if(actual!==legacy)begin
                        if(corrected_cases==0)$display("FIRST_LEGACY_WRAP address=%0d scale=%0d base=%0d old=%0d corrected=%0d",address,vscale,base,legacy,actual);
                        corrected_cases=corrected_cases+1;
                    end
                    checked=checked+1;
                end
            end
        end
        if(corrected_cases==0)$fatal(1,"velocity wrap counterexample absent");
        $display("PASS velocity_scaling checked=%0d default_compatible=%0d corrected=%0d",checked,default_checked,corrected_cases);$finish;
    end
endmodule
