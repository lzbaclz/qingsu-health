from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)


def init_db() -> None:
    from . import models  # noqa: F401  确保模型已注册

    SQLModel.metadata.create_all(engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """create_all 不会给已有表加列。原型阶段用这个补齐新增列，避免演示库因升级而报错。"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl_type = col.type.compile(dialect=engine.dialect)
                default = ""
                arg = getattr(col.default, "arg", None) if col.default is not None else None
                if isinstance(arg, bool):
                    default = f" DEFAULT {1 if arg else 0}"
                elif isinstance(arg, (int, float)):
                    default = f" DEFAULT {arg}"
                elif isinstance(arg, str):
                    default = " DEFAULT '" + arg.replace("'", "''") + "'"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}{default}'))
        if insp.has_table("task"):
            conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_task_dedupe_key ON task (dedupe_key)'))
        if insp.has_table("patient"):
            conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_clinic_code ON patient (clinic_id, display_code)'))


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
