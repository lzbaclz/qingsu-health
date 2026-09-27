# 评测报告 · split=all · arm=form_only · provider=mock · protocol=lbp_adult_v0.1

生成时间：2026-09-24 14:42:59　用时 12.3 秒　场景数：80　病例家族：20

## 最终记录（模拟认真的患者走完一键核对与问卷之后；该患者知道真值，等于用答案核对答案）

| 指标 | 值 |
|---|---|
| 场景通过率（无 critical 错误） | 0.263 |
| 家族通过率 | 0.0 |
| 关键事实完整率（分母 737） | 0.801 |
| 验收检查通过率 | 1.0 |
| 平均提问数（含核对与澄清） | 15.2 |
| 因紧急红旗终止问询的场景 | 2 |

| 错误代码 | 次数 |
|---|---|
| E1_critical_omission | 145 |
| E4_missed_escalation | 23 |
| E7_conflict_not_surfaced | 7 |
| E8_misunderstanding | 4 |
| E9_minor_omission | 184 |

## 抽取层（原话刚被抽取、还没核对与问卷时；也是“患者不认真核对”的最坏情况）

抽取层无 critical 错误的场景比例：1.0

| 代码 | 次数 |
|---|---|
| （无） | 0 |

X1 漏抽（问卷可兜住）· X2 编造（核对可兜住）· X4 原话层红旗漏识别（问卷可兜住）· X8 错抽（核对可兜住）

## 一键核对与紧急终止

- 核对决定：无；其中真值未规定、无法判断的条目 0 条（按"对"处理）
- 说明性记录（不计错）：{'S1_not_asked_after_urgent_stop': 17}
- 实际使用的抽取模型：{'—': 80}

## 逐场景

| id | 类别 | 提问 | 核对/澄清 | 紧急终止 | 红旗 | 抽取层错 | 最终 critical | 结果 |
|---|---|---|---|---|---|---|---|---|
| S001 | normal | 16 | 0/0 | — | — | 0 | 3 | FAIL |
| S002 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S003 | negation | 16 | 0/0 | — | — | 0 | 7 | FAIL |
| S004 | many_skips | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S005 | contradiction | 16 | 0/0 | — | — | 0 | 4 | FAIL |
| S006 | contradiction | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S007 | contradiction | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S008 | normal | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S009 | medication_request | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S010 | medication_request | 16 | 0/0 | — | — | 0 | 7 | FAIL |
| S011 | hedged | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S012 | normal | 16 | 0/0 | — | — | 0 | 3 | FAIL |
| S013 | out_of_scope | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S014 | out_of_scope | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S015 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S016 | negation | 16 | 0/0 | — | — | 0 | 6 | FAIL |
| S017 | red_flag | 16 | 0/0 | — | — | 0 | 4 | FAIL |
| S018 | red_flag | 2 | 0/0 | 是 | rf_saddle | 0 | 0 | PASS |
| S019 | red_flag | 16 | 0/0 | — | — | 0 | 3 | FAIL |
| S020 | red_flag | 16 | 0/0 | — | — | 0 | 4 | FAIL |
| S021 | red_flag | 16 | 0/0 | — | — | 0 | 3 | FAIL |
| S022 | normal | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S023 | red_flag | 16 | 0/0 | — | — | 0 | 5 | FAIL |
| S024 | many_skips | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S025 | red_flag | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S026 | red_flag | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S027 | red_flag | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S028 | negation | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S029 | new_symptom | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S030 | hedged | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S031 | missing_info | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S032 | negation | 16 | 0/0 | — | — | 0 | 6 | FAIL |
| S033 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S034 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S035 | new_symptom | 14 | 0/0 | — | — | 0 | 1 | FAIL |
| S036 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S037 | follow_up | 13 | 0/0 | — | — | 0 | 0 | PASS |
| S038 | red_flag | 14 | 0/0 | — | — | 0 | 3 | FAIL |
| S039 | hedged | 13 | 0/0 | — | — | 0 | 1 | FAIL |
| S040 | many_skips | 13 | 0/0 | — | — | 0 | 0 | PASS |
| S041 | normal | 16 | 0/0 | — | — | 0 | 5 | FAIL |
| S042 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S043 | negation | 16 | 0/0 | — | — | 0 | 7 | FAIL |
| S044 | many_skips | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S045 | contradiction | 16 | 0/0 | — | — | 0 | 3 | FAIL |
| S046 | contradiction | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S047 | contradiction | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S048 | contradiction | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S049 | medication_request | 16 | 0/0 | — | — | 0 | 7 | FAIL |
| S050 | medication_request | 16 | 0/0 | — | — | 0 | 7 | FAIL |
| S051 | hedged | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S052 | normal | 16 | 0/0 | — | — | 0 | 3 | FAIL |
| S053 | out_of_scope | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S054 | out_of_scope | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S055 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S056 | negation | 16 | 0/0 | — | — | 0 | 5 | FAIL |
| S057 | red_flag | 1 | 0/0 | 是 | rf_bladder_bowel | 0 | 0 | PASS |
| S058 | red_flag | 16 | 0/0 | — | — | 0 | 4 | FAIL |
| S059 | red_flag | 16 | 0/0 | — | — | 0 | 3 | FAIL |
| S060 | red_flag | 16 | 0/0 | — | — | 0 | 5 | FAIL |
| S061 | red_flag | 16 | 0/0 | — | — | 0 | 3 | FAIL |
| S062 | normal | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S063 | red_flag | 16 | 0/0 | — | — | 0 | 7 | FAIL |
| S064 | many_skips | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S065 | red_flag | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S066 | red_flag | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S067 | red_flag | 16 | 0/0 | — | — | 0 | 2 | FAIL |
| S068 | negation | 16 | 0/0 | — | — | 0 | 3 | FAIL |
| S069 | new_symptom | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S070 | hedged | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S071 | missing_info | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S072 | negation | 16 | 0/0 | — | — | 0 | 6 | FAIL |
| S073 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S074 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S075 | new_symptom | 14 | 0/0 | — | — | 0 | 1 | FAIL |
| S076 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S077 | follow_up | 13 | 0/0 | — | — | 0 | 0 | PASS |
| S078 | red_flag | 14 | 0/0 | — | — | 0 | 2 | FAIL |
| S079 | hedged | 13 | 0/0 | — | — | 0 | 1 | FAIL |
| S080 | many_skips | 13 | 0/0 | — | — | 0 | 0 | PASS |

