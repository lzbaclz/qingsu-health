"""真实模型连通性自检（命令行）：python -m app.llm.check

用一句固定的测试原话跑一次真实抽取，打印能否用、耗时和原因。离线词表模式直接说明不需要自检。
退出码：0 = 可用或离线模式；1 = 真实模型不可用（演示时会自动退回离线词表，但应先排查）。
"""
from __future__ import annotations

import sys

from ..config import settings
from .provider import probe


def main() -> int:
    r = probe()
    if r.get("mode") == "mock":
        print("模型自检：当前为离线词表模式（TIJI_LLM_PROVIDER=mock），不调用真实模型。")
        return 0
    head = f"模型自检：{r.get('name', settings.llm_provider)} · {r.get('credentials') or ''}"
    if r.get("ok"):
        print(f"{head}\n  可用：{r['detail']}，耗时 {r['seconds']} 秒。")
        return 0
    print(f"{head}\n  不可用：{r.get('detail')}（耗时 {r.get('seconds')} 秒）")
    fb = "会自动退回离线词表，并在医生端顶栏标出" if settings.llm_fallback == "mock" else "TIJI_LLM_FALLBACK=none，不会退回"
    print(f"  演示时{fb}。请先检查 key、网络或代理，再用 make llm-check 复查。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
