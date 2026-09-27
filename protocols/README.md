# protocols/ —— 临床协议

- `lbp_adult_v0.1.yaml`：成年腰背痛示范协议（**工程占位，待临床审核**）。规范见 `docs/04_临床协议规范.md`。
- `body_regions.yaml`：身体地图区域（前端 SVG 与后端共用）。
- `templates/医生工作表.md`：医生先用表格填写六份交付物 + 门诊访谈提纲；工程再转 YAML。
- `templates/场景审核表.md`：审核 `eval/scenarios/` 的记录格式。
- `review/医生工作表_AI模拟填写_v1.md`：AI 依据公开指南模拟医生填写的版本（含 15 条资料来源）；`review/对比表_AI版_vs_医生版.md`：医生版与 AI 版逐条对照表。
- `lbp_adult_v0.2_ai_draft.yaml`：由 AI 填写版推导的协议草案（`review/build_v02_draft.py` 生成，**未采用**，默认协议仍是 v0.1）。
- `lbp_adult_v0.2.yaml`：v0.2 候选，由 `review/build_v02.py` 按医生在 `review/decisions.yaml` 里的决定生成（`make protocol-v02`）。**医生已决定 0 / 146 条，它现在只是 AI 草案换了文件名**：状态 draft，不在 BP、视频或演示中出现；演示用 v0.1 并标"工程占位"。医生先用 `review/医生两小时决定表.md` 定实名、适用范围与 18 条红旗。
- `review/医生审核会_90分钟议程.md`：审核会议程；`review/compare_protocols.py`：两个协议版本的红旗触发对比。
- `knee_adult_v0.1.yaml`：第二专科（膝痛）复用示范，AI 草案，待临床审核（docs/13）；患者端入口 `/p?protocol=knee_adult_v0.1`。

校验：`make protocol-check`。
