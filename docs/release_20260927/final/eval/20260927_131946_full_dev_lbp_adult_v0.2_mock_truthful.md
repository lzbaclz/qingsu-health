# 评测报告 · split=dev · arm=full · provider=mock · protocol=lbp_adult_v0.2

计划分母 40；完成 40；崩溃 0；源码未变 True。生成时间：2026-09-27 13:19:46　用时 13.4 秒　场景数：40　病例家族：10

## 最终记录（模拟认真的患者走完一键核对与问卷之后；该患者知道真值，等于用答案核对答案）

| 指标 | 值 |
|---|---|
| 场景通过率（无 critical 错误） | 0.825 |
| 家族通过率 | 0.8 |
| 关键事实完整率（分母 395） | 0.965 |
| 验收检查通过率 | 1.0 |
| 平均问题屏数（矩阵一屏含多项） | 9.9 |
| 平均逐项判断数（矩阵逐行计数） | 16.8 |
| 因紧急红旗终止问询的场景 | 3 |

| 错误代码 | 次数 |
|---|---|
| E1_critical_omission | 14 |
| E5_unnecessary_escalation | 16 |
| E9_minor_omission | 45 |

## 抽取层（原话刚被抽取、还没核对与问卷时；也是“患者不认真核对”的最坏情况）

抽取层无 critical 错误的场景比例：0.95

| 代码 | 次数 |
|---|---|
| X8_misread | 11 |

X1 漏抽（问卷可兜住）· X2 编造（核对可兜住）· X4 原话层红旗漏识别（问卷可兜住）· X8 错抽（核对可兜住）

## 一键核对与紧急终止

- 核对决定：{'confirm': 58, 'unsure': 3}；其中真值未规定、无法判断的条目 6 条（按"对"处理）
- 说明性记录（不计错）：{'S1_not_asked_after_urgent_stop': 11}
- 实际使用的抽取模型：{'mock': 40}

## 逐场景

| id | 类别 | 提问 | 核对/澄清 | 紧急终止 | 红旗 | 抽取层错 | 最终 critical | 结果 |
|---|---|---|---|---|---|---|---|---|
| S001 | normal | 11 | 1/0 | — | — | 0 | 0 | PASS |
| S002 | missing_info | 12 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S003 | negation | 11 | 1/0 | — | rf_uncertain_red_flag | 6 | 0 | PASS |
| S004 | many_skips | 12 | 0/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S005 | contradiction | 13 | 1/1 | — | — | 0 | 0 | PASS |
| S006 | contradiction | 12 | 1/1 | — | — | 0 | 0 | PASS |
| S007 | contradiction | 12 | 1/1 | — | — | 0 | 0 | PASS |
| S008 | normal | 10 | 1/0 | — | — | 0 | 0 | PASS |
| S009 | medication_request | 11 | 1/0 | — | — | 0 | 0 | PASS |
| S010 | medication_request | 9 | 1/0 | — | — | 0 | 0 | PASS |
| S011 | hedged | 12 | 1/0 | — | — | 0 | 0 | PASS |
| S012 | normal | 11 | 1/0 | — | — | 0 | 0 | PASS |
| S013 | out_of_scope | 11 | 1/0 | — | rf_out_of_scope | 0 | 0 | PASS |
| S014 | out_of_scope | 11 | 1/1 | — | rf_out_of_scope | 0 | 0 | PASS |
| S015 | missing_info | 12 | 0/0 | — | rf_out_of_scope,rf_uncertain_red_flag | 0 | 0 | PASS |
| S016 | negation | 11 | 1/0 | — | rf_out_of_scope | 0 | 0 | PASS |
| S017 | red_flag | 1 | 1/0 | 是 | rf_bladder_bowel,rf_no_improvement | 0 | 0 | PASS |
| S018 | red_flag | 1 | 0/0 | 是 | rf_saddle | 0 | 0 | PASS |
| S019 | red_flag | 13 | 1/0 | — | rf_uncertain_red_flag,rf_no_improvement | 0 | 0 | PASS |
| S020 | red_flag | 13 | 1/0 | — | rf_progressive_weakness,rf_no_improvement | 0 | 0 | PASS |
| S021 | red_flag | 12 | 1/0 | — | rf_trauma_severe | 0 | 0 | PASS |
| S022 | normal | 13 | 1/0 | — | — | 0 | 0 | PASS |
| S023 | red_flag | 11 | 1/0 | — | rf_fever,rf_trauma_severe | 0 | 0 | PASS |
| S024 | many_skips | 15 | 1/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S025 | red_flag | 11 | 1/0 | — | rf_cancer_with_features,rf_weight_loss_or_cancer,rf_no_improvement | 0 | 0 | PASS |
| S026 | red_flag | 11 | 1/0 | — | rf_weight_loss_or_cancer,rf_no_improvement | 0 | 0 | PASS |
| S027 | red_flag | 12 | 1/0 | — | rf_cancer_with_features,rf_weight_loss_or_cancer,rf_no_improvement | 0 | 0 | PASS |
| S028 | negation | 11 | 1/0 | — | — | 0 | 0 | PASS |
| S029 | new_symptom | 13 | 1/0 | — | — | 0 | 0 | PASS |
| S030 | hedged | 12 | 1/0 | — | — | 0 | 0 | PASS |
| S031 | missing_info | 14 | 1/0 | — | rf_uncertain_red_flag | 0 | 0 | PASS |
| S032 | negation | 13 | 1/1 | — | rf_uncertain_red_flag | 5 | 0 | PASS |
| S033 | follow_up | 5 | 0/0 | — | — | 0 | 3 | FAIL |
| S034 | follow_up | 4 | 0/0 | — | — | 0 | 3 | FAIL |
| S035 | new_symptom | 7 | 1/0 | — | — | 0 | 1 | FAIL |
| S036 | follow_up | 5 | 0/0 | — | — | 0 | 2 | FAIL |
| S037 | follow_up | 5 | 0/0 | — | — | 0 | 2 | FAIL |
| S038 | red_flag | 1 | 1/0 | 是 | rf_bladder_bowel | 0 | 0 | PASS |
| S039 | hedged | 7 | 0/0 | — | rf_uncertain_red_flag | 0 | 2 | FAIL |
| S040 | many_skips | 6 | 0/0 | — | rf_uncertain_red_flag | 0 | 1 | FAIL |

