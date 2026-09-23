#!/usr/bin/env python
"""Entrypoint: python review.py <contract.pdf> [options]. See contract_reviewer/cli.py."""
import sys

from contract_reviewer.cli import main

if __name__ == "__main__":
    sys.exit(main())
