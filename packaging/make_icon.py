# -*- coding: utf-8 -*-
u"""Build `tsubasa/data/tsubasa.ico` from the shipped PNG exports. RUNBOOK 4e.

    python packaging/make_icon.py [--check]

⛔ A SCRIPT, NOT A ONE-OFF. The `.ico` is derived from files that are in the
repository, so it must be reproducible from them — otherwise it is a binary
nobody can regenerate, which is the same problem `decoration.json` and the
alias table are forbidden from having (*"never hand-edit — re-derive them"*).

===========================================================================
🚨 WHY AN `.ico` AT ALL, WHEN THERE ARE ALREADY PNGs
===========================================================================

They serve two DIFFERENT surfaces and one cannot do the other's job:

  * the PNGs are read at RUNTIME by Tk's `iconphoto`, which sets the icon of
    a window that is already open;
  * the `.ico` is compiled by PyInstaller into the executable as a **Win32
    resource**, and that is what Explorer, the taskbar button, Alt-Tab, the
    Start menu and the file's own properties read — **before Python starts.**

⛔ A frozen app with `iconphoto` set still shows PyInstaller's default icon in
Explorer. Setting one is not setting the other.

⚠ EVERY SIZE IS A REAL EXPORT. The pack has no vector source, so each entry
comes from its own PNG rather than from one image resampled — which is what
keeps a 16 px icon legible instead of mush.
"""
import os
import sys

#: ⚠ The sizes Windows actually asks for, in the order it prefers them.
#: 24 and 64 are included because the taskbar and Alt-Tab ask for them on
#: high-DPI displays and Windows resamples something else when they are absent.
SIZES = (16, 24, 32, 48, 64, 128, 256)


def data_dir():
    import tsubasa
    return os.path.join(os.path.dirname(os.path.abspath(tsubasa.__file__)),
                        u"data")


def build(target=None):
    from PIL import Image

    where = data_dir()
    target = target or os.path.join(where, u"tsubasa.ico")
    frames = []
    for size in SIZES:
        path = os.path.join(where, u"icon-%d.png" % size)
        if not os.path.isfile(path):
            sys.exit(u"⛔ %s is missing. The .ico is DERIVED from the shipped "
                     u"PNGs; it is not a separate asset to be dropped in."
                     % path)
        img = Image.open(path).convert("RGBA")
        if img.size != (size, size):
            sys.exit(u"⛔ %s is %dx%d, not %dx%d — the pack's exports are "
                     u"square and named for their size, so this one is wrong "
                     u"or was resaved." % (path, img.width, img.height,
                                           size, size))
        frames.append(img)

    # ⚠ Pillow writes the sizes given in `sizes=` from the BASE image unless
    # `append_images` is supplied — which would resample one export down and
    # throw away the hand-made small ones. The largest is the base and the
    # rest are appended as their own frames.
    base = frames[-1]
    base.save(target, format="ICO", sizes=[(s, s) for s in SIZES],
              append_images=frames[:-1])

    _faint(where)
    return target


#: How much of the mark is left in the empty-state variant.
FAINT = 0.45


def _faint(where):
    u"""Derive `icon-128-faint.png` — the empty-state mark. -> path

    ⭐ TRANSLUCENT, NOT PRE-BLENDED ONTO THE THEME COLOUR. Compositing onto
    `#15171b` here would bake this window's background into a file in the
    PACKAGE, so any other application embedding tsubasa gets a mark with our
    ground baked in, and changing the theme would silently leave a halo.
    Reducing the ALPHA lets Tk composite it over whatever is actually behind
    it.

    ⚠ It exists because the brief was *"nothing distracting"* and the empty
    state at full strength is a saturated logo in the middle of the window.
    ⛔ And it is DERIVED, not a separate asset — the same rule the alias table
    and the decoration vocabulary live under: *never hand-edit, re-derive.*
    """
    from PIL import Image

    source = os.path.join(where, u"icon-128.png")
    target = os.path.join(where, u"icon-128-faint.png")
    img = Image.open(source).convert("RGBA")
    r, g, b, a = img.split()
    a = a.point(lambda v: int(round(v * FAINT)))
    Image.merge("RGBA", (r, g, b, a)).save(target)
    return target


def check(target=None):
    u"""⭐ OPEN IT AND READ THE SIZES BACK. `doctrine/evidence`: a file that
    was written is not a file that contains what you meant. -> [int]"""
    from PIL import Image

    target = target or os.path.join(data_dir(), u"tsubasa.ico")
    if not os.path.isfile(target):
        sys.exit(u"⛔ %s does not exist. Run this script without --check."
                 % target)
    with Image.open(target) as ico:
        got = sorted(set(w for w, _h in ico.info.get("sizes", ())))
    missing = [s for s in SIZES if s not in got]
    if missing:
        sys.exit(u"⛔ %s carries %s and is MISSING %s. Windows would resample "
                 u"a neighbour, which is how a crisp icon becomes mush at the "
                 u"one size people actually see." % (target, got, missing))
    return got


def main():
    if "--check" in sys.argv:
        print(u"ok: tsubasa.ico carries %s" % (check(),))
        return 0
    target = build()
    got = check(target)
    print(u"wrote %s  (%d bytes, sizes %s)"
          % (target, os.path.getsize(target), got))
    return 0


if __name__ == "__main__":
    sys.exit(main())
