# -*- coding: utf-8 -*-
"""
Step 3i -- `tsubasa.place_subtitle()`: put a subtitle beside a video UNTOUCHED AND UNTIMED,
for hato's LAYER 15 (signed off by Sonic 2026-09-26): a video with no subtitle track has
nothing to time against, and hato's opt-in road places a subtitle chosen by its name.

🚨 NEVER CONVERTED. Every check that says so compares BYTES, and the text is Japanese built
from LITERALS -- an ASCII fixture cannot test an encoding rule (`LEDGER-HOT.md`).

⭐ And the two writer fixes hato's 14z pass left for this release, through BOTH callers of
the one writer (`place_subtitle` and `extract_subtitle(write=True)`):
  A-1  a folder that denies a new file made `tempfile.mkstemp` spin for DAYS on Windows --
       it reads ACCESS_DENIED as "that name is taken". Now it fails at once.
  C3   the writer looked, then REPLACED -- a file landing between was overwritten. Now the
       file appears in one step that refuses a name already taken.
"""
import os
import subprocess
import sys
import textwrap

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tsubasa                                             # noqa: E402
from tsubasa import place_subtitle                         # noqa: E402
from tsubasa import paths as P                             # noqa: E402
from tsubasa import place as PLACE                         # noqa: E402

#: ⚠ FROM LITERALS -- see the module docstring.
JA_SRT = (u"1\r\n00:00:01,000 --> 00:00:03,500\r\n葬送のフリーレン\r\n\r\n"
          u"2\r\n00:00:04,000 --> 00:00:06,500\r\n「ありがとう、ヒンメル」\r\n\r\n"
          u"3\r\n00:00:07,000 --> 00:00:09,500\r\nＯＰ：晴る…\r\n\r\n")
#: A Shift-JIS body: re-encoded to UTF-8 anywhere on the way, the bytes change.
SJIS = JA_SRT.encode("cp932")
VIDEO = b"\x1a\x45\xdf\xa3" + b"\x00" * 64            # never read: only its NAME matters


def _video(folder, name=u"[NanakoRaws] Seihantai na Kimi to Boku - 01 (TBS 1080p HEVC AAC).mkv"):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(VIDEO)
    return path


def _sub(folder, name=u"[NanakoRaws] Seihantai na Kimi to Boku - 01 (TBS 1080p HEVC AAC).ja.ass",
         data=None):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(JA_SRT.encode("utf-8") if data is None else data)
    return path


def _listing(folder):
    return sorted(p.name for p in folder.iterdir())


# ---------------------------------------------------------------------------
# placing
# ---------------------------------------------------------------------------

def test_it_places_the_subtitle_beside_the_video_byte_for_byte(tmp_path):
    u"""⭐ The whole point: the subtitle's own bytes, under the video's name, readable back
    as Japanese -- and nothing else left in the folder. A Shift-JIS body proves nothing
    was decoded on the way."""
    media, cache = tmp_path / u"media", tmp_path / u"cache"
    video = _video(media)
    sub = _sub(cache, data=SJIS)
    got = place_subtitle(video, sub, write=True)
    assert got.ok and not got.write_failed, got
    want = media / u"[NanakoRaws] Seihantai na Kimi to Boku - 01 (TBS 1080p HEVC AAC).ja.ass"
    assert got.output_path == str(want), got.output_path
    assert want.read_bytes() == SJIS, u"the bytes changed on the way"
    assert sub.read_bytes() == SJIS, u"the subtitle given was changed"
    assert _listing(media) == sorted([want.name, video.name]), _listing(media)
    assert (got.ext, got.lang) == (u"ass", u"ja"), (got.ext, got.lang)
    assert tsubasa.parse_subtitle_name(want.name).lang == u"ja"
    # ⭐ 15z (A6, MX-09) -- a clean write promises nothing it did not do
    assert got.notes == (), got.notes


