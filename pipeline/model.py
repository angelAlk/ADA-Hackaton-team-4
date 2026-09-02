from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline

from .config import PipelineConfig
from .features import BINARY_FEATURES, FEATURE_COLUMNS, NUMERIC_FEATURES


class MedianWithIndicator(BaseEstimator, TransformerMixin):
    """Train-fitted median imputation with one stable indicator per input."""

    def fit(self, X, y=None):
        array = np.asarray(X, dtype=float)
        self.medians_ = np.nanmedian(array, axis=0)
        self.medians_ = np.where(np.isnan(self.medians_), 0.0, self.medians_)
        self.n_features_in_ = array.shape[1]
        return self

    def transform(self, X):
        array = np.asarray(X, dtype=float)
        missing = np.isnan(array).astype(float)
        filled = np.where(np.isnan(array), self.medians_, array)
        return np.concatenate([filled, missing], axis=1)

    def get_feature_names_out(self, input_features=None):
        names = (
            list(input_features)
            if input_features is not None
            else [f"x{i}" for i in range(self.n_features_in_)]
        )
        return np.asarray(names + [f"{name}_missing" for name in names], dtype=object)


def build_estimator(config: PipelineConfig) -> Pipeline:
    preprocessing = ColumnTransformer(
        [
            ("numeric", MedianWithIndicator(), NUMERIC_FEATURES),
            (
                "binary",
                SimpleImputer(strategy="constant", fill_value=0),
                BINARY_FEATURES,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    params = config.model
    classifier = GradientBoostingClassifier(
        n_estimators=params.n_estimators,
        max_depth=params.max_depth,
        learning_rate=params.learning_rate,
        subsample=params.subsample,
        min_samples_leaf=params.min_samples_leaf,
        random_state=params.random_state,
    )
    return Pipeline([("preprocess", preprocessing), ("model", classifier)])


def classification_metrics(labels: pd.Series, scores: np.ndarray) -> dict:
    return {
        "rows": len(labels),
        "positives": int(labels.sum()),
        "base_rate": float(labels.mean()),
        "pr_auc": float(average_precision_score(labels, scores)),
        "roc_auc": float(roc_auc_score(labels, scores)),
    }


def train_model(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    config: PipelineConfig,
) -> tuple[Pipeline, dict]:
    estimator = build_estimator(config)
    y_train = train["label"].astype(int)
    negatives = int((y_train == 0).sum())
    positives = int((y_train == 1).sum())
    if positives == 0:
        raise ValueError("training set has no positive labels")
    scale_pos = negatives / positives
    sample_weight = np.where(y_train.to_numpy() == 1, scale_pos, 1.0)
    estimator.fit(
        train[FEATURE_COLUMNS],
        y_train,
        model__sample_weight=sample_weight,
    )

    train_scores = estimator.predict_proba(train[FEATURE_COLUMNS])[:, 1]
    validation_scores = estimator.predict_proba(validation[FEATURE_COLUMNS])[:, 1]
    transformed_names = estimator.named_steps["preprocess"].get_feature_names_out().tolist()
    importances = estimator.named_steps["model"].feature_importances_
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_type": "sklearn.ensemble.GradientBoostingClassifier",
        "random_state": config.model.random_state,
        "model_parameters": config.to_dict()["model"],
        "source_features": FEATURE_COLUMNS,
        "transformed_features": transformed_names,
        "class_weight_ratio": scale_pos,
        "metrics": {
            "train": classification_metrics(y_train, train_scores),
            "validation": classification_metrics(
                validation["label"].astype(int), validation_scores
            ),
        },
        "versions": {
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    numeric = estimator.named_steps["preprocess"].named_transformers_["numeric"]
    metadata["train_medians"] = dict(zip(NUMERIC_FEATURES, numeric.medians_.tolist()))
    metadata["feature_importance"] = dict(
        sorted(zip(transformed_names, importances.tolist()), key=lambda item: -item[1])
    )
    return estimator, metadata


def save_model(estimator: Pipeline, metadata: dict, artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(estimator, artifacts_dir / "fraud_model.joblib")
    (artifacts_dir / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    )


def load_model(artifacts_dir: Path) -> tuple[Pipeline, dict]:
    estimator = joblib.load(artifacts_dir / "fraud_model.joblib")
    metadata = json.loads((artifacts_dir / "model_metadata.json").read_text())
    return estimator, metadata
