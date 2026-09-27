"""问询引擎：确定性地决定"下一个问什么"。

顺序：
  0. 有生效中的"终止问询"红旗（协议 on_trigger: stop_questioning，通常是 urgent 级）→
     若触发它的事实只来自文字抽取、还没核对过，先给一次一键核对（防止误抽导致误报）；否则停止问询。
  1. 有 conflicting 的事实 → 先澄清（模板来自协议 clarifications，或通用模板）。
  2. 一键核对：只从自由文本抽取、未经患者直接回答的关键事实，逐条请患者确认（对 / 不对 / 不确定）。
     "不对"的事实回到"未询问"，由第 3 步的协议问题重新直接问。——漏抽由问卷兜住，错抽由核对兜住。
  3. 红旗一屏（第 1 轮团队评审）：本阶段 tier 1、是否型的红旗筛查题合成一屏，逐行"有 / 没有 / 不确定"必答，不计题数。
     红旗不对称信任：红旗的"没有"只认患者的直接回答——模型从原话里读出的"没有"、一键核对里点的"对"都不算，照样进这一屏
     （模型会把"屁股中间木木的，没什么感觉"读成"没有会阴麻木"）。
  4. 按阶段（pre_visit / follow_up）取协议问题，按 (tier, priority) 升序：
     - 事实已明确（present/denied）→ 不问；但红旗筛查类事实的"没有"若不是直接回答，照样问；
     - 已问过 → 不再问；when 条件不满足 → 不问；
     - 达到 max_questions 后只问 tier 1（必问）题。
模型不参与"问什么"的决定。
"""
from __future__ import annotations

from typing import Any, Optional

from sqlmodel import Session, select

from ..facts.store import as_expr_map, current_facts, display_value, has_direct_answer, is_extraction_only
from ..models import Alert, AskedQuestion, Encounter, EncounterKind, Fact, FactStatus
from ..protocol.expr import evaluate
from ..protocol.schema import FactDef, Protocol, QuestionDef

_SOURCE_LABEL = {
    "body_map": "身体图标记", "extraction": "文字描述", "answer": "问题回答",
    "correction": "修改", "doctor": "医生修正", "derived": "系统推导",
}

GENERIC_CLARIFICATION = {
    "text": "关于「{label}」，你的{first_source}是「{first}」，{second_source}是「{second}」。现在应以哪个为准？",
    "options": [
        {"label": "以「{first}」为准", "resolve": "keep_first"},
        {"label": "以「{second}」为准", "resolve": "keep_second"},
        {"label": "两者都对（情况有变化）", "resolve": "both"},
        {"label": "不确定", "resolve": "unknown"},
    ],
}


def pending_question(session: Session, encounter_id: str) -> Optional[AskedQuestion]:
    return session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == encounter_id,
                                                    AskedQuestion.answer_status == "pending")).first()


def asked_ids(session: Session, encounter_id: str) -> set[str]:
    """问过的题 id；红旗一屏里的每一行也算问过。"""
    rows = session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == encounter_id,
                                                  AskedQuestion.answer_status != "superseded")).all()
    ids = {r.question_id for r in rows}
    for r in rows:
        if r.kind == "red_flag_grid":
            ids.update(str(i.get("question_id")) for i in (r.options or []) if isinstance(i, dict))
    return ids


def needs_direct_red_flag_answer(f: Fact, protocol: Protocol) -> bool:
    """红旗不对称信任：红旗筛查类事实还没有患者的直接回答，而且不是"有"（"有"已经在提醒医生了）。"""
    return (f.key in protocol.red_flag_screen_keys and not has_direct_answer(f)
            and f.status in (FactStatus.NOT_ASKED, FactStatus.DENIED, FactStatus.UNCERTAIN))


