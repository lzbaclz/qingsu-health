"""隔离、可重复启动的模拟演示。默认不调用真实模型，不清除任何旧数据库。"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import sys


def main():
    ap = argparse.ArgumentParser()
    base = Path(__file__).resolve().parents[1] / ".local"
    ap.add_argument("--database", type=Path, default=base / "demo-v020.db")
    ap.add_argument("--access-file", type=Path, default=base / "demo-access.txt")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--provider", choices=["mock", "ollama", "compat", "anthropic"], default="mock")
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    os.environ.update(TIJI_MODE="demo", TIJI_DATABASE_URL="sqlite:///" + str(args.database.resolve()),
                      TIJI_LLM_PROVIDER="mock", TIJI_ENABLE_DEV="1")
    from sqlmodel import select
    from .db import init_db, session_scope
    from .models import StaffAccount
    from .security import hash_password
    from .seed import seed_demo
    init_db()
    with session_scope() as session:
        account = session.exec(select(StaffAccount).where(StaffAccount.username == "demo-doctor")).first()
        if not account:
            args.access_file.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(args.access_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            password = secrets.token_urlsafe(18)
            session.add(StaffAccount(username="demo-doctor", display_name="模拟演示医生", role="doctor",
                                     clinic_id="clinic_demo", password_hash=hash_password(password)))
            session.commit()
            with os.fdopen(fd, "w") as out:
                out.write(f"模拟演示访问资料（非真实临床账号）\n账号：demo-doctor\n口令：{password}\n")
        result = seed_demo(session)
    print(f"模拟演示数据：{args.database.resolve()}；已保留已有数据。", flush=True)
    print(f"登录资料：{args.access_file.resolve()}（文件权限 0600，口令不进入日志）。", flush=True)
    print("模拟路径准备：" + ("新建完成" if result.get("seeded") else "沿用已有记录"), flush=True)
    if args.prepare_only:
        return
    os.environ["TIJI_LLM_PROVIDER"] = args.provider
    os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)])


if __name__ == "__main__":
    main()