def test_lang_tag_writes_the_code_as_given(tmp_path):
    u"""⭐ hato's mark (its LAYER 15, fork 5): a file nobody timed is `<video>.jpn.<ext>`.
    `output_name` alone canonicalises `jpn` to `ja`, which would erase the mark -- and the
    name must still read back as Japanese, with the video's own stem."""
    video = _video(tmp_path / u"media", u"Show - 01.mkv")
    sub = _sub(tmp_path / u"cache", u"[G] Show - 01 [JPN].ja.srt")
    got = place_subtitle(video, sub, write=True, lang_tag=u"jpn")
    assert got.ok and got.output_path, got
    assert os.path.basename(got.output_path) == u"Show - 01.jpn.srt", got.output_path
    back = tsubasa.parse_subtitle_name(os.path.basename(got.output_path))
    assert (back.lang, back.stem, back.tag) == (u"ja", u"Show - 01", u"jpn"), back


@pytest.mark.parametrize("tag", [u"eng", u"en", u"und", u"ja-JP", u"jp n", u"ｊｐｎ", u"x"])
def test_a_lang_tag_for_another_language_or_no_language_is_refused(tmp_path, tag):
    u"""⛔ A name that says one language and means another is never written -- nor a form
    this reader never writes (`ja-JP`), nor one that is not a code at all."""
    video = _video(tmp_path / u"media", u"Show - 01.mkv")
    sub = _sub(tmp_path / u"cache", u"Show - 01 (web).ja.srt")
    got = place_subtitle(video, sub, write=True, lang_tag=tag)
    assert not got.ok and got.output_path is None, (tag, got)
    assert tag in got.reason, (tag, got.reason)
    assert _listing(tmp_path / u"media") == [u"Show - 01.mkv"], tag


def test_a_lang_tag_says_which_way_it_is_wrong(tmp_path):
    u"""Not a code at all, a code for another language, and a LOOKALIKE -- the Kelvin sign
    lower-cases to `k`, so `Ko` would read as Korean and write a non-ASCII name."""
    video = _video(tmp_path / u"media", u"Show - 01.mkv")
    ja = _sub(tmp_path / u"cache", u"Show - 01 (web).ja.srt")
    assert u"not a language code" in place_subtitle(video, ja, lang_tag=u"x").reason
    assert u"means en" in place_subtitle(video, ja, lang_tag=u"eng").reason
    ko = _sub(tmp_path / u"cache", u"Show - 01 (web).ko.srt")
    assert place_subtitle(video, ko, lang_tag=u"kor").ok, u"a real code was refused"
    got = place_subtitle(video, ko, lang_tag=u"Ko")
    assert not got.ok and u"plain letters" in got.reason, got


def test_a_lang_tag_that_is_not_text_is_a_callers_mistake(tmp_path):
    video = _video(tmp_path / u"media", u"Show - 01.mkv")
    sub = _sub(tmp_path / u"cache", u"x.ja.srt")
    with pytest.raises(TypeError):
        place_subtitle(video, sub, lang_tag=True)


@pytest.mark.parametrize("name", [u"x.ja.srt", u"x.jpn.srt", u"x.jp.srt", u"x.Japanese.srt"])
def test_the_language_comes_from_the_subtitles_own_name(tmp_path, name):
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    sub = _sub(tmp_path / u"cache", name)
    got = place_subtitle(video, sub, write=True)
    assert got.ok and got.lang == u"ja", (name, got)
    assert os.path.basename(got.output_path) == u"Ep 01.ja.srt", (name, got.output_path)


def test_a_subtitle_whose_name_gives_no_language_is_refused(tmp_path):
    u"""⛔ Placed untagged as `<video>.<ext>`, it would read as NO language -- and hato's next
    run would fetch again for ever (its `LEDGER-HOT.md`)."""
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    for name in (u"[G] Ep 01 [JPN].ass", u"Ep 01.und.ass"):
        sub = _sub(tmp_path / u"cache", name)
        got = place_subtitle(video, sub, write=True)
        assert not got.ok and u"gives no language" in got.reason, (name, got)
    assert _listing(tmp_path / u"media") == [u"Ep 01.mkv"]


def test_empty_oversize_and_non_subtitle_files_are_refused(tmp_path, monkeypatch):
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    empty = _sub(tmp_path / u"cache", u"a.ja.srt", data=b"")
    got = place_subtitle(video, empty, write=True)
    assert not got.ok and u"empty" in got.reason, got
    monkeypatch.setattr(PLACE, "MAX_BYTES", 64)
    big = _sub(tmp_path / u"cache", u"b.ja.srt", data=b"x" * 65)
    got = place_subtitle(video, big, write=True)
    assert not got.ok and u"over" in got.reason, got
    exact = _sub(tmp_path / u"cache", u"c.ja.srt", data=b"x" * 64)
    assert place_subtitle(video, exact).ok, u"a file AT the bound was refused"
    for name in (u"d.ja.txt", u"e.ja.sup", u"f.ja.mkv"):
        other = _sub(tmp_path / u"cache", name)
        got = place_subtitle(video, other, write=True)
        assert not got.ok and u"not a subtitle file" in got.reason, (name, got)
    assert _listing(tmp_path / u"media") == [u"Ep 01.mkv"]


