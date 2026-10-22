//=============================================================================
// tb_vel_timbre.v -- 力度->音色 与 独立亮度轴 的【端到端】判据（穿 tdm_top）
//
// 为什么要这条：V1-V9 验的是 vel_shape 【单元】；寄存器是否真能让它生效、
//   装载通路里的幅度是否真的变了，只有穿过 tdm_top 才能证明。
//   （本项目已经吃过"单元绿、集成路径从未跑到"的亏。）
//
// 做法：
//   1. 直接驱动 tdm_top 的事件端口（与 tb_vp7 同款）
//   2. 用层次引用戳 reg_bank 的 mem，设置 0x5C(TILT) / 0x6E(灵敏度) / 0x6D(开关)
//   3. 每个用例发一次 note-on，跟着 load_en 抓 16 条 load_amp（= 实际装载的频谱）
//   4. 落盘 vel_timbre.txt，由 Python 判据算谱心并比对
//
// 输出文件格式：每行 "标签 力度 <16 个幅度>"
//
// 2026-10-06 扩展：加入独立亮度轴（0x5C）的扫档与"跨预设"用例。
//   为什么亮度也要在【这一层】验：亮度是唯一"写寄存器 → 要经 0x63 刷新才生效"
//   的一维，它的坑全在集成路径上（刷新有没有带上、档位有没有取错区间）。
//=============================================================================
`timescale 1ns/1ps

module tb_vel_timbre;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;             // ≈27 MHz

    reg rst_n = 1'b0;

    wire [15:0] pad_bus;
    reg         uart_rx = 1'b1;
    wire        uart_tx;
    reg         ev_valid, ev_on;
    reg [6:0]   ev_note;
    reg [3:0]   ev_vel;
    reg [1:0]   preset;                     // 引脚音色（CTRL[3]=1 时由寄存器覆盖）

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(preset), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    integer    fd;
    integer    caps [0:15];
    integer    n, i, errors;
    reg [8*24-1:0] tag;

    //-------------------------------------------------------------- 抓一次装载
    task play_and_capture;
        input [3:0] v;
        input [8*24-1:0] label;
        integer k;
        begin
            // 发 note-on
            ev_note  = 7'd60;               // 固定 C4，只变力度/亮度
            ev_vel   = v;
            ev_on    = 1'b1;
            ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            ev_on    = 1'b0;

            // 跟随装载：每次 load_en 抓一条幅度
            k = 0;
            while (k < 16) begin
                @(posedge clk);
                if (u_top.u_nm.load_en) begin
                    caps[k] = u_top.u_nm.load_amp;
                    k = k + 1;
                end
            end

            // 落盘
            $fwrite(fd, "%0s %0d", label, v);
            for (i = 0; i < 16; i = i + 1) $fwrite(fd, " %0d", caps[i]);
            $fwrite(fd, "\n");
            $display("  %0s v=%0d 幅度 = %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                     label, v,
                     caps[0],caps[1],caps[2],caps[3],caps[4],caps[5],caps[6],caps[7],
                     caps[8],caps[9],caps[10],caps[11],caps[12],caps[13],caps[14],caps[15]);

            // 收尾：note-off，等声部释放
            ev_note = 7'd60; ev_on = 1'b0; ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            repeat (4000) @(posedge clk);
        end
    endtask

    //-------------------------------------------------------------- 写寄存器
    task set_reg;
        input [7:0] a;
        input [7:0] d;
        begin
            u_top.u_reg.mem[a] = d;
        end
    endtask

    initial begin
        $display("==============================================================");
        $display(" vel_timbre end-to-end criteria (through tdm_top)");
        $display("==============================================================");

        ev_valid = 1'b0; ev_on = 1'b0; ev_note = 7'd0; ev_vel = 4'd0; preset = 2'd0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (2000) @(posedge clk);

        //   实测采样率：**不要相信注释**。本项目的采样率随 NSLOT/时钟配置变过多次
        //   （39062.5 / 46875 / 48828 / 52734…），写死一个数会让频谱横轴与
        //   "期望频率"整体错位。这里直接量 sample_en 的周期（拍数）报出来，
        //   由上位机用 clk 频率换算 ⇒ 任何配置下都自洽。
        begin : meas_fs
            integer t0, t1, w;
            t0 = 0; t1 = 0; w = 0;
            while (w < 3) begin
                @(posedge clk);
                if (u_top.sample_en) begin
                    if (w == 0) t0 = $time;
                    if (w == 2) t1 = $time;
                    w = w + 1;
                end
            end
            $display(" [采样率自检] sample_en 周期 ≈ %0d ns（3 个样本）⇒ 每样本约 %0d ns",
                     (t1 - t0), (t1 - t0) / 2);
        end

        fd = $fopen("vel_timbre.txt", "w");
        if (fd == 0) begin
            $display("  FAIL  无法创建 vel_timbre.txt");
            $finish;
        end

        //-------------------------------------------------- 表加载自检
        //   为什么要在测试台里自检而不是"相信 $readmemh"：
        //   本项目已经三次栽在"运行目录缺表/表没装进去 ⇒ 全 X ⇒ 判据崩"上。
        //   表是运行期依赖，不是编译期依赖 —— 编译器不会替我们检查它。
        //   这里把两处权重表的实际内容打出来，缺表时【一眼可见】。
        $display(" [表自检] tilt_rom[112..127] 应为全 256（档位 7 = 恒等档）");
        $display("          tilt_rom[112..127] = %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                 u_top.u_nm.tilt_rom[112], u_top.u_nm.tilt_rom[113], u_top.u_nm.tilt_rom[114], u_top.u_nm.tilt_rom[115],
                 u_top.u_nm.tilt_rom[116], u_top.u_nm.tilt_rom[117], u_top.u_nm.tilt_rom[118], u_top.u_nm.tilt_rom[119],
                 u_top.u_nm.tilt_rom[120], u_top.u_nm.tilt_rom[121], u_top.u_nm.tilt_rom[122], u_top.u_nm.tilt_rom[123],
                 u_top.u_nm.tilt_rom[124], u_top.u_nm.tilt_rom[125], u_top.u_nm.tilt_rom[126], u_top.u_nm.tilt_rom[127]);
        $display("          tilt_rom[240..247]（档位 15 起首） = %0d %0d %0d %0d %0d %0d %0d %0d",
                 u_top.u_nm.tilt_rom[240], u_top.u_nm.tilt_rom[241], u_top.u_nm.tilt_rom[242], u_top.u_nm.tilt_rom[243],
                 u_top.u_nm.tilt_rom[244], u_top.u_nm.tilt_rom[245], u_top.u_nm.tilt_rom[246], u_top.u_nm.tilt_rom[247]);
        $display("          vel_wtab[255] 应为 466（0x1D2）：%0d", u_top.u_nm.u_vshape.wtab[255]);

        //-------------------------------------------------- 第一组：默认参数（恒等）
        //   寄存器保持上电默认：0x6D=0（力度->音色关）、0x6E=0（灵敏度关）、
        //   0x5C=0x70（亮度轴恒等点，由 reg_bank 初值给）
        $display(" [A] default parameters (identity expected)");
        play_and_capture(4'd2,  "ident_lo");
        play_and_capture(4'd14, "ident_hi");

        //-------------------------------------------------- 第二组：打开力度->音色
        //   0x6E 就是这一维的总开关兼灵敏度：
        //     0x00 → 关、<0x40 → 半灵敏、<0xC0 → 一等一、否则最灵敏。
        //   0x80 ⇒ 一等一 ⇒ 与"只用权重表"逐位相同（这是与单元判据 V9b 对齐的点）。
        //   0x6D/0x6B/0x6C 是历史"倾斜偏置/斜率"，改成查表后已不参与运算，
        //   这里显式写 1 只是为了证明"它们不再是开关"（写了也不改变结果）。
        set_reg(8'h6E, 8'h80);
        set_reg(8'h6D, 8'h01);
        repeat (100) @(posedge clk);
        //   诊断行：这一维出问题时，"寄存器有没有真的写进去"与"译码成了几"必须
        //   一眼可见 —— 本项目已有多次"写了寄存器但通路没接上"的经历。
        $display("  [diag] mem[0x6E]=%0d  vel_vscale=%0d  mem[0x5C]=%0d  mem[0x6D]=%0d",
                 u_top.u_reg.mem[8'h6E], u_top.vel_vscale,
                 u_top.u_reg.mem[8'h5C], u_top.u_reg.mem[8'h6D]);

        $display(" [B] velocity->timbre enabled (0x6E=0x80, sensitivity one-to-one)");
        play_and_capture(4'd2,  "tilt_lo");
        play_and_capture(4'd14, "tilt_hi");

        //-------------------------------------------------- 第三组：独立亮度轴扫档
        //   固定力度 8（中间档），只动 0x5C。恒等点是 0x70（档位 7）。
        //   为什么用 0x00/0x40/0x70/0xC0/0xFF 五档：覆盖两端 + 恒等点 + 两个中点，
        //   判据要看的是【单调性】与【恒等点确实恒等】两件事。
        //   注意一：这些用例必须在 0x6E 打开之后跑，否则"亮度轴+力度"的组合
        //     会被灵敏度那一维盖住，看不出单变量效果。
        //   注意二：0x70 这一档要与 tilt70 之外的力度档对照 —— 判据 L2 就是拿它
        //     去比"0x5C 在恒等点时，亮度维等于不存在"。
        set_reg(8'h5C, 8'h70);                  // 先回到恒等
        repeat (100) @(posedge clk);
        $display(" [C] independent brightness axis (0x5C), vel=8");
        play_and_capture(4'd8, "tilt70");
        set_reg(8'h5C, 8'h00); repeat (100) @(posedge clk);
        play_and_capture(4'd8, "tilt0");
        set_reg(8'h5C, 8'h40); repeat (100) @(posedge clk);
        play_and_capture(4'd8, "tilt40");
        set_reg(8'h5C, 8'h70); repeat (100) @(posedge clk);
        play_and_capture(4'd8, "tilt70b");      // 与 tilt70 应逐位相同（可复现性）
        set_reg(8'h5C, 8'hC0); repeat (100) @(posedge clk);
        play_and_capture(4'd8, "tiltC0");
        set_reg(8'h5C, 8'hFF); repeat (100) @(posedge clk);
        play_and_capture(4'd8, "tiltFF");

        //-------------------------------------------------- 第四组：换预设后亮度轴仍成立
        //   为什么必须换一个预设再验一次：亮度轴作用在"预设谱"之上，
        //   若接在预设之前（或只对预设 0 生效），换预设就会露馅。
        preset = 2'd2;
        repeat (200) @(posedge clk);
        set_reg(8'h5C, 8'h00); repeat (100) @(posedge clk);
        $display(" [D] brightness axis across presets (preset=2, vel=8)");
        play_and_capture(4'd8, "pre2_dark");
        set_reg(8'h5C, 8'hFF); repeat (100) @(posedge clk);
        play_and_capture(4'd8, "pre2_brt");
        preset = 2'd0;

        $fclose(fd);
        $display("  → vel_timbre.txt 已写出（15 行：恒等/力度/亮度扫档/跨预设）");
        $display("==============================================================");
        $display(" 端到端采集完成，请用 judge 脚本判定");
        $display("==============================================================");
        $finish;
    end

    initial begin
        #900_000_000;
        $display(" [watchdog] timeout");
        $finish;
    end

endmodule
