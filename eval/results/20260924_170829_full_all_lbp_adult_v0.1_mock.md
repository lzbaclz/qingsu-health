# 评测报告 · split=all · arm=full · provider=mock · protocol=lbp_adult_v0.1

生成时间：2026-09-24 17:08:29　用时 17.0 秒　场景数：80　病例家族：20

## 最终记录（模拟认真的患者走完一键核对与问卷之后；该患者知道真值，等于用答案核对答案）

| 指标 | 值 |
|---|---|
| 场景通过率（无 critical 错误） | 1.0 |
| 家族通过率 | 1.0 |
| 关键事实完整率（分母 718） | 1.0 |
| 验收检查通过率 | 1.0 |
| 平均提问数（含核对与澄清） | 14.4 |
| 因紧急红旗终止问询的场景 | 7 |

| 错误代码 | 次数 |
|---|---|
| （无） | 0 |

## 抽取层（原话刚被抽取、还没核对与问卷时；也是“患者不认真核对”的最坏情况）

抽取层无 critical 错误的场景比例：1.0

| 代码 | 次数 |
|---|---|
| X8_misread | 2 |

X1 漏抽（问卷可兜住）· X2 编造（核对可兜住）· X4 原话层红旗漏识别（问卷可兜住）· X8 错抽（核对可兜住）

## 一键核对与紧急终止

- 核对决定：{'confirm': 157, 'unsure': 10}；其中真值未规定、无法判断的条目 0 条（按"对"处理）
- 说明性记录（不计错）：{'S1_not_asked_after_urgent_stop': 40}
- 实际使用的抽取模型：{'mock': 80}

## 逐场景

