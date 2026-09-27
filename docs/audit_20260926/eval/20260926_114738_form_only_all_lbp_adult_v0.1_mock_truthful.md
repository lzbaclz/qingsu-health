# 评测报告 · split=all · arm=form_only · provider=mock · protocol=lbp_adult_v0.1

生成时间：2026-09-26 11:47:38　用时 18.1 秒　场景数：80　病例家族：20

## 最终记录（模拟认真的患者走完一键核对与问卷之后；该患者知道真值，等于用答案核对答案）

| 指标 | 值 |
|---|---|
| 场景通过率（无 critical 错误） | 0.9 |
| 家族通过率 | 0.8 |
| 关键事实完整率（分母 712） | 0.997 |
| 验收检查通过率 | 1.0 |
| 平均提问数（含核对与澄清） | 14.4 |
| 因紧急红旗终止问询的场景 | 7 |

| 错误代码 | 次数 |
|---|---|
| E4_missed_escalation | 6 |
| E5_unnecessary_escalation | 12 |
| E7_conflict_not_surfaced | 7 |
| E8_misunderstanding | 4 |
| E9_minor_omission | 100 |

## 抽取层（原话刚被抽取、还没核对与问卷时；也是“患者不认真核对”的最坏情况）

抽取层无 critical 错误的场景比例：1.0

| 代码 | 次数 |
|---|---|
| （无） | 0 |

X1 漏抽（问卷可兜住）· X2 编造（核对可兜住）· X4 原话层红旗漏识别（问卷可兜住）· X8 错抽（核对可兜住）

## 一键核对与紧急终止

- 核对决定：无；其中真值未规定、无法判断的条目 0 条（按"对"处理）
- 说明性记录（不计错）：{'S1_not_asked_after_urgent_stop': 48, 'S2_subsumed_by_urgent_stop': 1}
- 实际使用的抽取模型：{'—': 80}

## 逐场景

| id | 类别 | 提问 | 核对/澄清 | 紧急终止 | 红旗 | 抽取层错 | 最终 critical | 结果 |
|---|---|---|---|---|---|---|---|---|
| S001 | normal | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S002 | missing_info | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S003 | negation | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S004 | many_skips | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S005 | contradiction | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S006 | contradiction | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S007 | contradiction | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S008 | normal | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S009 | medication_request | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S010 | medication_request | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S011 | hedged | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S012 | normal | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S013 | out_of_scope | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S014 | out_of_scope | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S015 | missing_info | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S016 | negation | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S017 | red_flag | 1 | 0/0 | 是 | rf_bladder_bowel | 0 | 0 | PASS |
| S018 | red_flag | 2 | 0/0 | 是 | rf_saddle | 0 | 0 | PASS |
| S019 | red_flag | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S020 | red_flag | 16 | 0/0 | — | rf_progressive_weakness | 0 | 0 | PASS |
| S021 | red_flag | 16 | 0/0 | — | rf_trauma_severe | 0 | 0 | PASS |
| S022 | normal | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S023 | red_flag | 16 | 0/0 | — | rf_fever,rf_trauma_severe | 0 | 0 | PASS |
| S024 | many_skips | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S025 | red_flag | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S026 | red_flag | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S027 | red_flag | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S028 | negation | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S029 | new_symptom | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S030 | hedged | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S031 | missing_info | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S032 | negation | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S033 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S034 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S035 | new_symptom | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S036 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S037 | follow_up | 13 | 0/0 | — | — | 0 | 0 | PASS |
| S038 | red_flag | 5 | 0/0 | 是 | rf_bladder_bowel | 0 | 0 | PASS |
| S039 | hedged | 13 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S040 | many_skips | 13 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S041 | normal | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S042 | missing_info | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S043 | negation | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S044 | many_skips | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S045 | contradiction | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S046 | contradiction | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S047 | contradiction | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S048 | contradiction | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S049 | medication_request | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S050 | medication_request | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S051 | hedged | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S052 | normal | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S053 | out_of_scope | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S054 | out_of_scope | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S055 | missing_info | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S056 | negation | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S057 | red_flag | 1 | 0/0 | 是 | rf_bladder_bowel | 0 | 0 | PASS |
| S058 | red_flag | 2 | 0/0 | 是 | rf_saddle | 0 | 0 | PASS |
| S059 | red_flag | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S060 | red_flag | 2 | 0/0 | 是 | rf_saddle | 0 | 0 | PASS |
| S061 | red_flag | 16 | 0/0 | — | rf_trauma_severe | 0 | 0 | PASS |
| S062 | normal | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S063 | red_flag | 16 | 0/0 | — | rf_fever,rf_trauma_severe | 0 | 0 | PASS |
| S064 | many_skips | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S065 | red_flag | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S066 | red_flag | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S067 | red_flag | 16 | 0/0 | — | — | 0 | 1 | FAIL |
| S068 | negation | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S069 | new_symptom | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S070 | hedged | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S071 | missing_info | 16 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S072 | negation | 16 | 0/0 | — | — | 0 | 0 | PASS |
| S073 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S074 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S075 | new_symptom | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S076 | follow_up | 14 | 0/0 | — | — | 0 | 0 | PASS |
| S077 | follow_up | 13 | 0/0 | — | — | 0 | 0 | PASS |
| S078 | red_flag | 6 | 0/0 | 是 | rf_saddle | 0 | 0 | PASS |
| S079 | hedged | 13 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S080 | many_skips | 13 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |

