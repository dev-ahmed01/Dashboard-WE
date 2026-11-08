"""Contract tests: readiness must fail closed on database/schema/storage faults."""
import pytest
from fastapi import HTTPException

from app import main


class FakeResult:
    def __init__(self, revisions):
        self.revisions = revisions

    def scalars(self):
        return iter(self.revisions)


class FakeSession:
    def __init__(self, revisions=None, fail=False):
        self.revisions = revisions if revisions is not None else ["revision-1"]
        self.fail = fail

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement):
        if self.fail:
            raise RuntimeError("database credentials must not be revealed")
        if "alembic_version" in str(statement):
            return FakeResult(self.revisions)
        return FakeResult([])


class FakeStore:
    bucket = "test-bucket"

    def __init__(self, fail=False):
        self.fail = fail

    @property
    def client(self):
        return self

    def head_bucket(self, Bucket):
        assert Bucket == self.bucket
        if self.fail:
            raise RuntimeError("storage credentials must not be revealed")


def test_readiness_checks_schema_and_bucket(monkeypatch):
    monkeypatch.setattr(main, "_migration_heads", lambda: {"revision-1"})
    monkeypatch.setattr(main, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(main, "ObjectStore", lambda: FakeStore())
    assert main.readiness() == {"status": "ready"}


@pytest.mark.parametrize("failure", ["db", "schema", "storage"])
def test_readiness_fails_closed_without_leaking_details(monkeypatch, failure):
    monkeypatch.setattr(main, "_migration_heads", lambda: {"revision-1"})
    monkeypatch.setattr(
        main, "SessionLocal",
        lambda: FakeSession(revisions=["wrong"] if failure == "schema" else None,
                            fail=failure == "db"),
    )
    monkeypatch.setattr(main, "ObjectStore", lambda: FakeStore(fail=failure == "storage"))
    with pytest.raises(HTTPException) as exc:
        main.readiness()
    assert exc.value.status_code == 503
    assert exc.value.detail == "Service unavailable"
