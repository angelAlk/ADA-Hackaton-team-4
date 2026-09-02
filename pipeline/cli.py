from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .config import PipelineConfig
from .data import clean_sources
from .evaluation import evaluate_all, optimize_thresholds
from .features import FEATURE_COLUMNS, prepare_data
from .inference import predict_parquets
from .model import load_model, save_model, train_model
from .split import temporal_split


def clean(config: PipelineConfig) -> None:
    report = clean_sources(config.data_dir, config.cleaned_dir)
    print(json.dumps(report, indent=2))


def prepare(config: PipelineConfig) -> None:
    _, report = prepare_data(config.cleaned_dir, config.prepared_dir)
    print(json.dumps(report, indent=2))


def train(config: PipelineConfig) -> None:
    model_data = pd.read_parquet(config.prepared_dir / "model_data.parquet")
    splits, split_manifest = temporal_split(
        model_data, config.splits, config.artifacts_dir / "splits"
    )
    estimator, metadata = train_model(splits["train"], splits["validation"], config)
    validation_scores = estimator.predict_proba(
        splits["validation"][FEATURE_COLUMNS]
    )[:, 1]
    thresholds, search = optimize_thresholds(
        splits["validation"], validation_scores, config.business
    )
    metadata["decision_thresholds"] = thresholds
    metadata["threshold_selection_dataset"] = "validation"
    metadata["split_manifest"] = split_manifest
    metadata["business_parameters"] = config.to_dict()["business"]
    save_model(estimator, metadata, config.artifacts_dir)
    search.to_csv(config.artifacts_dir / "threshold_search.csv", index=False)
    print(json.dumps(metadata["metrics"], indent=2))
    print(json.dumps({"decision_thresholds": thresholds}, indent=2))


def evaluate(config: PipelineConfig) -> None:
    estimator, metadata = load_model(config.artifacts_dir)
    test = pd.read_parquet(config.artifacts_dir / "splits" / "test.parquet")
    scores = estimator.predict_proba(test[FEATURE_COLUMNS])[:, 1]
    report = evaluate_all(
        test,
        scores,
        metadata["decision_thresholds"],
        config.business,
        config.artifacts_dir,
    )
    print(json.dumps(report, indent=2))


def run_all(config: PipelineConfig) -> None:
    clean(config)
    prepare(config)
    train(config)
    evaluate(config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Temporal MTU fraud training pipeline")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--processed-dir", type=Path)
    parser.add_argument("--artifacts-dir", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("clean", "prepare", "train", "evaluate", "run-all"):
        subparsers.add_parser(command)
    predict_parser = subparsers.add_parser("predict")
    predict_parser.add_argument("--transactions", type=Path, required=True)
    predict_parser.add_argument("--customers", type=Path, required=True)
    predict_parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    config = PipelineConfig()
    if args.data_dir:
        config = replace(config, data_dir=args.data_dir)
    if args.processed_dir:
        config = replace(config, processed_dir=args.processed_dir)
    if args.artifacts_dir:
        config = replace(config, artifacts_dir=args.artifacts_dir)

    commands = {
        "clean": clean,
        "prepare": prepare,
        "train": train,
        "evaluate": evaluate,
        "run-all": run_all,
    }
    if args.command == "predict":
        result = predict_parquets(
            args.transactions,
            args.customers,
            config.artifacts_dir,
            args.output,
        )
        print(f"Wrote {len(result):,} predictions to {args.output}")
    else:
        commands[args.command](config)
