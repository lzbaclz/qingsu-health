"""通过实际问询采集同口径基线，不能用“现在痛”替代“近七天平均痛”。"""
from datetime import datetime, timedelta, timezone
from sqlmodel import select

from app.models import Task
from app.services import encounter as svc
from app.protocol.loader import for_encounter
from app.course.trajectory import trajectory
from app.facts.store import current_facts
from app.util import now, set_clock


def finish(session, enc, values):
    svc.add_body_map(session, enc, [{"region_id": "lower_back_right", "kind": "primary"}])
    shown = []
    for _ in range(100):
        q = svc.get_next_question(session, enc)
        if not q:
            break
        shown.append(q)
        if q['kind'] == 'red_flag_grid':
            answer = {'value': {x['question_id']: 'no' for x in q['items']}}
        elif q['kind'] == 'verification':
            answer = {'value': {x['fact_key']: 'confirm' for x in q['items']}}
        elif q['fact_key'] in values:
            answer = {'value': values[q['fact_key']]}
        elif q['type'] == 'yes_no':
            answer = {'value': 'no'}
        else:
            answer = {'unknown': True}
        svc.answer_question(session, enc, q['question_id'], **answer)
    else:
        raise AssertionError('模拟问询未结束')
    svc.patient_confirm(session, enc)
    return shown


def test_first_visit_collects_same_outcomes_and_followup_can_raise_a_review_task(session):
    set_clock(datetime(2026, 9, 28, 1, tzinfo=timezone.utc))
    try:
        parent = svc.create_encounter(session, patient_code=None, protocol_id='lbp_adult_v0.2')
        qs = finish(session, parent, {'age_band': '18_49', 'severity_now': 2, 'pain_avg_7d': 6, 'interference_7d': 5})
        assert {'q_pv_pain_avg_7d', 'q_pv_interference_7d'} <= {q['question_id'] for q in qs}
        initial_grid = next(q for q in qs if q['kind'] == 'red_flag_grid')
        assert '每一行' in initial_grid['text'] and '这次腰背痛以来有没有出现' not in initial_grid['text']
        assert current_facts(session, parent.id)['severity_now'].value == 2
        svc.doctor_confirm(session, parent, 'staff:synthetic-doctor', override_reason='仅合成流程验证')
        svc.set_followup_plan(session, parent, 'staff:synthetic-doctor', {
            'interval_days': 7, 'patient_message': '请一周后更新情况。', 'understanding_points': ['请一周后更新情况。']})
        code = svc.encounter_brief(session, parent)['patient_code']
        set_clock(now() + timedelta(days=7))
        child = svc.create_encounter(session, patient_code=code, protocol_id=parent.protocol_id,
                                     kind='follow_up', parent_encounter_id=parent.id)
        finish(session, child, {'pain_avg_7d': 9, 'interference_7d': 7, 'pgic': 'worse'})
        result = trajectory(session, child, for_encounter(session, child))
        pain = next(x for x in result['outcomes'] if x['key'] == 'pain_avg_7d')
        assert pain['baseline'] == 6 and pain['current'] == 9 and pain['baseline_substitute'] is None
        assert pain['label'] == '近 7 天平均痛' and pain['label_verdict'] == '明显变差'
        tasks = session.exec(select(Task).where(Task.encounter_id == child.id)).all()
        review = next(t for t in tasks if (t.detail or {}).get('rule_id') == 'rr_worse_vs_baseline')
        assert review.due_at is not None and review.assignee_role
    finally:
        set_clock(None)
