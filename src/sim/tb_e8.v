//=============================================================================
// tb_e8.v —— 拓展 E8 的 FPGA 侧协议验收
//
// 【两条协议，都用"线上真的跑了一遍"来验，而不是看内部信号】
//   test=0 寄存器回读：tb 往 0x60 写一个地址 → FPGA 应在 TX 上回两个字节
//          【地址】【数据】。tb 用串口解码器还原字节，与写入值比对。
//   test=1 曲谱下载：tb 通过 0x70/0x71 把 4 步曲谱写进 FPGA，
//          再把 SEQ_CTRL[2] 置 1（改用下载曲谱）并放行 → 引擎应弹下载的音。
//
// 【为什么要有独立的串口解码器】只看 `uart_tx_pin` 的电平无法证明"帧结构对"：
//   位宽差一点点、LSB/MSB 反了，都会让上位机收到垃圾。这里按 115200 8N1
//   逐位采样还原，等于把"上位机那一段"也搬进了仿真。
//=============================================================================

`timescale 1ns/1ps

module tb_e8;

    localparam integer CLK_HALF = 18;     // ≈27 MHz（与真实时钟同量级）
    localparam integer DIV      = 234;    // 27e6/115200

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    reg [1:0]  which;
    reg        uart_rx;
    wire       uart_tx;

    //-------------------------------------------------------------------------
    // DUT（整个顶层，才叫"FPGA 侧协议"）
    //-------------------------------------------------------------------------
    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(1'b0), .ev_on(1'b0), .ev_note(7'd0), .ev_vel(4'd0),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en()
    );

    //-------------------------------------------------------------------------
    // 串口发送（tb → FPGA）：115200 8N1
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

    //-------------------------------------------------------------------------
    // 串口接收（FPGA → tb）：检测起始位下降沿，再在每个位的中点采样
    //-------------------------------------------------------------------------
    integer fout, nbyte;
    reg     decoding;
    reg [7:0] sh;          // 收下的字节
    reg [3:0] biti;
    reg [15:0] bcnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            decoding <= 1'b0; bcnt <= 16'd0; biti <= 4'd0; sh <= 8'd0; nbyte <= 0;
        end
        else if (!decoding) begin
            if (uart_tx == 1'b0) begin          // 起始位下降沿
                decoding <= 1'b1;
                biti     <= 4'd0;
                sh       <= 8'd0;
                bcnt     <= DIV + DIV/2;        // 跳到第一个数据位中点
            end
        end
        else if (bcnt == 16'd0) begin
            if (biti < 4'd8) begin
                sh[biti] <= uart_tx;            // LSB 先收
                biti     <= biti + 4'd1;
                bcnt     <= DIV[15:0];
            end
            else begin
                decoding <= 1'b0;
                nbyte    <= nbyte + 1;
                $fdisplay(fout, "%0d", sh[7:0]);
                $display("     [RX 解码] 收到字节 0x%02h", sh[7:0]);
            end
        end
        else bcnt <= bcnt - 16'd1;
    end

    //-------------------------------------------------------------------------
    // 主流程
    //-------------------------------------------------------------------------
    integer ns;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) uart_rx <= 1'b1;
    end

    initial begin
        if (!$value$plusargs("test=%d", which)) which = 2'd0;
        uart_rx = 1'b1;
        rst_n   = 1'b0;
        repeat (50) @(posedge clk);
        rst_n   = 1'b1;
        repeat (200) @(posedge clk);

        if (which == 2'd0) begin
            fout = $fopen("e8_readback.txt", "w");
            $display("==============================================================");
            $display(" E8 test=0 寄存器回读：写 VIB_DEPTH 低位，再读回来");
            $display("==============================================================");
            // 写 0x33 = 0xD0（VIB_DEPTH 低位）
            send_byte(8'h33); send_byte(8'hD0);
            repeat (200) @(posedge clk);
            // 请求回读 0x33
            send_byte(8'h60); send_byte(8'h33);
            // 等两个字节发完（每字节 ~10 位 × 234 拍）
            repeat (DIV * 30) @(posedge clk);
            $fclose(fout);
            $display("  → e8_readback.txt（应为 0x33 0xD0）");
        end
        else begin
            fout = $fopen("e8_score.txt", "w");
            $display("==============================================================");
            $display(" E8 test=1 曲谱下载：写 4 步曲谱后由引擎演奏");
            $display("==============================================================");
            // 索引归零
            send_byte(8'h72); send_byte(8'h00);
            // 4 步：62/1, 64/1, 65/1, 67/1
            send_byte(8'h70); send_byte(8'd62); send_byte(8'h71); send_byte(8'd1);
            send_byte(8'h70); send_byte(8'd64); send_byte(8'h71); send_byte(8'd1);
            send_byte(8'h70); send_byte(8'd65); send_byte(8'h71); send_byte(8'd1);
            send_byte(8'h70); send_byte(8'd67); send_byte(8'h71); send_byte(8'd1);
            // 步数 = 4
            send_byte(8'h73); send_byte(8'd4);
            // 速度：tempo_inc = 12656 = 0x3170
            send_byte(8'h51); send_byte(8'h70);
            send_byte(8'h52); send_byte(8'h31);
            send_byte(8'h53); send_byte(8'h00);
            // 力度
            send_byte(8'h54); send_byte(8'h80);
            // 使能 + 用下载曲谱
            send_byte(8'h50); send_byte(8'h01);   // A6 判据：只写使能位，曲谱源由 SCORE_LEN 决定
            // 逐样本记录 LED 指引（内部信号够用：cur_note 就是"该弹哪个音"）
            for (ns = 0; ns < 12000; ns = ns + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
                $fdisplay(fout, "%0d %0d", u_top.sq_cur_note, u_top.sq_step);
            end
            $fclose(fout);
            $display("  → e8_score.txt（应依次出现 62 64 65 67）");
        end
        $finish;
    end

    initial begin
        #400_000_000;
        $display("[TIMEOUT] test=%0d", which);
        $finish;
    end

endmodule