def _question_to_payload(q: QuestionDef, protocol: Protocol) -> dict:
    fdef = protocol.fact(q.fact_key)
    options = q.options if q.options is not None else fdef.options
    payload: dict[str, Any] = {
        "question_id": q.id, "fact_key": q.fact_key, "text": q.text, "type": q.type,
        "kind": "protocol", "allow_unknown": q.allow_unknown, "allow_skip": q.allow_skip, "tier": q.tier,
        "options": [{"value": o.value, "label": o.label} for o in options] if options else [],
    }
    if q.type == "yes_no":
        payload["options"] = [{"value": "yes", "label": "有 / 是"}, {"value": "no", "label": "没有 / 否"}]
    if q.type == "scale":
        payload["min"], payload["max"] = fdef.min if fdef.min is not None else 0, fdef.max if fdef.max is not None else 10
        if q.anchors:
            payload["anchors"] = {str(k): v for k, v in sorted(q.anchors.items())}
    return payload


def build_clarification(protocol: Protocol, fact: Fact) -> dict:
    fdef = protocol.fact(fact.key)
    cands = (fact.value or {}).get("candidates", [])
    first, second = cands[0], cands[-1]
    tmpl = next((c for c in protocol.clarifications if c.fact_key == fact.key), None)
    def plain(c: dict) -> str:  # 澄清问句里不带"（患者表达不确定）"后缀
        st = c.get("status", "present")
        return display_value(fdef, "present" if st == "uncertain" else st, c.get("value"))

    fmt = {
        "label": fdef.label,
        "first": plain(first),
        "second": plain(second),
        "first_source": _SOURCE_LABEL.get(first.get("source", ""), "之前的表达"),
        "second_source": _SOURCE_LABEL.get(second.get("source", ""), "后来的表达"),
    }
    if tmpl:
        text = tmpl.text.format(**fmt)
        options = [{"label": o.label.format(**fmt), "resolve": o.resolve} for o in tmpl.options]
    else:
        text = GENERIC_CLARIFICATION["text"].format(**fmt)
        options = [{"label": o["label"].format(**fmt), "resolve": o["resolve"]} for o in GENERIC_CLARIFICATION["options"]]
    return {
        "question_id": f"clarify:{fact.key}:{fact.version}", "fact_key": fact.key, "text": text,
        "type": "single_choice", "kind": "clarification", "allow_unknown": True, "allow_skip": False,
        "options": [{"value": str(i), "label": o["label"], "resolve": o["resolve"]} for i, o in enumerate(options)],
        "candidates": cands,
    }


def active_stop_alerts(session: Session, encounter: Encounter, protocol: Protocol) -> list[Alert]:
    """生效中的"终止问询"红旗：规则要求 stop_questioning，且患者没有在核对中否认触发它的整理。"""
    rules = {r.id: r for r in protocol.red_flags}
    alerts = session.exec(select(Alert).where(Alert.encounter_id == encounter.id)).all()
    return [a for a in alerts if not a.patient_disputed and a.rule_id in rules
            and rules[a.rule_id].on_trigger == "stop_questioning"]


def patient_value_label(fdef: FactDef, status: str, value: Any) -> str:
    """给患者看的取值（不用"明确否认 / 患者表达不确定"这类给医生看的措辞）。"""
    if status == FactStatus.DENIED:
        return "没有"
    if fdef.type == "bool" or value is None:
        return "好像有，但不确定" if status == FactStatus.UNCERTAIN else "有"
    text = display_value(fdef, FactStatus.PRESENT, value)
    return f"{text}（不太确定）" if status == FactStatus.UNCERTAIN else text


