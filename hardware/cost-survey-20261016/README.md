# 成本调查 · 2026-10-16

状态：**讨论中**。价格记录范围内已核对，非整机已报价或可制造签收。

- domestic-price-references.csv：18条国内公开报价参考；JSON-LD Offer是每颗参考，整包价另列，所需数量档位/结算未确认。
- international-price-ladders.json：9条LCSC国际站公开USD阶梯价；不得直接当人民币商城价。
- component-cost-examples.csv：两种端点数量例的装机用料/最小包装采购分别计算。USD统一以**假设7.2**作成本情景，非实时汇率；保留来源币种。
- unquoted-reserves.csv：未报价项目的预留金额。只是情景，不称市场调查所得区间。
- screen-cost-scenarios.csv / cost-summary.json：屏幕参考价、接口代价和可追溯算式。保留7英寸，未因成本裁定交互或采购替代。

原始公开HTML/JSON-LD、数量单位、时间与访问失败保留在notes/cost-survey-20261016/evidence/。API原始尝试403，没有取得价格；未绕过登录/验证码，改用可公开读取商品页与网页检索。国际站和国内库存分开。

重要：theRatio=100表示一个最小销售增量100颗；validStockNumber按销售增量计，stockNumber/结构化库存按颗计，不能混用。价格来源公开但不是结算报价；最终还需数量阶梯、SMT最小数/损耗、实际屏幕版本和制造文件。

没有改引擎、原理图、旧BOM或旧快照，没有下单。完整结论见63号文档。
