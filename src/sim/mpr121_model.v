//=============================================================================
// mpr121_model.v —— MPR121 的仿真模型（仅用于验证 I2C 主机，不参与综合）
//
// 实现 MPR121 的行为子集：
//   · 7 位从机地址（由 ADDR_PIN 选择，0x5A / 0x5B / 0x5C / 0x5D）
//   · 寄存器读写，读多字节时地址自动递增
//   · 0x00 / 0x01 触摸状态寄存器由输入 touch[11:0] 驱动
//   · 0x04 起的滤波数据由 touch 派生（被摸 = 200，未摸 = 5），
//     低字节在前（与真器件一致）
//   · 支持重复起始位（复合格式读）
//
// 用法：顶层用 pullup 给 sda / scl 加上拉，把 master 与本模型并到同一对线上。
//=============================================================================
module mpr121_model #(
    parameter [6:0] ADDR = 7'h5A
)(
    input  wire        clk,
    input  wire        rst_n,
    inout  wire        sda,
    inout  wire        scl,
    input  wire [11:0] touch
);

    //-------------------------------------------------------------------------
    // 开漏输出：只有拉低或高阻
    //-------------------------------------------------------------------------
    reg  sda_drive_lo;
    assign sda = sda_drive_lo ? 1'b0 : 1'bz;

    wire sda_i = sda;
    wire scl_i = scl;

    //-------------------------------------------------------------------------
    // 边沿检测（同步到 clk）
    //-------------------------------------------------------------------------
    reg scl_q, sda_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin scl_q <= 1'b1; sda_q <= 1'b1; end
        else        begin scl_q <= scl_i; sda_q <= sda_i; end
    end

    wire scl_rise =  scl_i & ~scl_q;
    wire scl_fall = ~scl_i &  scl_q;
    wire cond_start =  scl_i & sda_q & ~sda_i;      // SCL 高时 SDA 下降
    wire cond_stop  =  scl_i & ~sda_q & sda_i;      // SCL 高时 SDA 上升

    //-------------------------------------------------------------------------
    // 寄存器堆
    //-------------------------------------------------------------------------
    reg [7:0] regs [0:127];
    reg [6:0] ptr;              // 当前寄存器指针（读多字节时递增）

    wire [7:0] touch_lo = touch[7:0];
    wire [7:0] touch_hi = {4'b0, touch[11:8]};

    // 滤波数据：被摸 = 200，未摸 = 5（派生，便于判据）
    function [9:0] filt_of;
        input integer ch;
        begin
            filt_of = touch[ch] ? 10'd200 : 10'd5;
        end
    endfunction

    integer   i;
    reg [9:0] ftmp;
    always @(posedge clk) begin
        regs[8'h00] <= touch_lo;
        regs[8'h01] <= touch_hi;
        for (i = 0; i < 12; i = i + 1) begin
            ftmp = filt_of(i);                     // 函数返回值先接住，再取位选
            regs[8'h04 + 2*i]     <= ftmp[7:0];
            regs[8'h04 + 2*i + 1] <= {6'b0, ftmp[9:8]};
        end
    end

    //-------------------------------------------------------------------------
    // 接收 / 发送状态机
    //-------------------------------------------------------------------------
    localparam [2:0] S_IDLE  = 3'd0,
                     S_ADDR  = 3'd1,
                     S_ACKA  = 3'd2,   // 地址应答
                     S_REG   = 3'd3,   // 收寄存器地址
                     S_ACKR  = 3'd4,
                     S_WDATA = 3'd5,   // 收写数据
                     S_ACKD  = 3'd6,
                     S_RDATA = 3'd7;   // 发读数据

    reg [2:0]  st;
    reg [2:0]  bitc;
    reg [7:0]  sh;
    reg        rw;              // 1 = 主设备在读
    reg        addr_hit;
    reg        ack_phase;       // 当前位是否为应答位（由主机/从机驱动）

    // 发送数据时，在 SCL 下降沿换位
    reg [7:0]  txsh;
    reg [3:0]  rbyte;           // 本次已读出的字节数（用于递增）

    // 读数据字节：由寄存器和指针决定（低字节在前）
    wire [7:0] rd_byte = regs[ptr];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= S_IDLE; bitc <= 3'd0; sh <= 8'h00; rw <= 1'b0;
            addr_hit <= 1'b0; sda_drive_lo <= 1'b0; ptr <= 7'h00;
            ack_phase <= 1'b0; txsh <= 8'h00; rbyte <= 4'd0;
            for (i = 0; i < 128; i = i + 1) regs[i] <= 8'h00;
        end else begin
            // ---------- 起始位：复位位计数，回到地址阶段 ----------
            if (cond_start) begin
                st <= S_ADDR; bitc <= 3'd0; sh <= 8'h00;
                sda_drive_lo <= 1'b0; ack_phase <= 1'b0;
            end
            // ---------- 停止位：释放总线 ----------
            else if (cond_stop) begin
                st <= S_IDLE; sda_drive_lo <= 1'b0; ack_phase <= 1'b0;
            end
            else begin
                case (st)
                    S_IDLE: sda_drive_lo <= 1'b0;

                    // 收地址
                    S_ADDR: begin
                        if (scl_rise) begin
                            sh <= {sh[6:0], sda_i};
                            bitc <= bitc + 3'd1;
                        end
                        if (scl_fall && bitc == 3'd7) begin
                            // sh 已含 8 位：高 7 位地址 + R/W
                            addr_hit <= (sh[7:1] == ADDR);
                            rw       <= sh[0];
                            st       <= S_ACKA;
                        end
                    end

                    // 地址应答（命中则拉低 SDA）
                    S_ACKA: begin
                        sda_drive_lo <= addr_hit;
                        if (scl_fall) begin
                            sda_drive_lo <= 1'b0;
                            bitc <= 3'd0; sh <= 8'h00;
                            if (!addr_hit) st <= S_IDLE;
                            else if (rw)   begin st <= S_RDATA; txsh <= rd_byte; end
                            else           st <= S_REG;
                        end
                    end

                    // 收寄存器地址
                    S_REG: begin
                        if (scl_rise) begin sh <= {sh[6:0], sda_i}; bitc <= bitc + 3'd1; end
                        if (scl_fall && bitc == 3'd7) begin
                            ptr <= sh[6:0];
                            st  <= S_ACKR;
                        end
                    end

                    S_ACKR: begin
                        sda_drive_lo <= 1'b1;
                        if (scl_fall) begin
                            sda_drive_lo <= 1'b0;
                            bitc <= 3'd0; sh <= 8'h00;
                            st   <= S_WDATA;
                        end
                    end

                    // 收写数据并写入寄存器
                    S_WDATA: begin
                        if (scl_rise) begin sh <= {sh[6:0], sda_i}; bitc <= bitc + 3'd1; end
                        if (scl_fall && bitc == 3'd7) begin
                            regs[ptr] <= sh;
                            ptr       <= ptr + 7'd1;      // 自动递增
                            st        <= S_ACKD;
                        end
                    end

                    S_ACKD: begin
                        sda_drive_lo <= 1'b1;
                        if (scl_fall) begin
                            sda_drive_lo <= 1'b0;
                            bitc <= 3'd0; sh <= 8'h00;
                            st   <= S_WDATA;
                        end
                    end

                    // 发读数据：SCL 低时换位，高时主机采样
                    S_RDATA: begin
                        if (scl_fall) begin
                            if (bitc == 3'd0) txsh <= rd_byte;      // 装载当前字节
                            else              txsh <= {txsh[6:0], 1'b0};
                            sda_drive_lo <= ~txsh[7];               // 输出最高位
                            if (bitc < 3'd7) bitc <= bitc + 3'd1;
                        end
                        if (scl_rise && bitc == 3'd7) begin
                            // 8 位已发完，下一拍进入应答采样
                            bitc <= 3'd0;
                        end
                    end
                endcase
            end
        end
    end

endmodule
