//=============================================================================
// tb_fxinit.v —— 最小复现：fx_delay 的线缓冲初值到底有没有生效
//   (a) 直接例化 fx_delay
//   (b) 经 tdm_top 例化 fx_delay
//   两者打印 line[0]，用来分辨"初值块没跑"还是"层次/实例问题"。
//=============================================================================
`timescale 1ns/1ps

module tb_fxinit;
    reg clk = 0, rst_n;
    always #19 clk = ~clk;

    // (a) 直接例化
    wire signed [23:0] da;
    fx_delay #(.DW(16), .AW(11), .CHO_BASE(1024)) u_a (
        .clk(clk), .rst_n(rst_n), .sample_en(1'b0), .din(24'sd0),
        .dry_en(1'b1), .dly_en(1'b0), .cho_en(1'b0), .rev_en(1'b0),
        .wet_sh(3'd0), .dly_len(16'd1500), .fb_q8(8'd0),
        .cho_rate(16'd0), .cho_depth(16'd0), .rev_fb_q8(8'd0), .rev_damp(3'd3),
        .dout(da), .tap_dbg()
    );

    // (b) 经顶层例化
    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(1'b0), .ev_on(1'b0), .ev_note(7'd0), .ev_vel(4'd0),
        .preset(2'd1), .test_mode(1'b0),
        .uart_rx_pin(1'b1), .uart_tx_pin(),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en()
    );

    // (c) 专门测"负样本"：干声开、湿声关，喂一个负的直流电平
    //     为什么必须单独测：**所有既有测试都用正冲激** ，
    //       所以"干+湿相加时负数被零扩展"这个 bug 一直没被抓到
    //       （它在音频判据里表现为输出直流 +50%、49% 削顶）。
    reg signed [23:0] neg_dc;
    wire signed [23:0] dc_out;

    // (c) 用的样本节拍（必须先声明：Verilog 端口连线要求先声明后使用）
    reg [9:0] pc_c;
    wire sample_en_c = (pc_c == 10'd511);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                    pc_c <= 10'd0;
        else if (pc_c == 10'd511)      pc_c <= 10'd0;
        else                           pc_c <= pc_c + 10'd1;
    end

    fx_delay #(.DW(16), .AW(11), .CHO_BASE(1024), .FLUSH_LEN(64)) u_c (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en_c), .din(neg_dc),
        .dry_en(1'b1), .dly_en(1'b0), .cho_en(1'b0), .rev_en(1'b0),
        .wet_sh(3'd0), .dly_len(16'd1500), .fb_q8(8'd0),
        .cho_rate(16'd0), .cho_depth(16'd0), .rev_fb_q8(8'd0), .rev_damp(3'd3),
        .dout(dc_out), .tap_dbg()
    );

    initial begin
        rst_n = 1'b0;
        repeat (100) @(posedge clk);
        rst_n = 1'b1;
        repeat (100) @(posedge clk);
        $display("[直接例化] line[0]=%0d line[100]=%0d",
                 $signed(u_a.line[0]), $signed(u_a.line[100]));
        $display("[顶层内]   line[0]=%0d line[100]=%0d",
                 $signed(u_top.u_fx.line[0]), $signed(u_top.u_fx.line[100]));

        // (c) 负样本：干声 = −1000000，湿声全关 ⇒ 输出必须仍是【负数】
        neg_dc = -24'sd1000000;
        repeat (3) @(posedge sample_en_c);
        $display("[负样本] din=%0d → dout=%0d（必须为负；若变成大正数 = 符号 bug 复发）",
                 $signed(neg_dc), $signed(dc_out));
        if (dc_out > 0) $display("  ✗✗ 符号 bug 复发！");
        else            $display("  ✓ 负数保持为负（干湿混音的符号正确）");
        $finish;
    end
endmodule