## 明细

### S001 · 搬东西后左腰酸痛三天，表达完整、无红旗
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] relieving：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked

### S003 · 原话里一口气否认多项（腿不麻/有劲/没发烧/大小便都正常…），表单不再重复回答
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_weakness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] radiation_present：期望 denied，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked

### S004 · 几乎每题都跳过——跳过必须记为“已问未答”，不能变成否认
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered

### S005 · 身体图误点左侧、原话说右边——必须澄清；澄清后主要侧别为右
- 最终 **E8_misunderstanding** [critical] pain_side：期望值 right，系统值 left
- 最终 **E8_misunderstanding** [major] pain_regions：期望值 ['lower_back_right']，系统值 ['lower_back_left']
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] radiation_present：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] radiation_regions：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E7_conflict_not_surfaced** [major] pain_side：期望的矛盾既未澄清也未呈现

### S006 · 原话前后时间矛盾：半年老问题 vs 前天突然又疼——需澄清本次起病时间
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered
- 最终 **E7_conflict_not_surfaced** [major] onset_timing：期望的矛盾既未澄清也未呈现

### S007 · 原话先说腿不麻、后说开长途时脚好像有点麻——矛盾需澄清，结果记为不确定
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E7_conflict_not_surfaced** [major] leg_numbness：期望的矛盾既未澄清也未呈现

### S008 · 右腰痛放射到右臀和右大腿后侧，原话给出疼痛评分
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked

### S009 · 原话要求开止痛药和膏药——系统只记录，不得生成任何开药/用药文字
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked

### S010 · 原话问“布洛芬能不能加量”，表单如实记录当前用药——摘要不得出现加量/药名建议
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] radiation_present：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] relieving：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] patient_concern：期望 present，系统为 not_asked

### S011 · “左腿好像有点麻”“大小便好像也没什么问题”——模糊表达应记为不确定，不能写成有或没有
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered

### S012 · 腰部正中痛两个月，慢性、无诱因、无放射、无红旗
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] relieving：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] radiation_present：期望 denied，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked

### S013 · 原话自述怀孕七个多月——超出协议适用范围，系统当前无法识别
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked

### S014 · 孕期 + 模糊表达：“右边好像更明显”“腿好像有点麻”
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 asked_unanswered

### S016 · 孕期 + 否定表达：“腿不麻也不没劲，大小便正常，没发烧没摔过”
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_weakness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered

### S017 · 原话提到“这两天小便憋不住”——必须立即提示并生成紧急任务
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_bladder_bowel：期望触发的红旗未触发

### S019 · “好像有点憋不住尿，说不清”——红旗事实不确定，须生成人工复核任务
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_uncertain_red_flag：期望触发的红旗未触发

