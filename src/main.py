"""
Main orchestrator for the relational tech watcher.

Runs the full pipeline: discover -> watch -> filter -> summarize -> match -> publish
"""

import logging
import sys

from .discover import discover, save_repos_state
from .watch import watch
from .filter import filter_changes
from .summarize import process_changes, summarize_new_repo
from .match import find_matches
from .publish import create_change_entry, create_welcome_entry, publish

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run():
    """Run a full scan cycle."""
    logger.info("=== Relational Tech Watcher: starting scan ===")

    # 1. Discover repos
    logger.info("--- Phase 1: Discover ---")
    state, new_repos, removed_repos = discover()
    repo_count = len(state["repos"])
    logger.info(f"Network: {repo_count} repos ({len(new_repos)} new, {len(removed_repos)} departed)")

    all_new_entries = []

    # 2. Welcome new repos
    if new_repos:
        logger.info("--- Welcoming new repos ---")
        for repo_name in new_repos:
            repo_info = state["repos"].get(repo_name, {})
            summary = summarize_new_repo(repo_info)
            entry = create_welcome_entry(repo_info, summary)
            all_new_entries.append(entry)
            logger.info(f"  Welcome: {repo_name}")

    # 3. Watch for changes
    logger.info("--- Phase 2: Watch ---")
    all_changes = watch(state)

    if not all_changes and not new_repos:
        logger.info("No new changes found across the network. Done.")
        save_repos_state(state)
        # Still regenerate site in case repo list changed
        if removed_repos:
            publish([], state["repos"])
        return

    # 4. Filter + Summarize + Match for each repo's changes
    logger.info("--- Phase 3: Filter + Summarize + Match ---")
    for full_name, changes in all_changes.items():
        repo_info = state["repos"].get(full_name, {})
        manifest = repo_info.get("manifest", {})

        logger.info(f"Processing {full_name} ({len(changes)} raw changes)...")

        # Structural filtering
        filtered = filter_changes(changes, manifest)

        if not filtered:
            continue

        # Semantic filtering + summarization
        summarized = process_changes(filtered, repo_info)

        if not summarized:
            continue

        # Match against other repos' interests
        for change in summarized:
            matches = find_matches(
                change.get("_tags", []),
                full_name,
                state["repos"],
            )
            entry = create_change_entry(change, repo_info, matches)
            all_new_entries.append(entry)

    # 5. Publish
    logger.info("--- Phase 4: Publish ---")
    logger.info(f"Publishing {len(all_new_entries)} new feed entries")
    publish(all_new_entries, state["repos"])

    # Save updated state (with last_checked timestamps)
    save_repos_state(state)

    logger.info("=== Scan complete ===")


if __name__ == "__main__":
    run()
