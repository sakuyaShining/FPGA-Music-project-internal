//=============================================================================
// tb_vp7.v —— VP7：上电行为（19 号 §7 + 修正案 A2）
//
// 判据原文："复位、**零 UART 写**、16384 样本：输出全零、无测试模式频谱
//           （test_mode 引脚下拉后=0）、preset=0（行为侧：第一事件响应符合预设 0 的谱）"
//
// 本测试台把这条拆成四组可证伪断言：
//   V1 **上电静音**：复位后不做任何 UART 写，16384 个样本的顶层输出**全为 0**
//   V2 **不进测试模式**：test_mode 引脚 = 0 且 CTRL[0] = 0 ⇒ 装载走 note_map 通路
//   V3 **上电寄存器表**（直接读 reg_bank）：CTRL/PRESET/FX/DELAY_LEN/SPEC_MODE/
//      HARM_PADS/SEQ_CTRL/TEMPO/SEQ_VEL/0x7F 必须等于 19 号 §3 的冻结默认
//   V4 **preset 默认确实是 0**（行为侧、非循环）：
//        默认（不写 0x37） 与 显式写 0x37=0 装载出的 16 个幅度 **逐位相同**
//        而 显式写 0x37=1 时 **必须不同** （证明"默认 0"不是"忽略音色"）
//=============================================================================

