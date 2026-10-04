//=============================================================================
// tb_test_mode.v —— RTL 内置测试模式的验收（F1 + R3）
//
// 验收标准：
//   T1 模式 1（固定谱峰）：32 个泛音各占一个等间隔频率格，
//        FFT 应当出现【恰好 32 个独立谱峰】，位置 = 400, 800, ..., 12800 Hz
//   T2 模式 2（随机自证）：LFSR 随机开关泛音 →
//        两个时间窗的频谱【应当不同】（预录做不到"每次都变"）
//   T3    测试模式走的是完整合成通路（相位累加器+查表+包络+加法树+混音），
//        不是旁路 —— 这一点从 RTL 结构上就能看出来，本测试台负责确认它确实出声
//
// 模型约定：1 个时钟 = 1 个样本，周期 21.3333 µs → fs = 46875 Hz
//   （与真实时钟链 27MHz/18/32 完全一致，所以 STEP_INC=143166 正好对应 400 Hz）
//=============================================================================

`timescale 1ns/1ps

module tb_test_mode;

    localparam NV      = 4;
    localparam NPART   = 8;
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam OUT_W   = 24;
    localparam NTONE   = NV * NPART;      // 32
    localparam N_SAMP  = 8192;            // FFT 点数 → 分辨率 5.72 Hz
    localparam CLK_HALF= 10666.667;       // 周期 21.3333 µs → fs = 46875 Hz

    reg clk, rst_n;
    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 测试模式参数发生器
    //-------------------------------------------------------------------------
    reg  [1:0]  mode;
    reg  [31:0] seed_free;

    wire [NV*NPART*PHASE_W-1:0] inc_t;
    wire [NV*NPART*AMP_W-1:0]   amp_t;
    wire                        rnd_active;

    // 自由计数器：模拟"不受复位清零"，播种用
    always @(posedge clk) seed_free <= seed_free + 32'd1;

    test_mode #(
        .NV(NV), .NPART(NPART), .PHASE_W(PHASE_W),
        .STEP_INC(24'd143166),      // 400 Hz @ fs=46875
        .TONE_AMP(8'd60)
    ) u_tm (
        .clk(clk), .rst_n(rst_n), .mode(mode), .seed_free(seed_free),
        .inc_out(inc_t), .amp_out(amp_t), .rnd_active(rnd_active)
    );

    //-------------------------------------------------------------------------
    // 合成引擎（测试模式只是换了 inc/amp，通路本身不动）
    //-------------------------------------------------------------------------
    wire signed [OUT_W-1:0] sample;
    wire [NV*OUT_W-1:0]     voice_out;

    synth_top #(
        .NV(NV), .NPART(NPART), .PHASE_W(PHASE_W),
        .AMP_W(AMP_W), .OUT_W(OUT_W)
    ) u_synth (
        .clk         (clk),
        .rst_n       (rst_n),
        .sample_en   (1'b1),
        .inc_all     (inc_t),
        .amp_all     (amp_t),
        .gate        ({NV{1'b1}}),      // 全部按住
        .env_en      (1'b1),            // ★ 包络【不旁路】：测试模式也走完整通路
        .a_inc       (16'd32768),       // 起音 1 拍到位
        .d_inc       (16'd0),
        .d_m         (2'd0),
        .d_k         (5'd0),
        .s_lvl       (16'd32768),       // 延音 = 满幅（恒定幅度 → 谱线干净）
        .r_inc       (16'd0),
        .r_m         (2'd0),
        .r_k         (5'd0),
        .env_cutoff  (16'd0),
        .exp_mode    (1'b1),
        .mix_gain_up (3'd0),            // 测试模式不放大，便于数峰
        .mix_shift   (2'd0),
        .sample_out  (sample),
        .voice_out   (voice_out)
    );

    //-------------------------------------------------------------------------
    integer f1, f2a, f2b;
    integer n;

    // 采一段并写文件
    task cap;
        input integer fh;
        input integer nsamp;
        integer k;
        begin
            for (k = 0; k < nsamp; k = k + 1) begin
                @(posedge clk);
                #1;
                $fdisplay(fh, "%0d", sample);
            end
        end
    endtask

    initial begin
        seed_free = 32'h1234_5678;
        rst_n     = 1'b0;
        mode      = 2'd0;
        repeat (8) @(posedge clk);
        rst_n     = 1'b1;
        repeat (32) @(posedge clk);       // 等包络稳定 + 流水线填满

        $display("==============================================");
        $display(" 测试模式自检  fs=46875  NTONE=%0d", NTONE);
        $display("==============================================");

        //---------------- T1：固定谱峰 ----------------
        mode = 2'd1;
        repeat (16) @(posedge clk);
        f1 = $fopen("tm_fixed.txt", "w");
        cap(f1, N_SAMP);
        $fclose(f1);
        $display(" [T1] 固定谱峰 → tm_fixed.txt");

        //---------------- T2：随机自证（两个时间窗）----------------
        mode = 2'd2;
        repeat (16) @(posedge clk);
        f2a = $fopen("tm_rnd_a.txt", "w");
        cap(f2a, N_SAMP);
        $fclose(f2a);
        // 等随机序列推进若干次（RND_PERIOD=2344 拍 → 跳过 4 个周期）
        repeat (4 * 2344) @(posedge clk);
        f2b = $fopen("tm_rnd_b.txt", "w");
        cap(f2b, N_SAMP);
        $fclose(f2b);
        $display(" [T2] 随机模式两个时间窗 → tm_rnd_a.txt / tm_rnd_b.txt");

        $display("==============================================");
        $display(" 仿真结束，请用 Python 做 FFT 数峰与比对");
        $display("==============================================");
        $finish;
    end

endmodule
