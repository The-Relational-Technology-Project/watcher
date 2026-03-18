"""
Significance filtering: decide which changes are worth surfacing.

Two layers:
1. Structural filters (cheap, pattern-based)
2. Semantic filter (LLM-based, for candidates that pass structural filters)
"""

import re
import logging
from .config import BOT_ACCOUNTS, SKIP_PATTERNS

logger = logging.getLogger(__name__)


def is_bot_author(author: str | None) -> bool:
    """Check if the author is a known automation bot."""
    if not author:
        return False
    return author.lower() in {b.lower() for b in BOT_ACCOUNTS}


def matches_skip_pattern(message: str) -> bool:
    """Check if a commit/PR message matches low-significance patterns."""
    first_line = message.strip().split("\n")[0].lower()
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, first_line, re.IGNORECASE):
            return True
    return False


def has_reltech_label(labels: list[str]) -> str | None:
    """
    Check for builder-defined significance labels.
    Returns 'highlight', 'skip', or None.
    """
    for label in labels:
        label_lower = label.lower().strip()
        if label_lower in ("reltech: highlight", "reltech:highlight", "reltech-highlight"):
            return "highlight"
        if label_lower in ("reltech: skip", "reltech:skip", "reltech-skip"):
            return "skip"
    return None


def is_trivial_commit(change: dict) -> bool:
    """Check if a commit is too small to be interesting."""
    if change.get("type") != "commit":
        return False
    stats = change.get("stats", {})
    total_changes = stats.get("total", 0)
    # A commit touching fewer than 5 lines total is likely trivial
    # (unless it's a config change, which could matter -- the LLM will catch that)
    return total_changes < 5


def structural_filter(change: dict, manifest: dict) -> str:
    """
    Apply cheap structural filters to a single change.
    Returns: 'highlight', 'pass', 'skip'
      - 'highlight': guaranteed inclusion (builder labeled it)
      - 'pass': send to semantic filter
      - 'skip': drop it
    """
    # Builder-defined labels take priority
    labels = change.get("labels", [])
    label_signal = has_reltech_label(labels)
    if label_signal == "highlight":
        return "highlight"
    if label_signal == "skip":
        return "skip"

    # Skip bot authors
    if is_bot_author(change.get("author")):
        return "skip"

    # Skip trivial commits
    if is_trivial_commit(change):
        return "skip"

    # Skip commits matching noise patterns
    message = change.get("message", change.get("title", ""))
    if matches_skip_pattern(message):
        return "skip"

    # Releases are almost always worth surfacing
    if change.get("type") == "release":
        return "highlight"

    # Everything else goes to the semantic filter
    return "pass"


def apply_threshold(changes: list[dict], threshold: str) -> list[dict]:
    """
    Apply the repo's declared significance threshold.
    - 'patch': surface everything that passes structural filters
    - 'minor': surface PRs, releases, and multi-file commits (default)
    - 'major': only surface releases and explicitly highlighted items
    """
    if threshold == "patch":
        return changes

    if threshold == "major":
        return [
            c for c in changes
            if c.get("type") == "release"
            or c.get("_significance") == "highlight"
        ]

    # 'minor' (default): skip single-file commits unless highlighted
    return [
        c for c in changes
        if c.get("type") != "commit"
        or c.get("changed_files", c.get("stats", {}).get("total", 0)) > 1
        or c.get("_significance") == "highlight"
    ]


def filter_changes(changes: list[dict], manifest: dict) -> list[dict]:
    """
    Run structural filters on a list of changes.
    Returns changes that should proceed to semantic analysis,
    with _significance field set.
    """
    threshold = manifest.get("watch", {}).get("threshold", "minor")
    filtered = []

    for change in changes:
        result = structural_filter(change, manifest)
        if result == "skip":
            logger.debug(f"  Skipping: {change.get('title', change.get('message', ''))[:60]}")
            continue
        change["_significance"] = result  # 'highlight' or 'pass'
        filtered.append(change)

    # Apply threshold
    filtered = apply_threshold(filtered, threshold)

    logger.info(f"  Structural filter: {len(changes)} -> {len(filtered)} changes")
    return filtered
