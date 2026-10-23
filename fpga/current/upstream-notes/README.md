# Tang Nano20K 可行性评估实验

阅读入口：[project/CURRENT.md](project/CURRENT.md)。

唯一RTL增量为`engine/src/mv_renderer.v`固定字形位置计算。其余源复制自86号实验，原文件保持。
该顶层仍为静音结构探针，禁止下载；完整功能产品尚无对应的完整顶层。

```powershell
python experiments/nano20k_feasibility_20261021/budget.py
python experiments/nano20k_feasibility_20261021/check_renderer.py
python experiments/nano20k_feasibility_20261021/check_engine_compat.py
python experiments/nano20k_feasibility_20261021/check_joint.py
python experiments/nano20k_feasibility_20261021/build_board.py build_nominal_v0 nominal
python experiments/nano20k_feasibility_20261021/audit_current.py
```

构建脚本拒绝覆盖现有目录，重跑请使用新`build_nominal_v数字`标签。加严只在正常路由已完成后有比较意义。
运行前读取`common.py`、`build_board.py`中的本机Icarus/Gowin/D盘路径；没有编程器命令。
`budget.py`只读外部主项目与06df硬件，输出本目录的预算；设计分配不是实测实现成本。

原回归黄金数据来自主项目71号；便携交付需连同这些黄金轨迹或可核验来源保留。
大产物在D盘，通过目录联接访问；本目录`.gitignore`不包含这些构建及证据，使用交付ZIP或重跑。
继承的其他`check_*`、`audit_*`与prepare_probe工具仅作历史参考，旧入口/断言不作为本轮签收。
