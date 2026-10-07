"""Tests for the Snowflake pipeline runner (mocked connection — no Snowflake needed)."""
import pytest

from sf_pipeline.run import (
    ConfigError,
    load_config,
    parse_checks,
    run_checks,
    split_statements,
)


def test_split_statements_skips_comments_and_empties():
    sql = "-- a comment\nSELECT 1;\n\n-- another\nSELECT 2;"
    assert split_statements(sql) == ["SELECT 1", "SELECT 2"]


def test_parse_checks_names_queries_and_skips_use():
    text = (
        "-- header comment\n"
        "USE SCHEMA s;\n\n"
        "-- null keys\n"
        "SELECT a FROM t WHERE a IS NULL;\n\n"
        "-- duplicate keys\n"
        "SELECT a, COUNT(*) FROM t GROUP BY 1 HAVING COUNT(*) > 1;"
    )
    checks = parse_checks(text)
    assert [name for name, _ in checks] == ["null keys", "duplicate keys"]
    assert all("SELECT" in sql for _, sql in checks)


class FakeCursor:
    """Stands in for a Snowflake cursor; pops one result set per execute."""

    def __init__(self, result_sets):
        self.result_sets = list(result_sets)
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)

    def fetchall(self):
        return self.result_sets.pop(0)


def test_run_checks_pass_and_fail():
    cur = FakeCursor([[], [(1, 2), (1, 3)]])
    results = run_checks(cur, [("null keys", "SELECT ..."), ("dupes", "SELECT ...")])
    assert results[0]["passed"] and results[0]["violations"] == 0
    assert not results[1]["passed"] and results[1]["violations"] == 2
    assert len(cur.executed) == 2


def test_load_config_rejects_placeholders(tmp_path, monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "secret")
    p = tmp_path / "config.yaml"
    p.write_text("account: <fill>\nuser: u\nwarehouse: w\ndatabase: d\nschema: s\n")
    with pytest.raises(ConfigError):
        load_config(p)


def test_load_config_reads_password_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "secret")
    p = tmp_path / "config.yaml"
    p.write_text(
        "account: abc.us-east-1\nuser: frank\nwarehouse: WH\ndatabase: DB\nschema: S\n"
    )
    cfg = load_config(p)
    assert cfg["password"] == "secret"
    assert cfg["warehouse"] == "WH"


def test_load_config_requires_password(tmp_path, monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_PASSWORD", raising=False)
    p = tmp_path / "config.yaml"
    p.write_text(
        "account: abc.us-east-1\nuser: frank\nwarehouse: WH\ndatabase: DB\nschema: S\n"
    )
    with pytest.raises(ConfigError):
        load_config(p)
