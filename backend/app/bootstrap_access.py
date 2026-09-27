"""本机创建账号：随机口令写入权限 0600 的本地文件，不进入日志或源码。"""
import argparse
import os
from pathlib import Path
import secrets

from sqlmodel import select
from .db import init_db, session_scope
from .models import StaffAccount
from .security import ROLES, hash_password


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--role", choices=sorted(ROLES), default="doctor")
    ap.add_argument("--clinic", default="clinic_demo")
    ap.add_argument("--output", default=".local/access.txt")
    args = ap.parse_args()
    init_db()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with session_scope() as session:
        if session.exec(select(StaffAccount).where(StaffAccount.username == args.username)).first():
            raise SystemExit("账号已存在，未覆盖口令")
        password = secrets.token_urlsafe(18)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            user = StaffAccount(username=args.username, display_name=args.name, role=args.role,
                                clinic_id=args.clinic, password_hash=hash_password(password))
            session.add(user)
            session.commit()
            with os.fdopen(fd, "w") as out:
                out.write(f"体迹 AI 本地访问\n账号：{args.username}\n口令：{password}\n角色：{args.role}\n机构：{args.clinic}\n")
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            path.unlink(missing_ok=True)
            raise
    print(f"账号已创建，访问资料保存在 {path.resolve()}（仅本机用户可读）。")


if __name__ == "__main__":
    main()
