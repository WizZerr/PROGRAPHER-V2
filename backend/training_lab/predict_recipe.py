from __future__ import annotations

import json
from pathlib import Path
import sys

import joblib
import numpy as np

from common import RECIPE_KEYS, build_feature_vector

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "data" / "ai" / "models" / "recipe_model_v1.joblib"


def main():
    if len(sys.argv) < 2:
        print("Usage: python training_lab/predict_recipe.py path_to_record.json")
        return

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return

    if not MODEL_PATH.exists():
        print(f"Model not found: {MODEL_PATH}")
        print("Run train_recipe_model.py first.")
        return

    record = json.loads(input_path.read_text(encoding="utf-8"))
    feature_names, feature_values = build_feature_vector(record)
    if feature_names is None or feature_values is None:
        print("Record does not contain enough data for prediction.")
        return

    artifact = joblib.load(MODEL_PATH)
    model = artifact["model"]
    pred = model.predict(np.array([feature_values], dtype=float))[0]

    recipe = {key: round(float(pred[idx]), 3) for idx, key in enumerate(RECIPE_KEYS)}
    print(json.dumps(recipe, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
