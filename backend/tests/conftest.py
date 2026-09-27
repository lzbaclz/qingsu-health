import os
import tempfile

os.environ["TIJI_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='tiji_test_')}/test.db"
os.environ["TIJI_LLM_PROVIDER"] = "mock"
os.environ["TIJI_MODE"] = "demo"
os.environ["TIJI_ENABLE_DEV"] = "0"
os.environ["TIJI_WORKER_INTERVAL"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db, session_scope  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _db():
    init_db()


@pytest.fixture()
def session():
    with session_scope() as s:
        yield s


@pytest.fixture(scope="session")
def client():
    from app.models import StaffAccount
    from app.security import hash_password
    with session_scope() as s:
        s.add(StaffAccount(username="test_doctor", display_name="测试医生", role="doctor",
                           clinic_id="clinic_demo", password_hash=hash_password("test-only-passphrase")))
        s.commit()
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": "test_doctor", "password": "test-only-passphrase"}).status_code == 200
        yield c
