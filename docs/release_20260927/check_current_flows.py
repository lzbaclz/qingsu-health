"""0.2.5 协议的当前流程检查；自编合成数据，非临床效果或模型准确率。"""
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'eval'))
os.environ.update(TIJI_MODE='demo',TIJI_LLM_PROVIDER='mock',TIJI_WORKER_INTERVAL='0',TIJI_DATABASE_URL=f"sqlite:///{tempfile.mkdtemp(prefix='tiji-current-flows-')}/eval.db")
from app.db import init_db,session_scope
from app.models import Task
from app.services import encounter as svc
from app.protocol.loader import for_encounter
from app.course.trajectory import trajectory
from app.util import now,set_clock
from sqlmodel import select
from provenance import source_manifest

# 先固定期望；unknown 必须经问询保存，不以0代替。最后一项验证紧急时停止。
CASES=[
 {'id':'FLOW01','base':6,'current':4,'expected':'improved_meaningful','urgent':False},
 {'id':'FLOW02','base':6,'current':8,'expected':'worse_meaningful','urgent':False},
 {'id':'FLOW03','base':None,'current':4,'expected':'insufficient','urgent':False},
 {'id':'FLOW04','base':6,'current':None,'expected':'insufficient','urgent':False},
 {'id':'FLOW05','base':0,'current':0,'expected':'no_meaningful_change','urgent':False},
 {'id':'FLOW06','base':6,'current':None,'expected':'insufficient','urgent':True},
]

def fill(s,e,value,urgent=False):
 svc.add_body_map(s,e,[{'region_id':'lower_back_right','kind':'primary'}])
 qs=[]
 values={'age_band':'18_49','severity_now':3,'pain_avg_7d':value,'interference_7d':4,'pgic':'same'}
 for _ in range(100):
  q=svc.get_next_question(s,e)
  if q is None:break
  qs.append({'id':q['question_id'],'kind':q['kind'],'keys':q.get('fact_keys',[q.get('fact_key')])})
  if q['kind']=='red_flag_grid':
   answer={'value':{i['question_id']:'yes' if urgent and i['fact_key']=='bladder_bowel_change' else 'no' for i in q['items']}}
  elif q['kind']=='verification':answer={'value':{i['fact_key']:'confirm' for i in q['items']}}
  elif q['fact_key'] in values:
   v=values[q['fact_key']];answer={'unknown':True} if v is None else {'value':v}
  elif q['type']=='yes_no':answer={'value':'no'}
  else:answer={'unknown':True}
  svc.answer_question(s,e,q['question_id'],**answer)
 else:raise RuntimeError('问询未收敛')
 stop=svc.stop_info(s,e)
 svc.patient_confirm(s,e)
 return qs,stop,svc.question_metrics(s,e.id)

init_db();manifest=source_manifest([Path(__file__)],ROOT/'protocols/lbp_adult_v0.2.yaml');rows=[]
for c in CASES:
 set_clock(datetime(2026,9,28,1,tzinfo=timezone.utc))
 with session_scope() as s:
  p=svc.create_encounter(s,patient_code=None,protocol_id='lbp_adult_v0.2')
  initial,_,initial_metrics=fill(s,p,c['base'])
  svc.doctor_confirm(s,p,'staff:synthetic-doctor',override_reason='合成流程测试')
  svc.set_followup_plan(s,p,'staff:synthetic-doctor',{'interval_days':7,'patient_message':'请一周后更新情况。','understanding_points':['请一周后更新情况。']})
  set_clock(now()+timedelta(days=7))
  child=svc.create_encounter(s,patient_code=svc.encounter_brief(s,p)['patient_code'],protocol_id=p.protocol_id,kind='follow_up',parent_encounter_id=p.id)
  following,stop,follow_metrics=fill(s,child,c['current'],c['urgent'])
  t=trajectory(s,child,for_encounter(s,child));pain=next(o for o in t['outcomes'] if o['key']=='pain_avg_7d')
  tasks=s.exec(select(Task).where(Task.encounter_id==child.id)).all()
  actual={'baseline':pain['baseline'],'current':pain['current'],'verdict':pain['verdict'],'baseline_substitute':pain['baseline_substitute'],'urgent_stop':stop['stop_reason']=='urgent_red_flag',
          'recovery_review':any((task.detail or {}).get('rule_id')=='rr_worse_vs_baseline' for task in tasks),'baseline_questions_present':{'q_pv_pain_avg_7d','q_pv_interference_7d'}<={q['id'] for q in initial}}
  passed=actual['baseline']==c['base'] and actual['current']==c['current'] and actual['verdict']==c['expected'] and actual['urgent_stop']==c['urgent'] and actual['baseline_substitute'] is None and actual['baseline_questions_present']
  if c['id']=='FLOW02':passed=passed and actual['recovery_review']
  rows.append({'case':c,'actual':actual,'pass':passed,'initial_questions':initial,'followup_questions':following,'initial_metrics':initial_metrics,'followup_metrics':follow_metrics})
 set_clock(None)
report={'at_utc':datetime.now(timezone.utc).isoformat(),'scope':'当前协议流程和数值完整性，未评估临床阈值有效性、语义模型准确率或界面文字','planned_n':len(CASES),'completed_n':len(rows),'passed':sum(r['pass'] for r in rows),'provenance_start':manifest,'source_unchanged':manifest==source_manifest([Path(__file__)],ROOT/'protocols/lbp_adult_v0.2.yaml'),'results':rows}
out=Path(__file__).parent/'v031-current-flows.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'passed':report['passed'],'planned_n':len(CASES),'path':str(out)},ensure_ascii=False))
raise SystemExit(0 if all(r['pass'] for r in rows) else 1)