def test_a_missing_video_or_subtitle_and_swapped_arguments_are_refused(tmp_path):
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    sub = _sub(tmp_path / u"cache", u"x.ja.srt")
    got = place_subtitle(media / u"gone.mkv", sub, write=True)
    assert not got.ok and u"no video" in got.reason, got
    got = place_subtitle(video, tmp_path / u"cache" / u"gone.ja.srt", write=True)
    assert not got.ok and u"no file" in got.reason, got
    got = place_subtitle(sub, video, write=True)
    assert not got.ok, got
    other = _sub(tmp_path / u"cache", u"y.ja.srt")
    got = place_subtitle(other, sub, write=True)          # a subtitle given as the video
    assert not got.ok and u"not a video" in got.reason, got
    assert _listing(media) == [u"Ep 01.mkv"]
    assert sorted(p.name for p in (tmp_path / u"cache").iterdir()) == [u"x.ja.srt",
                                                                      u"y.ja.srt"]


def test_a_subtitle_that_already_is_the_target_is_refused(tmp_path):
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    sub = _sub(media, u"Ep 01.ja.srt")
    got = place_subtitle(video, sub, write=True)
    assert not got.ok and u"already IS" in got.reason, got
    assert sub.read_bytes() == JA_SRT.encode("utf-8")


def test_it_writes_into_out_dir_when_given_and_makes_it(tmp_path):
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    sub = _sub(tmp_path / u"cache", u"x.ja.srt")
    out = tmp_path / u"Subs" / u"S2"
    got = place_subtitle(video, sub, write=True, out_dir=str(out))
    assert got.ok and got.output_path == str(out / u"Ep 01.ja.srt"), got
    assert _listing(tmp_path / u"media") == [u"Ep 01.mkv"], u"it wrote beside the video too"


def test_without_write_every_check_runs_and_nothing_is_written(tmp_path):
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    sub = _sub(tmp_path / u"cache", u"x.ja.srt")
    got = place_subtitle(video, sub)
    assert got.ok and got.output_path is None and not got.write_failed, got
    assert _listing(media) == [u"Ep 01.mkv"]
    bad = _sub(tmp_path / u"cache", u"y.srt")
    assert not place_subtitle(video, bad).ok, u"write=False skipped the checks"


def test_the_name_it_would_write_is_said_before_it_writes(tmp_path):
    u"""hato's 15z (B5) -- a caller that must FIND the file again has to know its name before
    it writes one: a name hato could not count was placed, then fetched for again every day.
    `target` is the name with `write=False`, the same once written, and None when refused."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    sub = _sub(tmp_path / u"cache", u"x.ja.forced.srt")
    ahead = place_subtitle(video, sub, lang_tag=u"jpn")
    assert ahead.target == str(media / u"Ep 01.jpn.forced.srt"), ahead.target
    assert _listing(media) == [u"Ep 01.mkv"], u"asking the name wrote a file"
    got = place_subtitle(video, sub, write=True, lang_tag=u"jpn")
    assert got.target == got.output_path == ahead.target, (got.target, got.output_path)
    again = place_subtitle(video, sub, write=True, lang_tag=u"jpn")
    assert again.write_failed and again.target == ahead.target, again
    assert place_subtitle(video, _sub(tmp_path / u"cache", u"y.srt")).target is None


def test_a_placed_file_is_readable_as_any_new_file_is(tmp_path, monkeypatch):
    u"""hato's 15z (A12) -- the temporary was created 0600, and the hard link or rename that
    publishes it keeps that mode: on Linux a placed subtitle was unreadable to a media
    server running as another user. ⭐ Created as any new file is: 0o666, the umask
    applied. (The mode asked is checked everywhere; the mode given, where it is kept.)"""
    asked, real = [], os.open

    def spy(path, flags, mode=0o777, *args, **kwargs):
        if str(path).endswith(u".tmp"):
            asked.append(mode)
        return real(path, flags, mode, *args, **kwargs)

    monkeypatch.setattr(P.os, "open", spy)
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"), write=True)
    monkeypatch.undo()
    assert got.output_path and asked == [0o666], (got, [oct(m) for m in asked])
    if os.name != "nt":
        umask = os.umask(0)
        os.umask(umask)
        mode = os.stat(got.output_path).st_mode & 0o777
        assert mode == 0o666 & ~umask, oct(mode)


def test_a_subtitles_flags_ride_into_the_name(tmp_path):
    u"""A forced subtitle is signs only; placed as the full one, a reader would count it as
    the video's subtitle."""
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    sub = _sub(tmp_path / u"cache", u"x.ja.forced.srt")
    got = place_subtitle(video, sub, write=True)
    assert os.path.basename(got.output_path) == u"Ep 01.ja.forced.srt", got


