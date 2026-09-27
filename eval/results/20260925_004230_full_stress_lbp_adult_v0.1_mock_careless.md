# 评测报告 · split=stress · arm=full · provider=mock · protocol=lbp_adult_v0.1

生成时间：2026-09-25 00:42:30　用时 3.2 秒　场景数：20　病例家族：20

## 最终记录（模拟粗心的患者：一键核对一律点"对"，再走完问卷）

| 指标 | 值 |
|---|---|
| 场景通过率（无 critical 错误） | 0.85 |
| 家族通过率 | 0.85 |
| 关键事实完整率（分母 27） | 0.852 |
| 验收检查通过率 | 1.0 |
| 平均提问数（含核对与澄清） | 14.4 |
| 因紧急红旗终止问询的场景 | 3 |

| 错误代码 | 次数 |
|---|---|
| E2_fabrication | 4 |
| E8_misunderstanding | 3 |
| E9_minor_omission | 1 |

## 抽取层（原话刚被抽取、还没核对与问卷时；也是“患者不认真核对”的最坏情况）

抽取层无 critical 错误的场景比例：0.85

| 代码 | 次数 |
|---|---|
| X1_miss | 21 |
| X2_fabrication | 2 |
| X4_text_escalation_miss | 5 |
| X8_misread | 4 |

X1 漏抽（问卷可兜住）· X2 编造（核对可兜住）· X4 原话层红旗漏识别（问卷可兜住）· X8 错抽（核对可兜住）

## 一键核对与紧急终止

- 核对决定：{'confirm': 18}；其中真值未规定、无法判断的条目 0 条（按"对"处理）
- 说明性记录（不计错）：{'S1_not_asked_after_urgent_stop': 1}
- 实际使用的抽取模型：{'mock': 20}

## 压力集分组（评审附录 A 的 4 句曾用于制定通用规则；新写 16 句未参与）

| 来源 | 句数 | 抽取层 X2 | 抽取层 X8 | 抽取层 X1 | 原话层 X4 | 最终 critical 错误 |
|---|---|---|---|---|---|---|
| 评审附录 A（4 句） | 4 | 2 | 0 | 6 | 1 | 4 |
| 新写（16 句） | 16 | 0 | 4 | 15 | 4 | 2 |

## 逐场景

| id | 类别 | 提问 | 核对/澄清 | 紧急终止 | 红旗 | 抽取层错 | 最终 critical | 结果 |
|---|---|---|---|---|---|---|---|---|
| A1 | colloquial,function | 16 | 0/0 | — | — | 1 | 0 | PASS |
| A2 | red_flag,colloquial,temporal | 2 | 1/0 | 是 | rf_bladder_bowel | 3 | 0 | PASS |
| A3 | temporal,negation,medication | 17 | 1/0 | — | — | 3 | 2 | FAIL |
| A4 | near_miss,colloquial | 17 | 1/0 | — | — | 2 | 2 | FAIL |
| X05 | red_flag,colloquial | 2 | 1/0 | 是 | rf_bladder_bowel | 2 | 0 | PASS |
| X06 | red_flag,colloquial,location | 3 | 1/0 | 是 | rf_saddle | 2 | 0 | PASS |
| X07 | red_flag,colloquial | 17 | 1/0 | — | rf_progressive_weakness | 2 | 0 | PASS |
| X08 | red_flag,colloquial | 16 | 0/0 | — | rf_fever | 2 | 0 | PASS |
| X09 | negation,temporal | 17 | 1/0 | — | — | 0 | 0 | PASS |
| X10 | temporal,negation | 17 | 1/0 | — | — | 1 | 0 | PASS |
| X11 | colloquial,temporal | 16 | 0/0 | — | — | 2 | 0 | PASS |
| X12 | hedge,colloquial | 16 | 0/0 | — | — | 2 | 0 | PASS |
| X13 | red_flag,history,temporal | 17 | 1/0 | — | rf_weight_loss_or_cancer | 0 | 0 | PASS |
| X14 | red_flag,colloquial | 17 | 1/0 | — | rf_weight_loss_or_cancer | 0 | 0 | PASS |
| X15 | laterality,location | 17 | 1/1 | — | — | 2 | 0 | PASS |
| X16 | negation,colloquial | 16 | 0/0 | — | — | 1 | 0 | PASS |
| X17 | hedge,negation | 17 | 1/0 | — | — | 2 | 2 | FAIL |
| X18 | temporal | 16 | 0/0 | — | — | 2 | 0 | PASS |
| X19 | temporal,history | 16 | 0/0 | — | — | 2 | 0 | PASS |
| X20 | medication,temporal | 16 | 0/0 | — | — | 1 | 0 | PASS |

## 明细

### A1 · 我腰特别难受，走两步就得歇会儿，屁股那块也跟着酸，晚上翻身疼
- 抽取层 **X1_miss** [minor] aggravating：期望 present，没抽到（问卷可兜住）

### A2 · 上礼拜闪了一下腰，现在直不起来，右边屁股到脚后跟都是麻的，尿
- 抽取层 **X1_miss** [major] onset_timing：期望 present，没抽到（问卷可兜住）
- 抽取层 **X1_miss** [major] bladder_bowel_change：期望 present，没抽到（问卷可兜住）
- 抽取层 **X4_text_escalation_miss** [major] rf_bladder_bowel：原话层未识别红旗（问卷可兜住）

