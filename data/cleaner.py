#!/usr/env python

# Validate and clean the four source parquet files. Originals are untouched.

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import PipelineConfig
from pipeline.data import clean_sources


def main():
    config = PipelineConfig()
    report = clean_sources(config.data_dir, config.cleaned_dir)
    for name, result in report["tables"].items():
        print(f"{name}: {result['source_rows']:,} -> {result['clean_rows']:,} rows")
    print(f"Quality report: {config.cleaned_dir / 'quality_report.json'}")


if __name__ == "__main__":
    main()
