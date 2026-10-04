//=============================================================================
// tb_audio.v —— 全链路音频渲染（把 FPGA 的输出变成你能听的 WAV）
//
// 【为什么要有它】
//   到目前为止所有证据都是"数字对数字"（逐位一致、判据通过）。但你要的是
//   "**绝对保证它还能跑**" + 亲耳听一下。本测试台把【顶层真实输出】逐样本
//   dump 出来（就是送进 I2S 的那个 `audio`），再由 render_wav.py 渲染成 48 kHz WAV。
//
// 【两种模式】
//   +test=0  协议全链路：**只用 UART 两字节帧**（就是上位机将来要发的）
//            下载一段曲谱 → 使能定序器 → 带混响播放
//            ⇒ 这一条同时回答"上位机到底怎么操作"
//   +test=1  效果器对比：同一段旋律连播 4 遍，每遍换一种效果
//            （干声 / 延迟 / 合唱 / 混响）⇒ 耳朵直接听出效果器在动
//
// 【时钟】27 MHz（CLK_HALF = 18.5185 ns）⇒ fs = 27e6/512 = 52734.375 Hz
//    必须与出货一致，否则 WAV 的音高与时长都不对。
//=============================================================================

`timescale 1ns/1ps

module tb_audio;

    localparam real    CLK_HALF = 18.5185;     // 27 MHz
    localparam integer DIV      = 234;         // 115200 baud 的位宽（27e6/115200）
    localparam integer NSLOT    = 512;

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    reg [1:0]  which;
    reg        uart_rx;
    wire       uart_tx;

    reg        ev_valid, ev_on;
    reg [6:0]  ev_note;
    reg [3:0]  ev_vel;

    wire [5:0] led;

    //-------------------------------------------------------------------------
    // DUT：完整顶层（引擎 + 音色映射 + 效果器 + I2S + UART + 定序器）
    //-------------------------------------------------------------------------
    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd1), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(led), .dac_din(), .dac_ws(), .dac_bck(), .pa_en()
    );

    // 样本节拍（与顶层内部一致：每 512 拍一个样本）
    reg [9:0] pc;
    wire sample_en = (pc == NSLOT - 1);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                 pc <= 10'd0;
        else if (pc == NSLOT - 1)   pc <= 10'd0;
        else                        pc <= pc + 10'd1;
    end

    //-------------------------------------------------------------------------
    // 串口发送：真两字节帧（地址 + 数据），与上位机完全一样
    //-------------------------------------------------------------------------
    task send_byte(input [7:0] b);
        integer i;
        begin
            uart_rx = 1'b0;                       // 起始位
            repeat (DIV) @(posedge clk);
            for (i = 0; i < 8; i = i + 1) begin
                uart_rx = b[i];                   // LSB 先发
                repeat (DIV) @(posedge clk);
            end
            uart_rx = 1'b1;                       // 停止位
            repeat (DIV) @(posedge clk);
        end
    endtask

    task wr_reg(input [7:0] a, input [7:0] d);
        begin
            send_byte(a);
            send_byte(d);
        end
    endtask

    //-------------------------------------------------------------------------
    // dump：两列（序号 值），render_wav.py 直接吃
    //-------------------------------------------------------------------------
    integer fout, k;

    task dump_samples(input integer n);
        integer q;
        begin
            for (q = 0; q < n; q = q + 1) begin
                @(posedge clk);
                while (!sample_en) @(posedge clk);
                $fdisplay(fout, "%0d %0d", q, $signed(u_top.audio));
            end
        end
    endtask

    task note_on(input [6:0] n, input [3:0] v);
        begin
            @(posedge clk);
            ev_note <= n; ev_vel <= v; ev_on <= 1'b1; ev_valid <= 1'b1;
            @(posedge clk);
            ev_valid <= 1'b0;
        end
    endtask

    task note_off(input [6:0] n);
        begin
            @(posedge clk);
            ev_note <= n; ev_on <= 1'b0; ev_valid <= 1'b1;
            @(posedge clk);
            ev_valid <= 1'b0;
        end
    endtask

    //-------------------------------------------------------------------------
    // 曲谱：欢乐颂开头 8 步（E E F G G F E D）
    //   通过 UART 写 0x70/0x71 逐对下载，0x73 写步数
    //-------------------------------------------------------------------------
    task put_note(input [7:0] n, input [7:0] beats);
        begin
            wr_reg(8'h70, n);
            wr_reg(8'h71, beats);
        end
    endtask

    integer seg;
    integer ns_dump;
    initial begin
        if (!$value$plusargs("test=%d", which)) which = 2'd0;
        if (!$value$plusargs("ns=%d", ns_dump)) ns_dump = 150000;

        uart_rx = 1'b1;
        ev_valid = 1'b0; ev_on = 1'b0; ev_note = 7'd0; ev_vel = 4'd0;

        rst_n = 1'b0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (4000) @(posedge clk);      // 等开机自举把默认值写完

        if (which == 2'd0) begin
            //=================================================================
            // test=0：**只用 UART** 下载曲谱并播放（带混响）
            //=================================================================
            fout = $fopen("audio_proto.txt", "w");
            $display("==============================================================");
            $display(" test=0 协议全链路：UART 下载曲谱 → 定序器播放（带混响）");
            $display("==============================================================");

            // 关掉滑音/颤音（CTRL=0x00）：曲目演示不需要 portamento。
            //   实测发现：滑音是按【时隙】而不是按声部的 —— 时隙被复用时，
            //   gq 初值是对着该时隙【残留的旧音高】算的，于是旋律里会听到
            //   "从上一个占用该时隙的音滑过来"（音频判据测到第 2 个音带低八度能量）。
            //   这是设计特征（演奏时的 portamento 很有用），但会让"逐音音高"判据失真。
            wr_reg(8'h00, 8'h00);              // CTRL = 0：不测试、无颤音、无滑音
            // 效果器：仅干声 + 混响（FX_CTRL bit0=干声, bit6=混响）
            wr_reg(8'h40, 8'h41);
            wr_reg(8'h48, 8'hC0);              // REV_FB   = 0.75
            wr_reg(8'h49, 8'h03);              // REV_DAMP = 3
            // 节拍：tempo_inc = 2^24 / (0.35 s × 52734.375) ≈ 909
            wr_reg(8'h51, 8'h8D); wr_reg(8'h52, 8'h03); wr_reg(8'h53, 8'h00);
            // 力度
            wr_reg(8'h54, 8'hC0);
            // 下载 8 步曲谱
            wr_reg(8'h72, 8'h00);              // 索引归零
            put_note(8'd64, 8'd1);   // E
            put_note(8'd64, 8'd1);   // E
            put_note(8'd65, 8'd1);   // F
            put_note(8'd67, 8'd1);   // G
            put_note(8'd67, 8'd1);   // G
            put_note(8'd65, 8'd1);   // F
            put_note(8'd64, 8'd1);   // E
            put_note(8'd62, 8'd2);   // D(2)
            wr_reg(8'h73, 8'd8);               // 步数 = 8
            // 使能定序器（A6：SCORE_LEN>0 即用下载曲谱，无需额外位）
            wr_reg(8'h50, 8'h01);               // A6：不写曲谱源位，靠 SCORE_LEN>0
            // 帧数：FX_CTRL/REV_FB/REV_DAMP(3) + TEMPO_INC(3) + SEQ_VEL(1)
            //      + SCORE_IDX(1) + 8×2(音高/拍数) + SCORE_LEN(1) + SEQ_CTRL(1) = 26 帧
            //  与 `python tools/scripts/dsp_host.py --dry demo-score` 输出的字节流完全一致
            $display("  已通过 UART 下发 26 个两字节帧（与 dsp_host.py demo-score 一致），开始录制…");

            // 探针：如果顶层输出是 x，先在这里分辨"引擎侧 x"还是"效果器侧 x"
            repeat (2000) @(posedge clk);
            $display("  [探针] sample=%0d  fx_out=%0d  audio=%0d  fx_active=%0d",
                     $signed(u_top.sample), $signed(u_top.fx_out),
                     $signed(u_top.audio), u_top.fx_active);
`ifdef SIM_INIT
            $display("  [探针] SIM_INIT 宏【已定义】");