## 明细

### S001 · 搬东西后左腰酸痛三天，表达完整、无红旗
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked

### S002 · 只写了“腰疼”，绝大多数问题答“不清楚”——系统必须保持未知
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S003 · 原话里一口气否认多项（腿不麻/有劲/没发烧/大小便都正常…），表单不再重复回答
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked

### S004 · 几乎每题都跳过——跳过必须记为“已问未答”，不能变成否认
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S005 · 身体图误点左侧、原话说右边——必须澄清；澄清后主要侧别为右
- 最终 **E8_misunderstanding** [critical] pain_side：期望值 right，系统值 left
- 最终 **E8_misunderstanding** [major] pain_regions：期望值 ['lower_back_right']，系统值 ['lower_back_left']
- 最终 **E9_minor_omission** [minor] function_impact：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E7_conflict_not_surfaced** [major] pain_side：期望的矛盾既未澄清也未呈现

### S006 · 原话前后时间矛盾：半年老问题 vs 前天突然又疼——需澄清本次起病时间
- 最终 **E7_conflict_not_surfaced** [major] onset_timing：期望的矛盾既未澄清也未呈现

### S007 · 原话先说腿不麻、后说开长途时脚好像有点麻——矛盾需澄清，结果记为不确定
- 最终 **E7_conflict_not_surfaced** [major] leg_numbness：期望的矛盾既未澄清也未呈现

### S008 · 右腰痛放射到右臀和右大腿后侧，原话给出疼痛评分
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked

### S009 · 原话要求开止痛药和膏药——系统只记录，不得生成任何开药/用药文字
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked

### S010 · 原话问“布洛芬能不能加量”，表单如实记录当前用药——摘要不得出现加量/药名建议
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] patient_concern：期望 present，系统为 not_asked

### S012 · 腰部正中痛两个月，慢性、无诱因、无放射、无红旗
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked

### S013 · 原话自述怀孕七个多月——超出协议适用范围，系统当前无法识别
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked

### S015 · 孕期 + 信息极少：只写“怀孕了，腰疼”，其余答不清楚
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S024 · 摔了一跤后腰疼，但疼痛程度等几乎全部跳过——外伤规则因程度未知无法触发
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S025 · 原话提到三年前乳腺癌、做过化疗——肿瘤病史须生成医生复核任务
- 最终 **E9_minor_omission** [minor] cancer_history：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S026 · 两个月瘦了七八斤、夜间更痛——体重下降须生成复核任务；肿瘤史未被问到时必须保持未知
- 最终 **E9_minor_omission** [minor] weight_loss：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S027 · 夜里经常疼醒 + 表单确认肿瘤史——须生成复核任务
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E8_misunderstanding** [major] relieving：期望值 ['activity']，系统值 ['none']
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S028 · 原话逐项否认体重下降/夜间痛/肿瘤史/发热——不应触发任何红旗
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked

### S029 · 老毛病腰痛，这次多了左小腿发麻——既往发作与新增表现都要记录
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked

### S030 · “左边小腿肚子好像有点麻，也说不太清”——记为不确定
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked

