"""
The learning layer for ONE face profile - each person has their own, in their
own folder, and nothing is shared between people (user, 2026-09-26).

Three things make the tool sharper for that person the more it works on them:

1. A growing bank of "other people" face fingerprints: the other faces in a
   picture where Seek found her, and a solo face that scores clearly below the
   cutoff (more than 0.10 under it). The per-person match cutoff is then
   set from how close the nearest OTHER face is - loose when the bank is small,
   tight when it is large.

2. A feedback log. When Seek cannot tell whether a face is the person, it logs
   its scores (by="auto"); in the clean stage the copy is also set aside in
   needs_review. A person's answer on the review page is logged with those
   scores (by="user") and is a labeled example. Seek's own unsure guesses are
   never examples.

3. A small trained judge (logistic regression over a few similarity numbers),
   fitted to a person's answers only. Once there are enough of them it
   replaces the fixed cutoff.

Everything lives as plain files in that person's own <profile>/learning/
folder. Nothing is shared between people (user, 2026-09-26).

stdlib + numpy. The judge uses a tiny hand-rolled logistic fit (no sklearn
dependency).
"""

from __future__ import annotations

import json
import os
import time

import numpy as np

from face_training.profiles import PROFILES_ROOT

# Everything here belongs to ONE person and lives in that person's own folder,
# <profile>/learning/ (user, 2026-09-26: "NOTHING about an individual profile
# should be shared with another profile"). There is no shared folder: searching
# for David never sees Susana's bank, answers, judge or crop margins, even when
# they are in the same photos. (It used to be _face_profiles/_global, shared by
# every person - a second person's own face could sit in it as "not them".)
LEARNING = "learning"


def learning_dir(slug: str) -> str:
    if not slug or os.path.basename(slug) != slug or slug.startswith("_"):
        raise ValueError(f"bad profile name {slug!r}")
    return os.path.join(PROFILES_ROOT, slug, LEARNING)


def _p(slug: str, name: str) -> str:
    return os.path.join(learning_dir(slug), name)


def OTHER_NPY(slug): return _p(slug, "other_faces.npy")
def OTHER_META(slug): return _p(slug, "other_faces_meta.jsonl")
def FEEDBACK(slug): return _p(slug, "feedback.jsonl")
def JUDGE(slug): return _p(slug, "judge.json")
def CROP_PREFS(slug): return _p(slug, "crop_prefs.json")

BASE_THRESHOLD = 0.32
BORDERLINE = 0.06          # decisions within this of the cutoff are logged for review
JUDGE_MIN_ROWS = 200      # feedback rows needed before the judge takes over
_DEDUP_SIM = 0.97          # near-identical embeddings are not added twice


def _ensure(slug: str):
    os.makedirs(learning_dir(slug), exist_ok=True)


# --------------------------------------------------------------------------- #
# the "other people" bank
# --------------------------------------------------------------------------- #
def _load_bank(slug: str) -> np.ndarray:
    if os.path.isfile(OTHER_NPY(slug)):
        return np.load(OTHER_NPY(slug)).astype(np.float32)
    return np.zeros((0, 512), dtype=np.float32)