| id | 类别 | 提问 | 核对/澄清 | 紧急终止 | 红旗 | 抽取层错 | 最终 critical | 结果 |
|---|---|---|---|---|---|---|---|---|
| S001 | normal | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S002 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S003 | negation | 12 | 2/0 | — | — | 0 | 0 | PASS |
| S004 | many_skips | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S005 | contradiction | 17 | 1/1 | — | — | 0 | 0 | PASS |
| S006 | contradiction | 17 | 1/1 | — | — | 0 | 0 | PASS |
| S007 | contradiction | 17 | 1/1 | — | — | 0 | 0 | PASS |
| S008 | normal | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S009 | medication_request | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S010 | medication_request | 13 | 1/0 | — | — | 0 | 0 | PASS |
| S011 | hedged | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S012 | normal | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S013 | out_of_scope | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S014 | out_of_scope | 17 | 1/1 | — | — | 0 | 0 | PASS |
| S015 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S016 | negation | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S017 | red_flag | 1 | 1/0 | 是 | rf_bladder_bowel | 0 | 0 | PASS |
| S018 | red_flag | 3 | 1/0 | 是 | rf_saddle | 0 | 0 | PASS |
| S019 | red_flag | 17 | 1/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S020 | red_flag | 17 | 1/0 | — | rf_progressive_weakness | 0 | 0 | PASS |
| S021 | red_flag | 17 | 1/0 | — | rf_trauma_severe | 0 | 0 | PASS |
| S022 | normal | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S023 | red_flag | 17 | 1/0 | — | rf_fever,rf_trauma_severe | 0 | 0 | PASS |
| S024 | many_skips | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S025 | red_flag | 17 | 1/0 | — | rf_weight_loss_or_cancer | 0 | 0 | PASS |
| S026 | red_flag | 17 | 1/0 | — | rf_weight_loss_or_cancer | 0 | 0 | PASS |
| S027 | red_flag | 17 | 1/0 | — | rf_weight_loss_or_cancer | 0 | 0 | PASS |
| S028 | negation | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S029 | new_symptom | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S030 | hedged | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S031 | missing_info | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S032 | negation | 17 | 1/1 | — | — | 1 | 0 | PASS |
| S033 | follow_up | 13 | 0/0 | — | — | 0 | 0 | PASS |
| S034 | follow_up | 12 | 0/0 | — | — | 0 | 0 | PASS |
| S035 | new_symptom | 11 | 1/0 | — | — | 0 | 0 | PASS |
| S036 | follow_up | 11 | 0/0 | — | — | 0 | 0 | PASS |
| S037 | follow_up | 10 | 0/0 | — | — | 0 | 0 | PASS |
| S038 | red_flag | 1 | 1/0 | 是 | rf_bladder_bowel | 0 | 0 | PASS |
| S039 | hedged | 14 | 1/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S040 | many_skips | 13 | 0/0 | — | — | 0 | 0 | PASS |
| S041 | normal | 15 | 1/0 | — | — | 0 | 0 | PASS |
| S042 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S043 | negation | 13 | 2/0 | — | — | 0 | 0 | PASS |
| S044 | many_skips | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S045 | contradiction | 17 | 1/1 | — | — | 0 | 0 | PASS |
| S046 | contradiction | 16 | 0/1 | — | — | 0 | 0 | PASS |
| S047 | contradiction | 17 | 1/1 | — | — | 0 | 0 | PASS |
| S048 | contradiction | 17 | 1/1 | — | — | 0 | 0 | PASS |
| S049 | medication_request | 14 | 1/0 | — | — | 0 | 0 | PASS |
| S050 | medication_request | 13 | 1/0 | — | — | 0 | 0 | PASS |
| S051 | hedged | 17 | 1/1 | — | — | 0 | 0 | PASS |
| S052 | normal | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S053 | out_of_scope | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S054 | out_of_scope | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S055 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S056 | negation | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S057 | red_flag | 2 | 1/0 | 是 | rf_bladder_bowel | 0 | 0 | PASS |
| S058 | red_flag | 1 | 1/0 | 是 | rf_saddle | 0 | 0 | PASS |
| S059 | red_flag | 17 | 1/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S060 | red_flag | 1 | 1/0 | 是 | rf_saddle,rf_progressive_weakness | 0 | 0 | PASS |
| S061 | red_flag | 17 | 1/0 | — | rf_trauma_severe | 0 | 0 | PASS |
| S062 | normal | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S063 | red_flag | 17 | 1/0 | — | rf_fever,rf_trauma_severe | 0 | 0 | PASS |
| S064 | many_skips | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S065 | red_flag | 17 | 1/0 | — | rf_weight_loss_or_cancer | 0 | 0 | PASS |
| S066 | red_flag | 17 | 1/0 | — | rf_weight_loss_or_cancer | 0 | 0 | PASS |
| S067 | red_flag | 17 | 1/0 | — | rf_weight_loss_or_cancer | 0 | 0 | PASS |
| S068 | negation | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S069 | new_symptom | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S070 | hedged | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S071 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S072 | negation | 17 | 1/0 | — | — | 0 | 0 | PASS |
| S073 | follow_up | 13 | 0/0 | — | — | 0 | 0 | PASS |
| S074 | follow_up | 12 | 0/0 | — | — | 0 | 0 | PASS |
| S075 | new_symptom | 12 | 1/1 | — | — | 1 | 0 | PASS |
| S076 | follow_up | 11 | 0/0 | — | — | 0 | 0 | PASS |
| S077 | follow_up | 11 | 0/0 | — | — | 0 | 0 | PASS |
| S078 | red_flag | 1 | 1/0 | 是 | rf_saddle | 0 | 0 | PASS |
| S079 | hedged | 14 | 1/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S080 | many_skips | 13 | 0/0 | — | — | 0 | 0 | PASS |

## 明细

### S032 · 否定表达带时间限定：“以前从来没麻过”不是否认现在麻；“没有摔倒”只否认外伤
- 抽取层 **X8_misread** [major] prior_episodes：抽成 denied:None，与既有输入矛盾，引发不必要的澄清

### S075 · 随访：更疼 + 新出现串到左臀、左腿发麻——主要部位仍是腰正中
- 抽取层 **X8_misread** [major] pain_side：抽成 present:left，与既有输入矛盾，引发不必要的澄清


> 本报告只说明系统在这些模拟场景上的表现；场景均未经临床审核，模拟通过不等于真实患者使用安全。