def test_a_trimmed_name_and_a_reserved_stem_are_said(tmp_path):
    u"""⭐ `output_name`'s notes reach the caller: a name that had to change is never
    changed silently -- a file quietly not where the player looks is the whole class.
    ⚠ An ASCII stem of 250: over 255 as the subtitle's name in EVERY filesystem's units,
    and a legal video name in all of them. (The 96-kanji name this used was legal on
    NTFS whole -- the check locked in 15z's A1.)"""
    media = tmp_path / u"media"
    long_stem = u"x" * 250
    video = _video(media, long_stem + u".mkv")
    sub = _sub(tmp_path / u"cache", u"x.ja.srt")
    got = place_subtitle(video, sub, write=True)
    assert got.ok and got.output_path, got
    assert any(u"trimmed" in n for n in got.notes), got.notes
    assert len(os.path.basename(got.output_path)) <= 255
    # ⚠ The NAMING step, directly: on this Windows `CON.eraiws.mkv` IS the console device,
    # so no such video can be made to hand over -- and `place_subtitle`'s notes are this
    # step's, as the trim above proves.
    target, notes = PLACE._name_for(str(tmp_path / u"CON.eraiws.mkv"), None, u"ja", u"srt",
                                    code=u"jpn")
    assert os.path.basename(target) == u"CON_.eraiws.jpn.srt", target
    assert any(u"reserved" in n for n in notes), notes


def test_asking_its_truth_raises(tmp_path):
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"))
    with pytest.raises(TypeError):
        bool(got)
    assert u"can be placed" in repr(got)


def test_the_names_are_exported():
    assert tsubasa.place_subtitle is place_subtitle
    assert u"place_subtitle" in tsubasa.__all__ and u"PlacedSubtitle" in tsubasa.__all__


# ---------------------------------------------------------------------------
# ⛔ never over a file that is there -- C3
# ---------------------------------------------------------------------------

def test_it_never_writes_over_a_file_that_is_there(tmp_path):
    u"""⛔ A subtitle already there is the person's -- or an earlier run's -- and is never
    replaced: `write_failed`, the reason, the file untouched, nothing left behind."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    theirs = media / u"Ep 01.jpn.srt"
    theirs.write_bytes(u"彼らのファイル".encode("utf-8"))
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"), write=True,
                         lang_tag=u"jpn")
    assert got.ok and got.write_failed and got.output_path is None, got
    assert u"already there" in got.reason, got.reason
    assert theirs.read_bytes() == u"彼らのファイル".encode("utf-8"), u"it wrote over theirs"
    assert _listing(media) == [u"Ep 01.jpn.srt", u"Ep 01.mkv"], _listing(media)


def test_a_file_landing_while_it_writes_is_not_overwritten(tmp_path, monkeypatch):
    u"""🚨 hato 14z (C3): the writer looked, then REPLACED -- a file landing between the two
    (3.6 ms median on a local disk: a pick racing a scheduled run, another tool) was
    overwritten. The target is planted AFTER the look could have happened -- while the
    temporary is being flushed -- and must survive byte for byte."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    theirs = media / u"Ep 01.ja.srt"
    real = os.fsync

    def plant(fd):
        real(fd)
        if not theirs.exists():
            theirs.write_bytes(u"割り込み".encode("utf-8"))

    monkeypatch.setattr(P.os, "fsync", plant)
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"), write=True)
    monkeypatch.setattr(P.os, "fsync", real)
    assert got.ok and got.write_failed and got.output_path is None, got
    assert theirs.read_bytes() == u"割り込み".encode("utf-8"), u"a file landing was overwritten"
    assert _listing(media) == [u"Ep 01.ja.srt", u"Ep 01.mkv"], u"a temporary was left behind"