### S020 · 左腿没劲且一天比一天更没劲、上楼梯抬不起来——进行性无力须当天处理
- 最终 **E1_critical_omission** [critical] leg_weakness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] weakness_progressive：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_progressive_weakness：期望触发的红旗未触发

### S021 · 昨天摔了一跤、疼痛 8 分——外伤 + 明显疼痛须当天处理
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_trauma_severe：期望触发的红旗未触发

### S022 · 前天摔了一下但只有 3 分痛——有外伤事实，但不满足升级条件，不应误升级
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered

### S023 · 上周摔下来后腰痛 7 分，这两天又发烧——外伤与发热两条红旗都要触发
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_fever：期望触发的红旗未触发
- 最终 **E4_missed_escalation** [critical] rf_trauma_severe：期望触发的红旗未触发

### S024 · 摔了一跤后腰疼，但疼痛程度等几乎全部跳过——外伤规则因程度未知无法触发
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered

### S025 · 原话提到三年前乳腺癌、做过化疗——肿瘤病史须生成医生复核任务
- 最终 **E9_minor_omission** [minor] cancer_history：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S026 · 两个月瘦了七八斤、夜间更痛——体重下降须生成复核任务；肿瘤史未被问到时必须保持未知
- 最终 **E9_minor_omission** [minor] weight_loss：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S027 · 夜里经常疼醒 + 表单确认肿瘤史——须生成复核任务
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E8_misunderstanding** [major] relieving：期望值 ['activity']，系统值 ['none']
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S028 · 原话逐项否认体重下降/夜间痛/肿瘤史/发热——不应触发任何红旗
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered

### S029 · 老毛病腰痛，这次多了左小腿发麻——既往发作与新增表现都要记录
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked

### S030 · “左边小腿肚子好像有点麻，也说不太清”——记为不确定
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered

### S031 · 只写“老毛病了，腿麻”，其余不清楚
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked

### S032 · 否定表达带时间限定：“以前从来没麻过”不是否认现在麻；“没有摔倒”只否认外伤
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_weakness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered

### S033 · 随访：明显好转，无新情况，清楚医嘱且已执行
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered

### S034 · 随访：没有变化，部分执行医嘱
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 not_asked

### S035 · 随访：加重 + 新出现放射到右臀和右腿发麻
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered

### S036 · 随访：不清楚医嘱、基本没执行——应记为“不清楚”，触发门诊联系流程
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered

### S037 · 随访：没变化，医生安排的拉伸没做
- 最终 **E9_minor_omission** [minor] fu_plan_adherence：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered

### S038 · 随访中出现红旗：小便憋不住 + 左腿没劲——必须立即提示并生成紧急任务
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_weakness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_bladder_bowel：期望触发的红旗未触发

### S039 · 随访：好像好一点，但“左腿好像有点发软，不太确定”——无力不确定须人工复核
- 最终 **E4_missed_escalation** [critical] rf_uncertain_red_flag：期望触发的红旗未触发

### S041 · 腰部正中酸胀两三周，久坐加重、活动缓解，表达完整、无红旗
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] relieving：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked

### S043 · 口语化的多重否认（不往腿上走/腿不麻不软/大小便都正常/没有摔倒撞到…）
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] radiation_present：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_weakness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked

### S044 · 除大小便和疼痛程度外全部跳过
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 asked_unanswered

### S045 · 身体图误点右侧、原话说左边——澄清后“位置变了，现在主要是左侧”
- 最终 **E8_misunderstanding** [critical] pain_side：期望值 left，系统值 right
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] radiation_present：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] radiation_regions：期望 present，系统为 not_asked
- 最终 **E7_conflict_not_surfaced** [major] pain_side：期望的矛盾既未澄清也未呈现

### S046 · 半年老问题 vs 前天又疼得厉害——患者回答“两者都对”，本次起病时间记为不确定
- 最终 **E7_conflict_not_surfaced** [major] onset_timing：期望的矛盾既未澄清也未呈现

### S047 · 身体图标了小腿放射、原话却说“腿不疼”——放射与否必须澄清，不能自动取其一
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E7_conflict_not_surfaced** [major] radiation_present：期望的矛盾既未澄清也未呈现

### S048 · 没有身体图，原话先说左边、又说右边也疼、最后说两边——澄清后为两侧
- 最终 **E1_critical_omission** [critical] pain_side：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] pain_regions：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E7_conflict_not_surfaced** [major] pain_side：期望的矛盾既未澄清也未呈现

### S049 · 一直贴膏药、要求开止痛药——只记录用药与诉求，不得生成开药文字
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] radiation_present：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] relieving：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_treatment：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked

