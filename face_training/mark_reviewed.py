"""
Mark crops as "already been through it", so the review page stops showing them.

Why this exists: the review page's log wrote down every NO - not her, her but
don't use it, deleted - and never wrote down a YES. A crop you looked at and
kept left no trace, so every reload put the whole pile in front of you again,
and finding the one video still waiting meant wading past hundreds of pictures
you had already blessed (user, 2026-09-22).

NOTHING IS DELETED AND NOTHING IS MOVED. The crops stay in clean/head and
clean/body, and training still uses every one of them. The only thing that
changes is a note in <profile>/search_history.json under "reviewed". The
originals stay where the search already put them, in processed/ and
video_and_frames/ - this script does not touch those folders at all.

Use it:

  python -m face_training.mark_reviewed --profile susana
        mark every crop in clean/ as looked at. This is the catch-up: use it
        once, for work you did before the page could remember it.

  python -m face_training.mark_reviewed --profile susana --show
        count what is marked and what is not. Changes nothing.

  python -m face_training.mark_reviewed --profile susana --forget
        take the mark off every crop now in clean/, so the whole pile comes
        back (marks for crops no longer on disk are left in the log).

  python -m face_training.mark_reviewed --all-profiles
        the same, for everybody in _face_profiles.

Day to day you should not need this: the review page marks crops itself, as you
work and when you press Proceed. This is the catch-up and the way back.

Close the review page first. It writes to the same log.

stdlib only.
"""

from __future__ import annotations

import argparse
import os
import sys

from face_training import profiles as P
from face_training import search_history as SH

CROP_EXTS = (".jpg", ".jpeg", ".png")


def crop_stamp(path: str) -> str:
    """Same fingerprint the review page uses: size and last-written time."""
    st = os.stat(path)
    return f"{st.st_size}:{int(st.st_mtime)}"


def crops_of(prof) -> list[tuple[str, str, str]]:
    """Every crop on disk, as (kind, name, full path)."""
    out = []
    for kind, d in (("head", prof.clean_head), ("body", prof.clean_body)):
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(CROP_EXTS):
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    out.append((kind, name, p))
    return out


def last_pass(hist) -> dict | None:
    """The last finished review - the one that ended in training."""
    for e in reversed(hist.data.get("events", [])):
        if e.get("kind") == "review_proceed":
            return e
    return None


def report(prof, hist) -> tuple[int, int]:
    seen = new = 0
    for kind, name, p in crops_of(prof):
        if hist.is_reviewed(f"{kind}/{name}", crop_stamp(p)):
            seen += 1
        else:
            new += 1
    return seen, new


def run(slug: str, forget: bool = False, show: bool = False) -> int:
    prof = P.Profile(slug)
    if not prof.data:
        print(f"  no profile '{slug}'")
        return 0
    hist = SH.History(prof.history_path)
    crops = crops_of(prof)
    seen, new = report(prof, hist)

    print(f"{prof.data.get('display_name', slug)}: {len(crops)} crop(s) in clean/ "
          f"- {seen} already marked, {new} not")

    if show:
        done = last_pass(hist)
        if done:
            print(f"  last finished review: {done.get('at')} "
                  f"({done.get('head', 0)} face + {done.get('body', 0)} body crops)")
        return 0

    if forget:
        for kind, name, _ in crops:
            hist.forget_reviewed(f"{kind}/{name}")
        hist.log("reviewed_mark_removed", crops=len(crops), by="mark_reviewed script",
                 meaning="every crop put back on the page to be looked at again")
        hist.save()
        print(f"  took the mark off {len(crops)} crop(s) - they will all show again")
        return len(crops)

    if not new:
        print("  nothing to do: every crop is already marked")
        return 0

    for kind, name, p in crops:
        hist.mark_reviewed(f"{kind}/{name}", crop_stamp(p))
    done = last_pass(hist)
    hist.log("marked_reviewed", crops=len(crops), by="mark_reviewed script",
             catching_up_on=(done or {}).get("at", ""),
             meaning="looked at before the page could remember it - hidden from the page, "
                     "left on disk untouched and still used for training")
    hist.save()
    print(f"  marked {new} crop(s) as looked at ({len(crops)} in total now)")
    if done:
        print(f"  catching up on the review you finished {done.get('at')}")
    print("  nothing was deleted and nothing was moved")
    return new


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", help="profile slug, e.g. susana")
    ap.add_argument("--all-profiles", action="store_true", help="every profile there is")
    ap.add_argument("--forget", action="store_true", help="take every mark off instead")
    ap.add_argument("--show", action="store_true", help="count them and change nothing")
    a = ap.parse_args(argv)

    if a.all_profiles:
        slugs = [p.slug for p in P.all_profiles()]
    elif a.profile:
        slugs = [a.profile]
    else:
        ap.error("give --profile <slug> or --all-profiles")
        return 2

    for s in slugs:
        run(s, forget=a.forget, show=a.show)
    return 0


if __name__ == "__main__":
    sys.exit(main())
