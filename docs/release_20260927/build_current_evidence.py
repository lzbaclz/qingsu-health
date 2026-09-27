"""按版本与配置汇总最新完整运行；保留旧版与失败，不挑最好成绩。"""
from pathlib import Path
import json
import statistics
from datetime import datetime
import xml.etree.ElementTree as ET

DIR=Path(__file__).resolve().parent
CURRENT=DIR/'final/eval'
records=[]
files=sorted((DIR/'v031_eval').glob('*context_ollama*.json'))+sorted(CURRENT.glob('*.json'))
for p in files:
 d=json.loads(p.read_text())
 if 'aggregate' in d:
  m=d['meta'];key=('context',m.get('provider'),m.get('think')) if 'context_' in p.name else (m.get('split'),m.get('arm'),m.get('provider'),m.get('patient'))
  records.append((key,p,d))
selected={key:(p,d) for key,p,d in records}
lines=['# 0.3.1 当前开发证据','',
'默认协议内容0.2.6。24句原生模型运行冻结于0.2.5；已核对抽取提示、字段、事件规则和共享代码完全相同，见final/shared-inference-compatibility.json。新增文本入口另有0.2.6真实推理检查。按同一配置的最新完整运行汇总，未完成的运行另列。全部为合成开发标签，不能解释为临床效果。', '',
'## 中文语境开发对照','',
'24句/12对，仅围绕腿麻；主字段投影分数不覆盖模型额外输出。数据参与过修复，未独立临床标注。no_context 是对相同候选去掉语境处理的消融，不是另一模型独立推理。候选澄清数不等于患者总题数。','',
'| 模型 | 策略 | 主字段符合标签 | 主体/时间符合标签 | 候选澄清数 |','|---|---|---|---|---|']
notes=[]
for key,(p,d) in selected.items():
 if key[0]!='context':continue
 a,m=d['aggregate'],d['meta']
 for arm,v in a['arms'].items():
  context=str(v['context_ok'])+'/'+str(v['denominator']) if v['context_ok'] is not None else '不支持'
  lines.append(f"| {m['provider']} | {arm} | {v['projection_ok']}/{v['denominator']} | {context} | {v['candidate_clarifications']} |")
 lat=sorted(r['inference_seconds'] for r in d['results'] if 'inference_seconds' in r)
 others=sum(bool(r.get('arms',{}).get('action_sensitive',{}).get('other_current_assertions')) for r in d['results'])
 notes+=['',f"{m['provider']}：计划{a['planned_n']}句，尝试{a['attempted_n']}句，失败{a['failed_n']}；源码运行中未变：{m['source_unchanged']}。"]
 if lat:notes.append(f"整句两遍抽取中位{statistics.median(lat):.2f}秒，p90近似{lat[round((len(lat)-1)*.9)]:.2f}秒。非隔离性能基准，不能承诺秒回。")
 notes.append(f"{others}/{a['planned_n']}句另有目标以外的断言，需逐项核验；不能把上述主字段分数称为整病例正确率。")
 notes.append(f"[原始结果和哈希]({p.relative_to(DIR)})；[逐句报告]({p.with_suffix('.md').relative_to(DIR)})。")
for p in sorted(CURRENT.glob('*context_ollama*.json')):
 d=json.loads(p.read_text())
 if 'aggregate' not in d:notes.append(f"运行中：{d['meta']['provider']}，已落盘{len(d['results'])}/{d['meta']['planned_n']}，暂不汇总成绩。")
