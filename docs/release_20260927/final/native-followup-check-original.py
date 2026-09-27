"""最终协议下新症状文本入口的单例本机真实推理检查；全部为合成数据。"""
import json,os,sys,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'eval'))
os.environ.update(TIJI_MODE='demo',TIJI_LLM_PROVIDER='ollama',TIJI_OLLAMA_MODEL='gpt-oss:20b',TIJI_OLLAMA_THINK='low',TIJI_LLM_FALLBACK='none',TIJI_DATABASE_URL=f"sqlite:///{tempfile.mkdtemp(prefix='tiji-native-followup-')}/eval.db")
from app.db import init_db,session_scope
from app.models import EncounterStatus,FactStatus,AuditLog
from app.services import encounter as svc
from app.facts.store import current_facts
from app.llm.provider import USAGE
from sqlmodel import select
from provenance import source_manifest
init_db();manifest=source_manifest([Path(__file__)],ROOT/'protocols/lbp_adult_v0.2.yaml');started=time.monotonic()
with session_scope() as s:
 p=svc.create_encounter(s,patient_code=None,protocol_id='lbp_adult_v0.2');p.status=EncounterStatus.DOCTOR_CONFIRMED;s.add(p);s.commit()
 c=svc.create_encounter(s,patient_code=svc.encounter_brief(s,p)['patient_code'],protocol_id=p.protocol_id,kind='follow_up',parent_encounter_id=p.id)
 for _ in range(30):
  q=svc.get_next_question(s,c)
  if q is None:raise RuntimeError('未到达新情况文本题')
  if q['question_id']=='q_fu_new_desc':break
  if q['kind']=='red_flag_grid':answer={'value':{i['question_id']:'no' for i in q['items']}}
  elif q['type']=='yes_no':answer={'value':'yes' if q['fact_key']=='fu_new_symptom' else 'no'}
  else:answer={'unknown':True}
  svc.answer_question(s,c,q['question_id'],**answer)
 text='今天才开始小便憋不住。'
 result=svc.answer_question(s,c,q['question_id'],value=text)
 facts=current_facts(s,c.id);following=svc.get_next_question(s,c)
 audit=s.exec(select(AuditLog).where(AuditLog.action=='extraction.completed',AuditLog.target_id==result['symptom_entry_id'])).one()
 checks={'symptom_input_linked':bool(result.get('symptom_entry_id')),'expected_urgent_rule':any(a['rule_id']=='rf_bladder_bowel' and a['severity']=='urgent' for a in result['new_alerts']),'prior_denial_preserved':facts['bladder_bowel_change'].status==FactStatus.CONFLICTING,'no_routine_question_continues':following is None or following.get('scope')=='urgent','actual_native_model':audit.detail['provider']=='ollama:gpt-oss:20b'}
 record={'at_utc':datetime.now(timezone.utc).isoformat(),'protocol_version':c.protocol_version,'synthetic_input':text,'model':'ollama:gpt-oss:20b','checks':checks,'passed':all(checks.values()),'seconds':round(time.monotonic()-started,2),'usage':USAGE.snapshot(),'result':result,'next_question':following,'extraction_audit':audit.detail,'source_manifest':manifest,'source_unchanged':manifest==source_manifest([Path(__file__)],ROOT/'protocols/lbp_adult_v0.2.yaml')}
 out=Path(__file__).parent/'final/native-followup-text.json';out.write_text(json.dumps(record,ensure_ascii=False,indent=2));print(json.dumps({'checks':checks,'path':str(out)},ensure_ascii=False))
