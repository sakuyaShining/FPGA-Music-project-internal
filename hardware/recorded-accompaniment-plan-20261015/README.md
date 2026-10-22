# 已录伴奏＋现场演奏：硬件规格候选

本目录是规格与算术规划，不是最终BOM、原理图或采购清单。需求已确认，实现仍待完成。完整说明见主目录61号技术文档。

- `hardware-requirements.csv`：已有/新增、建议规格、资格状态。预算列仅分配目标，不能当报价。
- `calculation.json`：原生采样率、PCM容量、缓冲与总线算式。
- `sources.json`：本轮查阅的原厂和标准组织来源。
- `rejected-search.json`：立创查询返回错型号的拒绝记录；不使用其价格/库存。
- `manifest.json`：文件与生成器SHA-256。

生成器：`notes/recorded-accompaniment-hardware-20261015/build_plan.py`。未改旧28行整机候选BOM；DAC尚未资格确认，不能下单。1MiB SDRAM预留、30元卡/50元AUX支路和有效0.5MB/s都只是候选设计值，需实测/报价。
