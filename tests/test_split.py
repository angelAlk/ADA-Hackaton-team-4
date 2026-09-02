import pandas as pd

from pipeline.config import SplitConfig
from pipeline.split import temporal_split


def test_temporal_split_is_disjoint_and_reproducible(tmp_path):
    frame = pd.DataFrame(
        {
            "txn_id": [6, 1, 2, 3, 4, 5],
            "txn_ts": pd.to_datetime(
                [
                    "2026-06-10",
                    "2026-05-01",
                    "2026-05-02",
                    "2026-05-25",
                    "2026-06-01",
                    "2026-06-02",
                ]
            ),
            "txn_week": [24, 18, 18, 22, 23, 24],
            "label": [1, 0, 1, 0, 1, 0],
        }
    )
    first, first_manifest = temporal_split(frame, SplitConfig(), tmp_path / "first")
    second, second_manifest = temporal_split(frame, SplitConfig(), tmp_path / "second")

    assert set(first["train"]["txn_id"]) == {1, 2}
    assert set(first["validation"]["txn_id"]) == {3, 4}
    assert set(first["test"]["txn_id"]) == {5, 6}
    assert first_manifest["splits"] == second_manifest["splits"]
    assert first_manifest["random_seed_used_for_membership"] is False
