#!/usr/bin/env python
"""Entrypoint: python summarise.py <contract.pdf|.docx|.md> [options]. See
contract_reviewer/summarize_cli.py."""
import sys

from contract_reviewer.summarize_cli import main

if __name__ == "__main__":
    sys.exit(main())
