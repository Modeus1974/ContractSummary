"""CLI entrypoint: python review.py <contract.pdf> [options]."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from contract_reviewer import config, io_utils, runtime
from contract_reviewer.graph import build_graph
from contract_reviewer.logging_setup import configure_logging, log_stage, log_warning


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Singapore contract review CLI")
    parser.add_argument("contract_pdf", help="Path to the contract PDF")
    parser.add_argument("--client-role", default=None)
    parser.add_argument("--perspective", default=None)
    parser.add_argument("--research-date", default=None)
    parser.add_argument(
        "--output", default=None, help="Override the default Reviews/... output path"
    )
    parser.add_argument(
        "--models-config",
        default=None,
        help="Path to models.yaml (default: ./models.yaml)",
    )
    parser.add_argument("--max-cycles", type=int, default=2)
    parser.add_argument(
        "--resume", default=None, help="Resume a previous run by its run ID"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)
    config.load_env()

    models_config_path = Path(args.models_config) if args.models_config else None
    runtime.set_tiers(config.load_tier_config(models_config_path))

    run_id = args.resume or io_utils.new_run_id()
    log_stage("run", run_id)

    initial_state = {
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_pdf_path": str(Path(args.contract_pdf).resolve()),
        "client_role": args.client_role,
        "client_perspective": args.perspective,
        "research_date": args.research_date
        or datetime.now(timezone.utc).date().isoformat(),
        "max_cycles": args.max_cycles,
        "output_path_override": args.output,
        "model_assignments": [],
        "errors": [],
    }

    graph = build_graph(io_utils.RUNS_DIR / "checkpoints.sqlite")
    graph_config = {"configurable": {"thread_id": run_id}}

    try:
        if args.resume:
            final_state = graph.invoke(None, config=graph_config)
        else:
            final_state = graph.invoke(initial_state, config=graph_config)
    except Exception as exc:
        if args.verbose:
            raise
        log_warning(f"Run failed: {exc}")
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1

    output_path = final_state.get("output_path")
    pdf_output_path = final_state.get("pdf_output_path")
    report_status = final_state.get("report_status")
    print(f"\nReport (Markdown): {output_path}")
    print(f"Report (PDF): {pdf_output_path or 'not generated -- see warnings above'}")
    print(f"Status: {report_status}")
    if final_state.get("incomplete_reason"):
        print(f"Blocker: {final_state['incomplete_reason']}")

    return 0 if report_status != "Incomplete" else 1


if __name__ == "__main__":
    sys.exit(main())
