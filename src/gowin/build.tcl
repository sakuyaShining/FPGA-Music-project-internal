# build.tcl —— Gowin 命令行构建脚本
# 用法： gw_sh.exe build.tcl
#
# 作用：不用打开 GUI，直接完成
#   读工程 → 综合 → 布局布线 → 生成码流
#
# 生成的码流文件在 impl/pnr/ 目录下，扩展名为 .fs

set proj "led_blink.gprj"

puts "=============================================="
puts " 打开工程: $proj"
puts "=============================================="
open_project $proj

puts ""
puts "=============================================="
puts " 开始综合 + 布局布线（这一步要等 1-3 分钟）"
puts "=============================================="
run all

puts ""
puts "=============================================="
puts " 构建结束"
puts "=============================================="

# 打印资源占用（如果报告存在）
set rpt "impl/pnr/led_blink.rpt.txt"
if {[file exists $rpt]} {
    puts ""
    puts "---- 资源占用摘要 ----"
    set fh [open $rpt r]
    set content [read $fh]
    close $fh
    foreach line [split $content "\n"] {
        if {[string match "*Logic*" $line] || [string match "*Register*" $line] \
            || [string match "*Block SRAM*" $line] || [string match "*Multiplier*" $line] \
            || [string match "*I/O Port*" $line] || [string match "*LUT*" $line]} {
            puts $line
        }
    }
}

# 打印时序摘要（WNS 等）
set trpt "impl/pnr/led_blink.trp.txt"
if {[file exists $trpt]} {
    puts ""
    puts "---- 时序摘要 ----"
    set fh [open $trpt r]
    set content [read $fh]
    close $fh
    foreach line [split $content "\n"] {
        if {[string match "*Slack*" $line] || [string match "*WNS*" $line] \
            || [string match "*Timing*" $line] || [string match "*Constraint*" $line]} {
            puts $line
        }
    }
}
