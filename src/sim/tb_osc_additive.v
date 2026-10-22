//=============================================================================
// tb_osc_additive.v —— 加法合成引擎的纯仿真验证
//
// 目的：证明【不依赖任何硬件】也能验证核心 DSP 设计。
//
// 跑两个测试，各自的样本 dump 到文件：
//   测试 A "harmonic"   : 8 个泛音，比例 1,2,3,4,5,6,7,8 （纯谐波）
//   测试 B "inharmonic" : 只把第 3 个泛音改成 2.76 倍，其余 7 个完全不动
//
// 为什么这样设计：
//   如果 B 的频谱里"只有第 3 个峰移动了"，就直接证明了
//   【每个泛音拥有独立的相位累加器与频率控制】—— 这正是赛题对
//   "独立振荡器"的定义，也是拿吞吐量指标的前提。
//
// 模型约定：1 个时钟 = 1 个样本，时钟周期 20 µs -> fs = 50 kHz
//=============================================================================

`timescale 1ns/1ps

module tb_osc_additive;

    localparam NUM_PART  = 8;
    localparam PHASE_W   = 24;
    localparam AMP_W     = 8;
    localparam N_SAMPLES = 12000;      // 每次测试 0.24 秒

    // 时钟：半周期 10 µs -> 周期 20 µs -> fs = 50 kHz
    localparam CLK_HALF  = 10000;      // 单位 ns

    reg clk;
    reg rst_n;

    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 激励表：从 .hex 读入（由 Python 生成）
    //   inc_arr[0..7]  = 谐波比例
    //   inc_arr[8..15] = 非谐波比例
    //-------------------------------------------------------------------------
    reg [PHASE_W-1:0] inc_arr [0:2*NUM_PART-1];
    reg [AMP_W-1:0]   amp_arr [0:NUM_PART-1];

    initial begin
        $readmemh("inc.hex", inc_arr);
        $readmemh("amp.hex", amp_arr);
    end

    //-------------------------------------------------------------------------
    // 把数组拼成展平向量（Verilog-2001 不支持数组端口）
    //-------------------------------------------------------------------------
    reg  [NUM_PART*PHASE_W-1:0] inc_flat;
    wire [NUM_PART*AMP_W-1:0]   amp_flat;

    genvar ga;
    generate
        for (ga = 0; ga < NUM_PART; ga = ga + 1) begin : G_FLAT
            assign amp_flat[ga*AMP_W +: AMP_W] = amp_arr[ga];
        end
    endgenerate

    //-------------------------------------------------------------------------
    // DUT
    //-------------------------------------------------------------------------
    wire signed [23:0] sample_out;

    osc_additive #(
        .NUM_PARTIALS (NUM_PART),
        .PHASE_W      (PHASE_W),
        .TAB_AW       (8),
        .AMP_W        (AMP_W),
        .OUT_W        (24)
    ) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .sample_en  (1'b1),          // 每拍都产生一个样本
        .inc_flat   (inc_flat),
        .amp_flat   (amp_flat),
        // ---------- 包络：本测试台走【旁路】，以保持与 v2/v3 基线逐字节可比 ----------
        // env_en=0 时 有效幅度 = amp<<8，核算 (x*(amp<<8))>>>16 ≡ (x*amp)>>>8，
        // 与加包络之前逐位一致。包络本身的行为由 tb_osc_env.v 单独验证。
        .env_en     (1'b0),
        .gate       (1'b0),
        .a_inc      (16'd0),
        .d_inc      (16'd0),
        .d_m        (2'd0),
        .d_k        (5'd0),
        .s_lvl      (16'd0),
        .r_inc      (16'd0),
        .r_m        (2'd0),
        .r_k        (5'd0),
        .env_cutoff (16'd0),
        .exp_mode   (1'b1),
        .sample_out (sample_out)
    );

    //-------------------------------------------------------------------------
    // 测试流程
    //-------------------------------------------------------------------------
    integer fh;
    integer n;
    integer gi;

    task run_case;
        input [8*40-1:0] fname;      // 输出文件名（最多 40 字符，必须够长否则会被截断！）
        input integer    inc_base;   // 在 inc_arr 里的起始下标
        begin
            // 装载本次用例的 8 个频率增量
            for (gi = 0; gi < NUM_PART; gi = gi + 1)
                inc_flat[gi*PHASE_W +: PHASE_W] = inc_arr[inc_base + gi];

            // 复位若干拍，让相位从 0 开始
            rst_n = 1'b0;
            repeat (4) @(posedge clk);
            rst_n = 1'b1;
            @(posedge clk);

            fh = $fopen(fname, "w");
            if (fh == 0) begin
                $display("[ERROR] 无法打开输出文件 %0s", fname);
                $finish;
            end

            for (n = 0; n < N_SAMPLES; n = n + 1) begin
                @(posedge clk);
                #1;                                   // 等组合逻辑稳定
                $fdisplay(fh, "%0d", sample_out);
            end

            $fclose(fh);
            $display("[DONE] %0s : 写了 %0d 个样本", fname, N_SAMPLES);
        end
    endtask

    initial begin
        $dumpfile("osc_additive.vcd");
        $dumpvars(0, tb_osc_additive);

        rst_n   = 1'b0;
        inc_flat = {(NUM_PART*PHASE_W){1'b0}};

        $display("==============================================");
        $display(" 加法合成引擎 —— 纯仿真验证");
        $display(" fs = 50 kHz, 泛音数 = %0d", NUM_PART);
        $display("==============================================");

        // 测试 A：纯谐波
        run_case("samples_harmonic.txt",   0);

        // 测试 B：第 3 个泛音改为非谐波（2.76 倍）
        run_case("samples_inharmonic.txt", NUM_PART);

        $display("==============================================");
        $display(" 仿真结束");
        $display("==============================================");
        $finish;
    end

endmodule
