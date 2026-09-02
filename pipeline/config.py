from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SplitConfig:
    train_max_week: int = 21
    validation_min_week: int = 22
    validation_max_week: int = 23
    test_min_week: int = 24


@dataclass(frozen=True)
class BusinessConfig:
    delay_effectiveness: float = 0.758
    warning_effectiveness: float = 0.215
    blocked_hours: float = 9.0
    ops_contact_probability: float = 0.34
    hour_value_mxn: float = 10.0
    warning_cost_mxn: float = 2.0
    ops_cost_mxn: float = 50.0


@dataclass(frozen=True)
class ModelConfig:
    random_state: int = 42
    n_estimators: int = 300
    max_depth: int = 4
    learning_rate: float = 0.05
    subsample: float = 0.8
    min_samples_leaf: int = 100


@dataclass(frozen=True)
class PipelineConfig:
    data_dir: Path = REPO_ROOT / "data" / "raw"
    processed_dir: Path = REPO_ROOT / "data" / "processed"
    artifacts_dir: Path = REPO_ROOT / "artifacts"
    splits: SplitConfig = field(default_factory=SplitConfig)
    business: BusinessConfig = field(default_factory=BusinessConfig)
    model: ModelConfig = field(default_factory=ModelConfig)

    @property
    def cleaned_dir(self) -> Path:
        return self.processed_dir / "cleaned"

    @property
    def prepared_dir(self) -> Path:
        return self.processed_dir / "prepared"

    @property
    def aggregated_dir(self) -> Path:
        return self.processed_dir / "aggregated"

    def to_dict(self) -> dict:
        result = asdict(self)
        result["data_dir"] = str(self.data_dir)
        result["processed_dir"] = str(self.processed_dir)
        result["artifacts_dir"] = str(self.artifacts_dir)
        return result
