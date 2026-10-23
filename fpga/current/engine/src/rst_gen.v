//=============================================================================
// rst_gen.v —— 复位生成器（上电复位 + 按键消抖）
//
// 【为什么需要这个模块】
//   板上实测（2026-10-23，beacon 探针）：Tang Nano 20K 的引脚 87（S1）
//   **空闲时读 0**。而本项目所有旧 cst 都把它当「低有效复位」直接送进内核，
//   于是内核永远处于复位 ⇒ 产品顶层在板上完全不启动（UART 全程静默）。
//
//   旧固件 tdm_live_test.fs 之所以能跑，是因为 tdm_board_test.v:12-16 那段
//   逻辑是**反的**：
//       always @(posedge clk or posedge rst_n)
//           if (rst_n) reset_release <= 0;
//           else       reset_release <= {reset_release[0], 1'b1};
//       ... .rst_n(reset_release[1])
//   引脚低 ⇒ 两拍后 release ⇒ 内核被**释放**。等于"默认释放"。
//
// 【硬件事实（官方依据）】
//   Sipeed Tang Nano 20K 官方例程把 87/88 当普通开关用：
//       IO_LOC "sw0" 87;  IO_PORT "sw0" IO_TYPE=LVCMOS33 PULL_MODE=NONE;
//   说明文字："The switches on the 20K are pulled down so there's no need for
//              a pull up or pull down in the FPGA. The output is a logic one
//              when you press the switch."
//   ⇒ **板上外部下拉，按下接 3V3，高有效。** PULL_MODE 应设 NONE 或 DOWN。
//   ⇒ 内部 PULL_MODE=UP 打不过板上 10k 下拉，引脚仍读 0（这解释了为什么
//      build_prod_v0/v1 改成 UP 也没救回来）。
//
// 【设计取向】
//   1. 复位**绝不依赖按键**：POR 计数器保证任何情况下都能确定性启动。
//      按键即使接反、断线、被按住，设计照样跑。
//   2. 按键只作为「附加的复位手段」，高有效 + 消抖。
//   3. 极性若与实物不符，最坏后果是"按 S1 不复位"，而不是"整机不启动"。
//      —— 这是刻意选择的失效方向。
//=============================================================================

`timescale 1ns/1ps

module rst_gen #(
    // 上电复位：计数器到 2^(POR_BITS-1) 释放。27 MHz 下 POR_BITS=16 ⇒ 1.21 ms
    parameter integer POR_BITS = 16,
    // 消抖：电平需稳定 2^DB_BITS 拍才被承认。27 MHz 下 DB_BITS=14 ⇒ 0.61 ms
    parameter integer DB_BITS  = 14
)(
    input  wire clk,
    input  wire btn,        // 板载按键，高有效（板上外部下拉，按下为 1）
    output wire rst_n,      // 内部低有效复位，送给所有子模块
    output wire por_done,   // 上电复位已完成
    output wire btn_state   // 消抖后的按键电平
);

    //-------------------------------------------------------------------------
    // 上电复位
    //   Gowin 寄存器上电默认为 0，但这里仍显式给初值：
    //   ① 仿真时 iverilog 不给初值就是 x，x+1 恒为 x，计数器永远不动；
    //   ② 综合时这是常量初值，不引入任何运算（见 reg_bank.v 头注释的教训：
    //      initial 里只放常量，别放循环/运算）。
    //-------------------------------------------------------------------------
    reg [POR_BITS-1:0] por_cnt;
    initial por_cnt = {POR_BITS{1'b0}};

    wire por_done_i = por_cnt[POR_BITS-1];

    always @(posedge clk) begin
        if (!por_done_i) por_cnt <= por_cnt + 1'b1;
    end

    //-------------------------------------------------------------------------
    // 按键消抖
    //   只在"引脚电平与已确认电平不同"时累加；一旦稳定就清零重来。
    //   机械按键抖动通常 < 1 ms，0.61 ms 的窗口对 S1 够用；
    //   按住不放时 btn_state 恒为 1 ⇒ rst_n 一直被按低，松手才释放。
    //-------------------------------------------------------------------------
    reg [DB_BITS-1:0] db_cnt;
    reg               btn_stable;
    initial begin
        db_cnt     = {DB_BITS{1'b0}};
        btn_stable = 1'b0;
    end

    always @(posedge clk) begin
        if (btn != btn_stable) begin
            if (db_cnt == {DB_BITS{1'b1}}) begin
                btn_stable <= btn;
                db_cnt     <= {DB_BITS{1'b0}};
            end else begin
                db_cnt <= db_cnt + 1'b1;
            end
        end else begin
            db_cnt <= {DB_BITS{1'b0}};
        end
    end

    assign rst_n     = por_done_i & ~btn_stable;
    assign por_done  = por_done_i;
    assign btn_state = btn_stable;

endmodule
