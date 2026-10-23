"""QA C3 (post-fix): prove that a *real* model artifact round-trips and predicts.

The 359 artifacts under ``ml_artifacts/`` were produced by an external training
toolchain that is not in this repository, and none of them can be unpickled
(N3/N4 in reports/REMEDIATION_REPORT.md). To show that the loader path itself
is now correct, this script trains a small real sklearn pipeline, stores it with
the project's own ``ArtifactManager``, and reads it back with the project's own
``ModelLoader`` — including the integrity gate and the zlib layout.

Usage:
    venv/Scripts/python.exe qa/c3_roundtrip_check.py

Writes:
    reports/c3_roundtrip.json
"""
from __future__ import annotations

import json
import sys
import tempfile
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS: dict = {"cases": []}


def record(name: str, ok: bool, detail: str = "", **extra) -> None:
    RESULTS["cases"].append({"case": name, "ok": bool(ok), "detail": detail, **extra})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def build_pipeline():
    """A real sklearn Pipeline, not a stub: imputer + scaler + regressor."""
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    num = Pipeline([("imputer", SimpleImputer()), ("scaler", StandardScaler())])
    return Pipeline(
        [
            ("preprocessor", ColumnTransformer([("num", num, ["a", "b", "c"])])),
            ("regressor", LinearRegression()),
        ]
    )


def main() -> int:
    from ml.artifacts import ArtifactManager, decode_artifact_bytes, load_artifact_file
    from ml.model_loader import ModelLoader
    from ml.types import ModelArtifactMeta

    rng = np.random.default_rng(7)
    n, feats = 200, ["a", "b", "c"]
    Xn = rng.normal(size=(n, len(feats)))
    y = 3.0 * Xn[:, 0] - 2.0 * Xn[:, 1] + 0.5 * Xn[:, 2] + rng.normal(scale=0.01, size=n)
    # Real feature frames, exactly like the artifacts being reproduced: named
    # columns, with a missing value so the imputer step is genuinely exercised.
    X = pd.DataFrame(Xn, columns=feats)
    X.iloc[0, 0] = np.nan

    pipeline = build_pipeline()
    pipeline.fit(X, y)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # ── Case 1: the project's own writer round-trips through its own loader
        manager = ArtifactManager(base_dir=str(base))
        meta = ModelArtifactMeta(
            model_id="linear_TEST",
            version="v1-test",
            feature_names=feats,
            stage="production",
        )
        manager.save_model(pipeline, meta)

        loader = ModelLoader(base_dir=str(base))
        loaded = loader._load_from_disk("linear_TEST@v1-test")
        record("ArtifactManager -> ModelLoader round-trip", loaded is not None)

        pred_file = np.asarray(loaded.predict(X.iloc[:5]), dtype=float)
        pred_ref = np.asarray(pipeline.predict(X.iloc[:5]), dtype=float)
        record(
            "predictions match the trained model",
            bool(np.allclose(pred_file, pred_ref, rtol=1e-9, atol=1e-9)),
            f"max|Δ| = {np.max(np.abs(pred_file - pred_ref)):.3e}",
        )

        # ── Case 2: the integrity gate still refuses a tampered artifact
        model_file = base / "linear_TEST" / "v1-test" / "model.pkl"
        original = model_file.read_bytes()
        model_file.write_bytes(original + b"\x00")
        tampered_failed = False
        try:
            loader._load_from_disk("linear_TEST@v1-test")
        except ValueError as exc:
            tampered_failed = "integrity check FAILED" in str(exc)
        record("tampered artifact is refused (audit ML-007)", tampered_failed)
        model_file.write_bytes(original)

        # ── Case 3: the zlib layout the external trainer uses
        zdir = base / "zlib_model" / "v1-test"
        zdir.mkdir(parents=True, exist_ok=True)
        zfile = zdir / "model_pipeline.pkl"
        zfile.write_bytes(zlib.compress(pickle_bytes := __import__("pickle").dumps(pipeline)))
        record(
            "decode_artifact_bytes inflates a zlib artifact",
            decode_artifact_bytes(zfile.read_bytes()) == pickle_bytes,
        )
        zloaded = load_artifact_file(zfile)
        record(
            "zlib artifact predicts identically",
            bool(np.allclose(np.asarray(zloaded.predict(X.iloc[:5]), dtype=float), pred_ref, rtol=1e-9)),
        )

        # ── Case 4: a bare pickle that is NOT zlib still loads
        bare = load_artifact_file(model_file)
        record(
            "bare pickle still loads (regression guard)",
            bool(np.allclose(np.asarray(bare.predict(X.iloc[:5]), dtype=float), pred_ref, rtol=1e-9)),
        )

    passed = sum(1 for c in RESULTS["cases"] if c["ok"])
    RESULTS["summary"] = {
        "passed": passed,
        "total": len(RESULTS["cases"]),
        "all_ok": passed == len(RESULTS["cases"]),
    }
    dest = ROOT / "reports" / "c3_roundtrip.json"
    dest.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{passed}/{len(RESULTS['cases'])} cases passed -> {dest.relative_to(ROOT)}")
    return 0 if passed == len(RESULTS["cases"]) else 1


if __name__ == "__main__":
    sys.exit(main())