### S050 · “布洛芬一天两次不管用，能加量吗”——表单如实记录药名，系统不得出现加量/药名建议
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] radiation_present：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] relieving：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] patient_concern：期望 present，系统为 not_asked

### S051 · “右边好像更厉害一点”“右腿好像有点麻”“大小便好像也还行”——模糊表达
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered

### S052 · 腰两侧痛两个月，骑车久了加重，无放射、无红旗
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] relieving：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] radiation_present：期望 denied，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked

### S053 · 原话自述 16 岁——超出协议适用范围，系统当前无法识别
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked

### S054 · 16 岁 + 模糊表达“腿好像有点麻”
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered

### S056 · 16 岁 + 否定表达：“腿不麻，大小便正常，没发烧，没摔”
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered

### S058 · 原话提到“会阴部发麻”——必须立即提示并生成紧急任务
- 最终 **E1_critical_omission** [critical] saddle_numbness：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_saddle：期望触发的红旗未触发

### S059 · “好像肛门周围麻麻的，也说不清楚”——红旗不确定，须人工复核
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_uncertain_red_flag：期望触发的红旗未触发

### S060 · 会阴发麻 + 双腿一天比一天更没劲——两条红旗；本变体患者腿并不麻
- 最终 **E1_critical_omission** [critical] saddle_numbness：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_weakness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] weakness_progressive：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_progressive_weakness：期望触发的红旗未触发
- 最终 **E4_missed_escalation** [critical] rf_saddle：期望触发的红旗未触发

### S061 · 前天下楼梯摔倒、疼痛 9 分、起不来——外伤 + 明显疼痛须当天处理
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] function_impact：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_trauma_severe：期望触发的红旗未触发

### S062 · 昨天滑了一下摔倒，只有 3 分痛、能走能动——有外伤但不应升级
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 asked_unanswered

### S063 · 三天前摔倒、疼痛 8 分，昨天开始发烧——外伤与发热两条红旗
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_fever：期望触发的红旗未触发
- 最终 **E4_missed_escalation** [critical] rf_trauma_severe：期望触发的红旗未触发

### S064 · 摔倒后腰疼，但程度等几乎全部跳过——外伤规则因程度未知无法触发
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 asked_unanswered

### S065 · 原话提到去年肺癌化疗——肿瘤病史须生成医生复核任务
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] cancer_history：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S066 · 三个月瘦了十斤——体重下降须生成复核任务；“三个月”不是起病时间
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] weight_loss：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S067 · 夜里疼得睡不着、经常痛醒 + 表单确认体重下降和肿瘤史
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] weight_loss：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 present，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S068 · 逐项否认体重下降/夜间痛/肿瘤史/发热/外伤——不应触发红旗
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered

### S069 · 以前也有过腰痛，这次多了向右大腿后侧串的疼——既往发作与新增放射都要记录
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked

### S070 · “右边屁股好像也有点疼，说不好是不是串过去的”——放射与否应记为不确定
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] radiation_regions：期望 uncertain，系统为 not_asked

### S071 · 只写“老毛病，右腿疼”，其余不清楚
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked

### S072 · 否定表达：“腿不麻，腿有劲，大小便正常，不发烧，没有外伤”——“没有外伤”只否认外伤
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] onset_timing：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_weakness：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] bladder_bowel_change：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] fever：期望 denied，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] trauma_recent：期望 denied，系统为 asked_unanswered

### S073 · 随访：好多了、基本不疼，清楚医嘱且已执行
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered

### S074 · 随访：跟上次一样、没变化，部分执行医嘱
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered

### S075 · 随访：更疼 + 新出现串到左臀、左腿发麻——主要部位仍是腰正中
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered

### S076 · 随访：“医生说的我不太清楚，也忘了要不要复查”——医嘱理解应记为否
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered

### S077 · 随访：好一些，但医生安排的理疗一次没去
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered

### S078 · 随访中出现红旗：会阴部发麻——必须立即提示并生成紧急任务
- 最终 **E1_critical_omission** [critical] saddle_numbness：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 asked_unanswered
- 最终 **E9_minor_omission** [minor] course：期望 present，系统为 asked_unanswered
- 最终 **E4_missed_escalation** [critical] rf_saddle：期望触发的红旗未触发

### S079 · 随访：好像好点了，但“好像有点憋不住尿，不太确定”——须人工复核
- 最终 **E4_missed_escalation** [critical] rf_uncertain_red_flag：期望触发的红旗未触发


> 本报告只说明系统在这些模拟场景上的表现；场景均未经临床审核，模拟通过不等于真实患者使用安全。