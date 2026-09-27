"""随访追问也是患者原话，不能绕过症状抽取与安全提醒。"""
from app.models import EncounterStatus, FactStatus, Entry
from app.facts.store import current_facts
from app.services import encounter as svc


def test_new_symptom_text_after_negative_grid_requires_urgent_review_and_preserves_conflict(session):
    parent = svc.create_encounter(session, patient_code=None, protocol_id='lbp_adult_v0.2')
    parent.status = EncounterStatus.DOCTOR_CONFIRMED
    session.add(parent); session.commit()
    child = svc.create_encounter(session, patient_code=svc.encounter_brief(session, parent)['patient_code'],
                                 protocol_id=parent.protocol_id, kind='follow_up', parent_encounter_id=parent.id)
    target = None
    for _ in range(30):
        q = svc.get_next_question(session, child)
        assert q is not None
        if q['question_id'] == 'q_fu_new_desc':
            target = q
            break
        if q['kind'] == 'red_flag_grid':
            answer = {'value': {i['question_id']: 'no' for i in q['items']}}
        elif q['type'] == 'yes_no':
            answer = {'value': 'yes' if q['fact_key'] == 'fu_new_symptom' else 'no'}
        else:
            answer = {'unknown': True}
        svc.answer_question(session, child, q['question_id'], **answer)
    assert target is not None
    result = svc.answer_question(session, child, target['question_id'], value='今天才开始小便憋不住。')
    # 同时抽到小便专用字段时规则可直接触发；一般字段里的先前否认仍须保留为矛盾。
    assert result.get('symptom_entry_id')
    assert session.get(Entry, result['symptom_entry_id']).payload['origin_answer_id'] == result['entry_id']
    assert any(a['severity'] == 'urgent' for a in result['new_alerts'])
    assert current_facts(session, child.id)['bladder_bowel_change'].status == FactStatus.CONFLICTING
    # 双方原话都保留；不得静默把先前直接回答改成“有”。
    question = svc.get_next_question(session, child)
    assert question is None or (question['kind'] == 'verification' and question.get('scope') == 'urgent')
