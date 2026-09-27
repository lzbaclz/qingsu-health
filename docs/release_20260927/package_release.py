"""打包当前源码和合成验收证据；排除凭据、数据库、依赖目录与封存集合。"""
from pathlib import Path
import json,hashlib,tarfile
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent/'final'
ARCHIVE=OUT/'tiji-ai-0.3.1-source-and-evidence.tar.gz'
MANIFEST=OUT/'release-manifest.json'
files=set()
for folder in ['backend/app','backend/tests','frontend/src','frontend/public','protocols']:
 for p in (ROOT/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.db'}:files.add(p)
for folder in ['eval/scenarios/dev','eval/scenarios/stress','eval/scenarios/redflag','eval/scenarios/context','eval/scenarios/examples','eval/scenarios/overlays','eval/scenarios/knee']:
 for p in (ROOT/folder).rglob('*'):
  if p.is_file():files.add(p)
files.update((ROOT/'eval').glob('*.py'))
for p in (ROOT/'frontend').iterdir():
 if p.is_file() and not p.name.startswith('.env') and p.suffix in {'.json','.ts','.js','.yaml','.html','.lock','.lockb'}:files.add(p)
for rel in ['README.md','Makefile','.gitignore','backend/pyproject.toml']:
 p=ROOT/rel
 if p.exists():files.add(p)
files.update((ROOT/'docs').glob('*.md'))
files.update(p for p in (ROOT/'docs/bp_slides').iterdir() if p.is_file())
for p in Path(__file__).resolve().parent.rglob('*'):
 if p.is_file() and p not in {ARCHIVE,MANIFEST} and p.name not in {'source-manifest.json','tiji-ai-0.3.1-source.tar.gz'}:files.add(p)
for p in files:
 assert not any(x in p.parts for x in ['holdout','locked','.local','node_modules','.venv','__pycache__'])
 assert not p.name.startswith('.env') and p.suffix not in {'.db','.sqlite','.sqlite3','.key','.pem'}
 assert 'access.txt' not in p.name
hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
with tarfile.open(ARCHIVE,'w:gz') as tf:
 for p in sorted(files):tf.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
# 读取包内字节逐个核对，不能把tar命令退出0当作完整性证明。
with tarfile.open(ARCHIVE,'r:gz') as tf:
 members=tf.getmembers()
 assert {m.name for m in members}==set(hashes)
 for m in members:
  assert m.isfile() and hashlib.sha256(tf.extractfile(m).read()).hexdigest()==hashes[m.name]
MANIFEST.write_text(json.dumps({'application':'0.3.1','protocol':'0.2.6','file_count':len(files),'files':hashes,'archive_sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),'archive_verified':True,'excludes':['patient databases','access credentials','.env','dependencies','held-out/locked datasets'],'disclosure':'All included evaluation data and app screenshots use synthetic cases. Founder facts were supplied by the user; clinical approval and trial claims remain pending.'},ensure_ascii=False,indent=2))
print(json.dumps({'file_count':len(files),'archive_bytes':ARCHIVE.stat().st_size,'archive_verified':True,'archive':str(ARCHIVE)},ensure_ascii=False))
