# -*- coding: utf-8 -*-
"""
The runner's own guarantees.

⭐ The runner is what makes "a test not in the runner does not exist" real, so
it is the one piece of this project that cannot be checked by the thing it
checks.  Everything here drives run_tests.py's real functions against synthetic
inputs -- never against the live config, which would only prove that today's
config happens to be tidy.

Each check asks doctrine/verification.md's question: if the mechanism under
test were deleted and the state around it stayed as it is, would this still
pass?
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import run_tests  # noqa: E402


def _cfg(suites, excused=None, harness_dir="tests"):
    return {
        "test": {
            "harnessDir": harness_dir,
            "harnessPattern": r"^test_.*\.py$",
            "runLogDir": "_runs",
            "suites": suites,
            "excused": excused or {},
        }
    }


# --------------------------------------------------------------------------
# orphan detection -- the rule that did not hold as prose
# --------------------------------------------------------------------------

def test_an_unregistered_harness_is_an_orphan(monkeypatch, tmp_path):
    """A build that had written this rule down still ENDED with four orphans."""
    harness = tmp_path / "tests"
    harness.mkdir()
    (harness / "test_alpha.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (harness / "test_beta.py").write_text("def test_b(): pass\n", encoding="utf-8")
    monkeypatch.setattr(run_tests, "HERE", tmp_path)

    cfg = _cfg([{"name": "only-alpha", "cmd": ["-m", "pytest", "tests/test_alpha.py"]}])
    found, orphans, missing, _excused = run_tests.self_check(cfg)

    assert len(found) == 2
    assert [o.name for o in orphans] == ["test_beta.py"]
    assert not missing


def test_a_registered_harness_is_not_an_orphan(monkeypatch, tmp_path):
    harness = tmp_path / "tests"
    harness.mkdir()
    (harness / "test_alpha.py").write_text("def test_a(): pass\n", encoding="utf-8")
    monkeypatch.setattr(run_tests, "HERE", tmp_path)

    cfg = _cfg([{"name": "alpha", "cmd": ["-m", "pytest", "tests/test_alpha.py"]}])
    _found, orphans, _missing, _excused = run_tests.self_check(cfg)
    assert orphans == []


def test_a_whole_directory_registration_covers_every_harness(monkeypatch, tmp_path):
    harness = tmp_path / "tests"
    harness.mkdir()
    for name in ("test_a.py", "test_b.py", "test_c.py"):
        (harness / name).write_text("def test_x(): pass\n", encoding="utf-8")
    monkeypatch.setattr(run_tests, "HERE", tmp_path)

    cfg = _cfg([{"name": "all", "cmd": ["-m", "pytest", "tests"]}])
    found, orphans, _missing, _excused = run_tests.self_check(cfg)
    assert len(found) == 3 and orphans == []


def test_an_excused_harness_is_not_an_orphan(monkeypatch, tmp_path):
    harness = tmp_path / "tests"
    harness.mkdir()
    (harness / "test_probe.py").write_text("def test_p(): pass\n", encoding="utf-8")
    monkeypatch.setattr(run_tests, "HERE", tmp_path)

    cfg = _cfg([], excused={"test_probe.py": "one-off probe; run by hand"})
    _found, orphans, _missing, _excused = run_tests.self_check(cfg)
    assert orphans == []


def test_a_suite_naming_a_missing_harness_is_reported(monkeypatch, tmp_path):
    """A typo in a suite's path silently registers nothing and covers nothing --
    which then reads as 'no orphans' rather than as a broken suite."""
    (tmp_path / "tests").mkdir()
    monkeypatch.setattr(run_tests, "HERE", tmp_path)

    cfg = _cfg([{"name": "typo", "cmd": ["-m", "pytest", "tests/test_ghost.py"]}])
    _found, _orphans, missing, _excused = run_tests.self_check(cfg)
    assert missing == [("typo", "tests/test_ghost.py")]


# --------------------------------------------------------------------------
# counting -- zero checks is a failure, not a pass
# --------------------------------------------------------------------------

def _junit(tmp_path, body):
    p = tmp_path / "r.xml"
    p.write_text(body, encoding="utf-8")
    return p


def test_junit_counts_are_read_not_guessed(tmp_path):
    p = _junit(tmp_path, '<testsuite tests="17" failures="0" errors="0" skipped="2"/>')
    assert run_tests.parse_junit(p) == (17, 0, 0, 2)


def test_junit_sums_nested_suites(tmp_path):
    p = _junit(tmp_path,
               '<testsuites>'
               '<testsuite tests="3" failures="1" errors="0" skipped="0"/>'
               '<testsuite tests="4" failures="0" errors="2" skipped="1"/>'
               '</testsuites>')
    assert run_tests.parse_junit(p) == (7, 1, 2, 1)


def test_a_missing_report_is_not_a_zero(tmp_path):
    """None and 0 must not collapse: 'the suite reported nothing' and 'the
    suite ran nothing' have different fixes, and only one is a harness bug."""
    assert run_tests.parse_junit(tmp_path / "absent.xml") is None


def test_a_corrupt_report_is_not_a_zero(tmp_path):
    p = _junit(tmp_path, "<testsuite tests=")
    assert run_tests.parse_junit(p) is None


def test_zero_collected_is_visible_in_the_counts(tmp_path):
    p = _junit(tmp_path, '<testsuite tests="0" failures="0" errors="0" skipped="0"/>')
    total, _f, _e, _s = run_tests.parse_junit(p)
    assert total == 0, "the runner turns this into a TOOLING verdict, not a pass"


# --------------------------------------------------------------------------
# tooling faults announce themselves
# --------------------------------------------------------------------------

def test_pytest_tooling_codes_are_not_treated_as_failures():
    """The oracle's own runner reported a missing pytest as 'corpus 1' --
    indistinguishable from one failing test. Four wrong diagnoses came from
    that confusion."""
    for code in (2, 3, 4, 5):
        assert code in run_tests.PYTEST_TOOLING_CODES
    assert 1 not in run_tests.PYTEST_TOOLING_CODES
    assert 0 not in run_tests.PYTEST_TOOLING_CODES


def test_exit_codes_are_distinct():
    codes = {run_tests.EXIT_OK, run_tests.EXIT_FAILED,
             run_tests.EXIT_TOOLING, run_tests.EXIT_ORPHAN}
    assert len(codes) == 4


# --------------------------------------------------------------------------
# the lock -- two runners at once read exactly like a regression
# --------------------------------------------------------------------------

def test_the_lock_refuses_a_second_run(tmp_path):
    lock = tmp_path / ".run.lock"
    with run_tests.RunLock(lock):
        assert lock.exists()
        with pytest.raises(SystemExit) as exc:
            with run_tests.RunLock(lock):
                pass
        assert exc.value.code == run_tests.EXIT_TOOLING
    assert not lock.exists(), "the lock outlived its run and will block the next one"


def test_the_lock_is_released_when_the_run_raises(tmp_path):
    lock = tmp_path / ".run.lock"
    with pytest.raises(ValueError):
        with run_tests.RunLock(lock):
            raise ValueError("boom")
    assert not lock.exists()