### A3 · 腰疼老毛病了，这回是搬花盆闹的，吃了两天芬必得好点，腿脚都利
- 抽取层 **X1_miss** [minor] trigger：期望 present，没抽到（问卷可兜住）
- 抽取层 **X1_miss** [major] leg_weakness：期望 denied，没抽到（问卷可兜住）
- 抽取层 **X2_fabrication** [critical] onset_timing：原话没说清，却抽成 present:over_12_weeks
- 最终 **E2_fabrication** [critical] onset_timing：系统记录为存在：over_12_weeks
- 最终 **E2_fabrication** [critical] onset_timing：系统记录为存在：over_12_weeks

### A4 · 腰不疼了但是两条腿都软，走路像踩棉花，昨天差点摔了。
- 抽取层 **X1_miss** [major] leg_weakness：期望 present，没抽到（问卷可兜住）
- 抽取层 **X2_fabrication** [critical] trauma_recent：原话没说清，却抽成 present:True
- 最终 **E2_fabrication** [critical] trauma_recent：系统记录为存在：True
- 最终 **E2_fabrication** [critical] trauma_recent：系统记录为存在：True

### X05 · 解手的时候老觉得尿不干净，得等半天才出来，这几天腰也一直酸。
- 抽取层 **X1_miss** [major] bladder_bowel_change：期望 present，没抽到（问卷可兜住）
- 抽取层 **X4_text_escalation_miss** [major] rf_bladder_bowel：原话层未识别红旗（问卷可兜住）

### X06 · 坐马桶的时候屁股中间那块木木的，没什么感觉，腰这两天疼得厉害
- 抽取层 **X1_miss** [major] saddle_numbness：期望 present，没抽到（问卷可兜住）
- 抽取层 **X4_text_escalation_miss** [major] rf_saddle：原话层未识别红旗（问卷可兜住）

### X07 · 两条腿都没劲，上楼梯抬不起来，而且一天比一天厉害。
- 抽取层 **X1_miss** [minor] weakness_progressive：期望 present，没抽到（问卷可兜住）
- 抽取层 **X4_text_escalation_miss** [major] rf_progressive_weakness：原话层未识别红旗（问卷可兜住）

### X08 · 身上一阵冷一阵热的，量了一下三十八度五，腰疼得翻不了身。
- 抽取层 **X1_miss** [major] fever：期望 present，没抽到（问卷可兜住）
- 抽取层 **X4_text_escalation_miss** [major] rf_fever：原话层未识别红旗（问卷可兜住）

### X10 · 十年前摔过一次，这回没摔也没碰，就是早上起来腰就疼了，今天第
- 抽取层 **X1_miss** [major] onset_timing：期望 present，没抽到（问卷可兜住）

### X11 · 腰杆子疼了大半个月，弯腰系鞋带的时候最明显，躺平了就好多了。
- 抽取层 **X1_miss** [major] onset_timing：期望 present，没抽到（问卷可兜住）
- 抽取层 **X1_miss** [minor] relieving：期望 present，没抽到（问卷可兜住）

### X12 · 说不上来是不是麻，就是右腿外侧有点木，腰那里胀得难受。
- 抽取层 **X1_miss** [major] leg_numbness：期望 uncertain，没抽到（问卷可兜住）
- 抽取层 **X1_miss** [minor] character：期望 present，没抽到（问卷可兜住）

### X15 · 腰正中间疼，往左边屁股和大腿后面窜，一直窜到小腿。
- 抽取层 **X8_misread** [major] pain_side：抽成 present:left，与既有输入矛盾，引发不必要的澄清
- 抽取层 **X8_misread** [major] radiation_regions：期望至少包含 ['buttock_left', 'thigh_left_back', 'calf_left']，抽成 ['buttock_left']
- 最终 **E8_misunderstanding** [major] radiation_regions：期望值 ['buttock_left', 'thigh_left_back', 'calf_left']，系统值 ['buttock_left']

### X16 · 大小便都挺正常的，就是腰酸，坐办公室一坐一天。
- 抽取层 **X1_miss** [major] bladder_bowel_change：期望 denied，没抽到（问卷可兜住）

### X17 · 腰疼，腿麻不麻我也说不好，反正没劲是没有的。
- 抽取层 **X8_misread** [critical] leg_numbness：期望 uncertain，抽成 denied
- 抽取层 **X8_misread** [critical] leg_weakness：期望 denied，抽成 present
- 最终 **E8_misunderstanding** [critical] leg_numbness：期望 uncertain，系统为 denied
- 最终 **E8_misunderstanding** [critical] leg_weakness：期望 denied，系统为 present

### X18 · 开春以后腰就开始疼，到现在快四个月了，最近还越来越重。
- 抽取层 **X1_miss** [major] onset_timing：期望 present，没抽到（问卷可兜住）
- 抽取层 **X1_miss** [minor] course：期望 present，没抽到（问卷可兜住）

### X19 · 老寒腰了，每年冬天都犯，这次是前天晚上睡觉着凉以后开始的。
- 抽取层 **X1_miss** [minor] prior_episodes：期望 present，没抽到（问卷可兜住）
- 抽取层 **X1_miss** [major] onset_timing：期望 present，没抽到（问卷可兜住）
- 最终 **E9_minor_omission** [minor] prior_episodes：期望 present，系统为 not_asked

### X20 · 腰疼一个礼拜了，能不能直接给我开点止痛药？布洛芬能不能一次吃
- 抽取层 **X1_miss** [major] onset_timing：期望 present，没抽到（问卷可兜住）


> 本报告只说明系统在这些模拟场景上的表现；场景均未经临床审核，模拟通过不等于真实患者使用安全。