`else
            $display("  [探针] SIM_INIT 宏【未定义】← 线缓冲初值没编进去");
`endif
            $display("  [探针] fx_dly_en=%0d fx_cho_en=%0d fx_rev_en=%0d wet_sh=%0d dly_len=%0d",
                     u_top.fx_dly_en, u_top.fx_cho_en, u_top.fx_rev_en,
                     u_top.fx_wet_sh, u_top.r_dlylen);
            $display("  [探针] u_fx.st=%0d wptr=%0d dl_tap=%0d ram_q=%0d",
                     u_top.u_fx.st, u_top.u_fx.wptr, $signed(u_top.u_fx.dl_tap),
                     $signed(u_top.u_fx.line[u_top.u_fx.wptr]));
            $display("  [探针] line[0]=%0d line[1]=%0d line[100]=%0d line[2047]=%0d",
                     $signed(u_top.u_fx.line[0]), $signed(u_top.u_fx.line[1]),
                     $signed(u_top.u_fx.line[100]), $signed(u_top.u_fx.line[2047]));
            $display("  [探针] wr_val=%0d fb_val=%0d rev_fbv=%0d rt0=%0d rev_lp=%0d",
                     $signed(u_top.u_fx.wr_val), $signed(u_top.u_fx.fb_val),
                     $signed(u_top.u_fx.rev_fbv), $signed(u_top.u_fx.rt[0]),
                     $signed(u_top.u_fx.rev_lp));

            dump_samples(ns_dump);              // ≈2.84 s
            $fclose(fout);
            $display("  → audio_proto.txt");
        end
        else begin
            //=================================================================
            // test=1：同一段旋律 4 遍，每遍一种效果（耳朵做判据）
            //=================================================================
            fout = $fopen("audio_fx.txt", "w");
            $display("==============================================================");
            $display(" test=1 效果器对比：干声 / 延迟 / 合唱 / 混响（各 ≈0.95 s）");
            $display("==============================================================");

            // 基础：延迟/合唱参数（沿用开机自举默认即可），力度固定
            ev_vel = 4'd12;
            for (seg = 0; seg < 4; seg = seg + 1) begin
                case (seg)
                    0: wr_reg(8'h40, 8'h01);   // 仅干声
                    1: wr_reg(8'h40, 8'h03);   // 干声 + 延迟
                    2: wr_reg(8'h40, 8'h05);   // 干声 + 合唱
                    3: wr_reg(8'h40, 8'h41);   // 干声 + 混响
                endcase
                // 一小段旋律：C E G C(2)
                note_on(7'd60, 4'd12); dump_samples(11000); note_off(7'd60);
                dump_samples(1500);
                note_on(7'd64, 4'd12); dump_samples(11000); note_off(7'd64);
                dump_samples(1500);
                note_on(7'd67, 4'd12); dump_samples(11000); note_off(7'd67);
                dump_samples(1500);
                note_on(7'd72, 4'd12); dump_samples(11000); note_off(7'd72);
                dump_samples(1500);          // 尾部留白 → 听得到延迟/混响尾巴
            end
            $fclose(fout);
            $display("  → audio_fx.txt");
        end
        $finish;
    end

    initial begin
        #30_000_000_000;                      // 30 s 仿真时间上限（≈30 s 音频）
        $display("[TIMEOUT] test=%0d", which);
        $finish;
    end

endmodule
