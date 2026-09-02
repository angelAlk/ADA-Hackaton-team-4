from dataclasses import replace

import numpy as np
import pandas as pd

from pipeline.config import ModelConfig, PipelineConfig
from pipeline.features import BINARY_FEATURES, FEATURE_COLUMNS, NUMERIC_FEATURES
from pipeline.model import load_model, save_model, train_model


def model_frame(rows=40):
    data = {}
    for index, column in enumerate(NUMERIC_FEATURES):
        data[column] = np.arange(rows, dtype=float) + index
    for index, column in enumerate(BINARY_FEATURES):
        data[column] = ((np.arange(rows) + index) % 2).astype(int)
    data["label"] = (np.arange(rows) % 5 == 0).astype(int)
    return pd.DataFrame(data)


def test_train_imputes_from_train_and_round_trips(tmp_path):
    train = model_frame()
    validation = model_frame(20)
    validation.loc[0, "amount_mxn"] = np.nan
    config = replace(
        PipelineConfig(artifacts_dir=tmp_path),
        model=ModelConfig(n_estimators=3, max_depth=2, min_samples_leaf=1),
    )

    estimator, metadata = train_model(train, validation, config)
    assert metadata["train_medians"]["amount_mxn"] == 19.5
    assert "amount_mxn_missing" in metadata["transformed_features"]
    before = estimator.predict_proba(validation[FEATURE_COLUMNS])[:, 1]

    save_model(estimator, metadata, tmp_path)
    loaded, loaded_metadata = load_model(tmp_path)
    after = loaded.predict_proba(validation[FEATURE_COLUMNS])[:, 1]
    np.testing.assert_allclose(before, after)
    assert loaded_metadata["random_state"] == 42
