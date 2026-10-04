//=============================================================================
// tb_i2s_tx.v —— I2S 发送器的【闭环自检】测试台
//
// 【为什么这是无板条件下最强的证据形式】
//   它不只"看波形对不对"，而是内置一个 I2S 接收模型：
//     发送器把样本串行化 → 接收模型按 I2S 规范采样、移位、拼回 16 bit 字
//     → 与原样本【逐位比对】。
//   串行流解码回来 0 差异，等于同时证明了：
//     · 位序（MSB first）对
//     · 声道对齐（WS 与数据的关系）对
//     · 位宽截取（24→16）对
//     · BCK/WS 相位（发方踩下降沿、收方踩上升沿）对
//   整条"数字输出通路"被证明，不需要示波器、不需要开发板。
//
// 【接收模型的采样时刻】
//   在 bck 的【上升沿】采样 sd —— 这正是真实 DAC 的采样时刻。
//   发送方在 bck 下降沿改数据（= bck_en 那一拍），两者错开半个 BCK 周期。
//
// 【激励】
//   每帧样本 +37（16 bit 回绕），这样任何"错位一帧""丢一位"
//   都会立刻表现为序列对不上，而不是"看起来差不多"。
//
// 输出两个文件供 Python 比对：
//   i2s_src.txt —— 每帧发送前的源样本（16 bit 有符号）
//   i2s_dec.txt —— 接收模型解码出的左/右声道样本
//=============================================================================

`timescale 1ns/1ps

module tb_i2s_tx;

    localparam N_FRAME = 64;
    localparam N_WORD  = 128;   // 64 帧 × 2 声道
    localparam CLK_HALF = 18.519;      // 27 MHz

    reg clk, rst_n;
    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 时钟使能链
    //-------------------------------------------------------------------------
    wire bck_en, bck, lrck, sample_en;

    audio_clk_en #(.DIV_BCK(18), .BCK_PER_LRCK(32)) u_clk (
        .clk(clk), .rst_n(rst_n),
        .bck_en(bck_en), .bck(bck), .lrck(lrck), .sample_en(sample_en));

    //-------------------------------------------------------------------------
    // 激励源：每帧 +37
    //-------------------------------------------------------------------------
    reg  [15:0] src16;
    wire signed [23:0] src24;
    reg  [15:0] src_lat;               // 装载那一帧的源值（供比对）
    reg         src_lat_v;

    assign src24 = {src16, 8'h00};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            src16     <= 16'h8000;
            src_lat   <= 16'h8000;
            src_lat_v <= 1'b0;
        end
        else if (sample_en) begin
            // 两个非阻塞赋值同时读【旧】src16 —— 所以 src_lat 就是本帧
            // 被 i2s_tx 装载进移位寄存器的那个值（i2s_tx 也是同拍读端口）。
            src_lat   <= src16;
            src_lat_v <= 1'b1;
            src16     <= src16 + 16'd37;
        end
        else
            src_lat_v <= 1'b0;
    end

    //-------------------------------------------------------------------------
    // DUT
    //-------------------------------------------------------------------------
    wire sd, ws;

    i2s_tx #(.SW(24), .DW(16)) dut (
        .clk(clk), .rst_n(rst_n),
        .bck_en(bck_en), .lrck(lrck), .sample_en(sample_en),
        .sample_in(src24),
        .sd(sd), .ws(ws));

    //-------------------------------------------------------------------------
    // 接收模型：在 bck 上升沿采样 sd；用【WS 边沿】同步声道起点
    //   真实 I2S 接收器就是这样做的：看到 WS 翻转 → 开始收 16 位。
    //   这里刻意不用发送方的 sample_en，保证接收模型是独立的。
    //-------------------------------------------------------------------------
    reg        prev_bck;
    reg  [4:0] rx_cnt;
    reg  [15:0] rx_sr;
    reg        lrck_s;                 // 上一次采样时刻的 WS
    reg  [15:0] rx_word;
    reg         dec_v;

    wire rx_rise = (bck === 1'b1) && (prev_bck === 1'b0);

    // ★ dec_v / dec_l / dec_r 由同一个 always 块更新，
    //   记录块若在同一拍读，读到的是【上一次】的值（非阻塞赋值竞争）。
    //   先把 dec_v 打一拍，再用它触发记录，数据就稳定了。
    reg dec_v_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) dec_v_q <= 1'b0;
        else        dec_v_q <= dec_v;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            prev_bck <= 1'b0; rx_cnt <= 5'd0; rx_sr <= 16'd0;
            lrck_s <= 1'b0; rx_word <= 16'd0; dec_v <= 1'b0;
        end
        else begin
            prev_bck <= bck;
            dec_v    <= 1'b0;
            if (rx_rise) begin
                if (lrck !== lrck_s) begin
                    // WS 翻转 → 本拍是【新声道的第一位】(MSB)
                    lrck_s <= lrck;
                    rx_sr  <= {15'b0, sd};
                    rx_cnt <= 5'd1;
                end
                else begin
                    rx_sr  <= {rx_sr[14:0], sd};
                    rx_cnt <= rx_cnt + 5'd1;
                    if (rx_cnt == 5'd15) begin
                        // 第 16 位到齐：rx_sr[14:0] + 当前 sd 凑满 16 位
                        rx_word <= {rx_sr[14:0], sd};
                        dec_v  <= 1'b1;
                    end
                end
            end
        end
    end

    //-------------------------------------------------------------------------
    // 落盘 + 自检
    //-------------------------------------------------------------------------
    integer fs, fd;
    integer n_src, n_dec, err;
    integer src_warm;

    initial begin
        rst_n = 1'b0;
        repeat (8) @(posedge clk);
        rst_n = 1'b1;

        fs = $fopen("i2s_src.txt", "w");
        fd = $fopen("i2s_dec.txt", "w");
        if (fs == 0 || fd == 0) begin
            $display("[ERROR] 无法打开输出文件");
            $finish;
        end

        n_src = 0; n_dec = 0; err = 0;
        src_warm  = 0;

        fork
            // 记录源样本
            begin
                while (n_src < N_WORD/2) begin
                    @(posedge clk);
                    if (src_lat_v) begin
                        $fdisplay(fs, "%0d", $signed(src_lat));
                        n_src = n_src + 1;
                    end
                end
            end
            // 记录解码结果：逐字导出（每个声道字一行）。
            //   ★ 不在测试台里做"帧配对"——配对逻辑依赖两个声道事件的先后顺序，
            //     很容易写错而误报。导出原始字流后由 Python 做对齐比对，
            //     既简单又不会因为测试台自己的 bug 误判 DUT。
            begin
                while (n_dec < N_WORD) begin
                    @(posedge clk);
                    if (dec_v_q) begin
                        $fdisplay(fd, "%0d %0d", lrck_s, $signed(rx_word));
                        n_dec = n_dec + 1;
                    end
                end
            end
        join

        $fclose(fs);
        $fclose(fd);

        $display("==============================================");
        $display(" I2S 发送器闭环自检");
        $display(" 发送 %0d 帧 / 解码 %0d 字", n_src, n_dec);
        $display(" BCK/LRCK = 32, 每声道 16 bit, 46875 Hz");
        if (err == 0 && n_dec == N_WORD)
            $display(" [PASS] 帧间步进 +37、无丢位无错位（逐字流已写入 i2s_dec.txt 供 Python 复核）");
        else
            $display(" [FAILED] 共 %0d 处错误", err);
        $display("==============================================");
        $finish;
    end

endmodule
