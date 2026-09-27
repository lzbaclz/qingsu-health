"""仅合成复述表达的实际本机推理检查；非理解/依从/疗效验证。"""
import json
import argparse
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
sys.path.insert(0, str(ROOT/'eval'))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', default='qwen3:4b')
parser.add_argument('--think', default='false')
args=parser.parse_args()
os.environ.update(TIJI_MODE='demo', TIJI_LLM_PROVIDER='ollama', TIJI_OLLAMA_MODEL=args.model, TIJI_OLLAMA_THINK=args.think, TIJI_LLM_FALLBACK='none', TIJI_LLM_TIMEOUT='90')
from app.course.teachback import compare
from app.llm.provider import USAGE
from provenance import source_manifest

cases = [
 ('T01','请一周后在这里更新情况。','我会在七天后在这里说说近况。','consistent'),
 ('T02','请一周后在这里更新情况。','我明天回来更新。','contradicts'),
 ('T03','请一周后在这里更新情况。','我看到了。','omitted'),
 ('T04','请一周后在这里更新情况。','我不会在一周后更新情况。','contradicts'),
]
manifest=source_manifest([Path(__file__)],ROOT/'protocols/lbp_adult_v0.2.yaml')
rows=[]
for key,plan,response,expected in cases:
 t=time.monotonic();result=compare([{'id':'p1','text':plan}],response)
 rows.append({'id':key,'plan':plan,'response':response,'expected_author_label':expected,'actual':result,
              'seconds':round(time.monotonic()-t,3), 'matched':result['source']=='model' and result['items'][0]['verdict']==expected})
 print(key,result['source'],result['items'][0]['verdict'],flush=True)
 if len(rows)>=3 and all(r['actual']['source']=='manual_required' for r in rows[-3:]):
  break
report={'at_utc':datetime.now(timezone.utc).isoformat(),'model':'ollama:'+args.model, 'think':args.think,'planned_n':len(cases),'attempted_n':len(rows),
        'matched':sum(r['matched'] for r in rows),'source_manifest':manifest,'source_unchanged':manifest==source_manifest([Path(__file__)],ROOT/'protocols/lbp_adult_v0.2.yaml'),
        'usage':USAGE.snapshot(),'limits':'作者/AI 预写开发标签，非独立临床标注。真实推理、无词表伪装。患者输入是合成文本；所有结果仍需医护复核。','results':rows}
output=Path(__file__).parent/'eval'/('teachback_'+args.model.replace(':','-')+'_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'.json')
output.write_text(json.dumps(report,ensure_ascii=False,indent=2));print(output)