def verification_items(facts: dict[str, Fact], protocol: Protocol, restrict_keys: Optional[set[str]] = None) -> list[dict]:
    spec = protocol.verification
    if not spec.enabled:
        return []
    fi = protocol.fact_index
    order = [k for k in protocol.summary.key_facts_order if k in fi] + [k for k in fi if k not in protocol.summary.key_facts_order]
    items: list[dict] = []
    for k in order:
        if restrict_keys is not None and k not in restrict_keys:
            continue
        f, d = facts.get(k), fi[k]
        if (protocol.event_verification.enabled and protocol.event_verification.skip_redundant_negative_verification
                and f and f.status == FactStatus.DENIED and k in protocol.red_flag_screen_keys):
            continue  # 直接安全问句仍必问；不重复让患者先确认同一否定抽取
        if f is None or not ((spec.include_critical and d.critical) or d.category in spec.include_categories):
            continue
        if f.status not in (FactStatus.PRESENT, FactStatus.DENIED, FactStatus.UNCERTAIN) or not is_extraction_only(f):
            continue
        quotes = list(dict.fromkeys(ev.get("quote", "") for ev in f.evidence if ev.get("quote")))
        items.append({"fact_key": k, "label": d.label, "status": f.status, "value": f.value,
                      "value_label": patient_value_label(d, f.status, f.value), "quote": "；".join(quotes)})
    return items[: spec.max_items]


def build_verification(items: list[dict], scope: str, n: int) -> dict:
    if scope == "urgent":
        text = "你的描述里提到了可能需要尽快处理的情况。请先确认我们的理解对不对："
    else:
        text = "请核对：我们从你刚才的描述里整理出下面几条关键信息，每条请选「对」「不对」或「不确定」。"
    return {
        "question_id": f"verify:{scope}:{n}", "fact_key": items[0]["fact_key"], "fact_keys": [i["fact_key"] for i in items],
        "text": text, "type": "verify", "kind": "verification", "scope": scope, "tier": 1,
        "allow_unknown": True, "allow_skip": False, "items": items,
        "options": [{"value": "confirm", "label": "对"}, {"value": "reject", "label": "不对"}, {"value": "unsure", "label": "不确定"}],
    }


GRID_OPTIONS = [{"value": "yes", "label": "有"}, {"value": "no", "label": "没有"}, {"value": "unsure", "label": "不确定"}]


def red_flag_grid_items(facts: dict[str, Fact], protocol: Protocol, stage_questions: list[QuestionDef],
                        already: set[str], stage: str = "pre_visit") -> list[dict]:
    """红旗一屏的行：协议写了题单（screening.pre_visit_grid / checkin_grid）就按题单，否则取 tier 1 是否型红旗题。
    有 when 条件的追问题（例如"腿没劲是否在加重"）在前一屏答完、条件满足后，作为第二屏出现。"""
    expr_map = as_expr_map(facts)
    listed = set(protocol.screening.checkin_grid if stage == "follow_up" else protocol.screening.pre_visit_grid)
    items = []
    for q in sorted(stage_questions, key=lambda q: (q.tier, q.priority)):
        in_grid = (q.id in listed) if listed else q.tier == 1
        if not in_grid or q.type != "yes_no" or q.id in already or q.fact_key not in protocol.red_flag_screen_keys:
            continue
        if not needs_direct_red_flag_answer(facts[q.fact_key], protocol) or not evaluate(q.when, expr_map):
            continue
        items.append({"question_id": q.id, "fact_key": q.fact_key, "text": q.text})
    return items


def build_red_flag_grid(items: list[dict], protocol: Protocol, n: int, stage: str) -> dict:
    spec = protocol.screening
    title = (spec.pre_visit_grid_title or spec.grid_title) if stage == "pre_visit" else spec.grid_title
    return {
        "question_id": f"grid:{stage}:{n}", "fact_key": items[0]["fact_key"], "fact_keys": [i["fact_key"] for i in items],
        "text": title if n == 1 else spec.grid_followup_title, "preface": spec.grid_preface,
        "type": "grid", "kind": "red_flag_grid", "tier": 1, "allow_unknown": False, "allow_skip": False,
        "items": items, "options": GRID_OPTIONS,
    }


def _grid_count(session: Session, encounter_id: str) -> int:
    rows = session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == encounter_id,
                                                    AskedQuestion.kind == "red_flag_grid")).all()
    return len(rows)


def _verification_count(session: Session, encounter_id: str) -> int:
    rows = session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == encounter_id,
                                                    AskedQuestion.kind == "verification")).all()
    return len(rows)


