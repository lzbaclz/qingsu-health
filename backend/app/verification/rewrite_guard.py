"""给患者的说明：术语对照（默认，不调用模型）与"要点以外的新内容"拦截。

第三轮评审 T5：让模型改写时加入"洛索洛芬""一天两次""腰肌拉伤""卧床休息两周""去做核磁"，旧校验（协议里 4 条越界正则）
一条都没拦住；发出后 V4 又对医生发送的通知整条豁免。这里做两件事：
1. glossary_explain：按协议里医生审定的术语对照表，在医生原句的术语后面加一句大白话。医生写的每个字都保留，
   不增加任何医学内容，不调用模型。这是默认方式（TIJI_PATIENT_REWRITE=glossary）。
2. new_terms：找出改写里有、医生要点里没有的医学实体——药名、剂量频次与时间、检查、诊断式说法、处置与活动建议。
   用于发送前拦截（医生删掉或写理由才能发）和 V4 复查。它是保守的词表加规则：宁可多拦，由医生决定。
"""
from __future__ import annotations

import re
from typing import Iterable

AI_LABEL = "（这段说明的措辞由 AI 协助改写，内容由医生确认后发送。）"

# ---------------------------------------------------------------- 术语对照（不调用模型）
def split_points(notes: str) -> list[str]:
    return [x.strip(" ，,") for x in re.split(r"[；;。\n]+", notes or "") if x.strip(" ，,")]


def glossary_explain(notes: str, glossary: Iterable) -> tuple[str, list[str]]:
    """把医生要点分条，并在第一次出现的术语后面加"（大白话）"。返回正文与插入的解释（拦截检查时要先去掉）。"""
    items = sorted(((g.term, g.plain) for g in glossary if getattr(g, "term", None) and getattr(g, "plain", None)),
                   key=lambda t: -len(t[0]))
    used: set[str] = set()
    inserted: list[str] = []
    out = []
    for i, p in enumerate(split_points(notes), 1):
        for term, plain in items:
            if term in used or term not in p:
                continue
            if any(term in u for u in used):  # 长词已解释过（如"影像检查"），短词不再重复
                continue
            ins = f"（{plain}）"
            p = p.replace(term, term + ins, 1)
            used.add(term)
            inserted.append(ins)
        out.append(f"{i}. {p}。")
    return "\n".join(out), inserted


# ---------------------------------------------------------------- 新内容拦截
_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNIT_CLASS = {"次": "次", "片": "片", "粒": "片", "袋": "片", "支": "片", "包": "片", "毫克": "mg", "mg": "mg", "克": "g", "g": "g",
               "毫升": "ml", "ml": "ml", "天": "天", "日": "天", "周": "周", "星期": "周", "个月": "月", "月": "月",
               "小时": "小时", "分钟": "分钟"}
_NUM_RE = re.compile(r"(\d+(?:\.\d+)?|[零一二两三四五六七八九十百半几]+)\s*(个月|星期|毫克|毫升|小时|分钟|次|片|粒|袋|支|包|mg|ml|克|g|天|日|周|月)")


def _cn_to_num(s: str) -> str:
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return str(float(s)).rstrip("0").rstrip(".")
    if s in ("半",):
        return "0.5"
    if "几" in s:
        return s
    if "十" in s:
        a, _, b = s.partition("十")
        tens = _CN_DIGIT.get(a, 1) if a else 1
        ones = _CN_DIGIT.get(b, 0) if b else 0
        return str(tens * 10 + ones)
    if len(s) == 1 and s in _CN_DIGIT:
        return str(_CN_DIGIT[s])
    return s


DRUG_WORDS = [
    "布洛芬", "芬必得", "美林", "对乙酰氨基酚", "扑热息痛", "泰诺", "必理通", "双氯芬酸", "扶他林", "洛索洛芬", "乐松", "塞来昔布",
    "西乐葆", "依托考昔", "安康信", "美洛昔康", "莫比可", "萘普生", "尼美舒利", "艾瑞昔布", "吲哚美辛", "氨酚曲马多", "曲马多",
    "羟考酮", "吗啡", "可待因", "乙哌立松", "妙纳", "氯唑沙宗", "替扎尼定", "巴氯芬", "甲钴胺", "弥可保", "维生素B", "加巴喷丁",
    "普瑞巴林", "乐瑞卡", "度洛西汀", "阿米替林", "泼尼松", "强的松", "甲泼尼龙", "地塞米松", "激素", "抗生素", "止痛药", "止疼药",
    "镇痛药", "消炎药", "消炎止痛药", "抗炎药", "肌松药", "膏药", "药膏", "贴剂", "膏贴", "中药", "西药", "云南白药", "红花油",
]
_DOSAGE_FORM_RE = re.compile(r"[一-龥A-Za-z]{1,8}?(?:缓释片|分散片|肠溶片|缓释胶囊|胶囊|颗粒|口服液|注射液|凝胶|软膏|乳膏|贴膏|喷雾剂)")
EXAM_WORDS = ["核磁", "磁共振", "MRI", "CT", "X光", "X线", "拍片", "拍个片", "片子", "B超", "彩超", "超声", "抽血", "验血", "化验",
              "血常规", "尿常规", "肌电图", "骨密度", "造影", "心电图"]
