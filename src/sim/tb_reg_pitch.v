//=============================================================================
// tb_reg_pitch.v —— 寄存器映射 + 实时变调（必须项 M6）的验收
//
// 验收标准：
//   P1 写进去能读回来     ：寄存器读回值与写入值一致
//   P2 ★ 运行时改音高生效 ：写一个新的 inc，输出频率随之改变
//   P3 ★ 变调【相位连续】 ：改音高的那一拍【不允许出现波形跳变】
//                            （相位累加器的相位不被清零，只是增量变了）
//   P4 复位不清参数       ：拉低再拉高 rst_n，音高寄存器内容不变
//
// 【P3 为什么是关键】
//   如果变调时把相位清零，波形会在那一拍从"当前值"跳回 0 ——
//   听感上就是"啪"的一声咔哒。这是新手做变调最容易踩的坑。
//   本测试台直接量"跳变幅度"，与正常波形的逐样本变化对比。
//
// 模型约定：1 个时钟 = 1 个样本，周期 20 µs → fs = 50 kHz
//   inc = round(f × 2^24 / 50000)
//     440 Hz → 147640
//     660 Hz → 221459
//=============================================================================

`timescale 1ns/1ps

module tb_reg_pitch;

    localparam NV = 4, NPART = 8, PHASE_W = 24, AMP_W = 8, OUT_W = 24;
    localparam CLK_HALF = 10000;      // 20 µs → fs = 50 kHz
    localparam N_SEG    = 4096;       // 每段样本数

    reg clk, rst_n;
    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 寄存器堆
    //-------------------------------------------------------------------------
    reg        wr_en;
    reg  [7:0] wr_addr, wr_data;
    reg        rd_en;
    reg  [7:0] rd_addr;
    wire [7:0] rd_data;
    wire [256*8-1:0] R;

    reg_bank #(.AW(8), .DW(8), .NW(256)) u_reg (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(rd_en), .rd_addr(rd_addr), .rd_data(rd_data),
        .regs_flat(R)
    );

    //-------------------------------------------------------------------------
    // 从寄存器切片出合成引擎要的参数
    //   ★ Verilog 不允许对切片再取切片（R[a +: 8][6:5] 是非法的），
    //     所以先落到具名 wire 上再取位。
    //-------------------------------------------------------------------------
    reg  [NV*NPART*PHASE_W-1:0] inc_all;
    reg  [NV*NPART*AMP_W-1:0]   amp_all;

    genvar g;
    generate
        for (g = 0; g < NV*NPART; g = g + 1) begin : G_SLICE
            // 音高：小端 24 位。索引用十进制常量，避免 8 位字面量与 genvar 混算被截断。
            always @(*) begin
                inc_all[g*PHASE_W +: PHASE_W] =
                    { R[(16 + g*3 + 2)*8 +: 8],
                      R[(16 + g*3 + 1)*8 +: 8],
                      R[(16 + g*3 + 0)*8 +: 8] };
                amp_all[g*AMP_W +: AMP_W] = R[(112 + g)*8 +: 8];
            end
        end
    endgenerate

    wire [15:0] r_a_inc  = { R[3*8 +: 8], R[2*8 +: 8] };
    wire [15:0] r_s_lvl  = { R[5*8 +: 8], R[4*8 +: 8] };
    wire [15:0] r_cutoff = { R[9*8 +: 8], R[8*8 +: 8] };
    wire [15:0] r_d_inc  = { R[11*8 +: 8], R[10*8 +: 8] };
    wire [15:0] r_r_inc  = { R[13*8 +: 8], R[12*8 +: 8] };
    wire [7:0]  r_d_mk   = R[7*8 +: 8];
    wire [7:0]  r_r_mk   = R[6*8 +: 8];
    wire [7:0]  r_mix    = R[1*8 +: 8];
    wire [7:0]  r_ctrl   = R[0*8 +: 8];
    wire [1:0]  r_d_m    = r_d_mk[6:5];
    wire [4:0]  r_d_k    = r_d_mk[4:0];
    wire [1:0]  r_r_m    = r_r_mk[6:5];
    wire [4:0]  r_r_k    = r_r_mk[4:0];
    wire [2:0]  r_gain   = r_mix[2:0];
    wire [1:0]  r_shift  = r_mix[4:3];
    wire        r_ctl_env  = r_ctrl[1];
    wire [7:0]  r_emode    = R[14*8 +: 8];
    wire        r_exp      = r_emode[0];

    //-------------------------------------------------------------------------
    // 合成引擎（单声部出声：只给声部 0 的泛音 0 非零幅度）
    //-------------------------------------------------------------------------
    wire signed [OUT_W-1:0] sample;
    wire [NV*OUT_W-1:0]     voice_out;

    synth_top #(
        .NV(NV), .NPART(NPART), .PHASE_W(PHASE_W),
        .AMP_W(AMP_W), .OUT_W(OUT_W)
    ) u_synth (
        .clk(clk), .rst_n(rst_n), .sample_en(1'b1),
        .inc_all(inc_all), .amp_all(amp_all),
        .gate({NV{1'b1}}),
        .env_en(r_ctl_env),
        .a_inc(r_a_inc), .d_inc(r_d_inc), .d_m(r_d_m), .d_k(r_d_k),
        .s_lvl(r_s_lvl), .r_inc(r_r_inc), .r_m(r_r_m), .r_k(r_r_k),
        .env_cutoff(r_cutoff), .exp_mode(r_exp),
        .mix_gain_up(r_gain), .mix_shift(r_shift),
        .sample_out(sample), .voice_out(voice_out)
    );

    //-------------------------------------------------------------------------
    // 写寄存器任务
    //-------------------------------------------------------------------------
    task wr;
        input [7:0] a;
        input [7:0] d;
        begin
            @(negedge clk);
            wr_en = 1'b1; wr_addr = a; wr_data = d;
            @(negedge clk);
            wr_en = 1'b0;
        end
    endtask

    // 写 24 位音高（小端 3 字节）
    task wr_pitch;
        input integer idx;          // 0..31
        input [23:0]  v;
        begin
            wr(8'h10 + idx*3 + 0, v[7:0]);
            wr(8'h10 + idx*3 + 1, v[15:8]);
            wr(8'h10 + idx*3 + 2, v[23:16]);
        end
    endtask

    // 写 16 位（小端 2 字节）
    task wr16;
        input [7:0] a;
        input [15:0] v;
        begin
            wr(a, v[7:0]);
            wr(a + 1'b1, v[15:8]);
        end
    endtask

    //-------------------------------------------------------------------------
    integer f, n, err;
    reg [7:0] rb;

    initial begin
        wr_en = 0; wr_addr = 0; wr_data = 0; rd_en = 0; rd_addr = 0;
        rst_n = 1'b0;
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        repeat (4) @(posedge clk);

        err = 0;
        $display("==============================================");
        $display(" 寄存器映射 + 实时变调自检  (M6)");
        $display("==============================================");

        //---------------- 准备：只让声部 0 的第 1 个泛音发声 ----------------
        // 其余声部/泛音幅度清零
        begin : CLR
            integer t;
            for (t = 0; t < NV*NPART; t = t + 1)
                wr(8'h70 + t, 8'd0);
        end
        wr(8'h70, 8'd120);                  // 声部0 泛音0 幅度
        wr(8'h00, 8'h03);                   // CTRL：门=1，包络=1
        wr16(8'h02, 16'd32768);             // 起音 1 拍到位
        wr16(8'h04, 16'd32768);             // 延音 = 满幅（恒定幅度，便于测频率）
        wr(8'h0E, 8'd1);

        //---------------- P1：写进去能读回来 ----------------
        wr(8'h70, 8'd123);
        rd_en = 1'b1; rd_addr = 8'h70;
        @(posedge clk); @(posedge clk);
        rb = rd_data;
        rd_en = 1'b0;
        if (rb !== 8'd123) begin
            err = err + 1; $display("  [FAIL] P1 回读 %0d != 写入 123", rb);
        end else
            $display("  [P1] 寄存器回读一致 (0x70 -> %0d)", rb);

        //---------------- P2/P3：变调 ----------------
        wr_pitch(0, 24'd147640);            // 440 Hz
        repeat (64) @(posedge clk);         // 让包络与流水线稳定

        f = $fopen("pitch.txt", "w");
        // ★ 必须用 fork 让【写寄存器】与【采样本】并行：
        //   wr_pitch 是阻塞任务，若写在采样循环里，
        //   采样会在那几个时钟里停下来 —— 文件里就出现
        //   【时间上的空模】而不是波形跳变，会误判成"相位被清零"。
        //   （这个假象已经误报过一次，记在此处。）
        fork
            begin : DUMP
                for (n = 0; n < 3*N_SEG; n = n + 1) begin
                    @(posedge clk); #1; $fdisplay(f, "%0d", sample);
                end
            end
            begin : PITCH_WR
                repeat (N_SEG) @(posedge clk);
                wr_pitch(0, 24'd221459);        // 变到 660 Hz
                repeat (N_SEG) @(posedge clk);
                wr_pitch(0, 24'd147640);        // 变回 440 Hz
            end
        join
        $fclose(f);
        $display("  [P2/P3] 变调序列已写入 pitch.txt（440 -> 660 -> 440）");
        $display("          段边界样本下标: %0d, %0d", N_SEG, 2*N_SEG);

        //---------------- P4：复位不清参数 ----------------
        rst_n = 1'b0;
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        repeat (4) @(posedge clk);
        rd_en = 1'b1; rd_addr = 8'h70;
        @(posedge clk); @(posedge clk);
        rb = rd_data;
        rd_en = 1'b0;
        if (rb !== 8'd123) begin
            err = err + 1; $display("  [FAIL] P4 复位后寄存器被清掉了 (%0d)", rb);
        end else
            $display("  [P4] 复位后寄存器内容保留 (0x70 仍为 %0d)", rb);

        $display("==============================================");
        if (err == 0)
            $display(" P1/P4 通过；请用 Python 复核 P2/P3（频率与相位连续性）");
        else
            $display(" [FAILED] 共 %0d 处错误", err);
        $display("==============================================");
        $finish;
    end

endmodule
