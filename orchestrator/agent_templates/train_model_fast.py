from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import log_loss, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor


def _build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    categorical_cols = [c for c in X.columns if X[c].dtype == "object" or str(X[c].dtype).startswith("category")]
    numeric_cols = [c for c in X.columns if c not in categorical_cols]

    numeric_pipe = Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))])
    categorical_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric_cols),
            ("cat", categorical_pipe, categorical_cols),
        ],
        remainder="drop",
    )


def _sigmoid(x: np.ndarray) -> np.ndarray:
    # Stable-ish sigmoid.
    x = np.clip(x, -50, 50)
    return 1.0 / (1.0 + np.exp(-x))


def main() -> int:
    root = Path(".")
    public = root / "public"
    train_path = public / "train_public.csv"
    test_path = public / "test_public.csv"
    sample_path = public / "sample_submission.csv"

    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)
    sample = pd.read_csv(sample_path)

    id_col = str(sample.columns[0])
    pred_cols = [str(c) for c in sample.columns[1:]]

    # Infer target column as the column present in train but not test (excluding id).
    missing_in_test = [c for c in train.columns if c not in test.columns]
    missing_in_test = [c for c in missing_in_test if str(c) != id_col]
    if not missing_in_test:
        raise RuntimeError("Could not infer target column from (train_public - test_public).")
    target_col = str(missing_in_test[0])

    X = train.drop(columns=[target_col])
    y = train[target_col]

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    pre = _build_preprocessor(X_train)

    submission = pd.DataFrame({id_col: test[id_col].values})

    if len(pred_cols) <= 1:
        pred_col = pred_cols[0] if pred_cols else "prediction"
        # Binary classification heuristic: y has only 2 unique values.
        is_binary = y.nunique(dropna=False) == 2
        if is_binary:
            model = HistGradientBoostingClassifier(random_state=42)
            pipe = Pipeline([("pre", pre), ("model", model)])
            pipe.fit(X_train, y_train)
            proba_val = pipe.predict_proba(X_val)[:, 1]
            val_ll = float(log_loss(y_val, proba_val))
            print(f"local_valid_logloss: {val_ll:.6f}")

            proba_test = pipe.predict_proba(test)[:, 1]
            proba_test = np.clip(proba_test, 1e-6, 1 - 1e-6)
            submission[pred_col] = proba_test
        else:
            model = HistGradientBoostingRegressor(random_state=42)
            pipe = Pipeline([("pre", pre), ("model", model)])
            pipe.fit(X_train, y_train)
            pred_val = pipe.predict(X_val)
            rmse = math.sqrt(mean_squared_error(y_val, pred_val))
            print(f"local_valid_rmse: {rmse:.6f}")

            pred_test = pipe.predict(test)
            submission[pred_col] = pred_test
    else:
        # Multiclass: output per-class probabilities for columns in sample submission.
        model = HistGradientBoostingClassifier(random_state=42)
        pipe = Pipeline([("pre", pre), ("model", model)])
        pipe.fit(X_train, y_train)

        proba_val = pipe.predict_proba(X_val)
        try:
            val_ll = float(log_loss(y_val, proba_val))
            print(f"local_valid_logloss: {val_ll:.6f}")
        except Exception:
            pass

        proba_test = pipe.predict_proba(test)
        # Map classes to columns by string match; fallback to uniform if mismatch.
        classes = [str(c) for c in getattr(pipe.named_steps["model"], "classes_", [])]
        class_to_idx = {c: i for i, c in enumerate(classes)}
        for c in pred_cols:
            if c in class_to_idx:
                submission[c] = proba_test[:, class_to_idx[c]]
            else:
                submission[c] = 1.0 / float(len(pred_cols))

    out_path = root / "submission.csv"
    submission.to_csv(out_path, index=False)
    print(f"wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

