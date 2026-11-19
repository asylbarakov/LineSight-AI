from sqlalchemy.dialects import postgresql
from sqlalchemy import CheckConstraint
from sqlalchemy.schema import CreateTable

from app.models import Base


def test_expected_tables_exist():
    assert set(Base.metadata.tables) == {
        "inspections",
        "videos",
        "jobs",
        "findings",
    }


def test_relationship_keys_exist():
    videos = Base.metadata.tables["videos"]
    jobs = Base.metadata.tables["jobs"]
    findings = Base.metadata.tables["findings"]

    assert {
        fk.target_fullname for fk in videos.foreign_keys
    } == {"inspections.id"}

    assert {
        fk.target_fullname for fk in jobs.foreign_keys
    } == {"inspections.id"}

    assert {
        fk.target_fullname for fk in findings.foreign_keys
    } == {"jobs.id"}


def test_postgresql_ddl_compiles():
    dialect = postgresql.dialect()

    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in sql


def test_job_runtime_columns():
    jobs = Base.metadata.tables["jobs"]

    expected = {
        "attempt_count",
        "lease_token",
        "heartbeat_at",
        "model_name",
        "model_version",
    }

    assert expected.issubset(jobs.columns.keys())

    assert jobs.c.attempt_count.nullable is False
    assert jobs.c.lease_token.nullable is True


def test_finding_frame_index():
    findings = Base.metadata.tables["findings"]

    assert "frame_index" in findings.columns
    assert findings.c.frame_index.nullable is True

    names = {
        constraint.name
        for constraint in findings.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_findings_frame_index" in names
