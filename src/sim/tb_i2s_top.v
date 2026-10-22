//=============================================================================
// tb_i2s_top.v —— 顶层音频通路端到端判据（tdm_top → fx → i2s_tx → 解码）
//
// 【为什么必须单独有这一条】
//   tb_i2s_tx.v / tb_i2s_std.v 验的是 i2s_tx 【单元】，喂进去的是测试台自己造的
//   24 位斜坡。而真正上板的是这条链：
//       tdm_engine 的 24 位饱和输出 → fx（干声旁路）→ i2s_tx 取高 16 位 → DAC
//   中间任何一环的位宽/符号/对接写错，单元测试全绿也照样听不见或听到噪声。
//   本项目已经反复吃过"单元绿、集成路径从未跑到"的亏，所以这条独立成判据。
//
// 【判据】
//   T1  i2s_tx 的 24→16 映射正确：解码字 == $signed(sample_out[23:8])
//   T2  逐样本比对（不是"看上去差不多"），允许一个固定的流水线滞后
//   T3  实际触发了饱和：统计 |decoded| == 32767 的样本数 > 0
//       （饱和路径若从未被跑到，T1 就只是"小信号下恰好对"）
//   T4  符号覆盖：解码样本里正负都存在
//
// 【激励】直接驱动事件端口（与 tb_vp7 / tb_vel_timbre 同款），
//   同时按 4 个音 + 满力度，把混音推到大信号区以触发饱和。
//
// 产物：i2s_top_ref.txt（参考 = sample_out[23:8]）/ i2s_top_dec.txt（解码）
//       由 tools/scripts/i2s_top_check.py 判定
//=============================================================================
`timescale 1ns/1ps

module tb_i2s_top;

    localparam NSAMP = 6000;            // ≈128 ms @46875 Hz，覆盖起音+衰减

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;         // ≈27 MHz

    reg rst_n = 1'b0;
    wire [15:0] pad_bus;               // pad 是 inout，必须用 wire（用 reg 会报"不能由原语驱动"）
    reg        uart_rx = 1'b1;
    wire       uart_tx;
    reg        ev_valid, ev_on;
    reg [6:0]  ev_note;
    reg [3:0]  ev_vel;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    //   参考侧：每个 sample_en 抓一次引擎的 24 位饱和输出
    //   ★ 同时探测引擎内部的 sum_raw（饱和【之前】的和）：
    //     顶层的 24 位饱和阈值是 ±(2^23-1)，但 tdm_engine 里是
    //         sample_out = acc_next <<< GAIN_UP(4)   （先左移 4 位再加饱和）
    //     所以真正会被截顶的是 acc_next ≥ 2^19。只统计"解码是否到 32767"无法区分
    //     "信号没到饱和区" 与 "饱和逻辑写错了" —— 必须把增益前的那一级也量出来，
    //     T3 才是有信息量的（否则它永远红，等于没有判据）。
    //-------------------------------------------------------------------------
    reg        ref_v;
    reg [23:0] ref_d;
    reg [31:0] sum_max;                 // 本次运行 sum_raw 的最大绝对值
    reg [31:0] sum_abs;
    integer    n_ref;

    always @(posedge clk) begin
        ref_v <= 1'b0;
        if (rst_n && u_top.sample_en) begin
            ref_d <= u_top.sample;          // 层次引用：24 位有符号
            ref_v <= 1'b1;
            //   注意：tdm_top 把 u_tdm 的 sum_raw 端口**空接**了（.sum_raw()），
            //   所以顶层没有这根线；直接从引擎内部寄存器取。
            sum_abs = u_top.u_tdm.sum_latched[31] ? (~u_top.u_tdm.sum_latched + 32'd1)
                                                  : u_top.u_tdm.sum_latched;
            if (sum_abs > sum_max) sum_max <= sum_abs;
        end
    end

    //-------------------------------------------------------------------------
    // 解码侧：标准 I2S 接收器（bck 上升沿采样，WS 翻转 = 新字 MSB）
    //-------------------------------------------------------------------------
    reg        p_bck;
    reg        ws_prev;
    reg [4:0]  cnt;
    reg [15:0] sr;
    reg [15:0] word;
    reg        v_word;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            p_bck <= 1'b0; ws_prev <= 1'b0; cnt <= 5'd0;
            sr <= 16'd0; word <= 16'd0; v_word <= 1'b0;
        end
        else begin
            p_bck  <= u_top.bck;
            v_word <= 1'b0;
            if ((u_top.bck === 1'b1) && (p_bck === 1'b0)) begin
                if (u_top.ws_i !== ws_prev) begin
                    ws_prev <= u_top.ws_i;
                    sr      <= {15'b0, u_top.sd_i};
                    cnt     <= 5'd1;
                end
                else begin
                    sr  <= {sr[14:0], u_top.sd_i};
                    cnt <= cnt + 5'd1;
                    if (cnt == 5'd15) begin
                        word   <= {sr[14:0], u_top.sd_i};
                        v_word <= 1'b1;
                    end
                end
            end
        end
    end

    //   参考与解码各写一份；两者都按"实际完成"落盘，由 Python 自校准对齐，
    //   因为 i2s_tx 有装载/移位延迟，硬编码偏移会随配置变化而失效。
    integer fref, fdec;
    integer n_src;
    reg [15:0] ref16;
    reg        ref16_v;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) ref16_v <= 1'b0;
        else        ref16_v <= ref_v;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) ref16 <= 16'd0;
        else if (ref_v) ref16 <= ref_d[23:8];   // 与 i2s_tx 的 24→16 取高位一致
    end

    integer i;
    reg [2:0] step;

    initial begin
        $display("==============================================================");
        $display(" 顶层音频通路：tdm_top → i2s_tx → 标准接收器（端到端）");
        $display("==============================================================");

        ev_valid = 1'b0; ev_on = 1'b0; ev_note = 7'd0; ev_vel = 4'd0;
        sum_max  = 32'd0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (2000) @(posedge clk);

        //---- 起音：32 个音同时、满力度
        //   为什么要 32 个音：先生后用 8 个音试过，解码峰值只到 11372（满幅 32767），
        //   引擎内部的 sum_raw 峰值只有约 1.5 M，而饱和阈值是 acc_next ≥ 2^19 = 524288
        //   （顶层再左移 4 位）⇒ 根本没进饱和区。32 复音是出货配置的满复音，
        //   用满复音去顶，才能真的把 24 位饱和路径跑到。
        for (i = 0; i < 32; i = i + 1) begin
            ev_note  = 7'd36 + i[6:0];          // 36..67，覆盖低中音区
            ev_vel   = 4'd15;                   // 满力度
            ev_on    = 1'b1;
            ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            ev_on    = 1'b0;
            repeat (300) @(posedge clk);        // 给分配器逐个处理的时间
        end

        //---- 采集
        fref = $fopen("i2s_top_ref.txt", "w");
        fdec = $fopen("i2s_top_dec.txt", "w");
        if (fref == 0 || fdec == 0) begin
            $display("  FAIL 无法创建输出文件");
            $finish;
        end

        n_ref = 0; n_src = 0;
        while (n_ref < NSAMP) begin
            @(posedge clk);
            if (ref_v) begin
                $fdisplay(fref, "%0d", $signed(ref_d[23:8]));
                n_ref = n_ref + 1;
            end
            if (v_word) begin
                $fdisplay(fdec, "%0d", $signed(word));
                n_src = n_src + 1;
            end
        end

        $fclose(fref); $fclose(fdec);
        $display(" 参考 %0d 样本 / 解码 %0d 字", n_ref, n_src);
        //   把饱和前那一级的峰值报出来，供判据计算"离饱和还有多远"
        $display(" SUMRAW_MAX=%0d", sum_max);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #400_000_000;
        $display(" [watchdog] timeout（参考 %0d / 解码 %0d）", n_ref, n_src);
        $finish;
    end

endmodule
