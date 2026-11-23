"""DELETE /me: withdrawal deletes the caller's own account, and only a signed-in caller's."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.deps import get_verifier_optional
from app.routers.me import get_admin_client
from tests.api.test_auth_quota import FakeVerifier

client = TestClient(app)


class _Query:
    def __init__(self, log: list) -> None:
        self.log = log

    def delete(self):
        return self

    def eq(self, col, value):
        self.log.append(("usage_deleted", col, value))
        return self

    def execute(self):
        return None


class FakeAdmin:
    def __init__(self, fail: bool = False) -> None:
        self.log: list = []
        self.fail = fail
        outer = self

        class _Admin:
            def delete_user(self, uid):
                if outer.fail:
                    raise RuntimeError("auth down")
                outer.log.append(("user_deleted", uid))

        class _Auth:
            admin = _Admin()

        self.auth = _Auth()

    def table(self, name):
        assert name == "usage_daily"
        return _Query(self.log)


@pytest.fixture(autouse=True)
def verifier() -> None:
    app.dependency_overrides[get_verifier_optional] = lambda: FakeVerifier()


def test_deletes_the_callers_own_account() -> None:
    admin = FakeAdmin()
    app.dependency_overrides[get_admin_client] = lambda: admin
    res = client.delete("/me", headers={"Authorization": "Bearer good"})
    assert res.status_code == 204
    assert admin.log == [("usage_deleted", "subject", "user:user-1"), ("user_deleted", "user-1")]


def test_a_guest_cannot_delete_anything() -> None:
    admin = FakeAdmin()
    app.dependency_overrides[get_admin_client] = lambda: admin
    assert client.delete("/me").status_code == 401
    assert client.delete("/me", headers={"Authorization": "Bearer forged"}).status_code == 401
    assert admin.log == []


def test_a_failed_deletion_says_so() -> None:
    app.dependency_overrides[get_admin_client] = lambda: FakeAdmin(fail=True)
    assert client.delete("/me", headers={"Authorization": "Bearer good"}).status_code == 502
