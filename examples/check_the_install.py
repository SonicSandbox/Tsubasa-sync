"""Is this tsubasa installation as good as it should be?

    python check_the_install.py         # exits 1 if something is silently wrong

tsubasa's data files are optional by design, so a damaged install still runs —
it just pairs fewer files by name. `self_check()` is how you find out. Call it
from your application's startup or its smoke test; it opens none of your files
and runs nothing.
"""
import sys

import tsubasa


def main():
    check = tsubasa.self_check()
    print(check)

    for sentence in check.problems:      # anything silently worse than it should be
        print("PROBLEM:", sentence)
    for sentence in check.notes:         # things that are fine, but worth knowing
        print("note:   ", sentence)

    return 0 if check.ok else 1


if __name__ == "__main__":
    sys.exit(main())
