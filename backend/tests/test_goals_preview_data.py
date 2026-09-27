import json
from pathlib import Path
import stat
import yaml
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app import data_admin
from app.course import goals
from app.db import engine
from app.main import app
from app.models import Encounter, Task
from app.protocol import get_protocol
from app.protocol.preview import PreviewCase, preview
from app.services import encounter as svc


def encounter(session):
    return svc.create_encounter(session, patient_code=None, protocol_id='lbp_adult_v0.2')


def obs(key, value=20, **kwargs):
    return dict(submission_key=key, state='measured', value=value, observed_date='2026-09-25',
                condition_match='same', conditions='平地，不提物品', note='', **kwargs)


def test_functional_comparison_never_treats_missing_or_changed_conditions_as_improvement(session):
    enc = encounter(session)
    goal = goals.create_goal(session, enc, '走到商店', 'minutes', '平地，不提物品', True)[0]
    goals.add_observation(session, enc, goal['id'], obs('observation-001'))
    second = {**obs('observation-002', 30), 'observed_date': '2026-09-26'}
    result = goals.add_observation(session, enc, goal['id'], second)[0]
    assert result['comparison']['comparable'] and result['comparison']['delta'] == 10
    third = {**obs('observation-003', 40), 'condition_match': 'changed', 'conditions': '扶着走', 'observed_date': '2026-09-27'}
    assert not goals.add_observation(session, enc, goal['id'], third)[0]['comparison']['comparable']
    fourth = {**obs('observation-004'), 'state': 'unknown', 'value': None}
    result = goals.add_observation(session, enc, goal['id'], fourth)[0]
    assert result['comparison']['delta'] is None and result['observations'][-1]['value'] is None
    assert len(goals.add_observation(session, enc, goal['id'], fourth)[0]['observations']) == 4
    with pytest.raises(svc.FlowError):
        goals.add_observation(session, enc, goal['id'], {**fourth, 'value': 0})


def test_functional_goal_scopes_to_patient_and_course_and_requires_confirmation(session):
    a, b = encounter(session), encounter(session)
    with pytest.raises(svc.FlowError):
        goals.create_goal(session, a, '散步', 'minutes', '平地', False)
    goal = goals.create_goal(session, a, '散步', 'minutes', '平地，不提物品', True)[0]
    with pytest.raises(svc.FlowError):
        goals.add_observation(session, b, goal['id'], obs('cross-patient-01'))
    assert goals.view(session, b) == []
    goals.add_observation(session, a, goal['id'], obs('same-day-001'))
    assert not goals.add_observation(session, a, goal['id'], obs('same-day-002', 30))[0]['comparison']['comparable']


def test_protocol_preview_finds_removed_alert_and_unassigned_role_without_live_mutation(session):
    base = get_protocol('lbp_adult_v0.2')
    cases = [PreviewCase.model_validate({'id':'redflag','facts':{'bladder_change':{'status':'present','value':True}}})]
    before_count = len(session.exec(select(Encounter)).all())
    candidate = base.model_dump(mode='json')
    same = preview(base, yaml.safe_dump(candidate), cases)
    assert same['changed_count'] == 0
    active = same['cases'][0]['before']['alerts']
    assert active
    remove_id = active[0]['rule_id']
    candidate['red_flags'] = [r for r in candidate['red_flags'] if r['id'] != remove_id]
    candidate['course']['task_routing'] = {}
    result = preview(base, yaml.safe_dump(candidate), cases)
    assert result['changed_count'] == 1
    assert remove_id not in [r['rule_id'] for r in result['cases'][0]['after']['alerts']]
    assert len(session.exec(select(Encounter)).all()) == before_count
    assert get_protocol('lbp_adult_v0.2').model_dump() == base.model_dump()


def test_protocol_preview_access_and_cross_protocol_rejected(client):
    with TestClient(app) as anon:
        assert anon.post('/api/protocols/preview-impact', json={'base_protocol_id':'lbp_adult_v0.2','candidate_yaml':'{}','cases':[{'id':'x'}]}).status_code == 401
    base = get_protocol('lbp_adult_v0.2')
    data = base.model_dump(mode='json'); data['protocol_id'] = 'other'
    with pytest.raises(ValueError, match='protocol_id'):
        preview(base, yaml.safe_dump(data), [PreviewCase(id='a')])


def test_backup_export_delete_restore_are_scoped_and_revoke_restored_access(session, tmp_path):
    from app.security import issue_session
    a, b = encounter(session), encounter(session)
    goals.create_goal(session, a, '走路', 'minutes', '平地', True)
    issue_session(session, __import__('fastapi').Response(), 'patient', a.patient_id, a.clinic_id)
    source = Path(engine.url.database)
    copy = tmp_path / 'maintenance.db'
    original = data_admin.backup(source, copy)
    assert original['integrity'] == 'ok'
    assert stat.S_IMODE(copy.stat().st_mode) == 0o600
    export = tmp_path / 'patient.json'
    data_admin.export_patient(copy, export, a.clinic_id, a.patient_id)
    bundle = json.loads(export.read_text())
    assert 'accesssession' not in bundle['tables'] and 'patientinvite' not in bundle['tables']
    assert bundle['tables']['functionalgoal']
    with pytest.raises(ValueError):
        data_admin.export_patient(copy, tmp_path/'forbidden.json', 'wrong-clinic', a.patient_id)
    assert data_admin.delete_patient(copy, a.clinic_id, a.patient_id)['dry_run']
    with pytest.raises(ValueError):
        data_admin.delete_patient(copy, a.clinic_id, a.patient_id, execute=True, confirm='wrong')
    data_admin.delete_patient(copy, a.clinic_id, a.patient_id, execute=True, confirm=a.patient_id, policy_reference='synthetic-test-only')
    with data_admin.connect(copy) as c:
        assert c.execute('SELECT COUNT(*) FROM patient WHERE id=?', (a.patient_id,)).fetchone()[0] == 0
        assert c.execute('SELECT COUNT(*) FROM patient WHERE id=?', (b.patient_id,)).fetchone()[0] == 1
        assert c.execute('SELECT COUNT(*) FROM functionalgoal WHERE patient_id=?', (a.patient_id,)).fetchone()[0] == 0
    restored = tmp_path/'restored.db'
    data_admin.backup(source, restored, restore=True)
    with data_admin.connect(restored) as c:
        assert c.execute('SELECT COUNT(*) FROM accesssession WHERE revoked=0').fetchone()[0] == 0
        assert c.execute('SELECT COUNT(*) FROM patientinvite').fetchone()[0] == 0
    assert session.get(Encounter, a.id) is not None  # 原始测试库没被删除
    with pytest.raises(FileExistsError):
        data_admin.backup(source, restored)


def test_public_health_hides_runtime_details():
    with TestClient(app) as anon:
        assert anon.get('/api/health').json() == {'ok': True}
        assert anon.get('/api/status').status_code == 401
