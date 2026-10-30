#!/usr/bin/env bash
#=============================================================================
# run_sim.sh —— Control88 板级 RTL 一键回归
#
#   bash run_sim.sh after     # 跑当前 rtl/，写 regression-after.log
#   bash run_sim.sh before    # 跑 before-fix/ 对照副本，写 regression-before.log
#
# 覆盖 5 组：
#   sr595 / sr165 / arb   —— Q4-R7 位序与仲裁（2026-10-29）
#   i2c_before            —— 共享 RTL i2c_master.v 的接收路径（负对照，必须 FAIL）
#   i2c_after             —— 本地 c88_i2c.v（必须全 PASS）
#   nvstore               —— EEPROM 记录读/写/校验（2026-10-30）
#
# 依赖：D:/iverilog/bin/iverilog.exe + vvp.exe（Icarus Verilog 14.0）
# 说明：不用管道 tee 落盘（长仿真下会丢缓冲），每步先写临时文件再 grep 追加。
#=============================================================================
set -u
IV="${IV:-/d/iverilog/bin/iverilog.exe}"
VV="${VV:-/d/iverilog/bin/vvp.exe}"
RTL="${RTL:-../rtl}"
OUT="${1:-after}"
LOG="regression-${OUT}.log"
SHARED_I2C="${SHARED_I2C:-D:/FPGA-Project/current-design/src/rtl/i2c_master.v}"

run() {  # $1=name  $2=top  $3..=源文件
    local name="$1" top="$2"; shift 2
    echo "### $name ($top)" >> "$LOG"
    if ! "$IV" -g2012 -o "sim_${name}.vvp" "$top" "$@" >> "$LOG" 2>&1; then
        echo "RESULT: COMPILE_ERROR ($name)" >> "$LOG"
        echo "---" >> "$LOG"
        return 1
    fi
    "$VV" "sim_${name}.vvp" > "raw_${name}.txt" 2>&1
    grep -E "FAIL|ok |CHECK|RESULT|keys=|shifted|读取次数|最后输出|preset|dbg_frame|EEPROM" \
        "raw_${name}.txt" >> "$LOG"
    echo "---" >> "$LOG"
}

# 带额外编译宏的版本（i2c_after 需要 -DUSE_FIX 换实例）
run_d() {  # $1=name $2=define $3=top $4..=源文件
    local name="$1" def="$2" top="$3"; shift 3
    echo "### $name ($top, $def)" >> "$LOG"
    if ! "$IV" -g2012 "$def" -o "sim_${name}.vvp" "$top" "$@" >> "$LOG" 2>&1; then
        echo "RESULT: COMPILE_ERROR ($name)" >> "$LOG"
        echo "---" >> "$LOG"
        return 1
    fi
    "$VV" "sim_${name}.vvp" > "raw_${name}.txt" 2>&1
    grep -E "FAIL|CHECK|RESULT" "raw_${name}.txt" >> "$LOG"
    echo "---" >> "$LOG"
}

: > "$LOG"
{
  echo "### 回归对象: $RTL   (mode=$OUT)"
  echo "### 时间: $(date -Iseconds)"
  echo "### iverilog: $("$IV" -V 2>&1 | head -1)"
} >> "$LOG"

if [ "$OUT" = "before" ]; then
    SR595="before-fix/c88_sr595.v"; SPI="before-fix/c88_spi.v"
else
    SR595="$RTL/c88_sr595.v"; SPI="$RTL/c88_spi.v"
fi

run sr595 tb_sr595.v tb_models.v "$SR595" "$SPI"
run sr165 tb_sr165.v tb_models.v "$RTL/c88_sr165.v" "$SPI"
run arb   tb_arb.v   tb_models.v "$RTL/c88_top.v" "$RTL/c88_scan.v" \
         "$SR595" "$RTL/c88_sr165.v" "$SPI" "$RTL/c88_evq.v"

# ---- Q4-R5：I2C 接收路径（负对照 + 修复版）与 EEPROM 存储 ----
run   i2c_before tb_i2c_read.v tb_i2c_models.v "$SHARED_I2C"
run_d i2c_after  "-DUSE_FIX" tb_i2c_read.v tb_i2c_models.v "$RTL/c88_i2c.v"
run   nvstore    tb_nvstore.v tb_i2c_models.v "$RTL/c88_nvstore.v" "$RTL/c88_i2c.v"

{
  echo "### 汇总"
  echo "PASS 组数: $(grep -c '^RESULT: PASS' "$LOG")"
  echo "FAIL 组数: $(grep -c '^RESULT: FAIL' "$LOG")"
  echo "TIMEOUT 组数: $(grep -c '^RESULT: TIMEOUT' "$LOG")"
  echo "COMPILE_ERROR 组数: $(grep -c 'RESULT: COMPILE_ERROR' "$LOG")"
} >> "$LOG"

rm -f sim_*.vvp
cat "$LOG"
