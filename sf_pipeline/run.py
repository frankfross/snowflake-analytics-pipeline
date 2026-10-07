#!/usr/bin/env python3
"""Run the Snowflake analytics pipeline.

Executes versioned .sql files in order (setup -> load -> marts), then runs
the data-contract checks in 04_checks.sql, where any returned row is a
violation. Exits 1 if any check fails.

Usage:
    SNOWFLAKE_PASSWORD='...' python -m sf_pipeline.run --config config.yaml
    SNOWFLAKE_PASSWORD='...' python -m sf_pipeline.run --steps load,checks
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"

STEP_FILES = {
    "setup": ["01_setup.sql", "02_staging.sql"],
    "load": ["03_load_and_marts.sql"],
    "checks": ["04_checks.sql"],
}
REQUIRED_KEYS = ["account", "user", "warehouse", "database", "schema"]


class ConfigError(Exception):
    pass


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text())
    missing = [
        k for k in REQUIRED_KEYS if not cfg.get(k) or str(cfg.get(k)).startswith("<")
    ]
    if missing:
        raise ConfigError(f"{path}: fill in these values: {missing}")
    password = os.environ.get("SNOWFLAKE_PASSWORD") or cfg.get("password")
    if not password or str(password).startswith("<"):
        raise ConfigError("set the SNOWFLAKE_PASSWORD environment variable")
    cfg["password"] = password
    return cfg


def split_statements(text: str) -> list[str]:
    """Split SQL text on semicolons, dropping comments and empty chunks."""
    stmts = []
    for chunk in text.split(";"):
        lines = [ln for ln in chunk.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            stmts.append(stmt)
    return stmts


def parse_checks(text: str) -> list[tuple[str, str]]:
    """Split a checks file into (name, sql) pairs.

    The check name comes from the `-- comment` above each query; USE
    statements are skipped (session setup, not assertions).
    """
    checks: list[tuple[str, str]] = []
    name, buf = "unnamed check", []

    def flush():
        nonlocal name, buf
        sql = "\n".join(buf).strip().rstrip(";").strip()
        if sql and not sql.lstrip().upper().startswith("USE"):
            checks.append((name, sql))
        buf = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            label = stripped.lstrip("-").strip()
            if buf:
                flush()
            if label:
                name = label
        elif stripped:
            buf.append(line)
    flush()
    return checks


def run_step(cur, label: str, files: list[str]) -> int:
    """Execute every statement in the given SQL files. Returns statement count."""
    n = 0
    for fname in files:
        for stmt in split_statements((SQL_DIR / fname).read_text()):
            cur.execute(stmt)
            n += 1
    print(f"[step] {label:<10} OK ({n} statements)")
    return n


def run_checks(cur, checks: list[tuple[str, str]]) -> list[dict]:
    """Execute check queries; any returned row is a violation."""
    results = []
    for check_name, sql in checks:
        cur.execute(sql)
        rows = cur.fetchall()
        ok = len(rows) == 0
        mark = "PASS" if ok else "FAIL"
        print(f"[check] {check_name:<28} {mark} ({len(rows)} rows)")
        results.append(
            {"name": check_name, "passed": ok, "violations": len(rows),
             "sample": rows[:3]}
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Snowflake pipeline.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument(
        "--steps",
        default="setup,load,checks",
        help="comma-separated subset of: setup,load,checks",
    )
    args = parser.parse_args()

    try:
        cfg = load_config(Path(args.config))
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    import snowflake.connector  # imported here so tests don't need the driver

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    unknown = [s for s in steps if s not in STEP_FILES]
    if unknown:
        print(f"unknown steps: {unknown}", file=sys.stderr)
        return 2

    conn = snowflake.connector.connect(
        account=cfg["account"],
        user=cfg["user"],
        password=cfg["password"],
        warehouse=cfg["warehouse"],
        database=cfg["database"],
        schema=cfg["schema"],
        role=cfg.get("role"),
    )
    try:
        cur = conn.cursor()
        try:
            for step in steps:
                if step == "checks":
                    continue
                run_step(cur, step, STEP_FILES[step])
            failed = 0
            total = 0
            if "checks" in steps:
                results = run_checks(cur, parse_checks((SQL_DIR / "04_checks.sql").read_text()))
                total = len(results)
                failed = sum(not r["passed"] for r in results)
            if failed:
                print(f"pipeline FAILED: {failed}/{total} checks violated")
                return 1
            print(f"pipeline succeeded: {total}/{total} checks passed")
            return 0
        finally:
            cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
