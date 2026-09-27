# 协议对比 · lbp_adult_v0.1 vs lbp_adult_v0.2_ai_draft · 同一组 80 个场景

运行：2026-09-24 01:55:19 / 2026-09-24 01:57:20（离线词表 mock；场景脚本按 v0.1 编写）

> 读法：场景脚本只回答 v0.1 的问题，v0.2 新增的问题一律按"不清楚"处理，所以 v0.2 的"关键事实遗漏"多是版本绑定造成的；
> **有信息量的是红旗触发差异、紧急终止次数和提问数**。医生对比两版时重点看下面的差异行。

| 指标 | lbp_adult_v0.1 | lbp_adult_v0.2_ai_draft |
|---|---|---|
| 平均提问数（含核对与澄清） | 14.4 | 28.0 |
| 紧急终止问询的场景 | 7 | 7 |
| 期望红旗漏触发 E4 | 0 | 1 |
| 脚本未预期的额外触发 E5 | 0 | 19 |

## 各规则触发次数

| 规则 | lbp_adult_v0.1 | lbp_adult_v0.2_ai_draft |
|---|---|---|
| rf_bilateral_only | 0 | 2 |
| rf_bladder_bowel | 3 | 2 |
| rf_cancer_with_features | 0 | 2 |
| rf_ces_bilateral | 0 | 1 |
| rf_fever | 2 | 2 |
| rf_no_improvement | 0 | 7 |
| rf_out_of_scope | 0 | 7 |
| rf_progressive_weakness | 2 | 2 |
| rf_saddle | 4 | 4 |
| rf_trauma_severe | 4 | 4 |
| rf_uncertain_red_flag | 4 | 4 |
| rf_weight_loss_or_cancer | 6 | 6 |

## 结果不同的场景（17 / 80）

| 场景 | 标题 | A 触发 | B 触发 | A 终止 | B 终止 |
|---|---|---|---|---|---|
| S013 | 原话自述怀孕七个多月——超出协议适用范围，系统当前无 | — | rf_out_of_scope | — | — |
| S014 | 孕期 + 模糊表达：“右边好像更明显”“腿好像有点麻 | — | rf_out_of_scope | — | — |
| S015 | 孕期 + 信息极少：只写“怀孕了，腰疼”，其余答不清 | — | rf_out_of_scope | — | — |
| S016 | 孕期 + 否定表达：“腿不麻也不没劲，大小便正常，没 | — | rf_out_of_scope | — | — |
| S017 | 原话提到“这两天小便憋不住”——必须立即提示并生成紧 | rf_bladder_bowel | rf_bladder_bowel, rf_no_improvement | 是 | 是 |
| S019 | “好像有点憋不住尿，说不清”——红旗事实不确定，须生 | rf_uncertain_red_flag | rf_no_improvement, rf_uncertain_red_flag | — | — |
| S020 | 左腿没劲且一天比一天更没劲、上楼梯抬不起来——进行性 | rf_progressive_weakness | rf_progressive_weakness | — | 是 |
| S025 | 原话提到三年前乳腺癌、做过化疗——肿瘤病史须生成医生 | rf_weight_loss_or_cancer | rf_cancer_with_features, rf_no_improvement, rf_weight_loss_or_cancer | — | — |
| S026 | 两个月瘦了七八斤、夜间更痛——体重下降须生成复核任务 | rf_weight_loss_or_cancer | rf_no_improvement, rf_weight_loss_or_cancer | — | — |
| S027 | 夜里经常疼醒 + 表单确认肿瘤史——须生成复核任务 | rf_weight_loss_or_cancer | rf_no_improvement, rf_weight_loss_or_cancer | — | — |
| S029 | 老毛病腰痛，这次多了左小腿发麻——既往发作与新增表现 | — | rf_no_improvement | — | — |
| S053 | 原话自述 16 岁——超出协议适用范围，系统当前无法 | — | rf_out_of_scope | — | — |
| S054 | 16 岁 + 模糊表达“腿好像有点麻” | — | rf_out_of_scope | — | — |
| S055 | 16 岁 + 信息极少：“我16岁，腰疼” | — | rf_out_of_scope | — | — |
| S057 | 原话没提大小便，表单回答大小便控制有变化——必须立即 | rf_bladder_bowel | rf_bilateral_only, rf_no_improvement | 是 | — |
| S060 | 会阴发麻 + 双腿一天比一天更没劲——两条红旗；本变 | rf_progressive_weakness, rf_saddle | rf_bilateral_only, rf_ces_bilateral, rf_progressive_weakness, rf_saddle | 是 | 是 |
| S065 | 原话提到去年肺癌化疗——肿瘤病史须生成医生复核任务 | rf_weight_loss_or_cancer | rf_cancer_with_features, rf_weight_loss_or_cancer | — | — |

## 给医生的三个问题

1. B 版新增的规则（双腿同时症状、步态、性功能、肿瘤史伴特征、外伤伴骨折风险、病程超过 6 周仍加重等）触发次数见上表——哪些过于保守、哪些不够？
2. B 版必问题 16 道、平均提问数见上表；你能接受的上限是多少？哪些必问可以降级？
3. 正式切换版本时需要按新问法改写场景脚本并重新审核。