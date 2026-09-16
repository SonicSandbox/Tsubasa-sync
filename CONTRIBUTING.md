# Contributing

Thanks for looking. This project has a few habits that are unusual enough to
be worth stating up front — they are not style preferences, they were each
paid for by a bug.

---

## The one rule everything else serves

> **A confidently wrong answer is worse than no answer.**

A subtitle written 0.4 s out is worse than one not written at all, because the
user stops looking. Refusal with a stated reason is a **feature**, and any
change that trades a refusal for a guess needs evidence, not an argument.

---

## Running the tests

```bash
python run_tests.py              # everything
python run_tests.py --list       # what would run, and what each suite covers
python run_tests.py -k pairing   # passes through to pytest
```

The runner enforces three things that a bare `pytest` does not:

- **A test not in the runner does not exist.** It enumerates every harness on
  disk and fails on any that is neither registered in `tsubasa.config.json`
  nor excused there in writing. Add a test file, register it.
- **Zero checks is a failure, not a pass.** Counts come from JUnit XML, not
  from regexing prose, because an empty suite also exits 0.
- **A tooling fault announces itself** with its own exit code, so "pytest
  isn't installed" can never be mistaken for "a test failed".

Some suites need a media corpus that is not in this repository. They **skip
with a reason** rather than failing; everything else runs anywhere.

---

## What a change should come with

**A feature ships with its test, in the same commit.** Not a follow-up.

Then, before you believe the test:

> **Break the fix and watch the test fail.** Restore it, watch it pass.

Thirty seconds, and it is the only thing separating *"the bug is gone"* from
*"the check never worked."* This project has a long record of green checks
sitting over live defects, and every one of them would have been caught by
that thirty seconds.

⭐ If you can make the check **mechanical** rather than a rule in a comment,
do. A comment saying *"remember to X"* is a rule you can forget; a check that
fails is not.

---

## Things that will get a change sent back

Each of these is a real defect this project shipped:

- **Asserting state instead of output.** *"The view is restored"* was green
  against a view restored completely empty. Ask the second question: and does
  it have anything in it?
- **A fixture that cannot show the failure.** An ASCII fixture cannot test an
  encoding rule. An empty string cannot test concatenation. A one-element list
  cannot test ordering. Ask what your fixture's value does to the *operator*
  under test.
- **A threshold set by taste.** Every constant here sits in a measured band
  with its population written beside it. A number without one is a guess with
  a decimal point.
- **Matching prose to make a decision.** `"11 confident, 1 refused"` contains
  the word `confident`. Read the field.
- **Deleting a user's file.** Trash only. This is not negotiable and there is
  a static check that enforces it.

---

## Style

- Python 3.10+, standard library and `numpy` for the library path. **A new
  hard dependency needs a reason** — the one-dependency install is a promise
  to everyone embedding this, and a test enforces it.
- Comments explain **why**, especially where the obvious thing is wrong. Most
  of the long comments in this codebase are a defect's headstone; if you find
  one that no longer applies, deleting it is a welcome change.
- Docstrings say what a function **returns** and what it will **never** do.

---

## Reporting a bug

The most useful report is **a filename and what you expected**. This project's
hardest problems are all naming problems, and a real filename is worth more
than a description of one.

If a subtitle synced wrongly, the single most useful thing is the output of:

```bash
tsubasa --verbose --dry-run /path/to/folder
```

`--dry-run` writes nothing, and `--verbose` includes the raw numbers the
default output deliberately hides — which is exactly what a diagnosis needs.

---

## Licence

By contributing you agree your work is licensed **GPL-3.0-or-later**, the same
as the project.
