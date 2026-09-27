# 评测场景索引

共 80 条场景，20 个病例家族（F01–F10 在 dev，F11–F20 在 locked，家族不跨集）。
所有场景均为模拟数据，非真实患者；ground_truth 为工程占位，需临床审核（见各文件 notes/review）。

## 类别分布

| 类别 | dev | locked |
|---|---|---|
| normal | 4 | 3 |
| missing_info | 3 | 3 |
| negation | 4 | 4 |
| contradiction | 3 | 4 |
| new_symptom | 2 | 2 |
| medication_request | 2 | 2 |
| red_flag | 10 | 10 |
| out_of_scope | 2 | 2 |
| hedged | 3 | 3 |
| many_skips | 3 | 3 |
| follow_up | 4 | 4 |
| （kind=follow_up 计数） | 8 | 8 |

## 病例家族

| 家族 | 场景 |
|---|---|
| F01_left_lbp_after_lifting | S001, S002, S003, S004 |
| F02_right_lbp_radiating_driver | S005, S006, S007, S008 |
| F03_central_lbp_medication_request | S009, S010, S011, S012 |
| F04_pregnant_lbp_out_of_scope | S013, S014, S015, S016 |
| F05_chronic_lbp_cauda_equina_flags | S017, S018, S019, S020 |
| F06_fall_from_ladder_trauma | S021, S022, S023, S024 |
| F07_breast_cancer_history_back_pain | S025, S026, S027, S028 |
| F08_recurrent_lbp_new_numbness | S029, S030, S031, S032 |
| F09_followup_right_lbp_sitting | S033, S034, S035, S036 |
| F10_followup_left_lbp_radiating | S037, S038, S039, S040 |
| F11_central_lbp_programmer | S041, S042, S043, S044 |
| F12_left_lbp_radiating_farmer | S045, S046, S047, S048 |
| F13_bilateral_lbp_medication_request | S049, S050, S051, S052 |
| F14_teenager_lbp_out_of_scope | S053, S054, S055, S056 |
| F15_chronic_lbp_bilateral_numbness_flags | S057, S058, S059, S060 |
| F16_fall_down_stairs_trauma | S061, S062, S063, S064 |
| F17_lung_cancer_history_back_pain | S065, S066, S067, S068 |
| F18_recurrent_lbp_new_radiation | S069, S070, S071, S072 |
| F19_followup_central_lbp_teacher | S073, S074, S075, S076 |
| F20_followup_right_lbp_calf_driver | S077, S078, S079, S080 |

## 场景列表