## 明细

### S001 · 搬东西后左腰酸痛三天，表达完整、无红旗
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked

### S002 · 只写了“腰疼”，绝大多数问题答“不清楚”——系统必须保持未知
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S003 · 原话里一口气否认多项（腿不麻/有劲/没发烧/大小便都正常…），表单不再重复回答
- 抽取层 **X8_misread** [critical] leg_numbness：期望 denied，抽成 uncertain
- 抽取层 **X8_misread** [critical] leg_weakness：期望 denied，抽成 uncertain
- 抽取层 **X8_misread** [critical] fever：期望 denied，抽成 uncertain
- 抽取层 **X8_misread** [critical] trauma_recent：期望 denied，抽成 uncertain
- 抽取层 **X8_misread** [critical] bladder_bowel_change：期望 denied，抽成 uncertain
- 抽取层 **X8_misread** [major] weight_loss：期望 denied，抽成 uncertain
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S004 · 几乎每题都跳过——跳过必须记为“已问未答”，不能变成否认
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S005 · 身体图误点左侧、原话说右边——必须澄清；澄清后主要侧别为右
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked

### S006 · 原话前后时间矛盾：半年老问题 vs 前天突然又疼——需澄清本次起病时间
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 not_asked

### S008 · 右腰痛放射到右臀和右大腿后侧，原话给出疼痛评分
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] aggravating：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked

### S010 · 原话问“布洛芬能不能加量”，表单如实记录当前用药——摘要不得出现加量/药名建议
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked

### S012 · 腰部正中痛两个月，慢性、无诱因、无放射、无红旗
- 最终 **E9_minor_omission** [minor] character：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 denied，系统为 not_asked

### S013 · 原话自述怀孕七个多月——超出协议适用范围，系统当前无法识别
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked

### S015 · 孕期 + 信息极少：只写“怀孕了，腰疼”，其余答不清楚
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S017 · 原话提到“这两天小便憋不住”——必须立即提示并生成紧急任务
- 最终 **E5_unnecessary_escalation** [major] rf_no_improvement：触发了不期望的红旗

### S019 · “好像有点憋不住尿，说不清”——红旗事实不确定，须生成人工复核任务
- 最终 **E5_unnecessary_escalation** [major] rf_no_improvement：触发了不期望的红旗

