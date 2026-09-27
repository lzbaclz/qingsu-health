#!/usr/bin/env python3
"""从 v0.1 推导 v0.2 AI 草案（可重复运行）。

保留 v0.1 全部 fact key / question id / 语义相同的 red flag id，以便评测脚本兼容；
按 protocols/review/医生工作表_AI模拟填写_v1.md 新增事实、问题（含 tier 1 必问）、红旗。
用法：python protocols/review/build_v02_draft.py
"""
from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "protocols" / "lbp_adult_v0.1.yaml"
DST = ROOT / "protocols" / "lbp_adult_v0.2_ai_draft.yaml"


def fact(key, label, type_, category, **kw):
    d = {"key": key, "label": label, "type": type_, "category": category, "clinical_review_required": True}
    d.update(kw)
    return d


def opt(v, l, syn=None):
    return {"value": v, "label": l, "synonyms": syn or []}


def q(id_, key, type_, pri, text, when=None, stage="pre_visit", allow_skip=True, purpose=None, tier=2):
    d = {"id": id_, "fact_key": key, "type": type_, "priority": pri, "text": text, "allow_unknown": True,
         "allow_skip": allow_skip, "stage": stage, "tier": tier}
    if when:
        d["when"] = when
    if purpose:
        d["purpose"] = purpose
    return d


def rf(id_, label, when, sev, msg, action="immediate_notice_and_task"):
    # 紧急级：提示"立即就医"后终止问询（模拟评审 P0-4）；其余继续
    return {"id": id_, "label": label, "when": when, "severity": sev, "action": action,
            "on_trigger": "stop_questioning" if sev == "urgent" else "continue",
            "task_kind": "red_flag_review", "patient_message": msg, "clinical_review_required": True}