lines+=notes+['','## 既有情境在当前协议上的检查','',
'原有随访的“当前痛”等标签与新版“近7天平均痛”不同；不暗改真值。这是兼容性和失败定位记录，不能据通过率宣称临床可靠或模型排名。','',
'| 运行 | 完成/计划 | 无critical错误 | 平均屏数 | 平均逐项判断 |','|---|---|---|---|---|']
notes=[]
for key,(p,d) in selected.items():
 if key[0]=='context':continue
 a,m=d['aggregate'],d['meta'];passed=m['pass_count_with_all_planned_denominator']
 lines.append(f"| {m['split']}/{m['arm']}/{m['patient']} | {m['completed_n']}/{m['planned_n']} | {passed['passed']}/{passed['denominator']} | {a['mean_questions_asked']} | {a['mean_decisions_shown']} |")
 notes.append(f"\n[{p.with_suffix('.md').name}]({p.with_suffix('.md').relative_to(DIR)})。源码运行中未变：{m['source_unchanged']}。")
lines+=notes+['','## 复述实际推理与失败历史','',
'空患者引文原来是可选字段，模型可能返回“一致”但无证据。恢复后已把引用改为非空必填，并保留逐字检查和可定位的错误代码。不能通过删除检查来消除失败。','',
'| 模型/运行 | 实际/计划 | 结构通过 | 标签一致/计划 |','|---|---|---|---|']
notes=[]
for p in sorted((DIR/'eval').glob('teachback_*.json'),key=lambda p:json.loads(p.read_text()).get('at_utc','')):
 d=json.loads(p.read_text());valid=sum(r['actual']['source']=='model' for r in d['results'])
 lines.append(f"| {d['model']}，{d['at_utc']} | {d['attempted_n']}/{d['planned_n']} | {valid} | {d['matched']}/{d['planned_n']} |")
 notes.append(f"\n[该次完整记录]({p.relative_to(DIR)})。源码运行中未变：{d['source_unchanged']}。")
lines+=notes+['','四条样例仅为小规模开发检查。有效引用不保证语义正确；所有表达差异都需医护核实，执行状态另记。不同模型/提示版本不可直接当作公平能力排行榜。']
junit=DIR/'v031-tests.xml'
if junit.exists():
 root=ET.parse(junit).getroot();suites=root.findall('testsuite') if root.tag=='testsuites' else [root]
 n=sum(int(s.attrib['tests']) for s in suites);errors=sum(int(s.attrib.get('errors',0))+int(s.attrib.get('failures',0)) for s in suites)
 lines+=['','## 工程与真人证据','',f'当前完整后端{n}项，失败/错误{errors}；前端构建和lint结果见 verification_031.json。']
lines+=['','日期快捷选择已验证持久化与同条件差值，四类医生页面已核对；任意日期选择器未做完整自动化验收。', '',
'用户已确认创始人李子卿、许青冬及许青冬的临床背景。协议审核和机构授权未提供；访谈/试用与十周驻场均待定。', '',
'72句封存留出集未查看、未运行。旧版所有报告保留于 eval/；本版最终流程报告在 final/eval/；冻结的原生抽取报告在 v031_eval/，两者的适用范围已单列。']
lines += ['', '## 最终协议的新症状文本入口', '', '[实际本机调用原始记录](final/native-followup-text.json)；[检查口径与原始否认保留证据](final/native-followup-text-assessment.json)。原检查对“保留否认”采用了过强的同字段冲突条件；修正核查没有重跑模型或更改原始返回。实际结果触发预期紧急提醒，原先的否认仍可追溯，后续仅进入紧急核对。', '', '[六条当前协议流程检查](v031-current-flows.json)覆盖改善、变差、缺测、零值和紧急停止，不将其当作临床验证。原生24句运行的[源码快照](final/native-inference-source.tar.gz)中63个文件逐一匹配当次SHA256，见[核验记录](final/native-source-verification.json)。']
(DIR/'current_evidence.md').write_text('\n'.join(lines)+'\n')
(DIR/'selected_reports.json').write_text(json.dumps({'selected_by':'latest_complete_per_configuration_in_v031_directory_not_best_score','reports':[str(p.relative_to(DIR)) for p,d in selected.values()]},ensure_ascii=False,indent=2))
print(DIR/'current_evidence.md')
