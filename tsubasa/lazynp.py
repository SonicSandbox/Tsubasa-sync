# -*- coding: utf-8 -*-
u"""numpy, imported the first time it is actually used. RUNBOOK 4g.

    np = numpy_when_needed(globals())   # then use `np.` exactly as before

⛔ **THAT LINE USED TO READ `from ..lazynp import np`, WHICH DOES NOT WORK**
(`ImportError: cannot import name 'np'`) — this module exports
`numpy_when_needed` and nothing else. A false line of prose in the file whose
whole job is to explain itself. Found by an adversary; the two real call
sites always did it the right way.

===========================================================================
🚨 WHY: THE GUI IMPORTED numpy TO DRAW A WINDOW
===========================================================================

Sonic, on the shipped app: *"why does my computer lag, my mouse lag when it
starts up?"* Measured on the frozen build — **1.7–4.2 s to a window against
0.8–1.1 s of CPU**, so most of it is waiting rather than working. But of the
CPU half, **245 ms was numpy**, and the GUI never does arithmetic: it shells
out to `tsubasa.exe` for every run.

It arrived because importing ANY tsubasa submodule runs `tsubasa/__init__.py`,
which imports the public API eagerly — `align` → `align.fit` → numpy. The GUI
asks for `tsubasa.paths` and gets the whole numeric stack.

===========================================================================
⛔ WHY NOT A LAZY `__init__`, WHICH IS THE OBVIOUS FIX
===========================================================================

It was tried and **measured to break a pinned compatibility shape.**
`tsubasa/__init__.py` deliberately REBINDS `tsubasa.align` from the subpackage
to the function, because `05-interface.md` promises
`from tsubasa import align` is callable and hato pins it. With a PEP 562
`__getattr__` the import system sets the parent attribute to the SUBPACKAGE
first, and `__getattr__` never fires once an attribute exists:

    import tsubasa.align; tsubasa.align   eager -> function   lazy -> module
    import tsubasa.align as X             eager -> function   lazy -> module

Two of six forms change silently. ⛔ `LEDGER-HOT.md` records that exact shape
as one where mutants go from KILLED to SURVIVED with no fault to explain it.

⭐ So the import is deferred where it is CHEAP AND LOCAL instead: numpy is used
only INSIDE functions in `align/fit.py` and `align/objective.py` — verified by
walking both syntax trees for module-level, default-argument and decorator
uses, of which there are none. Nothing about the public API moves.

===========================================================================
⚠ HOW IT WORKS, AND ITS ONE LIMIT
===========================================================================

A module-level `__getattr__` (PEP 562) does **not** help here: it is consulted
for attribute access on the module object, never for a plain global lookup
inside that module's own functions. So this is a proxy object bound to the
name `np`, whose first attribute access imports numpy and **replaces itself in
the module globals** — every later `np.` in that module is the real thing, at
no cost.

⛔ The limit, stated rather than discovered: anything that touches `np` WITHOUT
an attribute — `type(np)`, `isinstance(x, np.ndarray)` is fine, but a bare
`np` passed somewhere — sees the proxy until the first attribute access. No
call site does that, and a check enforces it.
"""


class _LazyNumpy(object):
    u"""Stands in for `numpy` until something asks it for a name.

    ⚠ `__slots__` and no state: the whole object is one method, and it is
    replaced in the importing module's globals on first use, so it must not
    carry anything worth losing.
    """

    __slots__ = ("_globals",)

    def __init__(self, module_globals):
        self._globals = module_globals

    def __getattr__(self, name):
        # ⛔ THE SLOT ITSELF IS NOT PROXIED, AND WITHOUT THIS LINE IT RECURSES
        # FOR EVER. `copy.copy(np)` builds the instance with `cls.__new__`,
        # which never sets `__slots__`, so `self._globals` below misses,
        # re-enters here, and misses again: measured at **999 frames, 996 of
        # them on the assignment line** — a traceback that blames the
        # statement instead of the cause. Found by an adversarial pass.
        if name == u"_globals":
            raise AttributeError(name)

        import numpy

        # ⭐ REPLACE ITSELF, so this happens once per module rather than once
        # per attribute. Every later `np.` is an ordinary global lookup of the
        # real module, with no proxy in the path.
        self._globals[u"np"] = numpy
        return getattr(numpy, name)

    def __repr__(self):                                   # pragma: no cover
        return u"<numpy, not imported yet>"


def numpy_when_needed(module_globals):
    u"""-> a stand-in to bind to `np` in `module_globals`."""
    return _LazyNumpy(module_globals)


__all__ = ["numpy_when_needed"]
