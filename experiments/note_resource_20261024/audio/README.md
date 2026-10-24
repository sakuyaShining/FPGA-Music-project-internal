# 真实TDM音频后端接合候选

这是D-019资源协调器增量，不替换三个current工程目录，不是完整乐器顶层。输入和验证见project/versions/note-resource-audio-20261024.json；上一版协调器单元清单保持原样。

## 路径与事务

note_resource_mgr → note_audio_backend → tdm_engine_transactional → 原osc_env/pitch_mod/原生音高RAM，实际512分量、32组、每层16分量。FINGER_EXPR、RIGHT_TIMBRE和独立乐器包络接口启用。引擎从已捕获tdm_engine_rh派生，原文件不动，来源见ENGINE-SOURCE.json。

- PREPARE按层/组请求16个分量，写到尚不可听的待生效区。PUBLISH使所有层在同一完整音频遍历可见，等待最后分量及输出流水线排空才确认完成。
- RELEASE只关门，保留真实释放包络及占组。FINISH须完整遍历确认全部分量包络IDLE、零电平、关门且没有未提交装载；带token反馈，不以零PCM或OFF当作空闲。
- RETIRE在共同音频边界清退整实例剩余层，清掉实际包络/幅度/门和在途装载后才确认。目前是立即清退，没有批准的防爆音淡出，不宣称抢占听感合格。
- 复位先静音并清退512分量，完成后开放请求。分量响应核对ticket/token/层/序号，错误响应丢弃并留痕；工作口接受不等于实际发声完成。

## 限定验证

TRANSACTIONAL=0的177951个时钟PCM/原始和及抽样内部状态与原引擎一致，不是全部输入的形式化等价证明。最终audio-02：546条请求、4093帧实际PCM（4059非零）、551次完整发布、6次强制退场，含四层/满32组、尾音优先、两来源、真实自然结束、三类取消、带音复位及长按音保留期间262次组复用。逐分量检查同一遍历完整发布，并检查退场/自然完成的实际引擎状态。最长接受至响应3547拍只绑定本测试提供器，不代表实体触摸≤10ms；没有独立完整PCM参考或听感签收。

提前消费、忽略清退、过早结束、忽略分量token四项变异均被指定断言检出；编译失败/超时/无关失败不算。首轮运行器将变异误应用到非目标文件，正向两项通过后以异常退出；原脚本/进度/输出保留，修复目标选择及新增5防护单测后，新目录全量重跑。

同版音频探针综合通过：9749Logic（8434LUT、667ALU、108RAM16），4122REG、11BSRAM、5DSP，无综合警告。外部分量提供器端口不含完整外围/数据生成器/文件/界面，不能据此承诺整机fit。尚无本版PnR、有效STA或码流，RTL时序门未满足。

```powershell
python -m unittest discover -s experiments/note_resource_20261024/audio/tests -v
python experiments/note_resource_20261024/audio/verify_audio.py --fault-checks --output <不存在的仓库外新目录>
python experiments/note_resource_20261024/audio/synthesize_audio.py --output <另一个不存在的仓库外新目录>
```

## 剩余工作

测试台按已捕获note_inc/preset_part/vel_shape表生成分量，包络为显式测试配置，不是设备端音符数据生成器。实际事件、完整槽定义/配置快照、激发/力度/修饰加载、手指边沿/移动和曲谱路由待接合；提供器必须遵守背压且最终完成，超时恢复和整链最坏排队仍待落实。

约0.5ms短淡出后完整起新音已提问，尚无人类批准，不能升级为音乐规则。NR07仅推进到真实TDM/包络局部数字路径；完整产品资源/PnR/STA、触摸延迟及实体听感仍未签收。禁止下载、Flash或制造放行。