def add_others(embs, profile_slug: str, source: str = ""):
    """embs: iterable of unit 512-vectors known not to be this person."""
    _ensure(profile_slug)
    embs = [np.asarray(e, dtype=np.float32) for e in embs if e is not None]
    if not embs:
        return 0
    bank = _load_bank(profile_slug)
    added = 0
    rows = []
    for e in embs:
        e = e / (np.linalg.norm(e) + 1e-9)
        if len(bank) and float((bank @ e).max()) >= _DEDUP_SIM:
            continue
        bank = np.vstack([bank, e[None, :]])
        rows.append({"i": len(bank) - 1, "profile": profile_slug,
                     "source": os.path.basename(source),
                     "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        added += 1
    if added:
        np.save(OTHER_NPY(profile_slug), bank.astype(np.float16))
        with open(OTHER_META(profile_slug), "a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    return added


def bank_size(slug: str) -> int:
    return len(_load_bank(slug))


def adaptive_threshold(slug: str, identity_mean: np.ndarray,
                       self_sims: np.ndarray | None = None) -> float:
    """
    cutoff = safely between the closest OTHER face and the person's own faces.
    Falls back to BASE_THRESHOLD when the bank is too small to be informative.
    """
    bank = _load_bank(slug)
    if len(bank) < 25:
        return BASE_THRESHOLD
    m = identity_mean / (np.linalg.norm(identity_mean) + 1e-9)
    nearest_other = float((bank @ m).max())
    lo = nearest_other + 0.06
    if self_sims is not None and len(self_sims):
        own_floor = float(np.percentile(self_sims, 10)) - 0.05
        hi = max(BASE_THRESHOLD, own_floor)
        cutoff = min(max(lo, BASE_THRESHOLD), max(hi, BASE_THRESHOLD))
    else:
        cutoff = max(lo, BASE_THRESHOLD)
    return float(np.clip(cutoff, BASE_THRESHOLD, 0.55))


# --------------------------------------------------------------------------- #
# feedback log
# --------------------------------------------------------------------------- #
def log_decision(profile_slug: str, sim: float, second: float, multi: bool,
                 kept: bool, source: str, decided_by: str = "auto",
                 borderline: bool = False):
    _ensure(profile_slug)
    # `source` is kept as the bare filename because every row ever written
    # used that, and the user/auto rows for one photo have to keep matching
    # each other. But a filename alone cannot find the photo again: 17 of
    # Susana's 22 uncertain photos have a name that exists in more than one
    # archive folder, and IMG_0110.JPG exists in eight. So record the full
    # path alongside it. Without this the review screen can only ever show a
    # name and a number, which is no basis for judging whether it is her.
    # Stored exactly as given when it is already absolute, and dropped
    # otherwise. abspath() is not used: on a path with a single leading
    # backslash - which is how a UNC path arrives when a shell has eaten one,
    # and that has happened here before - it silently invents a drive-letter
    # path that does not exist, and a confidently wrong path is worse than no
    # path. A relative one is no use later either; the folder it was relative
    # to is long gone by review time.
    full = source if os.path.isabs(source) else ""
    # sim/second may be None: a person judging a face in the review window is
    # telling us the ANSWER, not a measurement. Writing 0.0 there would look
    # like a real reading of zero and train_judge() would fit to it - and one
    # fake row at 0.0 among real ones around 0.35 also drags the column mean
    # and spread it standardises by. A row with no scores is still ground
    # truth for "has this been decided"; it just teaches the judge nothing.
    row = {"profile": profile_slug,
           "sim": None if sim is None else round(float(sim), 4),
           "second": None if second is None else round(float(second), 4),
           "multi": bool(multi),
           "kept": bool(kept), "source": os.path.basename(source),
           "path": full,
           "by": decided_by, "borderline": bool(borderline),
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(FEEDBACK(profile_slug), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def scores_for(profile_slug: str, source: str):
    """The scores the search measured for this photo -> (sim, second, multi).

    A person looking at a face in the review window knows the answer but not
    the numbers. The numbers already exist: the search wrote them down when it
    could not call this photo, which is why the photo is in the folder at all.
    Pairing the person's verdict with the search's own measurement is what
    makes it a training example - "at these readings, the answer was her".
    Without it a confirmation teaches nothing.
    """
    if not os.path.isfile(FEEDBACK(profile_slug)):
        return None
    base = os.path.basename(source)
    best = None
    with open(FEEDBACK(profile_slug), encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if (r.get("profile") == profile_slug and r.get("source") == base
                    and r.get("by") != "user" and r.get("sim") is not None):
                if best is None or str(r.get("at", "")) >= str(best.get("at", "")):
                    best = r
    if best is None:
        return None
    return (best["sim"], best["second"], bool(best.get("multi")))


def apply_review(profile_slug: str, source: str, keep: bool,
                 sim: float, second: float, multi: bool):
    log_decision(profile_slug, sim, second, multi, keep, source,
                 decided_by="user", borderline=False)
    train_judge(profile_slug)          # refit whenever new ground truth arrives


# --------------------------------------------------------------------------- #
# the small trained judge
# --------------------------------------------------------------------------- #
def _features(sim: float, second: float, multi: bool) -> np.ndarray:
    return np.array([1.0, sim, sim * sim, second, sim - second, 1.0 if multi else 0.0])


def train_judge(slug: str) -> bool:
    """Fit THIS person's judge to the user's answers about this person - and ONLY
    to the user's answers.

    Seek logs the calls it is not sure about (by="auto"). Those rows record a
    guess, not the truth: the photo is set aside precisely because Seek could
    not tell whether it is her. They used to be fitted too, as if the guess
    were the answer - an unsure "her" taught the judge that the face was her,
    an unsure "not her" that it was not, and every rescan of the same photo
    added another copy of the guess (Susana: 224 guesses for 22 photos). The
    user, 2026-09-14: that is not acceptable in an app built for accuracy.
    Auto rows are still written: an answer in Needs review takes its scores
    from them (scores_for), which is what makes the answer a usable example.
    """
    if not os.path.isfile(FEEDBACK(slug)):
        return False
    X, y = [], []
    with open(FEEDBACK(slug), encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("by") != "user":
                continue          # Seek's own unsure guess - never ground truth
            if r.get("sim") is None or r.get("second") is None:
                continue          # a decision with no measurement behind it
            X.append(_features(r["sim"], r["second"], r["multi"]))
            y.append(1.0 if r["kept"] else 0.0)
    if len(X) < JUDGE_MIN_ROWS or len(set(y)) < 2:
        return False
    X = np.stack(X)
    y = np.array(y)
    # standardise columns 1.. (leave the bias term)
    mu = X[:, 1:].mean(axis=0)
    sd = X[:, 1:].std(axis=0) + 1e-6
    Xs = X.copy()
    Xs[:, 1:] = (X[:, 1:] - mu) / sd

    w = np.zeros(Xs.shape[1])
    for _ in range(400):                       # plain gradient descent
        p = 1.0 / (1.0 + np.exp(-Xs @ w))
        w -= 0.1 * (Xs.T @ (p - y)) / len(y)

    _ensure(slug)
    with open(JUDGE(slug), "w", encoding="utf-8") as fh:
        json.dump({"w": w.tolist(), "mu": mu.tolist(), "sd": sd.tolist(),
                   "rows": len(y), "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, fh)
    _JUDGE_CACHE.pop(slug, None)
    return True


_JUDGE_CACHE: dict = {}          # one judge per person, never shared


def judge_prob(slug: str, sim: float, second: float, multi: bool) -> float | None:
    j = _JUDGE_CACHE.get(slug)
    if j is None:
        if not os.path.isfile(JUDGE(slug)):
            return None
        with open(JUDGE(slug), encoding="utf-8") as fh:
            j = _JUDGE_CACHE[slug] = json.load(fh)
    x = _features(sim, second, multi)
    x[1:] = (x[1:] - np.array(j["mu"])) / np.array(j["sd"])
    return float(1.0 / (1.0 + np.exp(-np.dot(np.array(j["w"]), x))))


def judge_info(slug: str) -> dict | None:
    if not os.path.isfile(JUDGE(slug)):
        return None
    with open(JUDGE(slug), encoding="utf-8") as fh:
        j = json.load(fh)
    return {"rows": j["rows"], "trained_at": j["trained_at"]}


# --------------------------------------------------------------------------- #
# crop-margin preferences  (nudged by which crops the user keeps vs deletes)
# --------------------------------------------------------------------------- #
def load_crop_prefs(slug: str) -> dict:
    if os.path.isfile(CROP_PREFS(slug)):
        try:
            with open(CROP_PREFS(slug), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            pass
    return {}


def nudge_crop_prefs(slug: str, kept: int, deleted_head: int, deleted_body: int):
    """The user deleting many of THIS person's head crops -> widen this person's
    head margin a little; many body crops -> widen the body strip. Small steps,
    clamped."""
    _ensure(slug)
    p = load_crop_prefs(slug)
    total = kept + deleted_head + deleted_body
    if total < 15:
        return
    from face_training import sort_photos as S
    he = p.get("head_expand", dict(S.HEAD_EXPAND))
    bsp = p.get("body_side_pad", S.BODY_SIDE_PAD)
    if deleted_head / total > 0.25:
        for k in he:
            he[k] = min(he[k] + 0.08, 1.4)
    if deleted_body / total > 0.25:
        bsp = min(bsp + 0.15, 2.0)
    p.update({"head_expand": he, "body_side_pad": bsp,
              "updated_from": p.get("updated_from", 0) + total,
              "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    with open(CROP_PREFS(slug), "w", encoding="utf-8") as fh:
        json.dump(p, fh, indent=2)


def decide(slug: str, sim: float, second: float, multi: bool,
           cutoff: float) -> tuple[bool, bool]:
    """
    The single "is this her?" decision for this person, used everywhere in Seek.
    Returns (is_her, is_borderline).
    """
    prob = judge_prob(slug, sim, second, multi)
    if prob is not None:
        is_her = prob >= 0.5
        borderline = 0.35 <= prob <= 0.65
        return is_her, borderline
    # no judge yet: fixed cutoff + the ambiguity rule
    if sim < cutoff:
        return False, (cutoff - BORDERLINE) <= sim < cutoff
    if multi and sim < 0.45 and (sim - second) < 0.10:
        return False, True
    return True, sim < (cutoff + BORDERLINE)
