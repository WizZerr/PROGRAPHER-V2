from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from common import RECIPE_KEYS, build_feature_vector, load_jsonl, record_target_recipe


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "data" / "ai" / "training_dataset.jsonl"
MODEL_DIR = ROOT / "data" / "ai" / "models"
MODEL_PATH = MODEL_DIR / "recipe_model_v1.joblib"


def main():
    if not DATASET_PATH.exists():
        print(f"Dataset not found: {DATASET_PATH}")
        print("Run POST /api/brain/dataset/export first.")
        return

    rows = load_jsonl(DATASET_PATH)
    X = []
    y = []
    feature_names = None

    for record in rows:
        target = record_target_recipe(record)
        if not target:
            continue

        names, features = build_feature_vector(record)
        if names is None or features is None:
            continue

        if feature_names is None:
            feature_names = names

        X.append(features)
        y.append([target[k] for k in RECIPE_KEYS])

    if len(X) < 5:
        print(f"Not enough labeled samples to train a meaningful model. Found: {len(X)}")
        return

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=float)

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=1,
    )
    model.fit(X, y)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": model,
        "feature_names": feature_names,
        "recipe_keys": RECIPE_KEYS,
        "sample_count": int(len(X)),
        "model_type": "RandomForestRegressor",
    }
    joblib.dump(artifact, MODEL_PATH)

    print("Training complete.")
    print(f"Model saved to: {MODEL_PATH}")
    print(f"Samples used: {len(X)}")
    print(f"Features: {len(feature_names or [])}")
    print("Recipe keys:", ", ".join(RECIPE_KEYS))


if __name__ == "__main__":
    main()
