"""
Build and use a person's face identity model.

An identity is an averaged ArcFace embedding (from InsightFace buffalo_l) plus
the list of reference faces it was built from. It is stored in a profile's
``identity/`` folder as plain files so it persists and can be inspected.

  build_identity(seed_folder, best_photo)  -> Identity
  Identity.match(face)                     -> cosine similarity 0..1
  Identity.save(dir) / Identity.load(dir)

Runs in the OneTrainer venv (insightface, onnxruntime, opencv, numpy, PIL).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np

from face_training.sort_photos import (
    HEAD_RATIO, MIN_DET_SCORE, _detect, _face_h, _get_app, _list_images,
    _load_bgr,
)

# a reference face must be at least this similar to the anchor (best photo) to
# be trusted into the identity
ANCHOR_MIN_SIM = 0.28
# used when no anchor is supplied: keep refs close to the first mean estimate
SELF_MIN_SIM = 0.30


@dataclass
class Identity:
    mean: np.ndarray                       # unit vector, shape (512,)
    ref_paths: list[str] = field(default_factory=list)
    ref_embeds: np.ndarray | None = None    # (N, 512) unit vectors
    anchor_path: str = ""
    warnings: list[str] = field(default_factory=list)

    # --- matching ---------------------------------------------------------
    def match(self, face) -> float:
        return float(np.dot(face.normed_embedding, self.mean))

    def match_emb(self, emb: np.ndarray) -> float:
        return float(np.dot(emb, self.mean))

    @property
    def n_refs(self) -> int:
        return len(self.ref_paths)

    # --- persistence -----------------------------------------------------
    def save(self, id_dir: str):
        os.makedirs(id_dir, exist_ok=True)
        np.save(os.path.join(id_dir, "mean.npy"), self.mean)
        if self.ref_embeds is not None:
            np.save(os.path.join(id_dir, "refs.npy"), self.ref_embeds)
        with open(os.path.join(id_dir, "refs.json"), "w", encoding="utf-8") as fh:
            json.dump({"ref_paths": self.ref_paths,
                       "anchor_path": self.anchor_path,
                       "warnings": self.warnings}, fh, indent=2)

    @staticmethod
    def load(id_dir: str) -> "Identity":
        mean = np.load(os.path.join(id_dir, "mean.npy"))
        refs_p = os.path.join(id_dir, "refs.npy")
        refs = np.load(refs_p) if os.path.isfile(refs_p) else None
        meta = {}
        mp = os.path.join(id_dir, "refs.json")
        if os.path.isfile(mp):
            with open(mp, encoding="utf-8") as fh:
                meta = json.load(fh)
        return Identity(mean=mean, ref_embeds=refs,
                        ref_paths=meta.get("ref_paths", []),
                        anchor_path=meta.get("anchor_path", ""),
                        warnings=meta.get("warnings", []))


def _unit(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-9)


# Two anchors that disagree by more than this are probably not the same person,
# which usually means the wrong file got picked in the chooser.
ANCHOR_AGREE_MIN = 0.45


def _anchor_from_many(best_photos, warnings) -> tuple[np.ndarray | None, str]:
    """Average the anchor photos into one reference embedding.

    One anchor is one lighting, one angle, one day. If that single photo is
    unflattering or oddly lit, every reference face gets judged against a
    slightly wrong idea of the person. Averaging two spreads that risk, and -
    more usefully - lets us check the two against each other: if they disagree
    badly it is almost always the wrong file in the chooser, which is worth
    saying out loud before it quietly poisons the whole profile.
    """
    paths = [p for p in (best_photos or []) if p]
    embs, used = [], []
    for p in paths:
        e = _anchor_embedding(p)
        if e is None:
            warnings.append(f"could not read a face from the anchor photo "
                            f"({os.path.basename(p)}); ignoring it")
        else:
            embs.append(e)
            used.append(p)
    if not embs:
        return None, "", [], []
    if len(embs) >= 2:
        agree = float(np.dot(embs[0], embs[1]))
        if agree < ANCHOR_AGREE_MIN:
            warnings.append(
                f"the two anchor photos look like different people "
                f"(similarity {agree:.2f}) - check you picked the right files; "
                f"using them both anyway")
    return _unit(np.mean(embs, axis=0)), used[0], embs, used


def _anchor_embedding(best_photo: str) -> np.ndarray | None:
    if not best_photo or not os.path.isfile(best_photo):
        return None
    img = _load_bgr(best_photo)
    if img is None:
        return None
    faces = _detect(_get_app(), img)
    if not faces:
        return None
    return faces[0].normed_embedding          # largest face


def build_identity(seed_folder: str, best_photo="",
                   extra_embeds: np.ndarray | None = None) -> Identity:
    """
    seed_folder   folder of the person's photos to learn from
    best_photo    the clearest photo(s) - a single path or a list of them -
                  used as an anchor to reject reference faces that are not
                  actually her. Two is better than one: see _anchor_from_many.
    extra_embeds  (N,512) unit vectors already confirmed as her (used when
                  re-teaching from gathered crops)
    """
    # Since 2026-09-13 a person is added from two chosen photos alone, with no
    # starter folder (seed_folder ""). Older profiles still carry a folder, and it
    # is still used when present.
    if seed_folder and not os.path.isdir(seed_folder):
        raise FileNotFoundError(seed_folder)

    app = _get_app()
    warnings: list[str] = []

    anchor_paths = [best_photo] if isinstance(best_photo, str) else list(best_photo or [])
    anchor_paths = [p for p in anchor_paths if p]
    anchor, anchor_first, anchor_embs, anchor_used = _anchor_from_many(anchor_paths, warnings)
    if anchor_paths and anchor is None:
        warnings.append("could not read a face from any chosen best photo; "
                        "learning without an anchor")

    solo, solo_paths = [], []
    for p in (_list_images(seed_folder) if seed_folder else []):
        img = _load_bgr(p)
        if img is None:
            continue
        faces = [f for f in _detect(app, img) if float(f.det_score) >= MIN_DET_SCORE]
        if len(faces) != 1:
            continue
        f = faces[0]
        if _face_h(f) / img.shape[0] < HEAD_RATIO * 0.7:   # tiny faces are unreliable refs
            continue
        emb = f.normed_embedding
        if anchor is not None and float(np.dot(emb, anchor)) < ANCHOR_MIN_SIM:
            continue                                        # not her
        solo.append(emb)
        solo_paths.append(p)

    if anchor is not None and not solo:
        # No folder, or nothing in it matched: the chosen photos themselves are
        # the reference faces - each one on its own, so two photos are two refs.
        solo = list(anchor_embs)
        solo_paths = list(anchor_used)
        if seed_folder:
            warnings.append("no folder photo matched the best photo closely; using "
                            "the chosen photo(s) alone as the reference")

    if not solo and seed_folder:
        # last resort: any single-face photo
        for p in _list_images(seed_folder):
            img = _load_bgr(p)
            if img is None:
                continue
            faces = [f for f in _detect(app, img) if float(f.det_score) >= MIN_DET_SCORE]
            if len(faces) == 1:
                solo.append(faces[0].normed_embedding)
                solo_paths.append(p)

    if not solo:
        raise ValueError("no clear single-face photo found to learn the person from")

    embeds = np.stack([_unit(e) for e in solo])
    paths = list(solo_paths)
    if extra_embeds is not None and len(extra_embeds):
        extra = np.stack([_unit(e) for e in extra_embeds])
        embeds = np.vstack([embeds, extra])
        paths += [""] * len(extra)

    mean = _unit(embeds.mean(axis=0))
    # refine: drop refs that pull away from the consensus, re-average
    cutoff = SELF_MIN_SIM if anchor is None else ANCHOR_MIN_SIM
    keep = (embeds @ mean) >= cutoff
    if keep.sum() >= 3:
        embeds = embeds[keep]
        paths = [p for p, k in zip(paths, keep) if k]
        mean = _unit(embeds.mean(axis=0))

    if len(embeds) < 3:
        warnings.append(f"identity learned from only {len(embeds)} face(s); "
                        f"matching may be shaky until Seek gathers more")

    return Identity(mean=mean, ref_paths=paths, ref_embeds=embeds,
                    anchor_path=anchor_first, warnings=warnings)
