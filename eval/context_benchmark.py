"""中文语境开发评测：模型原始输出、实际投影与追问策略分开计分。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from provenance import source_manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--provider', choices=['mock', 'ollama'], default='mock')
    ap.add_argument('--model', default='qwen3:4b')
    ap.add_argument('--think', default='false')
    ap.add_argument('--out', default=str(ROOT/'docs/release_20260927/eval'))
    a = ap.parse_args()
    os.environ.update(TIJI_MODE='demo', TIJI_LLM_PROVIDER=a.provider, TIJI_LLM_FALLBACK='none',
                      TIJI_OLLAMA_MODEL=a.model, TIJI_OLLAMA_THINK=a.think, TIJI_LLM_TIMEOUT='90', TIJI_WORKER_INTERVAL='0',
                      TIJI_DATABASE_URL=f"sqlite:///{tempfile.mkdtemp(prefix='tiji-context-eval-')}/eval.db")
    from app.db import init_db, session_scope
    from app.models import Entry, EntryKind, Encounter, ProtocolSnapshot
    from app.protocol import get_protocol
    from app.facts.store import current_facts, init_facts
    from app.events.service import events_for, decision_trace
    from app.extraction import service as extraction
    from app.llm.provider import build_provider, USAGE, ExtractionOutput
    from app.protocol.preview import digest
    import yaml
    path = ROOT/'eval/scenarios/context/context_dev_v1.json'
    data = json.loads(path.read_text())
    base = get_protocol('lbp_adult_v0.2')
    start_manifest = source_manifest([path], ROOT/'protocols/lbp_adult_v0.2.yaml')
    reader = build_provider(a.provider)
    init_db()
    out_dir = Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    stem = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S') + '_context_' + a.provider + ('_' + a.model.replace(':','-') if a.provider != 'mock' else '')
    output = out_dir/(stem+'.json')
    report = {'meta': {'dataset_source': data['source'], 'planned_n':len(data['items']), 'provider':reader.name, 'think':a.think,
                       'at_utc':datetime.now(timezone.utc).isoformat(), 'provenance_start':start_manifest,
                       'protocol_sha256':base.content_sha256,
                       'method':'每句实际调用主抽取和可用的红旗专查一次；同一原始候选在三个策略中配对重放，不冒充三次独立模型推理。未运行封存留出集。'}, 'results':[]}
    repeated_error, failures = None, 0
    for item in data['items']:
        row = {'id':item['id'], 'pair':item['pair'], 'text':item['text'], 'expected':item['expected']}
        t0 = time.monotonic()
        try:
            main_out = reader.extract(item['text'], base)
            rf_fn = getattr(reader, 'extract_red_flags', None)
            rf_out = rf_fn(item['text'], base) if rf_fn else None
            row['raw'] = {'main':main_out.model_dump(), 'red_flag':rf_out.model_dump() if rf_out else None}
            row['inference_seconds'] = round(time.monotonic()-t0, 3)
            class Replay:
                name = last_used = reader.name + ':paired-candidate-replay'
                def extract(self, text, protocol): return main_out
                def extract_red_flags(self, text, protocol): return rf_out or ExtractionOutput(facts=[])
            original = extraction.get_provider
            extraction.get_provider = lambda: Replay()
            arms = {}
            try:
                for arm in ['no_context', 'all', 'action_sensitive']:
                    p = base.model_copy(deep=True)
                    p.event_verification.enabled = arm != 'no_context'
                    p.event_verification.strategy = 'all' if arm == 'all' else 'action_sensitive'
                    p.content_sha256 = digest(p)
                    with session_scope() as session:
                        if not session.get(ProtocolSnapshot, p.content_sha256):
                            session.add(ProtocolSnapshot(id=p.content_sha256, protocol_id=p.protocol_id, version=p.version, content=p.model_dump(mode='json')))
                        enc = Encounter(patient_id='synthetic-eval', protocol_id=p.protocol_id, protocol_version=p.version, protocol_sha256=p.content_sha256)
                        session.add(enc); session.commit(); init_facts(session, enc, p)
                        entry = Entry(encounter_id=enc.id, seq=1, kind=EntryKind.FREE_TEXT, payload={'text':item['text']})
                        session.add(entry); session.commit()
                        extraction.extract_and_apply(session, enc, p, entry)
                        fact = current_facts(session, enc.id)[item['key']]
                        events = [e for e in events_for(session, enc.id) if item['key'] in e.fact_keys]
                        expected = item['expected']
                        projection_ok = fact.status in expected['current_allowed']
                        context_ok = any(e.subject == expected['subject'] and e.time_relation in expected['time_allowed'] for e in events) if arm != 'no_context' else None
                        arms[arm] = {'status':fact.status, 'value':fact.value, 'projection_ok':projection_ok, 'context_ok':context_ok,
                                     'other_current_assertions':[{'key':f.key,'status':f.status,'value':f.value} for f in current_facts(session, enc.id).values() if f.key != item['key'] and f.status in {'present','denied','uncertain','conflicting'}],
                                     'events':[{'subject':e.subject, 'assertion_type':e.assertion_type, 'time_relation':e.time_relation, 'quote':e.quote,
                                                'issues':e.inference_issues, 'trace':decision_trace(session, enc, p, e)} for e in events]}
                row['arms'] = arms
            finally:
                extraction.get_provider = original
            failures, repeated_error = 0, None
        except Exception as e:
            row['error'] = f'{type(e).__name__}: {e}'
            failures = failures + 1 if repeated_error == row['error'] else 1
            repeated_error = row['error']
        report['results'].append(row)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"{item['id']} {'ERROR' if 'error' in row else 'recorded'}", flush=True)
        if failures >= 3:
            report['meta']['stopped_after_three_same_errors'] = repeated_error
            break
    end = source_manifest([path], ROOT/'protocols/lbp_adult_v0.2.yaml')
    report['meta'].update(provenance_end=end, source_unchanged=end == start_manifest, usage=USAGE.snapshot())
    n = len(data['items'])
    report['aggregate'] = {'planned_n':n, 'attempted_n':len(report['results']),
                            'failed_n':sum('error' in r for r in report['results']), 'arms':{}}
    for arm in ['no_context','all','action_sensitive']:
        rows = [r['arms'][arm] for r in report['results'] if 'arms' in r]
        report['aggregate']['arms'][arm] = {'projection_ok':sum(r['projection_ok'] for r in rows),
             'context_ok':sum(bool(r['context_ok']) for r in rows) if arm != 'no_context' else None,
             'denominator':n, 'candidate_clarifications':sum(e['trace']['should_ask'] for r in rows for e in r['events'])}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    lines = ['# 中文语境最小差异开发评测', '', report['meta']['method'], '',
             '标签由本项目作者／AI 编写，未独立临床标注；仅开发结果。所有句子围绕腿麻；投影分数只看该目标字段，其他错误候选单列，不是整条病例准确率。候选澄清数不等于患者实际总题数。', '',
             f'计划 {n} 句；实际 {len(report["results"])} 句；失败 {report["aggregate"]["failed_n"]}；运行中源码未变：{end == start_manifest}。', '',
             '| 策略 | 当前事实投影符合标签 | 主体与时间符合标签 | 候选澄清数 |','|---|---|---|---|']
    for arm, value in report['aggregate']['arms'].items():
        lines.append(f"| {arm} | {value['projection_ok']}/{n} | {str(value['context_ok'])+'/'+str(n) if value['context_ok'] is not None else '不支持'} | {value['candidate_clarifications']} |")
    lines += ['', '逐句原始输出、错误与哈希见同名 JSON；所有失败保留。', '', '| id | 配对 | 结果（action_sensitive） |','|---|---|---|']
    for r in report['results']:
        value = r.get('arms',{}).get('action_sensitive',{})
        lines.append(f"| {r['id']} | {r['pair']} | {r.get('error') or ('符合' if value.get('projection_ok') and value.get('context_ok') else '未符合，见 JSON')} |")
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(str(output), flush=True)
    return 2 if report['meta'].get('stopped_after_three_same_errors') else 0


if __name__ == '__main__':
    raise SystemExit(main())
