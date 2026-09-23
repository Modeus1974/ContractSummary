"""CLI entrypoint: python summarise.py <contract.pdf|.docx|.md> [options]."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from contract_reviewer import config, docx_report, io_utils
from contract_reviewer.logging_setup import configure_logging, log_model_assignment, log_stage, log_warning
from contract_reviewer.summarize import run_summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Singapore contract summariser CLI")
    parser.add_argument("contract_file", help="Path to the contract PDF, .docx, or .md file")
    parser.add_argument("--client-role", default=None)
    parser.add_argument("--tier", default="balanced", choices=["efficient", "balanced", "flagship"])
    parser.add_argument("--output", default=None, help="Override the default Summary/... output path")
    parser.add_argument("--models-config", default=None, help="Path to models.yaml (default: ./models.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)
    config.load_env()

    models_config_path = Path(args.models_config) if args.models_config else None
    tiers = config.load_tier_config(models_config_path)
    tier = tiers[args.tier]

    source_path = str(Path(args.contract_file).resolve())
    run_id = io_utils.new_run_id()
    log_stage("run", run_id)
    log_stage("summarize", f"tier={args.tier}")

    result = run_summary(source_path, tier, client_role=args.client_role)

    if not result["ok"]:
        log_warning(result["incomplete_reason"])
        print(f"Could not summarise document: {result['incomplete_reason']}", file=sys.stderr)
        return 1

    log_model_assignment(result["model_assignment"])
    for issue in result["fidelity_issues"]:
        log_warning(f"fidelity check: {issue}")

    context = {
        "source_filename": Path(args.contract_file).name,
        "source_sha256": result["source_sha256"],
        "client_role": args.client_role,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "fidelity_issues": result["fidelity_issues"],
    }
    docx_bytes = docx_report.render_docx(result["summary"], context)

    output_path = Path(args.output) if args.output else io_utils.default_summary_path(Path(args.contract_file).name, run_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(docx_bytes)

    print(f"\nSummary (Word): {output_path}")
    if result["fidelity_issues"]:
        print(f"Data fidelity notices: {len(result['fidelity_issues'])} (see document)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