def test_with_no_hard_links_windows_still_never_overwrites(tmp_path, monkeypatch):
    u"""A volume with no hard links (FAT, some shares) cannot link. On Windows `os.rename`
    refuses an existing target, so the fallback is as safe; elsewhere it looks and then
    renames -- the old race -- and SAYS SO in the notes."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")

    def no_links(src, dst):
        raise OSError(1, "Incorrect function (no hard links here)")

    monkeypatch.setattr(P.os, "link", no_links)
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"), write=True)
    assert got.ok and got.output_path, got
    said = [n for n in got.notes if u"hard link" in n]
    assert bool(said) == (os.name != "nt"), got.notes
    theirs = media / u"Ep 01.ja.srt"
    theirs.write_bytes(u"彼らの".encode("utf-8"))
    other = _video(media, u"Ep 01.mp4")
    got = place_subtitle(other, _sub(tmp_path / u"cache", u"y.ja.srt"), write=True)
    assert got.write_failed and theirs.read_bytes() == u"彼らの".encode("utf-8"), got
    assert sorted(p.name for p in media.iterdir() if p.name.endswith(u".tmp")) == []


# ---------------------------------------------------------------------------
# 🚨 a folder that refuses a new file fails AT ONCE -- A-1
# ---------------------------------------------------------------------------

def _unwritable(folder):
    u"""`folder`, made so THIS user cannot add a file to it -- Windows: an ACL deny of
    add-file and add-folder (`icacls`); elsewhere 0o555. -> a callable that puts it back.
    ⛔ Called in a `finally`: a folder left denied could not even be cleaned up."""
    folder = str(folder)
    if sys.platform.startswith("win"):
        who = os.environ.get("USERNAME") or os.getlogin()
        subprocess.run([u"icacls", folder, u"/deny", u"%s:(WD,AD)" % who], check=True,
                       stdout=subprocess.DEVNULL)
        return lambda: subprocess.run([u"icacls", folder, u"/remove:d", who], check=True,
                                      stdout=subprocess.DEVNULL)
    if os.geteuid() == 0:
        pytest.skip(u"root writes anywhere: no folder can be made unwritable for it")
    os.chmod(folder, 0o555)
    return lambda: os.chmod(folder, 0o755)


#: ⚠ In a CHILD, under a timeout: the defect is a writer that never returns, and one
#: running in this process would hang the suite -- and the mutation gate -- for days.
_CHILD = textwrap.dedent(u"""\
    import os, sys, time
    sys.path.insert(0, sys.argv[1])
    from tsubasa import paths, place_subtitle
    which, folder, video, sub = sys.argv[2:6]
    started = time.time()
    if which == "place":
        got = place_subtitle(video, sub, write=True, out_dir=folder)
        said = "write_failed=%s ok=%s reason=%s" % (got.write_failed, got.ok, got.reason)
    else:
        writer = getattr(paths, which)
        try:
            writer(os.path.join(folder, "x.ja.srt"), b"x" if which != "atomic_write_text" else "x")
            said = "WROTE"
        except OSError as exc:
            said = "RAISED %s" % type(exc).__name__
    print("%s in %.1fs" % (said, time.time() - started))