DIAGNOSIS_WORDS = ["椎间盘", "突出", "膨出", "脱出", "劳损", "拉伤", "扭伤", "狭窄", "滑脱", "骨折", "骨质疏松", "强直", "坐骨神经",
                   "神经根", "炎症", "发炎", "肿瘤", "癌", "结核", "感染", "马尾", "综合征", "腰椎病", "颈椎病", "关节炎", "错位"]
_DIAG_ASSERT_RE = re.compile(r"(?:你|您)?(?:这|这个|这种|目前)?(?:是|属于|考虑|可能是|应该是|得了|患了|患有|诊断为|确诊)"
                             r"[^，。；,;\n]{0,8}?(?:病|症|炎|伤|突出|狭窄|劳损)")
TREATMENT_WORDS = ["卧床", "躺床", "床上休息", "不要下地", "别下地", "不要走动", "少走动", "不要走路", "制动", "绝对休息", "静养",
                   "手术", "开刀", "牵引", "针灸", "推拿", "按摩", "理疗", "正骨", "小针刀", "封闭", "打针", "输液", "热敷", "冷敷",
                   "冰敷", "护腰", "腰围", "支具", "拉伸", "游泳", "跑步", "快走", "瑜伽", "普拉提", "平板支撑", "小燕飞", "倒走", "健身"]

CATEGORY_LABEL = {"drug": "药名", "dose": "剂量/频次/时间", "exam": "检查", "diagnosis": "诊断式说法",
                  "treatment": "处置/活动建议", "scope": "越界词"}


def _entities(text: str) -> list[tuple[str, str, str]]:
    """(类别, 原文片段, 用于比较的规范形)。"""
    out: list[tuple[str, str, str]] = []
    for m in _NUM_RE.finditer(text):
        out.append(("dose", m.group(0), f"{_cn_to_num(m.group(1))}{_UNIT_CLASS.get(m.group(2), m.group(2))}"))
    for w in DRUG_WORDS:
        if w in text:
            out.append(("drug", w, w))
    for m in _DOSAGE_FORM_RE.finditer(text):
        out.append(("drug", m.group(0), m.group(0)))
    for w in EXAM_WORDS:
        if w in text:
            out.append(("exam", w, w))
    for w in DIAGNOSIS_WORDS:
        if w in text:
            out.append(("diagnosis", w, w))
    for m in _DIAG_ASSERT_RE.finditer(text):
        out.append(("diagnosis", m.group(0), "assert:" + m.group(0)))
    for w in TREATMENT_WORDS:
        if w in text:
            out.append(("treatment", w, w))
    return out


def new_terms(notes: str, text: str, forbidden_patterns: Iterable[str] = ()) -> list[dict]:
    """改写里有、医生要点里没有的医学实体。诊断式说法里的病名要点里已经写了的，不算新增（医生自己写的诊断）。"""
    notes = notes or ""
    note_norms = {n for _, _, n in _entities(notes)}
    out, seen = [], set()
    for cat, frag, norm in _entities(text or ""):
        if norm in note_norms or frag in notes or norm in seen:
            continue
        if norm.startswith("assert:") and any(w in notes for w in DIAGNOSIS_WORDS if w in frag):
            continue
        seen.add(norm)
        out.append({"term": frag, "category": cat, "category_label": CATEGORY_LABEL[cat]})
    for p in forbidden_patterns:
        for m in re.finditer(p, text or ""):
            t = m.group(0)
            if t and t not in notes and t not in seen and not any(t in x["term"] or x["term"] in t for x in out):
                seen.add(t)
                out.append({"term": t, "category": "scope", "category_label": CATEGORY_LABEL["scope"]})
    return out


def describe(terms: list[dict]) -> str:
    groups: dict[str, list[str]] = {}
    for t in terms:
        groups.setdefault(t["category_label"], []).append(t["term"])
    return "；".join(f"{k}：{'、'.join(v)}" for k, v in groups.items())


def strip_system_parts(message: str, removable: Iterable[str]) -> str:
    """拦截检查只看医学内容：去掉系统按协议附上的问候、复诊时间、紧急提示与 AI 标注，以及术语对照插入的解释。"""
    s = message or ""
    for r in sorted({x for x in removable if x}, key=len, reverse=True):
        s = s.replace(r, " ")
    return s
