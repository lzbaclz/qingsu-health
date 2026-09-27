# 体迹 AI · 常用命令（macOS/Linux）
PY=backend/.venv/bin/python
UV=backend/.venv/bin/uvicorn

.PHONY: setup backend frontend seed test eval eval-locked eval-form-only eval-stress eval-careless eval-real eval-cn eval-local demo llm-check protocol-check reset-db user-test-backend user-test-report protocol-v02 evidence

setup:            ## 安装后端与前端依赖
	cd backend && uv venv -q .venv && uv pip install -q -e ".[dev]"
	cd frontend && pnpm install

backend:          ## 启动后端 http://localhost:8000（文档 /docs）
	cd backend && .venv/bin/python -m app.demo --database .local/demo-v031-p026.db --access-file .local/demo-v031-p026-access.txt

frontend:         ## 启动前端 http://localhost:5173
	cd frontend && pnpm dev --port 5173

seed:             ## 灌入 4 条演示路径（正常/矛盾/红旗/随访）
	cd backend && .venv/bin/python -m app.demo --prepare-only --database .local/demo-v031-p026.db --access-file .local/demo-v031-p026-access.txt

reset-db:         ## 原数据库保护：请使用数据维护工具的预览与受控处置
	@echo "不删除既有数据库。新演示请使用 app.demo --database 新路径；数据处置见 docs/23。"

test:             ## 后端测试
	cd backend && .venv/bin/python -m pytest -q

eval:             ## 离线开发场景评测（不打开封存集合）
	cd backend && .venv/bin/python ../eval/runner.py --split dev --arm full

eval-locked:      ## 只跑锁定集
	cd backend && .venv/bin/python ../eval/runner.py --split locked --arm full

eval-form-only:   ## 消融：不抽取自由文本，只靠问答
	cd backend && .venv/bin/python ../eval/runner.py --split dev --arm form_only

protocol-check:   ## 校验协议 YAML（医生改完后运行）
	cd backend && .venv/bin/python -c "from app.protocol import list_protocols; import json; print(json.dumps(list_protocols(), ensure_ascii=False, indent=2))"

eval-stress:      ## 口语压力集（离线词表基线）
	cd backend && .venv/bin/python ../eval/runner.py --split stress

eval-careless:    ## 粗心患者对照：一键核对一律点"对"（开发场景 + 压力集），与认真患者（知道真值）的结果并列进证据表
	cd backend && .venv/bin/python ../eval/runner.py --split dev --patient careless
	cd backend && .venv/bin/python ../eval/runner.py --split stress --patient careless
	$(PY) docs/release_20260927/build_current_evidence.py

evidence:         ## 当前版本证据汇总（保留失败与开发集限制）
	$(PY) docs/release_20260927/build_current_evidence.py

eval-real:        ## 真实模型评测（Claude；需 ANTHROPIC_API_KEY）：先自检，再跑压力集（认真/粗心）+ 开发集，另跑压力集 effort=high 对照
	cd backend && TIJI_LLM_PROVIDER=anthropic .venv/bin/python -m app.llm.check
	cd backend && .venv/bin/python ../eval/runner.py --split stress --provider anthropic
	cd backend && .venv/bin/python ../eval/runner.py --split stress --provider anthropic --patient careless
	cd backend && .venv/bin/python ../eval/runner.py --split dev --provider anthropic
	cd backend && .venv/bin/python ../eval/runner.py --split stress --provider anthropic --effort high
	$(PY) docs/release_20260927/build_current_evidence.py

eval-cn:          ## 国产模型评测（需 TIJI_COMPAT_BASE_URL / TIJI_COMPAT_API_KEY / TIJI_COMPAT_MODEL）
	cd backend && TIJI_LLM_PROVIDER=compat .venv/bin/python -m app.llm.check
	cd backend && .venv/bin/python ../eval/runner.py --split stress --provider compat
	cd backend && .venv/bin/python ../eval/runner.py --split stress --provider compat --patient careless
	cd backend && .venv/bin/python ../eval/runner.py --split dev --provider compat
	$(PY) docs/release_20260927/build_current_evidence.py

eval-local:       ## 本机模型评测（Ollama，数据不出本机；LOCAL_MODEL 默认 qwen3:4b，gpt-oss:20b 需 LOCAL_THINK=low）
	cd backend && TIJI_LLM_PROVIDER=ollama TIJI_OLLAMA_MODEL=$${LOCAL_MODEL:-qwen3:4b} TIJI_OLLAMA_THINK=$${LOCAL_THINK:-false} TIJI_LLM_TIMEOUT=300 .venv/bin/python -m app.llm.check
	cd backend && TIJI_OLLAMA_MODEL=$${LOCAL_MODEL:-qwen3:4b} TIJI_OLLAMA_THINK=$${LOCAL_THINK:-false} TIJI_LLM_TIMEOUT=300 .venv/bin/python ../eval/runner.py --split stress --provider ollama
	cd backend && TIJI_OLLAMA_MODEL=$${LOCAL_MODEL:-qwen3:4b} TIJI_OLLAMA_THINK=$${LOCAL_THINK:-false} TIJI_LLM_TIMEOUT=300 .venv/bin/python ../eval/runner.py --split stress --provider ollama --patient careless
	$(PY) docs/release_20260927/build_current_evidence.py

demo:             ## 隔离模拟演示：随机账号、独立数据库、保留旧数据；真实模型可直接用 app.demo --provider 指定
	cd backend && .venv/bin/python -m app.demo --database .local/demo-v031-p026.db --access-file .local/demo-v031-p026-access.txt

access-account:   ## 手工创建机构账号；输出文件不得加入版本控制
	cd backend && .venv/bin/python -m app.bootstrap_access --username clinician --name 医生 --role doctor

llm-check:        ## 真实模型连通性自检：用一句固定测试原话跑一次真实抽取，打印能否用、耗时与原因
	cd backend && .venv/bin/python -m app.llm.check

user-test-backend: ## 可用性测试专用后端：打开"植入错抽"（卡 A 显眼型、卡 B 隐蔽型）；默认离线词表，参与者打的字不出本机；演示与录视频不要用
	@echo "可用性测试后端：植入错抽已打开；抽取用 $${UT_PROVIDER:-mock}（UT_PROVIDER=compat 可换境内模型；用境外模型须先在参与者说明里写明）"
	cd backend && TIJI_MODE=demo TIJI_USER_TEST_PLANT=1 TIJI_LLM_PROVIDER=$${UT_PROVIDER:-mock} .venv/bin/uvicorn app.main:app --reload --port 8000

user-test-report: ## 汇总可用性测试（患者编号以 UT- 开头的记录 + 主持人手工表）
	cd backend && .venv/bin/python ../eval/user_test/summarize.py

protocol-v02:     ## 按医生审核决定生成协议 v0.2 候选（protocols/review/decisions.yaml；医生决定为 0 时标题写明是 AI 草案）
	backend/.venv/bin/python protocols/review/build_v02.py

eval-context:    ## 中文语境最小差异开发集，词表基线
	$(PY) eval/context_benchmark.py --provider mock

eval-context-real: ## 本机真实推理，同一候选三策略配对
	$(PY) eval/context_benchmark.py --provider ollama --model $${LOCAL_MODEL:-qwen3:4b}
