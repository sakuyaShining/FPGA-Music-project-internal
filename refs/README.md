# refs/ 参考资料说明

> **本目录全部是只读参考资料**，来自竞赛官网和厂商官方渠道。不要修改，只用来查证。

## 目录用途

| 目录 | 内容 | 什么时候用 |
|---|---|---|
| **`candidate-guides/`** | 7 家协办企业《2026 选题指南》的 **原始 PDF** + 抽取出的纯文本，以及部分厂商的结构化提取稿 | 需要查赛题**原文**时。比如答辩前确认某条要求的确切措辞 |
| **`official-notices/`** | 竞赛官网的通知正文（2026 第一轮通知、FPT 赛题公示、竞赛背景等） | 查赛事规则、时间线、组委会要求 |
| **`report-template/`** | 官方作品报告模板（docx 原件 + 抽出的章节结构） | 写作品报告时对照章节与字数上限 |
| **`vendor-examples/`** | 厂商官方例程源码（目前有 Sipeed Tang Nano 20K 的 audio 例程） | 写代码时参考官方实现与引脚约束 |
| **`_site-archive/`** | 抓官网时保存的**原始响应**（html / js / json） | **一般不用看**。只在需要追溯"某条信息当初是怎么抓到的"时用 |

## candidate-guides/ 文件对应关系

每份指南通常有三个文件：

| 后缀 | 含义 |
|---|---|
| `.pdf` | 官方原始 PDF（权威） |
| `.txt` | 用 pypdf 抽取的纯文本（方便搜索，可能有排版噪声） |
| `-选题提取.md` / `-选题结构化提取.md` | 结构化整理稿（好读，但属于二手整理，有疑问要回查 PDF） |

⚠️ **取信顺序**：`.pdf` 原文 > `.txt` 抽取 > `-提取.md` 整理稿。

## 快速查证指引

| 想确认 | 查哪个文件 |
|---|---|
| 咱们赛题（高云选题二）的确切要求 | `candidate-guides/gaoyun.pdf`，第 15–16 页（或 `gaoyun.txt` 第 243–297 行） |
| 报名/提交/决赛时间、团队人数 | `official-notices/news_53.txt` |
| 作品要交哪些东西 | `_site-archive/student-work.html` |
| 作品报告章节与字数 | `report-template/template_general_2025-报告结构.txt` |
| 板卡 I2S 引脚怎么接 | `vendor-examples/tang20k-audio/audio_src_audio.cst` |
| 其他厂商的题（备选参考） | `candidate-guides/{amd,anlogic,efinix,fudanwei,pango,yihaiwei}.pdf` |