| id | family | split | kind | category | title | expected_alerts | expected_conflicts |
|---|---|---|---|---|---|---|---|
| S001 | F01_left_lbp_after_lifting | dev | pre_visit | normal | 搬东西后左腰酸痛三天，表达完整、无红旗 | — | — |
| S002 | F01_left_lbp_after_lifting | dev | pre_visit | missing_info | 只写了“腰疼”，绝大多数问题答“不清楚”——系统必须保持未知 | — | — |
| S003 | F01_left_lbp_after_lifting | dev | pre_visit | negation | 原话里一口气否认多项（腿不麻/有劲/没发烧/大小便都正常…），表单不再重复回答 | — | — |
| S004 | F01_left_lbp_after_lifting | dev | pre_visit | many_skips | 几乎每题都跳过——跳过必须记为“已问未答”，不能变成否认 | — | — |
| S005 | F02_right_lbp_radiating_driver | dev | pre_visit | contradiction | 身体图误点左侧、原话说右边——必须澄清；澄清后主要侧别为右 | — | pain_side |
| S006 | F02_right_lbp_radiating_driver | dev | pre_visit | contradiction | 原话前后时间矛盾：半年老问题 vs 前天突然又疼——需澄清本次起病时间 | — | onset_timing |
| S007 | F02_right_lbp_radiating_driver | dev | pre_visit | contradiction | 原话先说腿不麻、后说开长途时脚好像有点麻——矛盾需澄清，结果记为不确定 | — | leg_numbness |
| S008 | F02_right_lbp_radiating_driver | dev | pre_visit | normal | 右腰痛放射到右臀和右大腿后侧，原话给出疼痛评分 | — | — |
| S009 | F03_central_lbp_medication_request | dev | pre_visit | medication_request | 原话要求开止痛药和膏药——系统只记录，不得生成任何开药/用药文字 | — | — |
| S010 | F03_central_lbp_medication_request | dev | pre_visit | medication_request | 原话问“布洛芬能不能加量”，表单如实记录当前用药——摘要不得出现加量/药名建议 | — | — |
| S011 | F03_central_lbp_medication_request | dev | pre_visit | hedged | “左腿好像有点麻”“大小便好像也没什么问题”——模糊表达应记为不确定，不能写成有或没有 | — | — |
| S012 | F03_central_lbp_medication_request | dev | pre_visit | normal | 腰部正中痛两个月，慢性、无诱因、无放射、无红旗 | — | — |
| S013 | F04_pregnant_lbp_out_of_scope | dev | pre_visit | out_of_scope | 原话自述怀孕七个多月——超出协议适用范围，系统当前无法识别 | — | — |
| S014 | F04_pregnant_lbp_out_of_scope | dev | pre_visit | out_of_scope | 孕期 + 模糊表达：“右边好像更明显”“腿好像有点麻” | — | — |
| S015 | F04_pregnant_lbp_out_of_scope | dev | pre_visit | missing_info | 孕期 + 信息极少：只写“怀孕了，腰疼”，其余答不清楚 | — | — |
| S016 | F04_pregnant_lbp_out_of_scope | dev | pre_visit | negation | 孕期 + 否定表达：“腿不麻也不没劲，大小便正常，没发烧没摔过” | — | — |
| S017 | F05_chronic_lbp_cauda_equina_flags | dev | pre_visit | red_flag | 原话提到“这两天小便憋不住”——必须立即提示并生成紧急任务 | rf_bladder_bowel | — |
| S018 | F05_chronic_lbp_cauda_equina_flags | dev | pre_visit | red_flag | 原话只说“屁股那一片木木的”，表单明确回答会阴发麻——必须触发 rf_saddle | rf_saddle | — |
| S019 | F05_chronic_lbp_cauda_equina_flags | dev | pre_visit | red_flag | “好像有点憋不住尿，说不清”——红旗事实不确定，须生成人工复核任务 | rf_uncertain_red_flag | — |
| S020 | F05_chronic_lbp_cauda_equina_flags | dev | pre_visit | red_flag | 左腿没劲且一天比一天更没劲、上楼梯抬不起来——进行性无力须当天处理 | rf_progressive_weakness | — |
| S021 | F06_fall_from_ladder_trauma | dev | pre_visit | red_flag | 昨天摔了一跤、疼痛 8 分——外伤 + 明显疼痛须当天处理 | rf_trauma_severe | — |
| S022 | F06_fall_from_ladder_trauma | dev | pre_visit | normal | 前天摔了一下但只有 3 分痛——有外伤事实，但不满足升级条件，不应误升级 | — | — |
| S023 | F06_fall_from_ladder_trauma | dev | pre_visit | red_flag | 上周摔下来后腰痛 7 分，这两天又发烧——外伤与发热两条红旗都要触发 | rf_fever, rf_trauma_severe | — |
| S024 | F06_fall_from_ladder_trauma | dev | pre_visit | many_skips | 摔了一跤后腰疼，但疼痛程度等几乎全部跳过——外伤规则因程度未知无法触发 | — | — |
| S025 | F07_breast_cancer_history_back_pain | dev | pre_visit | red_flag | 原话提到三年前乳腺癌、做过化疗——肿瘤病史须生成医生复核任务 | rf_weight_loss_or_cancer | — |
| S026 | F07_breast_cancer_history_back_pain | dev | pre_visit | red_flag | 两个月瘦了七八斤、夜间更痛——体重下降须生成复核任务；肿瘤史未被问到时必须保持未知 | rf_weight_loss_or_cancer | — |
| S027 | F07_breast_cancer_history_back_pain | dev | pre_visit | red_flag | 夜里经常疼醒 + 表单确认肿瘤史——须生成复核任务 | rf_weight_loss_or_cancer | — |
| S028 | F07_breast_cancer_history_back_pain | dev | pre_visit | negation | 原话逐项否认体重下降/夜间痛/肿瘤史/发热——不应触发任何红旗 | — | — |
| S029 | F08_recurrent_lbp_new_numbness | dev | pre_visit | new_symptom | 老毛病腰痛，这次多了左小腿发麻——既往发作与新增表现都要记录 | — | — |
| S030 | F08_recurrent_lbp_new_numbness | dev | pre_visit | hedged | “左边小腿肚子好像有点麻，也说不太清”——记为不确定 | — | — |
| S031 | F08_recurrent_lbp_new_numbness | dev | pre_visit | missing_info | 只写“老毛病了，腿麻”，其余不清楚 | — | — |
| S032 | F08_recurrent_lbp_new_numbness | dev | pre_visit | negation | 否定表达带时间限定：“以前从来没麻过”不是否认现在麻；“没有摔倒”只否认外伤 | — | — |
| S033 | F09_followup_right_lbp_sitting | dev | follow_up | follow_up | 随访：明显好转，无新情况，清楚医嘱且已执行 | — | — |
| S034 | F09_followup_right_lbp_sitting | dev | follow_up | follow_up | 随访：没有变化，部分执行医嘱 | — | — |
| S035 | F09_followup_right_lbp_sitting | dev | follow_up | new_symptom | 随访：加重 + 新出现放射到右臀和右腿发麻 | — | — |
| S036 | F09_followup_right_lbp_sitting | dev | follow_up | follow_up | 随访：不清楚医嘱、基本没执行——应记为“不清楚”，触发门诊联系流程 | — | — |
| S037 | F10_followup_left_lbp_radiating | dev | follow_up | follow_up | 随访：没变化，医生安排的拉伸没做 | — | — |
| S038 | F10_followup_left_lbp_radiating | dev | follow_up | red_flag | 随访中出现红旗：小便憋不住 + 左腿没劲——必须立即提示并生成紧急任务 | rf_bladder_bowel | — |
| S039 | F10_followup_left_lbp_radiating | dev | follow_up | hedged | 随访：好像好一点，但“左腿好像有点发软，不太确定”——无力不确定须人工复核 | rf_uncertain_red_flag | — |
| S040 | F10_followup_left_lbp_radiating | dev | follow_up | many_skips | 随访：只写“还行”，除疼痛程度和大小便外全部跳过 | — | — |
| S041 | F11_central_lbp_programmer | locked | pre_visit | normal | 腰部正中酸胀两三周，久坐加重、活动缓解，表达完整、无红旗 | — | — |
| S042 | F11_central_lbp_programmer | locked | pre_visit | missing_info | 只写“腰不舒服”，其余基本答不清楚 | — | — |
| S043 | F11_central_lbp_programmer | locked | pre_visit | negation | 口语化的多重否认（不往腿上走/腿不麻不软/大小便都正常/没有摔倒撞到…） | — | — |
| S044 | F11_central_lbp_programmer | locked | pre_visit | many_skips | 除大小便和疼痛程度外全部跳过 | — | — |
| S045 | F12_left_lbp_radiating_farmer | locked | pre_visit | contradiction | 身体图误点右侧、原话说左边——澄清后“位置变了，现在主要是左侧” | — | pain_side |
| S046 | F12_left_lbp_radiating_farmer | locked | pre_visit | contradiction | 半年老问题 vs 前天又疼得厉害——患者回答“两者都对”，本次起病时间记为不确定 | — | onset_timing |
| S047 | F12_left_lbp_radiating_farmer | locked | pre_visit | contradiction | 身体图标了小腿放射、原话却说“腿不疼”——放射与否必须澄清，不能自动取其一 | — | radiation_present |
| S048 | F12_left_lbp_radiating_farmer | locked | pre_visit | contradiction | 没有身体图，原话先说左边、又说右边也疼、最后说两边——澄清后为两侧 | — | pain_side |
| S049 | F13_bilateral_lbp_medication_request | locked | pre_visit | medication_request | 一直贴膏药、要求开止痛药——只记录用药与诉求，不得生成开药文字 | — | — |
| S050 | F13_bilateral_lbp_medication_request | locked | pre_visit | medication_request | “布洛芬一天两次不管用，能加量吗”——表单如实记录药名，系统不得出现加量/药名建议 | — | — |
| S051 | F13_bilateral_lbp_medication_request | locked | pre_visit | hedged | “右边好像更厉害一点”“右腿好像有点麻”“大小便好像也还行”——模糊表达 | — | — |
| S052 | F13_bilateral_lbp_medication_request | locked | pre_visit | normal | 腰两侧痛两个月，骑车久了加重，无放射、无红旗 | — | — |
| S053 | F14_teenager_lbp_out_of_scope | locked | pre_visit | out_of_scope | 原话自述 16 岁——超出协议适用范围，系统当前无法识别 | — | — |
| S054 | F14_teenager_lbp_out_of_scope | locked | pre_visit | out_of_scope | 16 岁 + 模糊表达“腿好像有点麻” | — | — |
| S055 | F14_teenager_lbp_out_of_scope | locked | pre_visit | missing_info | 16 岁 + 信息极少：“我16岁，腰疼” | — | — |
| S056 | F14_teenager_lbp_out_of_scope | locked | pre_visit | negation | 16 岁 + 否定表达：“腿不麻，大小便正常，没发烧，没摔” | — | — |
| S057 | F15_chronic_lbp_bilateral_numbness_flags | locked | pre_visit | red_flag | 原话没提大小便，表单回答大小便控制有变化——必须立即提示并生成紧急任务 | rf_bladder_bowel | — |
| S058 | F15_chronic_lbp_bilateral_numbness_flags | locked | pre_visit | red_flag | 原话提到“会阴部发麻”——必须立即提示并生成紧急任务 | rf_saddle | — |
| S059 | F15_chronic_lbp_bilateral_numbness_flags | locked | pre_visit | red_flag | “好像肛门周围麻麻的，也说不清楚”——红旗不确定，须人工复核 | rf_uncertain_red_flag | — |
| S060 | F15_chronic_lbp_bilateral_numbness_flags | locked | pre_visit | red_flag | 会阴发麻 + 双腿一天比一天更没劲——两条红旗；本变体患者腿并不麻 | rf_progressive_weakness, rf_saddle | — |
| S061 | F16_fall_down_stairs_trauma | locked | pre_visit | red_flag | 前天下楼梯摔倒、疼痛 9 分、起不来——外伤 + 明显疼痛须当天处理 | rf_trauma_severe | — |
| S062 | F16_fall_down_stairs_trauma | locked | pre_visit | normal | 昨天滑了一下摔倒，只有 3 分痛、能走能动——有外伤但不应升级 | — | — |
| S063 | F16_fall_down_stairs_trauma | locked | pre_visit | red_flag | 三天前摔倒、疼痛 8 分，昨天开始发烧——外伤与发热两条红旗 | rf_fever, rf_trauma_severe | — |
| S064 | F16_fall_down_stairs_trauma | locked | pre_visit | many_skips | 摔倒后腰疼，但程度等几乎全部跳过——外伤规则因程度未知无法触发 | — | — |
| S065 | F17_lung_cancer_history_back_pain | locked | pre_visit | red_flag | 原话提到去年肺癌化疗——肿瘤病史须生成医生复核任务 | rf_weight_loss_or_cancer | — |
| S066 | F17_lung_cancer_history_back_pain | locked | pre_visit | red_flag | 三个月瘦了十斤——体重下降须生成复核任务；“三个月”不是起病时间 | rf_weight_loss_or_cancer | — |
| S067 | F17_lung_cancer_history_back_pain | locked | pre_visit | red_flag | 夜里疼得睡不着、经常痛醒 + 表单确认体重下降和肿瘤史 | rf_weight_loss_or_cancer | — |
| S068 | F17_lung_cancer_history_back_pain | locked | pre_visit | negation | 逐项否认体重下降/夜间痛/肿瘤史/发热/外伤——不应触发红旗 | — | — |
| S069 | F18_recurrent_lbp_new_radiation | locked | pre_visit | new_symptom | 以前也有过腰痛，这次多了向右大腿后侧串的疼——既往发作与新增放射都要记录 | — | — |
| S070 | F18_recurrent_lbp_new_radiation | locked | pre_visit | hedged | “右边屁股好像也有点疼，说不好是不是串过去的”——放射与否应记为不确定 | — | — |
| S071 | F18_recurrent_lbp_new_radiation | locked | pre_visit | missing_info | 只写“老毛病，右腿疼”，其余不清楚 | — | — |
| S072 | F18_recurrent_lbp_new_radiation | locked | pre_visit | negation | 否定表达：“腿不麻，腿有劲，大小便正常，不发烧，没有外伤”——“没有外伤”只否认外伤 | — | — |
| S073 | F19_followup_central_lbp_teacher | locked | follow_up | follow_up | 随访：好多了、基本不疼，清楚医嘱且已执行 | — | — |
| S074 | F19_followup_central_lbp_teacher | locked | follow_up | follow_up | 随访：跟上次一样、没变化，部分执行医嘱 | — | — |
| S075 | F19_followup_central_lbp_teacher | locked | follow_up | new_symptom | 随访：更疼 + 新出现串到左臀、左腿发麻——主要部位仍是腰正中 | — | — |
| S076 | F19_followup_central_lbp_teacher | locked | follow_up | follow_up | 随访：“医生说的我不太清楚，也忘了要不要复查”——医嘱理解应记为否 | — | — |
| S077 | F20_followup_right_lbp_calf_driver | locked | follow_up | follow_up | 随访：好一些，但医生安排的理疗一次没去 | — | — |
| S078 | F20_followup_right_lbp_calf_driver | locked | follow_up | red_flag | 随访中出现红旗：会阴部发麻——必须立即提示并生成紧急任务 | rf_saddle | — |
| S079 | F20_followup_right_lbp_calf_driver | locked | follow_up | hedged | 随访：好像好点了，但“好像有点憋不住尿，不太确定”——须人工复核 | rf_uncertain_red_flag | — |
| S080 | F20_followup_right_lbp_calf_driver | locked | follow_up | many_skips | 随访：只写“一般”，除疼痛程度和大小便外全部跳过 | — | — |
