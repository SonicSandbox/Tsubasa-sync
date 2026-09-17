# Anki Miner × tsubasa — integration scope

> **Status: PROPOSAL.** Not yet discussed with the Anki Miner maintainer.
>
> Written against **anki_miner `e63cb2d`** (main, 2026-09-15) and **tsubasa-sync 0.1.1**.
> Every Anki Miner file, function and signature named below was read from that commit — if
> their code has moved on, re-check section 9 before acting on anything here.

**In one paragraph:** Anki Miner pairs videos with subtitles by episode number alone, and its
own issue tracker shows where that breaks (#39, #80). Its Retime tool runs a chain of sync
engines. tsubasa does both jobs as a library: it pairs by **title and** episode — across
scripts, release groups and numbering schemes — and it aligns a subtitle against a reference
subtitle with a verdict that refuses rather than guesses. This document scopes two independent
integrations, **A (pairing)** and **B (a sync engine)**, names the one real conflict between the
two codebases, and lists exactly what to do and in what order.

- [0. What to do, in order](#0-what-to-do-in-order)
- [1. The problems this addresses](#1-the-problems-this-addresses)
- [2. tsubasa, in Anki Miner's terms](#2-tsubasa-in-anki-miners-terms)
- [3. Integration A — Batch Mining pairing](#3-integration-a--batch-mining-pairing)
- [4. Integration B — a sync engine in the Retime chain](#4-integration-b--a-sync-engine-in-the-retime-chain)
- [5. Anki Miner's project rules, and how this meets them](#5-anki-miners-project-rules-and-how-this-meets-them)
- [6. Decisions that belong to the maintainer](#6-decisions-that-belong-to-the-maintainer)
- [7. The issue to post](#7-the-issue-to-post)
- [8. After the maintainer answers](#8-after-the-maintainer-answers)
- [9. Facts checked, with locations](#9-facts-checked-with-locations)

---

## 0. What to do, in order

1. **Post the issue in section 7** on `github.com/0xzerolight/anki_miner` using the
   *Feature request* template. Link this document in it.
2. **Wait for the maintainer's answer. Do not open a pull request first.** This adds a
   dependency and touches a design decision they made in public (#39) — both are theirs to rule.
3. **When they answer, follow section 8** for the branch they chose (A, B, both, or neither).
4. **Before any code:** agree decisions D1–D5 (section 6) with them in the issue thread.
5. **Build to their workflow** (section 5): fork, a `feat/...` branch, one feature per PR,
   `black` + `ruff` + `mypy anki_miner`, the full pytest marker expression, a `CHANGELOG.md`
   entry, and translation catalogs if any UI string changes.
6. **Say in the PR that the work was AI-assisted.** Their contributing guide has no policy on
   it; saying so up front is the respectful default.
7. **Expect them to reshape it.** Their pattern with outside feature PRs is to rebase, fix and
   land the work through their own commits, then close the PR (#114, #115). That is a merge.

---

## 1. The problems this addresses

### Pairing (Batch Mining)

`EpisodeMatcher.match_by_episode_number` pairs **on the episode number alone** (season too when
both names carry one). Two reports show the limits:

| Issue | What happened | Maintainer's reply |
| --- | --- | --- |
| **#39** | A folder holding several shows paired subtitles to the wrong show's videos | *"Episode-matching is done by number, so it's assumed that the user mines only 1 anime series per video/subtitle folder pair … Adding name-matching is technically possible but would be rather messy in the code."* — documented as a constraint instead |
| **#80** | *"video of episode 03 got paired with subs from episode 36 and vice versa"* | *"I'll look into the pairing logic."* |

tsubasa's pairing is exactly the name-matching #39 calls messy, kept **outside** Anki Miner's code.

⚠ **#80's filenames are only in a screenshot**, so this document does **not** claim tsubasa fixes
#80. Ask the reporter for the two names and add them as a test before claiming it.

### Syncing (Utilities → Retime)

Retime tries ffsubsync (split) → alass (split) → alass (single offset) → ffsubsync (single
offset), and a validator decides. tsubasa would be one more engine for the case where the
reference is a **subtitle** (an embedded text track Anki Miner has extracted).

---

## 2. tsubasa, in Anki Miner's terms

| Concern | Answer |
| --- | --- |
| Install | `pip install tsubasa-sync` — imports as `tsubasa` |
| Licence | GPL-3.0-or-later — the same as Anki Miner |
| Python | 3.10–3.13, tested on Windows, macOS and Linux (Anki Miner needs 3.11+) |
| Hard dependencies | **numpy only** |
| Wheel size | ~4.7 MB, most of it the bundled alias table (Wikidata, CC0) |
| **ffmpeg** | **Not needed for either integration here.** `scan()` reads filenames only; `sync_to_reference()` and `render()` read subtitle files only |
| **PyInstaller** | **Nothing to configure.** tsubasa ships a hook under the `pyinstaller40` entry point, so Anki Miner's existing `anki_miner.spec` collects its data automatically. Verified by building a real frozen app |
| Checking a frozen build | `tsubasa.self_check().ok` — see section 5 |
| Threads / global state | None started. No results database or trash is touched by the calls this document uses |
| Documentation | [`docs/USAGE.md`](../USAGE.md) |

---

## 3. Integration A — Batch Mining pairing

### 3.1 Where it plugs in

`anki_miner/utils/file_pairing.py`:

```python
class FilePairMatcher:
    @staticmethod
    def find_pairs_by_episode_number(
        video_folder: Path, subtitle_folder: Path,
        video_extensions=None, subtitle_extensions=None,
        prefer_retimed: bool = True, *, secondary_folder: Path | None = None,
    ) -> list[FilePair]: ...
```

It lists both folders **non-recursively** (`iterdir`), skips junk (`is_junk_path`), sorts, and
calls `EpisodeMatcher.match_by_episode_number(videos, subtitles)` in
`anki_miner/utils/episode_matcher.py`, which consumes each subtitle once.

### 3.2 What the tsubasa-backed version does

Same inputs, same output type (`list[FilePair]`), so no caller changes:

```python
# anki_miner/utils/tsubasa_pairing.py — sketch
from pathlib import Path

from anki_miner.utils.file_pairing import FilePair, FilePairMatcher, RETIMED_SUFFIX


def find_pairs_with_tsubasa(video_folder: Path, subtitle_folder: Path, *,
                            prefer_retimed: bool = True) -> list[FilePair]:
    import tsubasa

    scan = tsubasa.scan(videos=video_folder, subs=subtitle_folder, recurse=False)
    video_exts = FilePairMatcher.VIDEO_EXTENSIONS
    subtitle_exts = FilePairMatcher.SUBTITLE_EXTENSIONS

    used: set[Path] = set()
    pairs: list[tuple[float, FilePair]] = []
    for video, candidates in scan.pairings():            # candidates: best first
        video_path = Path(video.path)
        if video_path.suffix.lower() not in video_exts:
            continue
        allowed = [
            c for c in candidates
            if Path(c.subtitle.path).suffix.lower() in subtitle_exts
            and c.identity != "different"                  # never another show
            and Path(c.subtitle.path) not in used          # a subtitle is used once
        ]
        # "same" before "unsure"; a _retimed file first when asked; a stable sort
        # keeps tsubasa's own ranking inside each group.
        allowed.sort(key=lambda c: (
            c.identity != "same",
            not (prefer_retimed and Path(c.subtitle.path).stem.endswith(RETIMED_SUFFIX)),
        ))
        if allowed:
            chosen = Path(allowed[0].subtitle.path)
            used.add(chosen)
            pairs.append((video.episode or 0, FilePair(video_path, chosen)))

    pairs.sort(key=lambda p: p[0])
    return [pair for _episode, pair in pairs]
```

### 3.3 Behaviour rules, and why

| Rule | Why |
| --- | --- |
| **Never pair `identity == "different"`** | This is the #39 fix: a subtitle whose title names another show is never used |
| **Accept `"unsure"` after `"same"`** | A folder of `05.mkv` / `05.srt` has no titles to compare. Refusing `unsure` would stop pairings that work today |
| **Each subtitle used once** | The same rule `EpisodeMatcher` already has, for the same reason |
| **Their extension sets, not tsubasa's** | tsubasa discovers more formats than Anki Miner mines; filtering keeps today's behaviour |
| **`recurse=False`** | Matches `iterdir` — today's behaviour |
| **`prefer_retimed` honoured** | Their `RETIMED_SUFFIX` rule: a `_retimed` subtitle outranks its off-timed original |
| **Season and episode are both respected** | tsubasa never pairs *S1E3* with *S3E3*; `video.season` / `video.episode` are available if a caller needs them |

### 3.4 What could regress, and the guard

| Risk | Guard |
| --- | --- |
| A folder that pairs today stops pairing | Accepting `unsure` (above). Test: every existing pairing test passes unchanged against the tsubasa matcher |
| A subtitle carrying no title is ranked differently | Covered by the same existing tests |
| tsubasa not installed | Keep `EpisodeMatcher` as the fallback when `import tsubasa` fails — decision D2 |
| Performance on large folders | `scan()` opens no files. It loads a 4 MB alias table once per process |

### 3.5 Tests to add

- **#39 as a test:** two shows' episodes 01–03 in one folder, subtitles for both → every video
  gets its own show's subtitle.
- **#80 as a test**, once the reporter supplies the filenames.
- **Cross-script:** `[NanakoRaws] Yomi no Tsugai S01E18 (AT-X TV 1080p HEVC AAC).mkv` pairs with
  `黄泉のツガイ.S01E18.WEBRip.ABEMA.ja[cc].srt`.
- **No-title folder:** `05.mkv` / `05.srt` still pairs (`unsure` accepted).
- **`prefer_retimed`:** with `EP01.srt` and `EP01_retimed.srt`, the retimed one is chosen.
- **Fallback:** with tsubasa absent (patched import), `EpisodeMatcher` is used.

---

## 4. Integration B — a sync engine in the Retime chain

### 4.1 The contract, as Anki Miner defines it

`anki_miner/services/subtitle_retimer.py` → `retime_subtitle(config, video, in_sub, out_sub, *,
reference_override, cancel_event, log_cb) -> RetimeOutcome`:

1. `resolve_reference(...)` picks the reference: an **embedded subtitle stream, extracted to a
   temp file** (`kind == "subtitle"`), or audio.
2. `clean_for_alignment(in_sub, …)` may strip non-dialogue lines; the engine then aligns that
   cleaned file, and `map_deltas_back(in_sub, candidate, kept_indices, mapped)` carries the
   timing back to the full file.
3. Each engine is a **runner** `runner(reference_path, align_input, candidate_path, log_cb) ->
   SyncResult` that writes its candidate file.
4. `validate_candidate(in_sub, candidate, result, video_duration_seconds=...)` accepts or
   rejects; `_commit(candidate, out_sub)` moves an accepted one into place.
5. **Engines never raise for content reasons** and never judge their own output — the validator
   does.

`SyncResult` (`anki_miner/services/sync_engines/__init__.py`): `ok`, `engine`, `offset_seconds`,
`framerate_scale`, `block_shifts_seconds`, `warnings`, `detail`.

### 4.2 🚨 The one real conflict: cue counts

`validate_candidate` rejects any candidate whose **cue count differs** from the original:

```python
if len(cand_events) != len(orig_events):
    reasons.append(f"cue count changed: {len(orig_events)} -> {len(cand_events)}")
```

`tsubasa.render()` **deliberately removes** a line that falls inside a stretch a broadcast cut
removed (`dropped_in_gap`), or one that would end before the video starts
(`dropped_before_zero`). Those are the only two removals it ever makes, and it counts both.
For a cut file — exactly where tsubasa is strongest — Anki Miner's validator would reject
tsubasa's result.

| Option | What changes | Cost |
| --- | --- | --- |
| **B1. The engine declines a file with any removal** — returns `ok=False` with a reason, and the chain moves on to ffsubsync / alass | Nothing in Anki Miner's validator | tsubasa handles only uncut files. Cut files go to the engines that handle them today |
| **B2. The validator accepts removals an engine declares** — e.g. a `dropped` count on `SyncResult`, allowed when it equals the difference | A small change to `validate_candidate` and `SyncResult` | Anki Miner accepts removed cues for the first time — their call |
| B3. tsubasa keeps every cue | Nothing on either side | ❌ Not recommended: a line inside a removed stretch has no right time, and keeping it puts the file out of order, which the same validator rejects |

**Recommendation: B1 for the first PR** — no change to Anki Miner's validator, and every result
tsubasa hands over passes it. B2 as a follow-up if the maintainer wants tsubasa on cut files.

### 4.3 The engine (sketch, option B1)

```python
# anki_miner/services/sync_engines/tsubasa_engine.py — sketch
from pathlib import Path

from anki_miner.services.sync_engines import SyncResult


def sync_with_tsubasa(config, reference: Path, in_sub: Path, out: Path, *,
                      sub_reference: bool, cancel_event=None, log_cb=None) -> SyncResult:
    engine = "tsubasa"
    if cancel_event is not None and cancel_event.is_set():
        return SyncResult(ok=False, engine=engine, detail="cancelled")
    if not sub_reference:
        return SyncResult(ok=False, engine=engine,
                          detail="aligns against subtitle cues; the reference is audio")
    try:
        import tsubasa
    except ImportError:
        return SyncResult(ok=False, engine=engine, detail="tsubasa is not installed")

    try:
        result = tsubasa.sync_to_reference(in_sub, reference)   # never writes
        if result.outcome != "CONFIDENT":
            return SyncResult(ok=False, engine=engine, detail=result.reason)
        rendered = tsubasa.render(result)                      # bytes, original encoding
    except (OSError, ValueError) as exc:                       # never raise for content
        return SyncResult(ok=False, engine=engine, detail=f"{type(exc).__name__}: {exc}")

    removed = rendered.dropped_in_gap + rendered.dropped_before_zero
    if removed:                                                # option B1
        return SyncResult(ok=False, engine=engine,
                          detail=f"{removed} line(s) fall inside a cut; left to the next engine")

    out.write_bytes(rendered.data)
    shifts = tuple(offset for _until, offset in result.segments)
    return SyncResult(
        ok=True, engine=engine,
        offset_seconds=result.offset,
        block_shifts_seconds=shifts if len(shifts) > 1 else (),
        detail=f"{result.match_percent}% match, {result.verdict_word}",
    )
```

Wiring, in `_engine_chain` — the existing runners and yields stay as they are:

```python
def _engine_chain(config, *, sub_reference: bool, cancel_event):
    def run_tsubasa(reference, in_sub, out, log_cb):
        return sync_with_tsubasa(config, reference, in_sub, out,
                                 sub_reference=sub_reference,
                                 cancel_event=cancel_event, log_cb=log_cb)

    # ... the existing run_ffsubsync / run_alass_* definitions, unchanged ...

    yield "tsubasa", run_tsubasa          # first, or last — decision D3
    yield "ffsubsync", run_ffsubsync
    yield "alass", run_alass_split
    yield "alass (single offset)", run_alass_offset
    yield "ffsubsync (single offset)", run_ffsubsync_offset
```

What tsubasa's `Result` carries that the log should keep: `reason` (never empty when not
CONFIDENT), `match_percent`, `verdict_word`, `segments`, `reference`, `notes`.

⚠ **A partial reference is refused.** If the extracted track covers only part of the subtitle,
tsubasa returns REFUSED — a cut in the uncovered part would be invisible. That is a normal
`ok=False` here, and the chain moves on.

### 4.4 Where in the chain

**Recommendation: first, when the reference is a subtitle.** It costs one alignment (typically
well under a second), it refuses rather than guessing, and a refusal simply falls through to the
engines that run today. The maintainer may prefer it last, as a fallback — decision D3.

### 4.5 In-process or a supervised child

ffsubsync runs as a supervised child (`--ffsubsync-child`) because a stuck alignment once took
the app's thread with it. tsubasa is pure Python plus numpy with no known hang modes, and the
two calls above are short. **Recommendation: in-process**, cancellation checked before the
call. If the maintainer wants every engine in a child for uniformity, the pattern in
`_ffsubsync_child.py` applies directly: a small child `main` that calls the two functions above
and writes one JSON line to fd 1 — decision D4.

### 4.6 Tests to add

- Shifted subtitle vs extracted reference → `ok=True`, `offset_seconds` within 50 ms, and the
  candidate passes `validate_candidate`.
- Audio reference → `ok=False` with the reason, and the chain continues.
- An unrelated reference → `ok=False` (REFUSED reason).
- A cut file → `ok=False` under option B1, and the next engine is tried.
- A Shift-JIS subtitle comes back in Shift-JIS.
- tsubasa not importable → `ok=False`, no exception.

---

## 5. Anki Miner's project rules, and how this meets them

| Their rule (CONTRIBUTING.md) | How this meets it |
| --- | --- |
| **"No new config"** — *the locked rule for the whole project* | Neither integration adds a setting. Pairing is automatic; the engine is a place in the chain |
| **One feature per PR** | A and B are separate PRs |
| **black (120) · ruff · mypy on `anki_miner/`** | tsubasa ships no type information. Add `"tsubasa.*"` to the existing `[[tool.mypy.overrides]]` list next to `"ffsubsync.*"` |
| **Tests:** `pytest -m "not youtube and not asr and not e2e and not golden"` | Spell out that full marker expression — bare `pytest` is not their gate |
| **Logging contract:** operation, subject, exception type and message; use the choke points | Engine outcomes through `log_summary`, the same way `alass_engine.py` logs; never a fresh `logger.info` |
| **`suppressed()` is the only sanctioned broad swallow** | The engine sketch catches `OSError` and `ValueError` only, which their ratchet does not count |
| **Translations** for any user-facing string | Engine names and reasons appear in the Retime log — check whether that log is translated (`QCoreApplication.translate` is used next to it) |
| **`CHANGELOG.md`** under `## [Unreleased]`, written for users | One entry per PR |
| **README edits** must update every `i18n/README.<code>.md` | Avoid touching the README in these PRs |

**Frozen builds.** Nothing to add to `anki_miner.spec`: PyInstaller finds tsubasa's hook itself.
To prove it in their existing smoke test (`scripts/bundle_smoke.sh`, modes chosen by
`ANKI_MINER_SMOKE=<mode>`), a `tsubasa` mode need only do:

```python
import tsubasa
check = tsubasa.self_check()
if not check.ok:
    raise SystemExit("tsubasa: " + "; ".join(check.problems))
print("BUNDLED_SMOKE_PASS")
```

Without its data, tsubasa still runs but pairs far fewer files by name, and says nothing — this
check is what makes that visible.

---

## 6. Decisions that belong to the maintainer

| # | Decision | Options | Suggested |
| --- | --- | --- | --- |
| **D1** | How tsubasa is depended on | a core dependency, or an extra (`anki-miner[tsubasa]`) | An extra first; core once it has earned it |
| **D2** | Pairing when tsubasa is present | replace `EpisodeMatcher`, or use tsubasa and keep `EpisodeMatcher` as the fallback | Keep the fallback |
| **D3** | Where the engine sits | first for subtitle references, or last | First |
| **D4** | How the engine runs | in-process, or a supervised child | In-process |
| **D5** | The cue-count conflict | B1 (decline files with removals) or B2 (validator accepts declared removals) | B1 now, B2 later if wanted |

Both projects are GPL-3.0-or-later, so licensing needs no decision.

---

## 7. The issue to post

Use the **Feature request** template. Paste into its fields:

**Problem / use case**

> Batch Mining pairs by episode number, which the README and #39 note assumes one series per
> folder — mixed folders mis-pair (#39), and #80 shows a numbering mix-up. Adding name-matching
> inside Anki Miner was described in #39 as messy. Separately, Retime's engine chain has no
> engine that aligns a subtitle directly against an extracted subtitle track with a strict
> accept/refuse verdict.

**Proposed solution**

> I maintain **tsubasa** (`pip install tsubasa-sync`, GPL-3.0-or-later,
> https://github.com/SonicSandbox/Tsubasa-sync), a library that pairs subtitles to videos by
> title **and** episode — across Japanese/English titles, release groups and per-season vs
> absolute numbering — and retimes a subtitle against another subtitle, refusing rather than
> guessing when the evidence is weak. It depends only on numpy, ships its own PyInstaller hook,
> and adds no setting.
>
> I've written a full scope of how it could plug into Anki Miner — two independent pieces
> (pairing and a sync engine), the one conflict with your validator (cue counts) and the options
> for it, and the decisions that would be yours:
> https://github.com/SonicSandbox/Tsubasa-sync/blob/main/docs/integrations/anki-miner.md
>
> Would either piece be welcome? If so I'm happy to open a PR for whichever you prefer, or to
> answer questions first. And if it isn't a fit, no problem at all.

**Additional context**

> Disclosure: I'm tsubasa's author, and it was built with substantial AI assistance.

---

## 8. After the maintainer answers

| Answer | Next steps |
| --- | --- |
| **"Yes to pairing (A)"** | Agree D1, D2 in the thread → fork → `feat/tsubasa-pairing` → section 3 code + 3.5 tests → add `"tsubasa.*"` to mypy overrides → CHANGELOG → run their gate → PR referencing the issue, #39 and #80 |
| **"Yes to the engine (B)"** | Agree D1, D3, D4, D5 → `feat/tsubasa-sync-engine` → section 4 code + 4.6 tests → CHANGELOG → gate → PR |
| **"Yes to both"** | Pairing first — it answers open issues and needs no validator decision — then the engine as a second PR |
| **"They'd rather wire it themselves"** | Point them at this document and [`docs/USAGE.md`](../USAGE.md); offer to answer API questions in the thread |
| **"Not a fit"** | Thank them and close the issue. Nothing else to do |

---

## 9. Facts checked, with locations

All at anki_miner `e63cb2d`.

| Fact | Where |
| --- | --- |
| Pairing entry point `FilePairMatcher.find_pairs_by_episode_number(...) -> list[FilePair]`, non-recursive, junk-filtered | `anki_miner/utils/file_pairing.py` |
| `RETIMED_SUFFIX = "_retimed"`; retimed detection is `path.stem.casefold().endswith("_retimed")` | same file |
| Number-only matching, subtitle consumed once, season respected when both have one | `anki_miner/utils/episode_matcher.py`, `EpisodeMatcher.match_by_episode_number` |
| `retime_subtitle(config, video, in_sub, out_sub, *, reference_override, cancel_event, log_cb) -> RetimeOutcome` | `anki_miner/services/subtitle_retimer.py` |
| Engine order: ffsubsync → alass → alass (single offset) → ffsubsync (single offset) | same file, `_engine_chain` |
| Runner signature `(reference, in_sub, out, log_cb) -> SyncResult` | same file |
| `SyncResult` fields | `anki_miner/services/sync_engines/__init__.py` |
| Validator rejects a changed cue count, shifts over 5 min, scrambled order, cues past the end, span ratio outside 0.8–1.25 | `anki_miner/services/sync_validator.py`, `validate_candidate` |
| ffsubsync runs as a child re-entering the app with `--ffsubsync-child`, one JSON line on fd 1 | `anki_miner/services/sync_engines/_ffsubsync_child.py`, `anki_miner/gui/launch.py` |
| Reference kinds `subtitle` / `audio`; subtitle streams extracted to a temp file | `anki_miner/services/retime_reference.py` |
| ffmpeg resolution: config override → bundled → PATH | `anki_miner/utils/ffmpeg_resolver.py` |
| mypy overrides include `"ffsubsync.*"` with `ignore_missing_imports = true` | `pyproject.toml` |
| PyInstaller build, `hookspath` pointing at their own hooks folder | `anki_miner.spec` |
| Contribution rules quoted in section 5 | `CONTRIBUTING.md`, `.github/pull_request_template.md` |
| #39 and #80 text and replies; #114/#115 landed by the maintainer's own rebase | the issues and PRs of those numbers |
