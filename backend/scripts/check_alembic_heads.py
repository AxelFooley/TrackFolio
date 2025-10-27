#!/usr/bin/env python3
"""
Alembic heads checker utility.

Uses the Alembic Python API to properly detect multiple migration heads,
avoiding fragile shell parsing that was causing false positives.

Exit codes:
  0: Single head detected (success)
  1: Multiple heads detected (error)
  2: Alembic configuration error
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
except ImportError as e:
    print(f"ERROR: Could not import alembic. {e}", file=sys.stderr)
    sys.exit(2)


def get_alembic_heads():
    """Get all current alembic heads using Python API.

    Returns:
        list: List of head revision IDs
    """
    try:
        # Get the alembic config from current directory
        config = Config("alembic.ini")
        script_dir = ScriptDirectory.from_config(config)

        # Get all heads
        heads = script_dir.get_heads()
        return list(heads)
    except Exception as e:
        print(f"ERROR: Failed to read alembic configuration: {e}", file=sys.stderr)
        sys.exit(2)


def main():
    """Check for multiple alembic heads."""
    heads = get_alembic_heads()

    # Print results
    print(f"HEADS_COUNT={len(heads)}")
    if heads:
        print(f"LATEST_REVISION={heads[0]}")

    # Exit with error if multiple heads
    if len(heads) > 1:
        print(f"ERROR: Multiple alembic heads detected: {len(heads)}", file=sys.stderr)
        for i, head in enumerate(heads, 1):
            print(f"  Head {i}: {head}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