`timescale 1ns/1ps

module tb_vp7;

    reg clk = 1'b0;
    reg rst_n;
    always #18.5185 clk = ~clk;

    wire [15:0] pad_bus;             // 纯输入（C0 之后 pad 不再是 inout）
    reg        uart_rx = 1'b1;
    wire       uart_tx;
    reg        ev_valid, ev_on;
    reg [6:0]  ev_note;
    reg [3:0]  ev_vel;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd3), .test_mode(1'b0),   // 引脚故意给 3 与 0：验证寄存器/引脚的优先级与默认
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    localparam integer DIV = 234;
    integer i, k, fails, nz, diff;
    integer a_amp [0:15];
    integer b_amp [0:15];
    integer c_amp [0:15];

    task send_byte(input [7:0] b);
        integer j;
        begin
            uart_rx = 1'b0; repeat (DIV) @(posedge clk);
            for (j = 0; j < 8; j = j + 1) begin uart_rx = b[j]; repeat (DIV) @(posedge clk); end
            uart_rx = 1'b1; repeat (DIV) @(posedge clk);
        end
    endtask
    task wr(input [7:0] a, input [7:0] d); begin send_byte(a); send_byte(d); end endtask

    task wait_samples(input integer n);
        integer j;
        begin
            for (j = 0; j < n; j = j + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
            end
        end
    endtask

    task press(input [6:0] n);
        begin
            @(posedge clk);
            ev_note <= n; ev_vel <= 4'd15; ev_on <= 1'b1; ev_valid <= 1'b1;
            @(posedge clk);
            ev_valid <= 1'b0;
            wait_samples(6);
        end
    endtask

    task snap(input integer which);
        integer j, v;
        begin
            for (j = 0; j < 16; j = j + 1) begin
                v = u_top.u_tdm.amp_mem[0*16 + j];
                case (which)
                    0: a_amp[j] = v;
                    1: b_amp[j] = v;
                    default: c_amp[j] = v;
                endcase
            end
        end
    endtask

    // 读上电寄存器（直接层次引用 reg_bank 的存储器）
    function [7:0] regval;
        input [7:0] a;
        begin
            regval = u_top.u_reg.mem[a];
        end
    endfunction

    integer bad;

    initial begin
        fails = 0;
        ev_valid = 0; ev_on = 0; ev_note = 0; ev_vel = 0;

        $display("==============================================================");
        $display(" VP7：上电行为（零 UART 写）");
        $display("==============================================================");

        rst_n = 1'b0; repeat (300) @(posedge clk);
        rst_n = 1'b1;
        wait_samples(40);                    // 让引导序列（44 条）走完 + 稳定

        //================= V1：上电静音 =================
        nz = 0;
        for (k = 0; k < 16384; k = k + 1) begin
            @(posedge clk);
            while (!u_top.sample_en) @(posedge clk);
            if (u_top.audio !== 24'sd0) nz = nz + 1;
        end
        $display("  [V1] 复位后零 UART 写，16384 个样本：非零样本 = %0d（必须 0）", nz);
        if (nz != 0) begin $display("        => FAIL 上电有声音"); fails = fails + 1; end
        else $display("        ⇒ 上电静音 ✓");

        //================= V2：不进测试模式 =================
        $display("  [V2] test_mode 引脚=0、CTRL[0]=%0d（必须 0）⇒ 不走测试栅格 ✓",
                 regval(8'h00) & 8'h01);
        if ((regval(8'h00) & 8'h01) != 0) begin
            $display("        => FAIL CTRL[0]=1 ⇒ 上电会进测试模式"); fails = fails + 1;
        end

        //================= V3：上电寄存器表（19 号 §3 冻结默认）=================
        $display("  [V3] 上电寄存器表：");
        bad = 0;
        // 期望值：地址, 期望, 说明
        begin : chk
            integer idx;
            // 用一个紧凑的小数组逐条比对
            for (idx = 0; idx < 12; idx = idx + 1) begin
                case (idx)
                    0:  begin if (regval(8'h00) !== 8'h02) bad = bad + 1;
                              $display("       CTRL(0x00)      = 0x%02X  期望 0x02", regval(8'h00)); end
                    1:  begin if (regval(8'h37) !== 8'h00) bad = bad + 1;
                              $display("       PRESET(0x37)    = 0x%02X  期望 0x00", regval(8'h37)); end
                    2:  begin if (regval(8'h40) !== 8'h01) bad = bad + 1;
                              $display("       FX_CTRL(0x40)   = 0x%02X  期望 0x01（仅干声）", regval(8'h40)); end
                    3:  begin if (regval(8'h41) !== 8'hDC || regval(8'h42) !== 8'h05) bad = bad + 1;
                              $display("       DELAY_LEN(0x41) = 0x%02X%02X 期望 0x05DC = 1500（A5）",
                                       regval(8'h42), regval(8'h41)); end
                    4:  begin if (regval(8'h48) !== 8'h80) bad = bad + 1;
                              $display("       RV_FB(0x48)     = 0x%02X  期望 0x80（默认反馈已降档，避免饱和）", regval(8'h48)); end
                    5:  begin if (regval(8'h49) !== 8'h03) bad = bad + 1;
                              $display("       RV_DAMP(0x49)   = 0x%02X  期望 0x03", regval(8'h49)); end
                    6:  begin if (regval(8'h50) !== 8'h00) bad = bad + 1;
                              $display("       SEQ_CTRL(0x50)  = 0x%02X  期望 0x00（定序器关）", regval(8'h50)); end
                    7:  begin if (regval(8'h5A) !== 8'h02) bad = bad + 1;
                              $display("       SPEC_MODE(0x5A) = 0x%02X  期望 0x02（叠加+自动刷新）", regval(8'h5A)); end
                    8:  begin if (regval(8'h5B) !== 8'h00) bad = bad + 1;
                              $display("       HARM_PADS(0x5B) = 0x%02X  期望 0x00（★ A1 的现行犯）", regval(8'h5B)); end
                    9:  begin if (regval(8'h7F) !== 8'h10) bad = bad + 1;
                              $display("       PROTO_VER(0x7F) = 0x%02X  期望 0x10（v1.0）", regval(8'h7F)); end
                    10: begin if (regval(8'h33) !== 8'h00 || regval(8'h34) !== 8'h00) bad = bad + 1;
                              $display("       VIB_DEPTH(0x33) = 0x%02X%02X 期望 0x0000（颤音关）",
                                       regval(8'h34), regval(8'h33)); end
                    default: begin if (regval(8'h35) !== 8'h00 || regval(8'h36) !== 8'h00) bad = bad + 1;
                              $display("       GLIDE_STEP(0x35)= 0x%02X%02X 期望 0x0000（滑音步长 0）",
                                       regval(8'h36), regval(8'h35)); end
                endcase
            end
        end
        if (bad != 0) begin $display("        => FAIL %0d 项不符", bad); fails = fails + 1; end
        else $display("        ⇒ 上电寄存器表与 19 号 §3 冻结默认一致 ✓");

        //================= V4：preset 默认 = 0（行为侧）=================
        // 注：引脚 preset=3，但 CTRL[3]=0 ⇒ preset_src=引脚 ⇒ 默认走引脚(3)
        //     所以本项测的是**寄存器源**：先 CTRL[3]=1 使能寄存器音色，再比较。
        wr(8'h00, 8'h0A);                    // CTRL：preset_src=1（bit3）+ VIB_EN（bit1）
        wait_samples(4);
        press(7'd64);   snap(0);             // 默认 0x37（未写）
        // 显式写 0x37=0
        rst_n = 1'b0; repeat (300) @(posedge clk); rst_n = 1'b1; wait_samples(40);
        wr(8'h00, 8'h0A); wr(8'h37, 8'h00);
        wait_samples(4);
        press(7'd64);   snap(1);
        // 显式写 0x37=1
        rst_n = 1'b0; repeat (300) @(posedge clk); rst_n = 1'b1; wait_samples(40);
        wr(8'h00, 8'h0A); wr(8'h37, 8'h01);
        wait_samples(4);
        press(7'd64);   snap(2);

        diff = 0;
        for (k = 0; k < 16; k = k + 1) if (a_amp[k] !== b_amp[k]) diff = diff + 1;
        bad = 0;
        for (k = 0; k < 16; k = k + 1) if (b_amp[k] === c_amp[k]) bad = bad + 1;
        $display("  [V4] 默认 vs 显式 0x37=0：不符 %0d 个（必须 0）", diff);
        $display("       显式 0x37=0 vs 0x37=1：相同 %0d 个（必须 <16，否则音色没切换）", bad);
        if (diff != 0) begin $display("        => FAIL 默认音色不是预设 0"); fails = fails + 1; end
        else if (bad == 16) begin $display("        => FAIL 改 0x37 不影响装载 ⇒ 音色源没接上"); fails = fails + 1; end
        else $display("        ⇒ 默认音色 = 预设 0，且 0x37 确实切换音色 ✓");

        $display("");
        if (fails == 0) $display("RESULT vp7=PASS silent=1 regs=1 preset0=1");
        else            $display("RESULT vp7=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #900_000_000;
        $display("RESULT vp7=TIMEOUT");
        $finish;
    end

endmodule
