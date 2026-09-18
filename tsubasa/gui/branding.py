# -*- coding: utf-8 -*-
u"""The mark, and where to find it. RUNBOOK 4e.

    branding.set_window_icon(root)        # title bar, Alt-Tab, taskbar
    mark = branding.image(24)             # a PhotoImage, or None

===========================================================================
⭐ ONE OWNER FOR THE PATH, because there are three hosts and they disagree
===========================================================================

Running from a source tree, from a wheel, and from a PyInstaller bundle put
`tsubasa/data/` in three different places. ⛔ `naming/alias.py` already learned
this the expensive way — 0.1.0 shipped broken because a path resolved through
the repository instead of through the installed package — so this resolves the
same way that one does, off `tsubasa.__file__`, and nothing else computes it.

===========================================================================
🚨 A `PhotoImage` NOBODY REFERENCES IS GARBAGE-COLLECTED, AND THE ICON GOES
===========================================================================

Tk keeps no reference to image objects; Python frees them and the widget is
left pointing at nothing — silently, with no error and no icon. **So every
caller must hold what it is given**, and every one here does: `App` keeps
`mark_small` and `mark_big`, and `set_window_icon` stashes its images on the
root.

⛔ **AND THE MODULE MAY NOT HOLD THEM INSTEAD.** A `PhotoImage` belongs to the
**Tk interpreter that created it**. A module-level cache was the first design,
and it broke **eighteen checks at once** with `TclError: image "pyimage1"
doesn't exist` — the second Tk root in a process was handed an image built by
the first, which had since been destroyed. ⚠ The product makes one root per
launch and would never have seen it; a suite, an embedding application, or
anything that reopens a window would. **Lifetime belongs to the owner of the
window, not to the module.**

⚠ **Every size is a real export.** The pack has no vector source, so
`image(24)` returns the 24 px file rather than the 256 resampled — which is
the difference between a legible small icon and mush.
"""
import os


def data_dir():
    u"""-> the package's `data/` directory, on every host."""
    import tsubasa
    return os.path.join(os.path.dirname(os.path.abspath(tsubasa.__file__)),
                        u"data")


def icon_path(size, faint=False):
    u"""⚠ `faint=True` is the EMPTY-STATE variant — the same mark with its
    alpha reduced, derived by `packaging/make_icon.py`. It is translucent
    rather than pre-blended onto the theme colour, so Tk composites it over
    whatever is actually behind it and no background is baked into a file
    that ships in the package."""
    name = u"icon-%d-faint.png" if faint else u"icon-%d.png"
    return os.path.join(data_dir(), name % size)


def ico_path():
    u"""-> the Windows `.ico`, for a freezer to compile into an executable.

    ⚠ Not used at runtime by anything here. It is in the package so that the
    PyInstaller spec can point at the INSTALLED tsubasa rather than at a
    checkout — the same reasoning as the hook tsubasa ships.
    """
    return os.path.join(data_dir(), u"tsubasa.ico")


def available():
    u"""-> [int], the sizes actually present, ascending."""
    out = []
    try:
        for name in os.listdir(data_dir()):
            if name.startswith(u"icon-") and name.endswith(u".png"):
                try:
                    out.append(int(name[5:-4]))
                except ValueError:
                    pass
    except OSError:
        return []
    return sorted(out)


def image(size, master=None, faint=False):
    u"""-> a FRESH `tkinter.PhotoImage` at `size`, or None if it cannot be had.

    ⛔ A NEW OBJECT EVERY CALL, AND THE CALLER KEEPS IT. See the module note:
    a `PhotoImage` is owned by the Tk interpreter that made it, so a cache
    here hands a dead image to the next window. **The caller holds it**,
    because the caller is what the image's lifetime actually follows.

    ⚠ `master` is passed through so the image is built on the RIGHT
    interpreter when there is more than one. Tk defaults to the most recently
    created root, which is exactly the assumption that breaks.

    ⛔ NEVER RAISES. `doctrine/architecture`: *instruction, not refusal.* A
    missing or unreadable icon is a slightly plainer window; it is not a
    reason for the application not to open, and a decorative asset may not be
    load-bearing.

    ⚠ PNG in a `PhotoImage` needs **Tk 8.6**. Older Tk raises `TclError` here
    rather than at import, which is why the guard is around the construction.
    """
    try:
        import tkinter as tk

        path = icon_path(size, faint=faint)
        # ⚠ The faint variant is derived, so an older install may not have it.
        # Falling back to the full-strength mark is a louder empty state, not
        # a missing one — `doctrine/architecture`: instruction, not refusal.
        if faint and not os.path.isfile(path):
            path = icon_path(size)
        if not os.path.isfile(path):
            return None
        if master is not None:
            return tk.PhotoImage(file=path, master=master)
        return tk.PhotoImage(file=path)
    except Exception:                                     # noqa: BLE001
        return None


def set_window_icon(root):
    u"""Put the mark on the title bar, Alt-Tab and the taskbar button. -> bool

    🚨 `default=True` IS THE WHOLE REASON THE SETTINGS WINDOW GETS ONE TOO.
    The first argument of `iconphoto` is `default`, and only when it is true
    do toplevels created LATER inherit the icon. With it false the main
    window is branded and every dialog is not, which looks like a bug rather
    than like a choice.

    ⚠ Several sizes are handed over at once and Windows picks per surface —
    16 px for the title bar, 32 for Alt-Tab, larger for the taskbar. Passing
    only one makes Windows resample it for the others.

    ⛔ This does NOT give the .exe its icon. That is a Win32 resource compiled
    into the binary, read before Python starts — `packaging/make_icon.py`.
    """
    images = [img for img in (image(s, master=root) for s in available())
              if img]
    if not images:
        return False
    try:
        root.iconphoto(True, *images)
    except Exception:                                     # noqa: BLE001
        return False
    # 🚨 STASHED ON THE ROOT, or Python frees them the moment this function
    # returns and the title bar goes blank with no error anywhere. The root
    # is the right owner: the images live exactly as long as the window does.
    root._tsubasa_icons = images
    return True


__all__ = ["available", "data_dir", "ico_path", "icon_path", "image",
           "set_window_icon"]
