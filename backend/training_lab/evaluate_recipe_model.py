from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

from common import RECIPE_KEYS, build_feature_vector, load_jsonl, record_target_recipe

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "data" / "ai" / "training_dataset.jsonl"


def main():
    if not DATASET_PATH.exists():
        print(f"Dataset not found: {DATASET_PATH}")
        print("Run POST /api/brain/dataset/export first.")
        return

    rows = load_jsonl(DATASET_PATH)
    X = []
    y = []

    for record in rows:
        target = record_target_recipe(record)
        if not target:
            continue
        names, features = build_feature_vector(record)
        if names is None or features is None:
            continue
        X.append(features)
        y.append([target[k] for k in RECIPE_KEYS])

    if len(X) < 10:
        print(f"Need at least 10 labeled samples for a useful evaluation. Found: {len(X)}")
        return

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=float)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
    )

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    print("Evaluation complete")
    print(f"Train samples: {len(X_train)}")
    print(f"Test samples:  {len(X_test)}")
    print("")

    overall = mean_absolute_error(y_test, pred)
    print(f"Overall MAE: {overall:.4f}")
    print("Per slider MAE:")
    for idx, key in enumerate(RECIPE_KEYS):
        mae = mean_absolute_error(y_test[:, idx], pred[:, idx])
        print(f"  {key:12s} {mae:.4f}")


if __name__ == "__main__":
    main()