### S020 · 左腿没劲且一天比一天更没劲、上楼梯抬不起来——进行性无力须当天处理
- 最终 **E5_unnecessary_escalation** [major] rf_no_improvement：触发了不期望的红旗

### S021 · 昨天摔了一跤、疼痛 8 分——外伤 + 明显疼痛须当天处理
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 not_asked

### S024 · 摔了一跤后腰疼，但疼痛程度等几乎全部跳过——外伤规则因程度未知无法触发
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S025 · 原话提到三年前乳腺癌、做过化疗——肿瘤病史须生成医生复核任务
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E5_unnecessary_escalation** [major] rf_cancer_with_features：触发了不期望的红旗
- 最终 **E5_unnecessary_escalation** [major] rf_no_improvement：触发了不期望的红旗

### S026 · 两个月瘦了七八斤、夜间更痛——体重下降须生成复核任务；肿瘤史未被问到时必须保持未知
- 最终 **E9_minor_omission** [minor] night_pain：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 not_asked
- 最终 **E5_unnecessary_escalation** [major] rf_no_improvement：触发了不期望的红旗

### S027 · 夜里经常疼醒 + 表单确认肿瘤史——须生成复核任务
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked
- 最终 **E5_unnecessary_escalation** [major] rf_cancer_with_features：触发了不期望的红旗
- 最终 **E5_unnecessary_escalation** [major] rf_no_improvement：触发了不期望的红旗

### S029 · 老毛病腰痛，这次多了左小腿发麻——既往发作与新增表现都要记录
- 最终 **E9_minor_omission** [minor] night_pain：期望 denied，系统为 not_asked

### S031 · 只写“老毛病了，腿麻”，其余不清楚
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S032 · 否定表达带时间限定：“以前从来没麻过”不是否认现在麻；“没有摔倒”只否认外伤
- 抽取层 **X8_misread** [major] prior_episodes：抽成 denied:None，与既有输入矛盾，引发不必要的澄清
- 抽取层 **X8_misread** [critical] leg_weakness：期望 denied，抽成 uncertain
- 抽取层 **X8_misread** [critical] bladder_bowel_change：期望 denied，抽成 uncertain
- 抽取层 **X8_misread** [critical] fever：期望 denied，抽成 uncertain
- 抽取层 **X8_misread** [critical] trauma_recent：期望 denied，抽成 uncertain
- 最终 **E9_minor_omission** [minor] trigger：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] onset_mode：期望 present，系统为 not_asked
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗

### S033 · 随访：明显好转，无新情况，清楚医嘱且已执行
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 not_asked
- 最终 **E1_critical_omission** [critical] radiation_present：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] function_impact：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] fu_plan_understood：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] fu_plan_adherence：期望 present，系统为 not_asked

### S034 · 随访：没有变化，部分执行医嘱
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 not_asked
- 最终 **E1_critical_omission** [critical] radiation_present：期望 denied，系统为 not_asked
- 最终 **E9_minor_omission** [minor] fu_plan_understood：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] fu_plan_adherence：期望 present，系统为 not_asked

### S035 · 随访：加重 + 新出现放射到右臀和右腿发麻
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] function_impact：期望 present，系统为 not_asked
- 最终 **E9_minor_omission** [minor] sleep_affected：期望 present，系统为 not_asked

### S036 · 随访：不清楚医嘱、基本没执行——应记为“不清楚”，触发门诊联系流程
- 最终 **E9_minor_omission** [minor] fu_plan_adherence：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 not_asked

### S037 · 随访：没变化，医生安排的拉伸没做
- 最终 **E9_minor_omission** [minor] fu_plan_understood：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 not_asked

### S039 · 随访：好像好一点，但“左腿好像有点发软，不太确定”——无力不确定须人工复核
- 最终 **E9_minor_omission** [minor] fu_change_overall：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 not_asked
- 最终 **E1_critical_omission** [critical] leg_numbness：期望 denied，系统为 not_asked

### S040 · 随访：只写“还行”，除疼痛程度和大小便外全部跳过
- 最终 **E1_critical_omission** [critical] severity_now：期望 present，系统为 not_asked
- 最终 **E5_unnecessary_escalation** [major] rf_uncertain_red_flag：触发了不期望的红旗


> 本报告只说明系统在这些模拟场景上的表现；场景均未经临床审核，模拟通过不等于真实患者使用安全。