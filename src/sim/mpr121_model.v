//=============================================================================
// mpr121_model.v —— MPR121 的仿真模型（只用于验证 I2C 主机，不参与综合）
//
// 位时序约定（关键）：
//   bitc 0..7 = 数据位：接收在上升沿采样，发送在下降沿换位
//   bitc == 8 = 应答位：接收方拉低作应答；发送方释放 SDA 由对方应答
//   应答位【必须单独等它的上升沿与下降沿】，不能在数据位第 8 位之后立刻结算，
//   否则整帧会错开一位（前一版就是这样失败的）。
//
// 行为子集：
//   · 7 位从机地址（ADDR 参数）；写时第一个数据字节是寄存器地址，之后自动递增
//   · 读时按指针送数，主机每应答一次指针加一
//   · 0x00 / 0x01 触摸状态由 touch[11:0] 驱动；0x04 起滤波数据由 touch 派生
//   · 支持重复起始位（复合格式读）
//=============================================================================
module mpr121_model #(
    parameter [6:0] ADDR = 7'h5A,
    parameter       PROBE = 1'b1
)(
    input  wire        clk,
    input  wire        rst_n,
    inout  wire        sda,
    inout  wire        scl,
    input  wire [11:0] touch
);

    reg  sda_drive_lo;
    assign sda = sda_drive_lo ? 1'b0 : 1'bz;

    wire sda_i = sda;
    wire scl_i = scl;

    // ---------------- 同步与边沿检测 ----------------
    reg scl_q, sda_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin scl_q <= 1'b1; sda_q <= 1'b1; end
        else        begin scl_q <= scl_i; sda_q <= sda_i; end
    end

    wire scl_rise   =  scl_i & ~scl_q;
    wire scl_fall   = ~scl_i &  scl_q;
    wire cond_start =  scl_i & sda_q & ~sda_i;
    wire cond_stop  =  scl_i & ~sda_q & sda_i;

    // ---------------- 寄存器堆 ----------------
    reg [7:0] regs [0:127];
    reg [6:0] ptr;

    integer   i;
    reg [9:0] ftmp;
    always @(posedge clk) begin
        regs[8'h00] <= touch[7:0];
        regs[8'h01] <= {4'b0, touch[11:8]};
        for (i = 0; i < 12; i = i + 1) begin
            ftmp = touch[i] ? 10'd200 : 10'd5;
            regs[8'h04 + 2*i]     <= ftmp[7:0];
            regs[8'h04 + 2*i + 1] <= {6'b0, ftmp[9:8]};
        end
    end

    // ---------------- 状态 ----------------
    localparam [1:0] S_ADDR = 2'd0, S_RX = 2'd1, S_TX = 2'd2;

    reg [1:0] st;
    reg [3:0] bitc;
    reg [7:0] sh;
    reg [7:0] txsh;
    reg       rw;
    reg       first_wr;
    reg       ack_clked;     // 接收：应答位已被时钟
    reg       mack;          // 发送：主机在应答位上给出的电平（0 = 应答）

    wire [7:0] cur = regs[ptr];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= S_ADDR; bitc <= 4'd0; sh <= 8'h00; txsh <= 8'h00;
            rw <= 1'b0; ptr <= 7'h00; sda_drive_lo <= 1'b0; first_wr <= 1'b0;
            ack_clked <= 1'b0; mack <= 1'b1;
            for (i = 0; i < 128; i = i + 1) regs[i] <= 8'h00;
        end else begin
            if (cond_start) begin
                if (PROBE) $display("      [从机] 检测到起始位，位计数归零");
                st <= S_ADDR; bitc <= 4'd0; sh <= 8'h00;
                sda_drive_lo <= 1'b0; ack_clked <= 1'b0;
            end else if (cond_stop) begin
                sda_drive_lo <= 1'b0; bitc <= 4'd0; ack_clked <= 1'b0;
            end else begin
                case (st)
                    // ================= 收地址 =================
                    S_ADDR: begin
                        if (bitc < 4'd8) begin
                            if (scl_rise) begin
                                sh   <= {sh[6:0], sda_i};
                                bitc <= bitc + 4'd1;
                            end
                        end else begin
                            // 应答只能在 SCL 低电平期间驱动：
                            // 若在第 8 个数据位的高电平期间就拉低，整帧会偏一位
                            if (!scl_i) sda_drive_lo <= (sh[7:1] == ADDR) ? 1'b1 : 1'b0;
                            if (scl_rise) ack_clked <= 1'b1;
                            if (scl_fall && ack_clked) begin
                                ack_clked <= 1'b0;
                                bitc <= 4'd0;
                                sda_drive_lo <= 1'b0;
                                if (PROBE) $display("      [从机] 收到地址 0x%02h，%s", {sh[7:1],1'b0}, (sh[7:1]==ADDR) ? "命中" : "不命中");
                                if (sh[7:1] == ADDR) begin
                                    rw <= sh[0];
                                    if (sh[0]) begin
                                        if (PROBE) $display("      [从机] 进入发送态，寄存器 0x%02h = 0x%02h", ptr, cur);
                                        st   <= S_TX;
                                        txsh <= cur;
                                        sda_drive_lo <= ~cur[7];
                                    end else begin
                                        st <= S_RX;
                                        first_wr <= 1'b1;
                                    end
                                end
                            end
                        end
                    end

                    // ================= 收数据 =================
                    S_RX: begin
                        if (bitc < 4'd8) begin
                            if (scl_rise) begin
                                sh   <= {sh[6:0], sda_i};
                                bitc <= bitc + 4'd1;
                            end
                        end else begin
                            if (!scl_i) sda_drive_lo <= 1'b1;      // 应答位拉低（同样只在 SCL 低时）
                            if (scl_rise) ack_clked <= 1'b1;
                            if (scl_fall && ack_clked) begin
                                ack_clked <= 1'b0;
                                bitc <= 4'd0;
                                sda_drive_lo <= 1'b0;
                                if (PROBE) $display("      [从机] 收到数据字节 0x%02h（first_wr=%b）", sh, first_wr);
                                if (first_wr) begin
                                    ptr      <= sh[6:0];
                                    first_wr <= 1'b0;
                                end else begin
                                    regs[ptr] <= sh;
                                    ptr       <= ptr + 7'd1;
                                end
                            end
                        end
                    end

                    // ================= 发数据 =================
                    S_TX: begin
                        if (bitc < 4'd8) begin
                            if (scl_fall) begin
                                bitc <= bitc + 4'd1;
                                txsh <= {txsh[6:0], 1'b0};
                                sda_drive_lo <= ~txsh[6];
                            end
                        end else begin
                            sda_drive_lo <= 1'b0;                  // 释放，由主机应答
                            if (scl_rise) mack <= sda_i;           // 采样主机应答
                            if (scl_fall) begin
                                bitc <= 4'd0;
                                if (!mack) begin                     // 主机应答 -> 继续下一字节
                                    ptr  <= ptr + 7'd1;
                                    txsh <= cur;
                                    sda_drive_lo <= ~cur[7];
                                end
                            end
                        end
                    end
                endcase
            end
        end
    end

endmodule