def build() -> dict:
    p = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    p["protocol_id"] = "lbp_adult_v0.2_ai_draft"
    p["version"] = "0.2.0-ai"
    p["status"] = "draft"
    p["title"] = "成年腰背痛 · 就诊前采集与诊后随访（AI 模拟临床填写草案）"
    p["owners"]["clinical_lead"] = "待填写（本草案由 AI 依据公开指南起草，见 protocols/review/医生工作表_AI模拟填写_v1.md）"
    p["review"] = {"last_reviewed": None, "next_review": None, "sources": [
        "NICE NG59 (2016, upd. 2020-12)", "Finucane et al. JOSPT 2020 International Framework for Red Flags",
        "GIRFT National Suspected CES Pathway 2023", "Hartvigsen et al. Lancet 2018;391:2356",
        "中国慢性腰背痛诊疗指南（2024版）中华疼痛学杂志 2024;20(1)", "中国非特异性腰背痛临床诊疗指南 2022",
        "NICE NG65 (2017)", "NHS Back pain patient information", "Menezes Costa CMAJ 2012", "GIRFT/MACP CES warning card"]}
    sc = p["scope"]
    sc["setting"] = "小型康复/疼痛/全科门诊。就诊前：门诊邀请患者在就诊前 1–3 天填写；诊后：医生评估并纳入随访后使用。线上只做信息采集与整理，不做分诊替代、不做诊疗。"
    sc["service_hours"] = "工作日 9:00–17:30 当班护士/助理查看队列；医生每日两次核对；非工作时间提交次工作日处理；紧急提示全程显示（按门诊实际修改）"
    sc["inclusion"] = ["年满 18 岁", "本次主诉为腰背部疼痛/不适（肋缘以下、臀横纹以上），伴或不伴臀腿部疼痛麻木",
                       "已由本门诊邀请（有邀请码/患者编号）", "本人填写，或家属协助但本人在场并确认"]
    sc["exclusion"] = ["未满 18 岁（16–17 岁是否纳入待临床决定）", "妊娠期或产后 6 周内（待临床确认）", "重大外伤后首次就诊——直接急诊",
                       "已知脊柱肿瘤、感染、新鲜骨折或术后早期在治疗中（待临床确认）", "他人代填且本人无法确认", "开始页已出现紧急症状者"]
    sc["service_notice"] = ("这个工具帮助你在见医生之前，把腰背不舒服的情况说清楚，并整理给门诊医生核对。它不做诊断，不提供治疗或用药建议，"
                            "也不能代替医生看病。你填写的内容会由门诊医生在工作时间查看；非工作时间提交的，医生会在下一个工作日看到。"
                            "如果情况紧急，请不要等待，按页面上方的提示立即就医。")
    sc["emergency_notice"] = ("如果出现以下任何一种情况，请不要等待线上回复，立即前往就近医院急诊或拨打 120：① 新出现的排尿困难、尿不出来、尿失禁或大便失禁；"
                              "② 会阴部、肛门周围或大腿内侧发麻，或擦拭时感觉异常；③ 两条腿同时出现疼痛、麻木或无力，或无力在一天天加重；"
                              "④ 伴发热（38℃ 以上）或寒战；⑤ 严重外伤后出现的腰背痛；⑥ 伴胸痛、呼吸困难。（AI 草案，待临床审核）")
    sc["out_of_scope_message"] = ("根据你的回答，这个工具目前不适合你的情况（例如未满 18 岁、怀孕或产后不久、严重外伤后）。这不是对病情的判断。"
                                  "请直接联系门诊预约，或按上方紧急提示就医。你已填写的内容不会被用作医疗记录。")
    p["max_questions"] = 20

    facts = p["facts"]
    idx = {f["key"]: f for f in facts}
    idx["bladder_bowel_change"]["label"] = "大小便控制是否出现变化（v0.1 兼容项；v0.2 拆为 bladder_change / bowel_change）"
    idx["night_pain"]["label"] = "是否夜间痛醒（v0.1 兼容项；v0.2 用 rest_or_night_worst）"
    idx["leg_numbness"]["lexicon"]["context_terms"] = ["腿", "脚"]
    facts.extend([
        fact("age_band", "你的年龄段", "enum", "scope", required=True, critical=True,
             options=[opt("under_18", "18 岁以下", ["十六岁", "十七岁", "16岁", "17岁", "未成年"]), opt("18_49", "18–49 岁"),
                      opt("50_69", "50–69 岁"), opt("70_plus", "70 岁及以上")],
             notes="红旗阈值：>50 岁肿瘤风险、>70 岁骨折风险（中国 2024 表 2）；<18 触发不适用"),
        fact("pregnancy_status", "是否处于孕期或产后 6 周内", "enum", "scope", required=True,
             options=[opt("not_applicable", "不适用"), opt("no", "否"), opt("yes", "是", ["怀孕", "孕期", "刚生完", "产后"]), opt("unsure", "不确定")]),
        fact("thoracic_pain", "疼痛是否主要在背部中上段（两肩胛之间）", "bool", "location",
             lexicon={"present_terms": ["后背疼", "背心疼", "肩胛骨中间", "上背"], "denied_terms": []}),
        fact("severity_worst_24h", "过去 24 小时最痛时（0–10）", "scale", "severity", required=True, min=0, max=10),
        fact("rest_or_night_worst", "是否休息时或夜里最痛", "bool", "red_flag", required=True,
             lexicon={"present_terms": ["躺着也疼", "躺着也痛", "半夜疼醒", "夜里最疼", "晚上更疼", "休息也疼", "痛醒", "疼醒"],
                      "denied_terms": ["晚上不疼", "躺着就好", "夜里不疼"]}),
        fact("bilateral_leg_symptoms", "两条腿是否同时有疼痛/麻木/无力", "bool", "red_flag", required=True, critical=True,
             lexicon={"present_terms": ["两条腿", "双腿", "两只脚", "两边腿"], "denied_terms": ["只有一条腿", "一条腿"]}),
        fact("gait_disturbance", "走路是否不稳、拖步、容易绊倒", "bool", "red_flag", critical=True,
             lexicon={"present_terms": ["走不稳", "拖着腿", "绊倒", "走路打晃", "腿软摔"], "denied_terms": ["走路正常", "走得稳"]}),
        fact("bladder_change", "排尿是否出现新变化（尿不出/费力/感觉不到/憋不住/失禁）", "bool", "red_flag", required=True, critical=True,
             lexicon={"present_terms": ["尿不出", "排尿困难", "尿失禁", "憋不住尿", "漏尿", "小便有问题", "尿不干净", "感觉不到尿"],
                      "denied_terms": ["小便正常", "排尿正常", "小便没问题"]}),
        fact("bowel_change", "大便控制是否出现新变化（失禁/感觉不到便意）", "bool", "red_flag", required=True, critical=True,
             lexicon={"present_terms": ["大便失禁", "拉裤子", "大便憋不住", "感觉不到便意"], "denied_terms": ["大便正常", "大便没问题"]}),
        fact("sexual_function_change", "性功能是否出现新变化（可不回答）", "bool", "red_flag", critical=True,
             lexicon={"present_terms": ["性功能", "勃起", "阴道没感觉"], "denied_terms": []}),
        fact("infection_risk", "感染/骨折风险因素", "multi_enum", "history", required=True,
             options=[opt("steroid_or_immunosuppressant", "长期用激素或免疫抑制剂", ["激素", "免疫抑制剂", "强的松", "泼尼松"]),
                      opt("diabetes", "糖尿病", ["糖尿病"]), opt("recent_infection", "近期有感染", ["感冒发烧", "尿路感染", "感染"]),
                      opt("recent_spinal_procedure", "近期腰部注射或手术", ["打过封闭", "腰部手术", "打针"]),
                      opt("iv_drug", "静脉注射药物", ["静脉注射"]), opt("none", "都没有", ["都没有"])]),
        fact("osteoporosis_or_fragility", "是否有骨质疏松或轻微外力骨折史", "bool", "history",
             lexicon={"present_terms": ["骨质疏松", "骨松", "骨折过"], "denied_terms": ["没有骨质疏松"]}),
        fact("morning_stiffness_30min", "早晨僵硬是否超过 30 分钟", "bool", "inflammatory",
             lexicon={"present_terms": ["早上僵", "起床僵", "晨僵"], "denied_terms": []}),
        fact("improves_with_activity", "活动后减轻、休息反而加重", "bool", "inflammatory",
             lexicon={"present_terms": ["活动开了就好", "越躺越疼", "动一动好些"], "denied_terms": []}),
        fact("night_waking_second_half", "是否在后半夜因症状醒来", "bool", "inflammatory"),
        fact("buttock_alternating", "臀部疼痛是否左右交替", "bool", "inflammatory"),
        fact("prior_imaging", "是否做过腰部影像检查及时间", "text", "history",
             lexicon={"present_terms": ["拍过片", "做过核磁", "做过CT", "X光", "MRI", "核磁"]}),
        fact("walking_distance", "因腰痛只能走很短距离", "bool", "function",
             lexicon={"present_terms": ["走不远", "走一会就", "走不了多远"], "denied_terms": ["能走远"]}),
        fact("work_type", "工作类型", "enum", "psychosocial",
             options=[opt("sedentary", "久坐为主", ["坐办公室", "开车"]), opt("physical", "体力为主", ["搬运", "工地", "体力活"]),
                      opt("mixed", "两者都有"), opt("not_working", "目前不工作", ["退休", "不上班"])]),
        fact("fear_of_movement", "是否觉得活动会伤到腰、不敢动", "bool", "psychosocial",
             lexicon={"present_terms": ["不敢动", "怕动", "怕伤到"], "denied_terms": []}),
        fact("low_mood", "最近是否情绪低落、提不起兴趣（可不回答）", "bool", "psychosocial",
             lexicon={"present_terms": ["情绪低落", "心情差", "没兴趣", "抑郁"], "denied_terms": []}),
        fact("catastrophizing", "是否觉得这腰永远好不了", "bool", "psychosocial",
             lexicon={"present_terms": ["好不了了", "永远好不了", "废了"], "denied_terms": []}),
        fact("fu_side_effect", "按医嘱处理后是否出现不舒服（只记录）", "bool", "followup"),
    ])

    old_q = {x["id"]: x for x in p["questions"]}
    for x in old_q.values():
        x.setdefault("tier", 2)
    old_q["q_bladder_bowel"]["when"] = "False"   # 由 q_bladder / q_bowel 替代
    old_q["q_night_pain"]["when"] = "False"      # 由 q_rest_night 替代
    old_q["q_weight_loss"]["when"] = "False"     # 由 q_weight_loss2（tier 1）替代
    old_q["q_cancer_history"]["when"] = "False"  # 由 q_cancer_history2（tier 1）替代
    old_q["q_saddle"].update(priority=5, tier=1, text="会阴部、肛门周围或大腿内侧有没有发麻、或擦拭时感觉和平时不一样？")
    old_q["q_leg_weakness"].update(priority=7, tier=1)
    old_q["q_weakness_progressive"].update(priority=8, tier=1)
    old_q["q_fever"].update(priority=11, tier=1, text="这几天有没有发烧（38℃ 以上）或发冷寒战？")
    old_q["q_trauma"].update(priority=12, tier=1)
    old_q["q_onset_timing"].update(priority=17, text="这一次腰背不舒服是从多久前开始的？（如果是老毛病，请按这一次发作算）")
    for k, pri in [("q_onset_mode", 18), ("q_trigger", 19), ("q_side", 20), ("q_radiation_present", 21), ("q_radiation_regions", 22),
                   ("q_leg_numbness", 23), ("q_severity_now", 24), ("q_course", 27), ("q_aggravating", 28), ("q_relieving", 29),
                   ("q_function_impact", 30), ("q_sleep_affected", 32), ("q_character", 33)]:
        old_q[k]["priority"] = pri
    for k, pri in [("q_prior_episodes", 37), ("q_prior_treatment", 38), ("q_current_medication", 40), ("q_patient_concern", 45)]:
        old_q[k].update(priority=pri, tier=3)
    infl = "facts.age_band.any(['18_49']) and facts.onset_timing.value == 'over_12_weeks'"
    new_q = [
        q("q_age_band", "age_band", "single_choice", 1, "请选择你的年龄段。", allow_skip=False, purpose="范围核查；红旗阈值", tier=1),
        q("q_pregnancy", "pregnancy_status", "single_choice", 2, "你是否处于孕期或产后 6 周内？（不适用请选\"不适用\"）", allow_skip=False, purpose="范围核查", tier=1),
        q("q_bladder", "bladder_change", "yes_no", 3, "最近两周内，排尿有没有新出现的变化：比如尿不出来、要很用力、感觉不到尿、憋不住或漏尿？", purpose="马尾综合征（GIRFT 2023）", tier=1),
        q("q_bowel", "bowel_change", "yes_no", 4, "最近两周内，大便控制有没有新出现的变化：比如憋不住、或感觉不到便意？", purpose="马尾综合征", tier=1),
        q("q_bilateral", "bilateral_leg_symptoms", "yes_no", 6, "两条腿是不是同时出现疼痛、发麻或没劲？", purpose="马尾/双侧神经根", tier=1),
        q("q_gait", "gait_disturbance", "yes_no", 9, "走路有没有不稳、拖步或容易绊倒？", purpose="中国 2024 表 2 步态障碍", tier=1),
        q("q_sexual", "sexual_function_change", "yes_no", 10, "这个问题可以选择不回答：最近性功能有没有新出现的变化？", purpose="马尾综合征（GIRFT 2023）", tier=1),
        q("q_cancer_history2", "cancer_history", "yes_no", 13, "以前有没有得过肿瘤（癌症）？", purpose="脊柱转移最有用的指标（Lancet 2018）", tier=1),
        q("q_weight_loss2", "weight_loss", "yes_no", 14, "最近几个月体重有没有不明原因地明显下降？", purpose="肿瘤/感染", tier=1),
        q("q_infection_risk", "infection_risk", "multi_choice", 15, "下面这些情况有没有？（可多选）", purpose="感染与骨折风险因素", tier=1),
        q("q_osteoporosis", "osteoporosis_or_fragility", "yes_no", 16, "有没有骨质疏松，或以前轻轻一摔就骨折过？",
          when="facts.age_band.any(['50_69','70_plus']) or facts.trauma_recent.present or facts.infection_risk.has('steroid_or_immunosuppressant')",
          purpose="骨折风险（Lancet 2018 Panel 2）", tier=1),
        q("q_severity_worst", "severity_worst_24h", "scale", 25, "过去 24 小时最痛的时候是几分？0 完全不痛，10 无法忍受。"),
        q("q_rest_night", "rest_or_night_worst", "yes_no", 26, "是不是休息或躺着时也疼，甚至夜里最疼？", purpose="中国 2024 表 2 红旗"),
        q("q_walking", "walking_distance", "yes_no", 31, "是不是因为腰痛只能走很短的距离？"),
        q("q_thoracic", "thoracic_pain", "yes_no", 34, "疼痛是不是主要在背部中上段（两个肩胛骨之间）？", tier=3),
        q("q_morning_stiff", "morning_stiffness_30min", "yes_no", 35, "早晨起来腰是不是发僵超过半小时？", when=infl, tier=3),
        q("q_improves_activity", "improves_with_activity", "yes_no", 36, "是不是活动开了反而轻一些，躺着休息反而更僵更疼？", when=infl, tier=3),
        q("q_night_waking", "night_waking_second_half", "yes_no", 37, "是不是常在后半夜因为腰疼醒来？", when=infl, tier=3),
        q("q_buttock_alt", "buttock_alternating", "yes_no", 38, "臀部的疼痛是不是左右交替出现？", when=infl, tier=3),
        q("q_prior_imaging", "prior_imaging", "text", 39, "有没有做过腰部的 X 线、CT 或核磁？大概什么时候？", tier=3),
        q("q_fear", "fear_of_movement", "yes_no", 41, "你会不会担心活动会伤到腰，所以尽量不动？", tier=3),
        q("q_low_mood", "low_mood", "yes_no", 42, "这个问题可以不回答：最近有没有情绪低落、对平时喜欢的事提不起兴趣？", tier=3),
        q("q_catastrophizing", "catastrophizing", "yes_no", 43, "你有没有觉得\"这个腰可能永远好不了\"？", tier=3),
        q("q_work_type", "work_type", "single_choice", 44, "你的工作主要是？", tier=3),
    ]
    p["questions"] = list(old_q.values()) + new_q

    fu = p["followup"]
    fu_old = {x["id"]: x for x in fu["questions"]}
    for x in fu_old.values():
        x.setdefault("tier", 2)
    fu_old["q_fu_bladder"].update(fact_key="bladder_change", tier=1, text="最近两周内，排尿有没有新出现的变化（尿不出、费力、憋不住、漏尿）？")
    fu_old["q_fu_saddle"]["tier"] = 1
    fu_old["q_fu_weakness"]["tier"] = 1
    fu["questions"] = list(fu_old.values()) + [
        q("q_fu_bowel", "bowel_change", "yes_no", 15, "大便控制有没有新出现的变化？", stage="follow_up", tier=1),
        q("q_fu_bilateral", "bilateral_leg_symptoms", "yes_no", 16, "两条腿是不是同时出现疼痛、发麻或没劲？", stage="follow_up", tier=1),
        q("q_fu_gait", "gait_disturbance", "yes_no", 17, "走路有没有不稳、拖步或容易绊倒？", stage="follow_up", tier=1),
        q("q_fu_fever", "fever", "yes_no", 18, "这几天有没有发烧或寒战？", stage="follow_up", tier=1),
        q("q_fu_severity_worst", "severity_worst_24h", "scale", 11, "过去 24 小时最痛的时候是几分？", stage="follow_up"),
        q("q_fu_side_effect", "fu_side_effect", "yes_no", 32, "按医生安排处理后，有没有出现新的不舒服？（只做记录）", stage="follow_up", tier=3),
    ]
    fu["change_facts"] = fu["change_facts"] + ["severity_worst_24h", "bilateral_leg_symptoms", "gait_disturbance", "bladder_change",
                                               "bowel_change", "sexual_function_change", "rest_or_night_worst"]

    CES = "你提到{what}。这可能是需要当天紧急处理的情况，请不要等待线上回复：立即前往就近医院急诊，告诉医生你有腰痛并且出现了这个变化。（AI 草案，待临床审核）"
    p["red_flags"] = [
        # 与 v0.1 语义相同的规则保留原 id，便于评测对比
        rf("rf_bladder_bowel", "排尿/排便新变化", "facts.bladder_change.present or facts.bladder_bowel_change.present or facts.bowel_change.present", "urgent", CES.format(what="排尿或排便出现了新变化")),
        rf("rf_saddle", "会阴/肛周/大腿内侧感觉异常", "facts.saddle_numbness.present", "urgent", CES.format(what="会阴部或肛门周围感觉异常")),
        rf("rf_ces_sexual", "性功能新变化", "facts.sexual_function_change.present", "urgent", "你提到性功能出现了新变化，与腰痛同时出现时需要尽快评估。请立即联系门诊或前往急诊。（AI 草案，待临床审核）"),
        rf("rf_ces_bilateral", "双腿同时症状伴其他马尾症状",
           "facts.bilateral_leg_symptoms.present and (facts.bladder_change.present or facts.bowel_change.present or facts.saddle_numbness.present or facts.sexual_function_change.present or facts.weakness_progressive.present)",
           "urgent", "两条腿同时出现症状并伴有上述变化，需要当天紧急评估。请立即前往急诊。（AI 草案，待临床审核）"),
        rf("rf_bilateral_only", "双腿同时症状", "facts.bilateral_leg_symptoms.present", "same_day", "你提到两条腿同时有症状。请今天内联系门诊，医生会尽快安排评估。（AI 草案，待临床审核）"),
        rf("rf_progressive_weakness", "腿部无力且在加重", "facts.weakness_progressive.present", "urgent", "你提到腿没劲并且在加重。进行性加重的无力需要尽快当面评估，请今天内前往急诊或联系门诊。（AI 草案，待临床审核）"),
        rf("rf_gait", "步态障碍", "facts.gait_disturbance.present", "same_day", "你提到走路不稳。请今天内联系门诊。（AI 草案，待临床审核）"),
        rf("rf_fever", "发热/寒战", "facts.fever.present", "same_day", "你提到有发热。腰痛伴发热需要尽快评估，请今天内联系门诊；如高热不退或伴寒战，请直接急诊。（AI 草案，待临床审核）"),
        rf("rf_infection_risk_with_pain", "感染风险因素伴休息/夜间痛或发热",
           "facts.infection_risk.any(['steroid_or_immunosuppressant','diabetes','recent_infection','recent_spinal_procedure','iv_drug']) and (facts.rest_or_night_worst.present or facts.fever.present)",
           "same_day", "（仅供医生复核）", action="task_only"),
        rf("rf_fracture_risk", "外伤伴骨折风险因素",
           "facts.trauma_recent.present and (facts.age_band.any(['50_69','70_plus']) or facts.osteoporosis_or_fragility.present or facts.infection_risk.has('steroid_or_immunosuppressant'))",
           "same_day", "你提到近期有外伤，并且有骨折的风险因素。请今天内联系门诊安排评估。（AI 草案，待临床审核）"),
        rf("rf_trauma_severe", "外伤后明显疼痛", "facts.trauma_recent.present and facts.severity_now.gte(7)", "same_day", "你提到近期有外伤且疼痛明显。请今天内联系门诊说明情况。（AI 草案，待临床审核）"),
        rf("rf_cancer_with_features", "肿瘤史伴需留意特征",
           "facts.cancer_history.present and (facts.weight_loss.present or facts.rest_or_night_worst.present or facts.night_pain.present or facts.age_band.any(['50_69','70_plus']) or facts.course.value == 'worsening')",
           "same_day", "你提到有肿瘤病史并伴有需要留意的情况。请今天内联系门诊，医生会尽快安排评估。（AI 草案，待临床审核）"),
        rf("rf_weight_loss_or_cancer", "体重下降 / 肿瘤病史 / 休息夜间痛", "facts.weight_loss.present or facts.cancer_history.present or facts.night_pain.present or facts.rest_or_night_worst.present", "routine", "（仅供医生复核）", action="task_only"),
        rf("rf_inflammatory_pattern", "炎性腰背痛线索",
           "facts.age_band.any(['18_49']) and facts.onset_timing.value == 'over_12_weeks' and ((facts.morning_stiffness_30min.present and facts.improves_with_activity.present) or (facts.morning_stiffness_30min.present and facts.night_waking_second_half.present) or (facts.improves_with_activity.present and facts.night_waking_second_half.present) or facts.buttock_alternating.present)",
           "routine", "（仅供医生复核：考虑脊柱关节炎评估路径，NICE NG65）", action="task_only"),
        rf("rf_thoracic", "胸段为主", "facts.thoracic_pain.present", "routine", "（仅供医生复核）", action="task_only"),
        rf("rf_out_of_scope", "不在适用范围", "facts.age_band.value == 'under_18' or facts.pregnancy_status.value == 'yes'", "routine",
           "根据你的回答，这个工具目前不适合你的情况（例如未满 18 岁、怀孕或产后不久）。这不是对病情的判断。请直接联系门诊预约，或按上方紧急提示就医。（AI 草案，待临床审核）"),
        rf("rf_uncertain_red_flag", "关键红旗表达不确定",
           "facts.bladder_change.uncertain or facts.bowel_change.uncertain or facts.saddle_numbness.uncertain or facts.bilateral_leg_symptoms.uncertain or facts.leg_weakness.uncertain or facts.bladder_bowel_change.uncertain",
           "same_day", "（仅供医生复核：患者对关键问题表达不确定，需人工确认）", action="task_only"),
        rf("rf_no_improvement", "病程超过 6 周且加重", "facts.onset_timing.any(['weeks_6_to_12','over_12_weeks']) and facts.course.value == 'worsening'", "routine", "（仅供医生复核）", action="task_only"),
    ]
    p["clarifications"].append({"fact_key": "onset_timing",
        "text": "关于这次不舒服开始的时间，你的{first_source}是「{first}」，{second_source}提到「{second}」。如果是老毛病，请按这一次发作算。现在应以哪个为准？",
        "options": [{"label": "这一次是「{first}」", "resolve": "keep_first"}, {"label": "这一次是「{second}」", "resolve": "keep_second"},
                    {"label": "不确定", "resolve": "unknown"}]})
    p["scope_guard"]["forbidden_patterns"].append("考虑.*(突出|狭窄|滑脱|骨折|肿瘤|感染)|建议.*(CT|MRI|核磁|拍片|X线)")
    p["summary"]["key_facts_order"] = ["age_band", "pregnancy_status"] + p["summary"]["key_facts_order"] + [
        "severity_worst_24h", "rest_or_night_worst", "bilateral_leg_symptoms", "gait_disturbance", "bladder_change", "bowel_change",
        "sexual_function_change", "infection_risk", "osteoporosis_or_fragility", "thoracic_pain", "walking_distance", "prior_imaging",
        "fear_of_movement", "low_mood", "catastrophizing", "work_type"]
    p["evaluation"]["critical_facts"] = ["age_band", "pain_side", "pain_regions", "onset_timing", "severity_now", "radiation_present", "leg_numbness",
                                         "leg_weakness", "weakness_progressive", "bilateral_leg_symptoms", "gait_disturbance", "bladder_change",
                                         "bowel_change", "saddle_numbness", "sexual_function_change", "fever", "trauma_recent", "cancer_history",
                                         "fu_new_symptom", "bladder_bowel_change"]
    return p


HEADER = """# =====================================================================
# 体迹 AI · 临床协议 v0.2 —— AI 模拟临床填写草案（未采用）
# 由 protocols/review/build_v02_draft.py 从 v0.1 推导；保留 v0.1 的全部 key / question id / 语义相同的 red flag id 以兼容评测。
# 不是执业医师意见；每一条 clinical_review_required: true 的内容都必须由临床队友审核。
# 与医生版对比后，由工程合并为正式 v0.2。默认协议仍为 lbp_adult_v0.1。
# =====================================================================
"""

if __name__ == "__main__":
    p = build()
    DST.write_text(HEADER + yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    print(f"written {DST}: {len(p['facts'])} facts, {len(p['questions'])} questions, {len(p['red_flags'])} red flags")
