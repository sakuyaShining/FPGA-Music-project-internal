// Diagnostic stimulus only: no physical electrode/display acquisition.
module board_test_driver #(
    parameter REPORT_CYCLES=135000,CASE_CYCLES=27000000,TAIL_CYCLES=40500000
)(
    input wire clk,rst_n,warm,fault,wr_en,
    input wire [7:0] wr_addr,wr_data,
    output reg armed,running,
    output reg [7:0] test_case,
    output wire initialized,
    output wire cfg_valid,cfg_commit,
    output wire [1:0] cfg_slot,
    output wire [3:0] cfg_part,
    output wire [47:0] cfg_word,
    input wire cfg_ready,
    output reg frame_valid,
    input wire frame_ready,
    output reg [25:0] contact,
    output reg [233:0] position,
    output reg [181:0] note_map,
    output reg [31:0] frame_sequence,
    output reg [3:0] selection,
    input wire [25:0] bound
);
    reg [47:0] slot_rom[0:31];
    initial $readmemh("board_slots.hex",slot_rom);
    reg [5:0] init_index;
    reg [31:0] report_timer,case_timer;
    reg [8:0] slide;
    reg slide_down;
    assign initialized=init_index==34;
    assign cfg_valid=!initialized;
    assign cfg_commit=init_index==16||init_index==33;
    assign cfg_slot=init_index>16?2'd1:2'd0;
    wire [5:0] init_part=init_index>16?init_index-6'd17:init_index;
    assign cfg_part=init_part[3:0];
    assign cfg_word=slot_rom[{cfg_slot[0],cfg_part}];
    integer i;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            init_index<=0;armed<=0;running<=0;test_case<=0;case_timer<=0;
            frame_valid<=0;contact<=0;position<=0;note_map<=0;frame_sequence<=0;
            report_timer<=0;selection<=1;slide<=128;slide_down<=0;
        end else begin
            if(cfg_valid&&cfg_ready)init_index<=init_index+1'b1;
            if(running)begin
                if(case_timer>=CASE_CYCLES+TAIL_CYCLES-1)running<=0;
                else case_timer<=case_timer+1'b1;
            end
            if(frame_valid)begin
                if(frame_ready)begin frame_valid<=0;frame_sequence<=frame_sequence+1'b1;report_timer<=0;end
            end else if(report_timer>=REPORT_CYCLES-1&&initialized)begin
                frame_valid<=1;contact<=0;
                for(i=0;i<26;i=i+1)begin position[i*9+:9]<=128;note_map[i*7+:7]<=7'd48+i[6:0];end
                if(running&&case_timer<CASE_CYCLES&&armed&&!fault)begin
                    case(test_case)
                        1,3:begin contact<=1;note_map[0+:7]<=69;end
                        2:begin contact<=7;note_map[0+:7]<=60;note_map[7+:7]<=64;note_map[14+:7]<=67;end
                        4:begin
                            contact<=3;note_map[0+:7]<=60;note_map[7+:7]<=64;position[0+:9]<=slide;
                            if(slide_down)begin if(slide<=64)slide_down<=0;else slide<=slide-9'd8;end
                            else begin if(slide>=192)slide_down<=1;else slide<=slide+9'd8;end
                        end
                        5:begin if(case_timer<CASE_CYCLES/10)contact<=1;note_map[0+:7]<=69;end
                        6:contact<=case_timer<CASE_CYCLES/2?26'h000ffff:26'h001ffff;
                    endcase
                end
            end else if(report_timer<REPORT_CYCLES)report_timer<=report_timer+1'b1;
            // Only the test page can arm the physical speaker. Power-on is mute.
            if(wr_en)begin
                if(wr_addr==8'hC0&&wr_data==8'hA6&&warm&&initialized&&!fault)armed<=1;
                if(wr_addr==8'hC1&&wr_data>=1&&wr_data<=6&&armed&&warm&&initialized&&!running&&bound==0&&frame_ready)begin
                    running<=1;test_case<=wr_data;case_timer<=0;slide<=128;slide_down<=0;
                    selection<=(wr_data==3||wr_data==6)?4'b0011:4'b0001;
                    if(!frame_valid)report_timer<=REPORT_CYCLES;
                end
                if((wr_addr==8'hC0&&wr_data==0)||wr_addr==8'hC2)begin
                    armed<=0;running<=0;if(!frame_valid)report_timer<=REPORT_CYCLES;
                end
            end
            if(fault)begin armed<=0;running<=0;end
        end
    end
endmodule
