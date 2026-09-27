"""候选协议在独立内存数据库中的当前状态预演，不读取或覆盖患者库。"""
from __future__ import annotations

import hashlib
import json
import yaml
from pydantic import BaseModel, Field
from typing import Any, Literal
from sqlmodel import SQLModel, Session, create_engine
from ..models import Encounter, Fact, Alert
from ..questioning.engine import next_question
from .schema import Protocol
from .triage import evaluate_rule


class PreviewFact(BaseModel):
    status: Literal['present', 'denied', 'not_asked', 'asked_unanswered', 'uncertain', 'conflicting']
    value: Any = None
    direct_answer: bool = True


class PreviewCase(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    stage: Literal['pre_visit', 'follow_up'] = 'pre_visit'
    facts: dict[str, PreviewFact] = Field(default_factory=dict, max_length=100)


def digest(p):
    return hashlib.sha256(json.dumps(p.model_dump(mode='json'), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def simulate(p, case):
    # 不接触 app.db.engine；每次建立并销毁内存数据库，不调用模型、外发或任务 worker。
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            enc = Encounter(patient_id='synthetic-preview', protocol_id=p.protocol_id, protocol_version=p.version, kind=case.stage)
            session.add(enc)
            fmap = {}
            for fd in p.facts:
                f = case.facts.get(fd.key, PreviewFact(status='not_asked'))
                if f.status == 'conflicting' and (not isinstance(f.value, dict) or len(f.value.get('candidates', [])) < 2):
                    raise ValueError('矛盾事实必须提供至少两个 candidates')
                fmap[fd.key] = (f.status, f.value)
                session.add(Fact(encounter_id=enc.id, key=fd.key, status=f.status, value=f.value,
                                 evidence=[{'kind': 'answer' if f.direct_answer else 'free_text', 'quote': '模拟情境'}],
                                 source='answer' if f.direct_answer else 'extraction'))
            alerts = []
            for rule in p.red_flags:
                triggered, provisional = evaluate_rule(rule, fmap)
                if not triggered:
                    continue
                route = p.course.task_routing.get(rule.severity)
                alerts.append({'rule_id': rule.id, 'severity': rule.severity, 'provisional': provisional,
                               'action': rule.action, 'on_trigger': rule.on_trigger,
                               'patient_message': rule.conflict_patient_message if provisional else rule.patient_message,
                               'task_kind': rule.task_kind, 'responsibility': route.model_dump() if route else None})
                session.add(Alert(encounter_id=enc.id, rule_id=rule.id, severity=rule.severity,
                                  label=rule.label, patient_message=rule.patient_message, provisional=provisional))
            session.commit()
            q = next_question(session, enc, p)
            return {'next_question': q, 'alerts': alerts, 'unmapped_facts': sorted(set(case.facts) - set(p.fact_index)),
                    'unassigned_alerts': [a['rule_id'] for a in alerts if not a['responsibility']]}
    finally:
        engine.dispose()


def _diff(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        return [d for k in sorted(set(a) | set(b)) for d in _diff(a.get(k), b.get(k), f'{path}.{k}'.strip('.'))]
    return [] if a == b else [{'path': path, 'before': a, 'after': b}]


def preview(base, candidate_yaml, cases):
    candidate = Protocol.model_validate(yaml.safe_load(candidate_yaml))
    if candidate.protocol_id != base.protocol_id:
        raise ValueError('候选 protocol_id 必须与基线一致；跨专科不作直接比较')
    if len({c.id for c in cases}) != len(cases):
        raise ValueError('情境编号不能重复')
    rows = []
    for case in cases:
        before, after = simulate(base, case), simulate(candidate, case)
        rows.append({'id': case.id, 'changed': before != after, 'before': before, 'after': after})
    return {'base': {'version': base.version, 'sha256': digest(base)},
            'candidate': {'version': candidate.version, 'sha256': digest(candidate)},
            'case_count': len(rows), 'changed_count': sum(r['changed'] for r in rows),
            'configuration_changes': _diff(base.model_dump(mode='json'), candidate.model_dump(mode='json')),
            'review_gaps': candidate.review_gaps(), 'cases': rows,
            'scope': '仅比较给定事实状态下的下一问、红旗提醒与责任配置。不是完整疗程仿真、临床批准或全路径证明；不覆盖运行协议。'}
