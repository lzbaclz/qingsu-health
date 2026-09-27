# 2026-09-26 工程验证日志

实际执行：后端 `.venv/bin/python -m pytest -q`；前端 `pnpm run build && pnpm run lint`。后端测试自行使用临时数据库。没有接触真实患者数据，也未调用真实模型。

## 后端

```text
........................................................................ [ 46%]
........................................................................ [ 93%]
..........                                                               [100%]
154 passed in 6.14s
```

## 前端

构建及 lint 退出码均为 0；lint 有 9 条 warning，不应表述为零警告。

```text
vite v8.3.0 building client environment for production...
transforming...
✓ 69 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.56 kB │ gzip:   0.39 kB
dist/assets/index-0HVQpjXo.css   42.72 kB │ gzip:   9.36 kB
dist/assets/index-DrNEbqun.js   436.59 kB │ gzip: 133.89 kB

✓ built in 168ms
$ oxlint
src/patient/DescribePage.tsx:33:36: warning react(purity): Cannot call impure function during render help: `Date.now` is an impure function. Calling an impure function can produce unstable results that update unpredictably when the component re-renders
src/patient/BodyPage.tsx:20:36: warning react(purity): Cannot call impure function during render help: `Date.now` is an impure function. Calling an impure function can produce unstable results that update unpredictably when the component re-renders
src/patient/BodyPage.tsx:25:7: warning react(set-state-in-effect): Calling setState synchronously within an effect can trigger cascading renders help: Effects should synchronize React with external systems. Calling setState synchronously inside an effect starts another render and is usually unnecessary. Derive the value during render, initialize state directly, or update it from the event that caused the change. Use an effect only when synchronizing with an external system.
src/patient/ConfirmPage.tsx:24:36: warning react(purity): Cannot call impure function during render help: `Date.now` is an impure function. Calling an impure function can produce unstable results that update unpredictably when the component re-renders
src/patient/EncounterLayout.tsx:30:10: warning react(set-state-in-effect): Calling setState synchronously within an effect can trigger cascading renders help: Effects should synchronize React with external systems. Calling setState synchronously inside an effect starts another render and is usually unnecessary. Derive the value during render, initialize state directly, or update it from the event that caused the change. Use an effect only when synchronizing with an external system.
src/doctor/EncounterDetailPage.tsx:43:10: warning react(set-state-in-effect): Calling setState synchronously within an effect can trigger cascading renders help: Effects should synchronize React with external systems. Calling setState synchronously inside an effect starts another render and is usually unnecessary. Derive the value during render, initialize state directly, or update it from the event that caused the change. Use an effect only when synchronizing with an external system.
src/doctor/detail/DoctorActions.tsx:24:5: warning react(set-state-in-effect): Calling setState synchronously within an effect can trigger cascading renders help: Effects should synchronize React with external systems. Calling setState synchronously inside an effect starts another render and is usually unnecessary. Derive the value during render, initialize state directly, or update it from the event that caused the change. Use an effect only when synchronizing with an external system.
src/components/BodyMap.tsx:396:14: warning react(only-export-components): Fast refresh only works when a file only exports components. Use a new file to share constants or functions between components.
src/components/BodyMap.tsx:641:17: warning react(only-export-components): Fast refresh only works when a file only exports components. Use a new file to share constants or functions between components.
```