def next_question(session: Session, encounter: Encounter, protocol: Protocol) -> Optional[dict]:
    """返回下一个问题（不落库），没有则 None（包括因紧急红旗终止）。"""
    facts = current_facts(session, encounter.id)

    stops = active_stop_alerts(session, encounter, protocol)
    if stops:
        rules = {r.id: r for r in protocol.red_flags}
        trigger_keys = {k for a in stops for k in rules[a.rule_id].fact_keys}
        items = verification_items(facts, protocol, restrict_keys=trigger_keys)
        if items:
            return build_verification(items, "urgent", _verification_count(session, encounter.id) + 1)
        return None

    for f in facts.values():
        if f.status == FactStatus.CONFLICTING:
            return build_clarification(protocol, f)

    if protocol.event_verification.enabled:
        from ..events.service import next_context_question
        stage = "follow_up" if encounter.kind == EncounterKind.FOLLOW_UP else "pre_visit"
        stage_questions = (protocol.followup.questions if stage == "follow_up" else [q for q in protocol.questions if q.stage in ("pre_visit", "both")])
        if protocol.screening.grid_enabled:
            grid = red_flag_grid_items(facts, protocol, stage_questions, asked_ids(session, encounter.id), stage)
            if grid:
                return build_red_flag_grid(grid, protocol, _grid_count(session, encounter.id) + 1, stage)
        context = next_context_question(session, encounter, protocol)
        if context:
            return context

    items = verification_items(facts, protocol)
    if items:
        return build_verification(items, "normal", _verification_count(session, encounter.id) + 1)

    stage = "follow_up" if encounter.kind == EncounterKind.FOLLOW_UP else "pre_visit"
    stage_questions = (protocol.followup.questions if encounter.kind == EncounterKind.FOLLOW_UP
                       else [q for q in protocol.questions if q.stage in ("pre_visit", "both")])
    already = asked_ids(session, encounter.id)

    if protocol.screening.grid_enabled:
        grid = red_flag_grid_items(facts, protocol, stage_questions, already, stage)
        if grid:
            return build_red_flag_grid(grid, protocol, _grid_count(session, encounter.id) + 1, stage)

    expr_map = as_expr_map(facts)
    cap_reached = encounter.question_count >= protocol.max_questions
    for q in sorted(stage_questions, key=lambda q: (q.tier, q.priority)):
        if q.id in already:
            continue
        if cap_reached and q.tier != 1:
            continue  # 达到上限后只允许必问题（tier 1）
        f = facts[q.fact_key]
        fdef = protocol.fact(q.fact_key)
        extracted_text_only = fdef.type == "text" and f.status == FactStatus.PRESENT and is_extraction_only(f)
        if needs_direct_red_flag_answer(f, protocol):
            pass  # 红旗的"没有"不是直接回答：照样问
        elif f.status in (FactStatus.PRESENT, FactStatus.DENIED, FactStatus.ASKED_UNANSWERED) and not extracted_text_only:
            continue  # 文本型事实只是从原话里"提到"时，仍请患者明确说一次（例如用药）
        if not evaluate(q.when, expr_map):
            continue
        return _question_to_payload(q, protocol)
    return None


def register_asked(session: Session, encounter: Encounter, payload: dict) -> AskedQuestion:
    existing = session.exec(select(AskedQuestion).where(AskedQuestion.encounter_id == encounter.id,
                                                        AskedQuestion.question_id == payload["question_id"],
                                                        AskedQuestion.answer_status == "pending")).first()
    if existing:
        return existing
    aq = AskedQuestion(encounter_id=encounter.id, question_id=payload["question_id"],
                       fact_keys=payload.get("fact_keys") or [payload["fact_key"]], text=payload["text"], kind=payload["kind"],
                       options=payload["items"] if payload["kind"] in ("verification", "red_flag_grid") else payload.get("options", []),
                       payload=payload)
    session.add(aq)
    if payload.get("tier", 2) != 1:
        encounter.question_count += 1  # 必问题不计入上限
    session.add(encounter)
    session.commit()
    session.refresh(aq)
    return aq