### S031 · 只写“老毛病了，腿麻”，其余不清楚
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S032 · 否定表达带时间限定：“以前从来没麻过”不是否认现在麻；“没有摔倒”只否认外伤
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked

### S034 · 随访：没有变化，部分执行医嘱
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 not_asked

### S040 · 随访：只写“还行”，除疼痛程度和大小便外全部跳过
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S041 · 腰部正中酸胀两三周，久坐加重、活动缓解，表达完整、无红旗
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked

### S042 · 只写“腰不舒服”，其余基本答不清楚
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S043 · 口语化的多重否认（不往腿上走/腿不麻不软/大小便都正常/没有摔倒撞到…）
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked

### S044 · 除大小便和疼痛程度外全部跳过
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S045 · 身体图误点右侧、原话说左边——澄清后“位置变了，现在主要是左侧”
- 最终 **E8_misunderstanding** [critical] pain_side：期望值 left，系统值 right
- 最终 **E7_conflict_not_surfaced** [major] pain_side：期望的矛盾既未澄清也未呈现

### S046 · 半年老问题 vs 前天又疼得厉害——患者回答“两者都对”，本次起病时间记为不确定
- 最终 **E7_conflict_not_surfaced** [major] onset_timing：期望的矛盾既未澄清也未呈现

### S047 · 身体图标了小腿放射、原话却说“腿不疼”——放射与否必须澄清，不能自动取其一
- 最终 **E7_conflict_not_surfaced** [major] radiation_present：期望的矛盾既未澄清也未呈现

### S048 · 没有身体图，原话先说左边、又说右边也疼、最后说两边——澄清后为两侧
- 最终 **E9_minor_omission** [minor] pain_regions：期望 present，系统为 not_asked
- 最终 **E7_conflict_not_surfaced** [major] pain_side：期望的矛盾既未澄清也未呈现

### S049 · 一直贴膏药、要求开止痛药——只记录用药与诉求，不得生成开药文字
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_treatment：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked

### S050 · “布洛芬一天两次不管用，能加量吗”——表单如实记录药名，系统不得出现加量/药名建议
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] current_medication：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] patient_concern：期望 present，系统为 not_asked

### S052 · 腰两侧痛两个月，骑车久了加重，无放射、无红旗
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked

### S053 · 原话自述 16 岁——超出协议适用范围，系统当前无法识别
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked

### S055 · 16 岁 + 信息极少：“我16岁，腰疼”
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S061 · 前天下楼梯摔倒、疼痛 9 分、起不来——外伤 + 明显疼痛须当天处理
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked

### S064 · 摔倒后腰疼，但程度等几乎全部跳过——外伤规则因程度未知无法触发
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S065 · 原话提到去年肺癌化疗——肿瘤病史须生成医生复核任务
- 最终 **E9_minor_omission** [minor] cancer_history：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S066 · 三个月瘦了十斤——体重下降须生成复核任务；“三个月”不是起病时间
- 最终 **E9_minor_omission** [minor] weight_loss：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S067 · 夜里疼得睡不着、经常痛醒 + 表单确认体重下降和肿瘤史
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] weight_loss：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 present，系统为 not_asked
- 最终 **E4_missed_escalation** [critical] rf_weight_loss_or_cancer：期望触发的红旗未触发

### S068 · 逐项否认体重下降/夜间痛/肿瘤史/发热/外伤——不应触发红旗
- 最终 **E9_minor_omission** [minor] weight_loss：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] cancer_history：期望 denied，系统为 not_asked

### S069 · 以前也有过腰痛，这次多了向右大腿后侧串的疼——既往发作与新增放射都要记录
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked

### S070 · “右边屁股好像也有点疼，说不好是不是串过去的”——放射与否应记为不确定
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] radiation_regions：期望 uncertain，系统为 not_asked

### S071 · 只写“老毛病，右腿疼”，其余不清楚
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S072 · 否定表达：“腿不麻，腿有劲，大小便正常，不发烧，没有外伤”——“没有外伤”只否认外伤
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked

### S080 · 随访：只写“一般”，除疼痛程度和大小便外全部跳过
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗


> 本报告只说明系统在这些模拟场景上的表现；场景均未经临床审核，模拟通过不等于真实患者使用安全。