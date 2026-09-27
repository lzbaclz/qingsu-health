"""本机管理员数据工具。默认只读；删除需明确对象、执行开关及机构处置依据。"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid


def connect(path, writable=False):
    path = Path(path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + ('?mode=rw' if writable else '?mode=ro'), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _contains(value, ids):
    if isinstance(value, str):
        return value in ids or value.removeprefix('patient:') in ids
    if isinstance(value, dict):
        return any(_contains(v, ids) for v in value.values())
    if isinstance(value, list):
        return any(_contains(v, ids) for v in value)
    return False


def patient_rows(conn, clinic_id, patient_id):
    patient = conn.execute('SELECT * FROM patient WHERE id=? AND clinic_id=?', (patient_id, clinic_id)).fetchone()
    if not patient:
        raise ValueError('该机构不存在此患者')
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    encounters = [dict(r) for r in conn.execute('SELECT * FROM encounter WHERE patient_id=? AND clinic_id=?', (patient_id, clinic_id))]
    eids = {r['id'] for r in encounters}
    result = {'patient': [dict(patient)], 'encounter': encounters}
    for table in sorted(tables - {'patient', 'encounter', 'auditlog', 'sqlite_sequence'}):
        columns = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        if 'encounter_id' in columns or 'patient_id' in columns:
            rows = [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]
            result[table] = [r for r in rows if r.get('encounter_id') in eids or r.get('patient_id') == patient_id]
    task_ids = {r['id'] for r in result.get('task', [])}
    if 'taskdelivery' in tables:
        result['taskdelivery'] = [dict(r) for r in conn.execute('SELECT * FROM taskdelivery') if r['task_id'] in task_ids]
    if 'accesssession' in tables:
        result['accesssession'] = [dict(r) for r in conn.execute("SELECT * FROM accesssession WHERE kind='patient' AND subject_id=?", (patient_id,))]
    ids = {r['id'] for rows in result.values() for r in rows if 'id' in r}
    if 'auditlog' in tables:
        result['auditlog'] = [dict(r) for r in conn.execute('SELECT * FROM auditlog')
                              if r['target_id'] in ids or _contains(r['actor'], ids) or _contains(json.loads(r['detail'] or '{}'), ids)]
    return result


def write_private(path, data):
    # 禁止覆盖既有文件，生成时即限制权限。
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_patient(database, output, clinic_id, patient_id):
    with connect(database) as conn:
        conn.execute('BEGIN')
        rows = patient_rows(conn, clinic_id, patient_id)
        # 导出临床记录和审计；访问令牌摘要不属于患者内容包。
        rows.pop('accesssession', None); rows.pop('patientinvite', None)
        write_private(output, {'format': 'tiji-patient-export.v1', 'created_at': datetime.now(timezone.utc).isoformat(), 'tables': rows})
    return {k: len(v) for k, v in rows.items()}


def backup(database, output, *, restore=False):
    source, target = Path(database).resolve(strict=True), Path(output).resolve()
    if source == target:
        raise ValueError('目标不能是原数据库')
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with connect(source) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('完整性检查未通过')
            if restore:
                names = {r[0] for r in dst.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'accesssession' in names:
                    dst.execute('UPDATE accesssession SET revoked=1')
                if 'patientinvite' in names:
                    dst.execute('DELETE FROM patientinvite')
                # 不能让恢复环境重复发送外部消息；仍需管理员重新配置与对账。
                if 'taskdelivery' in names:
                    dst.execute("UPDATE taskdelivery SET state='unconfigured' WHERE state!='delivered'")
        return {'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'integrity': 'ok', 'access_revoked': restore}
    except Exception:
        # 保留失败副本供检查，不冒充成功，也不删除源文件。
        raise


def delete_patient(database, clinic_id, patient_id, *, execute=False, confirm=None, policy_reference=None):
    with connect(database, writable=execute) as conn:
        conn.execute('BEGIN IMMEDIATE' if execute else 'BEGIN')
        rows = patient_rows(conn, clinic_id, patient_id)
        counts = {k: len(v) for k, v in rows.items()}
        if not execute:
            return {'dry_run': True, 'counts': counts}
        if confirm != patient_id or not policy_reference or not policy_reference.strip():
            raise ValueError('执行删除需输入相同患者 ID 并提供机构处置批准／保留政策引用')
        if any(r['state'] == 'sending' for r in rows.get('taskdelivery', [])):
            raise ValueError('存在发送中的任务；请停服务并完成消息对账后再处置')
        for table, records in rows.items():
            conn.executemany(f'DELETE FROM "{table}" WHERE id=?', [(r['id'],) for r in records])
        deletion_id = 'del_' + uuid.uuid4().hex
        conn.execute('INSERT INTO auditlog (id,actor,action,target_type,target_id,detail,created_at) VALUES (?,?,?,?,?,?,?)',
                     ('aud_' + uuid.uuid4().hex, 'local-data-operator', 'patient.deleted', 'disposal', deletion_id,
                      json.dumps({'counts': counts, 'policy_reference': policy_reference}), datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return {'deleted': True, 'disposal_id': deletion_id, 'counts': counts,
                'boundary': '仅当前数据库；历史备份、导出和外部系统需按机构政策另行处置。建议停服务维护。'}


def inventory(database, clinic_id, older_than_days):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
    with connect(database) as conn:
        rows = conn.execute('''SELECT p.id, p.display_code, MAX(e.updated_at) AS last_activity
          FROM patient p JOIN encounter e ON e.patient_id=p.id
          WHERE p.clinic_id=? GROUP BY p.id HAVING MAX(e.updated_at)<?''', (clinic_id, cutoff)).fetchall()
    return {'dry_run': True, 'age_threshold_days': older_than_days, 'patients': [dict(r) for r in rows],
            'notice': '这是人工审查清单，年限不是法定保存期限；不自动删除，需核对未结事项和机构保留要求。'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['backup', 'restore', 'export-patient', 'delete-patient', 'inventory'])
    p.add_argument('--database', required=True); p.add_argument('--output')
    p.add_argument('--clinic'); p.add_argument('--patient'); p.add_argument('--older-than-days', type=int)
    p.add_argument('--execute', action='store_true'); p.add_argument('--confirm-patient'); p.add_argument('--policy-reference')
    a = p.parse_args()
    if a.operation in {'backup', 'restore', 'export-patient'} and not a.output:
        p.error('此操作需要 --output；禁止覆盖已有文件')
    if a.operation in {'export-patient', 'delete-patient', 'inventory'} and not a.clinic:
        p.error('需要 --clinic')
    if a.operation in {'export-patient', 'delete-patient'} and not a.patient:
        p.error('需要 --patient')
    if a.operation in {'backup', 'restore'}:
        result = backup(a.database, a.output, restore=a.operation == 'restore')
    elif a.operation == 'export-patient':
        result = export_patient(a.database, a.output, a.clinic, a.patient)
    elif a.operation == 'delete-patient':
        result = delete_patient(a.database, a.clinic, a.patient, execute=a.execute,
                                confirm=a.confirm_patient, policy_reference=a.policy_reference)
    else:
        if not a.older_than_days or a.older_than_days < 1:
            p.error('人工检查需要正数 --older-than-days')
        result = inventory(a.database, a.clinic, a.older_than_days)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