""")


@pytest.mark.parametrize("which", ["place", "write_new_bytes", "atomic_write_bytes",
                                   "atomic_write_text"])
def test_a_folder_that_denies_a_new_file_fails_at_once(tmp_path, which):
    u"""🚨 hato 14z (A-1): in a folder that denies adding a file, `tempfile.mkstemp` read
    Windows' ACCESS_DENIED as "that name is taken" and tried 2**31 names -- 40,052 in 8 s,
    one core at 100%, a run that never ended. Every writer here now fails at once: the
    general two (every `sync()` write goes through `atomic_write_bytes`) and the new one."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    sub = _sub(tmp_path / u"cache", u"x.ja.srt")
    shut = tmp_path / u"shut"
    shut.mkdir()
    put_back = _unwritable(shut)
    try:
        proc = subprocess.run(
            [sys.executable, u"-c", _CHILD, ROOT, which, str(shut), str(video), str(sub)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    except subprocess.TimeoutExpired:
        pytest.fail(u"%s was still trying after 60 s in a folder that denies a new file -- "
                    u"the A-1 spin" % which)
    finally:
        put_back()
    said = proc.stdout.strip()
    assert proc.returncode == 0, (which, said, proc.stderr[-600:])
    # ⚠ THE REFUSAL ITSELF, not merely "it stopped": a writer retrying a bounded few names
    # on a denial also stops, and would tell the person the names were TAKEN.
    if which == "place":
        assert u"write_failed=True ok=True" in said and u"denied" in said, said
        # ⭐ 15z (A11) -- the system's words, never the name of the temporary
        assert u".tmp" not in said, said
    else:
        assert said.startswith(u"RAISED PermissionError"), said
    assert list(shut.iterdir()) == [], u"something was left in the folder"


# ---------------------------------------------------------------------------
# ⭐ hato's 15z -- the adversarial pass over this step (hato ADVERSARY-2026-09-26, A)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"a 91-kanji name is legal only where names count UTF-16 units")
def test_a_japanese_name_the_filesystem_holds_is_never_cut(tmp_path):
    u"""🚨 A1 -- NTFS counts 255 UTF-16 UNITS, and the trim counted UTF-8 bytes: a 91-kanji
    video's subtitle was cut to 82 characters -- a stem no longer the video's, which no
    player loads -- and two episodes differing after character 82 wrote ONE name."""
    media = tmp_path / u"media"
    first = _video(media, u"葬送のフリーレン" * 11 + u"第二期 - 01.mkv")
    second = _video(media, u"葬送のフリーレン" * 11 + u"第二期 - 02.mkv")
    for video in (first, second):
        got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"), write=True)
        assert got.ok and got.output_path and not got.notes, (video.name, got, got.notes)
        back = tsubasa.parse_subtitle_name(os.path.basename(got.output_path))
        assert back.stem == video.stem, (back.stem, video.stem)


def _planting(monkeypatch, target, names=(u"link", u"rename", u"replace")):
    u"""Plant a file at `target` at the moment of PUBLISHING -- inside the call that makes
    the new file appear, which is where 0.1.9's look-then-replace lost the race (A2)."""
    for name in names:
        real = getattr(P.os, name)

        def planted(src, dst, _real=real):
            if os.path.normcase(os.fspath(dst)) == os.path.normcase(str(target)) \
                    and not os.path.lexists(dst):
                with open(dst, "wb") as fh:
                    fh.write(u"割り込み".encode("utf-8"))
            return _real(src, dst)

        monkeypatch.setattr(P.os, name, planted)


@pytest.mark.parametrize("links", [
    True,
    pytest.param(False, marks=pytest.mark.skipif(
        not sys.platform.startswith("win"),
        reason=u"elsewhere the no-link path is the reservation -- its own check below"))],
    ids=[u"hard-link", u"no-hard-link"])
def test_a_file_landing_at_the_moment_it_is_published_is_not_overwritten(
        tmp_path, monkeypatch, links):
    u"""🚨 A2 -- C3's first check planted during `fsync`, BEFORE the look a look-then-replace
    writer makes after it: the old defect put back stayed green (MX-14). Here the other
    file lands INSIDE the publishing call -- the link, or on Windows with no hard links the
    rename -- and survives byte for byte, the reason saying so (MX-01), nothing left."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    theirs = media / u"Ep 01.ja.srt"
    if not links:
        monkeypatch.setattr(P.os, "link", lambda src, dst: (_ for _ in ()).throw(
            OSError(1, u"Incorrect function (no hard links here)")))
        _planting(monkeypatch, theirs, names=(u"rename", u"replace"))
    else:
        _planting(monkeypatch, theirs)
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"), write=True)
    assert got.ok and got.write_failed and got.output_path is None, got
    assert u"already there" in got.reason, got.reason
    assert theirs.read_bytes() == u"割り込み".encode("utf-8"), u"a file landing was overwritten"
    assert _listing(media) == [u"Ep 01.ja.srt", u"Ep 01.mkv"], u"a temporary was left behind"


def test_a_temporary_that_cannot_be_removed_never_hides_what_happened(tmp_path, monkeypatch):
    u"""🚨 A3 -- a folder that lets a file be added but not deleted (or a reader holding
    the temporary): the cleanup's error REPLACED the real one -- *"Access is denied:
    …tmp"* where the answer was *"already there"* -- and on success a `.tmp` stayed,
    said nowhere a caller reads. ⭐ Landed: the file written, the leftover in the notes
    (MX-03). Not landed: the real reason, the leftover after it. ⭐ And a name already
    taken is found BEFORE any temporary exists."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    real_unlink = P.os.unlink

    def stuck(path, *a, **k):
        if os.fspath(path).endswith(u".tmp"):
            raise PermissionError(5, u"Access is denied", os.fspath(path))
        return real_unlink(path, *a, **k)

    monkeypatch.setattr(P.os, "unlink", stuck)
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"), write=True)
    assert got.ok and not got.write_failed and got.output_path, got
    assert (media / u"Ep 01.ja.srt").read_bytes() == JA_SRT.encode("utf-8")
    assert any(u"could not be removed" in n for n in got.notes), got.notes
    for leftover in [p for p in media.iterdir() if p.name.endswith(u".tmp")]:
        real_unlink(str(leftover))
    # the name taken while it writes: the REAL reason, the leftover said after it
    other = _video(media, u"Ep 02.mkv")
    _planting(monkeypatch, media / u"Ep 02.ja.srt")
    got = place_subtitle(other, _sub(tmp_path / u"cache", u"y.ja.srt"), write=True)
    assert got.write_failed and got.reason.startswith(u"Ep 02.ja.srt is already there"), got
    assert u"could not be removed" in got.reason, got.reason
    for leftover in [p for p in media.iterdir() if p.name.endswith(u".tmp")]:
        real_unlink(str(leftover))
    # ⭐ a name taken BEFORE: no temporary is ever made
    before = set(_listing(media))
    got = place_subtitle(other, _sub(tmp_path / u"cache", u"z.ja.srt"), write=True)
    assert got.write_failed and u"already there" in got.reason, got
    assert set(_listing(media)) == before, u"a temporary was made for a name already taken"


def test_on_a_volume_with_no_hard_links_elsewhere_the_name_is_reserved_first(
        tmp_path, monkeypatch):
    u"""🚨 A5 -- POSIX with no hard links (exFAT, FAT, some SMB mounts): `rename` REPLACES
    there, and the fallback looked, then renamed -- a file landing between was overwritten.
    ⭐ The name is RESERVED (created exclusively), then filled; a file there at the
    reservation is never touched. (Simulated here: POSIX's rules, on any system.)"""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    monkeypatch.setattr(P, "_WINDOWS_RENAME", False)
    monkeypatch.setattr(P.os, "link", lambda src, dst: (_ for _ in ()).throw(
        OSError(95, u"Operation not supported")))
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"), write=True)
    assert got.ok and got.output_path and not got.write_failed, got
    assert (media / u"Ep 01.ja.srt").read_bytes() == JA_SRT.encode("utf-8")
    assert any(u"reserved first" in n for n in got.notes), got.notes
    # the other file lands at the moment of the reservation
    other = _video(media, u"Ep 02.mkv")
    theirs = media / u"Ep 02.ja.srt"
    real_open = P.os.open

    def reserve(path, flags, *rest):
        if os.fspath(path) == str(theirs) and not theirs.exists():
            theirs.write_bytes(u"割り込み".encode("utf-8"))
        return real_open(path, flags, *rest)

    monkeypatch.setattr(P.os, "open", reserve)
    got = place_subtitle(other, _sub(tmp_path / u"cache", u"y.ja.srt"), write=True)
    assert got.write_failed and u"already there" in got.reason, got
    assert theirs.read_bytes() == u"割り込み".encode("utf-8"), u"the reservation replaced theirs"
    assert not [p for p in media.iterdir() if p.name.endswith(u".tmp")]


def test_a_temporary_name_already_taken_moves_on_and_touches_nothing(tmp_path, monkeypatch):
    u"""A6 (MX-04, 05, 06) -- `_temporary` over names already taken: a FILE at the first
    (left exactly as it was: opened exclusively, never over it), a DIRECTORY at the
    second (on Windows it answers ACCESS_DENIED -- a taken name, not a refusal), the third
    used."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    tokens = iter([u"aaaaaaaa", u"bbbbbbbb", u"cccccccc", u"dddddddd"])
    monkeypatch.setattr(P.secrets, "token_hex", lambda n: next(tokens))
    taken_file = media / u".Ep 01.ja.srt.aaaaaaaa.tmp"
    taken_file.write_bytes(b"someone else's")
    taken_dir = media / u".Ep 01.ja.srt.bbbbbbbb.tmp"
    taken_dir.mkdir()
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"), write=True)
    assert got.ok and got.output_path, got
    assert taken_file.read_bytes() == b"someone else's" and taken_dir.is_dir()
    assert (media / u"Ep 01.ja.srt").read_bytes() == JA_SRT.encode("utf-8")
    assert not (media / u".Ep 01.ja.srt.cccccccc.tmp").exists(), u"the used temporary stayed"


@pytest.mark.parametrize("ext", [u"ssa", u"vtt"])
def test_every_text_format_is_placed(tmp_path, ext):
    u"""A6 (MX-10) -- `.ssa` and `.vtt` are subtitles tsubasa places, as `.srt` and `.ass`."""
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.%s" % ext), write=True)
    assert got.ok and os.path.basename(got.output_path) == u"Ep 01.ja.%s" % ext, got


def test_the_real_bound_is_sixteen_megabytes(tmp_path):
    u"""A6 (MX-11) -- the bound itself, not a patched one: 16 MiB is a subtitle, a byte
    more is not."""
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    at = _sub(tmp_path / u"cache", u"a.ja.srt", data=b"x" * (16 * 1024 * 1024))
    assert place_subtitle(video, at).ok, u"a file AT 16 MiB was refused"
    over = _sub(tmp_path / u"cache", u"b.ja.srt", data=b"x" * (16 * 1024 * 1024 + 1))
    got = place_subtitle(video, over)
    assert not got.ok and u"over 16 MB" in got.reason, got


def test_a_subtitle_given_as_the_video_is_refused_in_any_case(tmp_path):
    u"""A6 (MX-12) -- the swapped-arguments guard reads the extension case-blind."""
    sub = _sub(tmp_path / u"cache", u"x.ja.srt")
    upper = _sub(tmp_path / u"cache", u"y.JA.SRT")
    got = place_subtitle(upper, sub)
    assert not got.ok and u"not a video" in got.reason, got


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"one file under two cases exists only where names ignore case")
def test_a_subtitle_that_is_the_target_in_another_case_is_refused(tmp_path):
    u"""A6 (MX-02) -- `_same_file` asks the FILESYSTEM: on Windows `Ep 01.JA.srt` and
    `Ep 01.ja.srt` are one file, and placing it over itself is nothing to place."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    sub = _sub(media, u"Ep 01.JA.srt")
    got = place_subtitle(video, sub, write=True)
    assert not got.ok and u"already IS" in got.reason, got


def test_without_write_a_name_already_taken_is_said(tmp_path):
    u"""A8 -- *every check made* includes this one: *can be placed* over a name already
    taken was a promise the write would break."""
    media = tmp_path / u"media"
    video = _video(media, u"Ep 01.mkv")
    (media / u"Ep 01.ja.srt").write_bytes(b"theirs")
    got = place_subtitle(video, _sub(tmp_path / u"cache", u"x.ja.srt"))
    assert got.ok and u"already there" in got.reason, got
    assert u"can be placed" not in repr(got), repr(got)


def test_an_out_dir_with_a_nul_or_a_file_in_its_place_is_said_not_raised(tmp_path):
    u"""A9 -- a NUL in `out_dir` RAISED `ValueError` out of a function that promises only
    `TypeError`. A11 -- an `out_dir` that is a FILE read *"Cannot create a file when that
    file already exists"*, which says the TARGET is there."""
    video = _video(tmp_path / u"media", u"Ep 01.mkv")
    sub = _sub(tmp_path / u"cache", u"x.ja.srt")
    got = place_subtitle(video, sub, write=True, out_dir=str(tmp_path / u"a\x00b"))
    assert not got.ok and u"NUL" in got.reason, got
    blocker = tmp_path / u"Subs"
    blocker.write_bytes(b"a file, not a folder")
    got = place_subtitle(video, sub, write=True, out_dir=str(blocker))
    assert got.write_failed and u"where its folder should be" in got.reason, got
    assert u"already there" not in got.reason, got.reason
