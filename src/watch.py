"""
Watch repos for new activity since the last scan.
Checks releases, merged PRs, and significant commits.

Supports solo dev / direct-commit workflows by grouping related commits
into logical changes, so a day's work becomes one feed entry instead of
fifteen individual commits.
"""

import logging
from datetime import datetime, timezone, timedelta
from github import Github, GithubException
from .config import GITHUB_TOKEN

logger = logging.getLogger(__name__)

# How far back to look on first scan of a new repo (don't flood the feed)
FIRST_SCAN_LOOKBACK_DAYS = 7

# Commit grouping: commits within this window by the same author are grouped
COMMIT_GROUP_WINDOW_HOURS = 6


def get_recent_releases(repo, since: datetime) -> list[dict]:
    """Get releases published since the given timestamp."""
    releases = []
    try:
        for release in repo.get_releases():
            published = release.published_at
            if not published:
                continue
            if published.replace(tzinfo=timezone.utc) <= since:
                break  # releases are reverse chronological
            releases.append({
                "type": "release",
                "title": release.title or release.tag_name,
                "tag": release.tag_name,
                "body": release.body or "",
                "url": release.html_url,
                "author": release.author.login if release.author else None,
                "timestamp": published.isoformat(),
            })
    except GithubException as e:
        logger.warning(f"Failed to fetch releases for {repo.full_name}: {e}")
    return releases


def get_merged_prs(repo, since: datetime) -> list[dict]:
    """Get PRs merged since the given timestamp."""
    prs = []
    try:
        # Get recently closed PRs and filter for merged
        for pr in repo.get_pulls(state="closed", sort="updated", direction="desc"):
            if not pr.merged:
                continue
            merged_at = pr.merged_at.replace(tzinfo=timezone.utc)
            if merged_at <= since:
                break
            # Skip draft/WIP PRs that somehow got merged
            if pr.draft:
                continue
            prs.append({
                "type": "pr_merged",
                "title": pr.title,
                "number": pr.number,
                "body": pr.body or "",
                "url": pr.html_url,
                "author": pr.user.login if pr.user else None,
                "labels": [label.name for label in pr.labels],
                "timestamp": merged_at.isoformat(),
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
                "_pr_merge_sha": pr.merge_commit_sha,
            })
    except GithubException as e:
        logger.warning(f"Failed to fetch PRs for {repo.full_name}: {e}")
    return prs


def get_recent_commits(
    repo, since: datetime, branches: list[str], pr_shas: set[str] | None = None
) -> list[dict]:
    """
    Get commits since the given timestamp on watched branches.
    Filters out commits already represented by a merged PR (using pr_shas).
    """
    if pr_shas is None:
        pr_shas = set()

    commits = []
    seen_shas = set()

    for branch_name in branches:
        try:
            branch_commits = repo.get_commits(sha=branch_name, since=since)
            for commit in branch_commits:
                if commit.sha in seen_shas:
                    continue
                seen_shas.add(commit.sha)

                # Skip commits that are part of a merged PR
                if commit.sha in pr_shas:
                    continue

                author_login = None
                if commit.author:
                    author_login = commit.author.login
                elif commit.commit.author:
                    author_login = commit.commit.author.name

                commits.append({
                    "type": "commit",
                    "sha": commit.sha[:8],
                    "full_sha": commit.sha,
                    "message": commit.commit.message,
                    "author": author_login,
                    "url": commit.html_url,
                    "timestamp": commit.commit.author.date.isoformat()
                        if commit.commit.author.date else None,
                    "stats": {
                        "additions": commit.stats.additions if commit.stats else 0,
                        "deletions": commit.stats.deletions if commit.stats else 0,
                        "total": commit.stats.total if commit.stats else 0,
                    },
                })
        except GithubException as e:
            logger.warning(
                f"Failed to fetch commits for {repo.full_name}/{branch_name}: {e}"
            )

    return commits


def _collect_pr_commit_shas(repo, prs: list[dict]) -> set[str]:
    """
    Collect SHAs of commits that belong to merged PRs so we can
    exclude them from direct-commit results (avoid double counting).
    """
    pr_shas = set()
    for pr_data in prs:
        # The merge commit SHA
        merge_sha = pr_data.get("_pr_merge_sha")
        if merge_sha:
            pr_shas.add(merge_sha)
        # Also try to get the PR's individual commits
        try:
            pr_number = pr_data.get("number")
            if pr_number:
                pr_obj = repo.get_pull(pr_number)
                for commit in pr_obj.get_commits():
                    pr_shas.add(commit.sha)
        except GithubException:
            pass
    return pr_shas


def group_commits(commits: list[dict]) -> list[dict]:
    """
    Group related commits into logical changes for the feed.

    Solo developers and AI-assisted tools (Lovable, Claude Code, etc.) often
    commit directly to main without PRs. A day's work might be 10-15 commits
    that together represent one meaningful change. Grouping prevents feed spam
    while still capturing the full story of what was built.

    Grouping rules:
    - Same author
    - Within COMMIT_GROUP_WINDOW_HOURS of each other
    - Combined into a single "commit_group" change with aggregate stats

    Single commits that don't group with anything remain as individual "commit"
    entries (the filter/summarize pipeline handles them normally).
    """
    if not commits:
        return []

    # Sort by timestamp
    def parse_ts(c):
        ts = c.get("timestamp")
        if ts:
            return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        return datetime.min.replace(tzinfo=timezone.utc)

    sorted_commits = sorted(commits, key=parse_ts)

    groups = []
    current_group = [sorted_commits[0]]

    for commit in sorted_commits[1:]:
        prev = current_group[-1]
        prev_ts = parse_ts(prev)
        curr_ts = parse_ts(commit)
        same_author = (commit.get("author") or "").lower() == (prev.get("author") or "").lower()
        within_window = (curr_ts - prev_ts) <= timedelta(hours=COMMIT_GROUP_WINDOW_HOURS)

        if same_author and within_window:
            current_group.append(commit)
        else:
            groups.append(current_group)
            current_group = [commit]

    groups.append(current_group)

    # Convert groups to changes
    results = []
    for group in groups:
        if len(group) == 1:
            # Single commit -- pass through as-is
            results.append(group[0])
        else:
            # Multiple commits -- create a grouped entry
            results.append(_make_commit_group(group))

    return results


def _make_commit_group(commits: list[dict]) -> dict:
    """
    Combine a list of related commits into a single commit_group change.
    Aggregates stats, collects all messages for the LLM to summarize,
    and links to the most recent commit.
    """
    total_additions = sum(c.get("stats", {}).get("additions", 0) for c in commits)
    total_deletions = sum(c.get("stats", {}).get("deletions", 0) for c in commits)

    # Build a combined message: first lines of each commit
    commit_messages = []
    for c in commits:
        first_line = c.get("message", "").strip().split("\n")[0]
        if first_line:
            commit_messages.append(f"- {first_line}")

    combined_message = "\n".join(commit_messages)

    # Use the latest commit's URL and timestamp
    latest = commits[-1]
    earliest = commits[0]

    return {
        "type": "commit_group",
        "title": f"{len(commits)} commits by {latest.get('author', 'unknown')}",
        "message": combined_message,
        "commit_count": len(commits),
        "author": latest.get("author"),
        "url": latest.get("url"),
        "urls": [c.get("url") for c in commits],
        "shas": [c.get("sha") for c in commits],
        "timestamp": latest.get("timestamp"),
        "first_timestamp": earliest.get("timestamp"),
        "stats": {
            "additions": total_additions,
            "deletions": total_deletions,
            "total": total_additions + total_deletions,
        },
    }


def check_readme_changed(repo, since: datetime) -> dict | None:
    """Check if the README was updated since last scan."""
    try:
        # Check commits that touched README files
        for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
            try:
                commits = repo.get_commits(path=readme_name, since=since)
                first = None
                for c in commits:
                    first = c
                    break
                if first:
                    return {
                        "type": "readme_update",
                        "title": f"README updated",
                        "message": first.commit.message,
                        "url": first.html_url,
                        "author": first.author.login if first.author else None,
                        "timestamp": first.commit.author.date.isoformat()
                            if first.commit.author.date else None,
                    }
            except GithubException:
                continue
    except GithubException:
        pass
    return None


def watch(state: dict) -> dict:
    """
    Check all known repos for new activity.
    Returns a dict mapping repo full_name to a list of raw changes.
    """
    g = Github(GITHUB_TOKEN)
    all_changes = {}

    for full_name, repo_info in state["repos"].items():
        logger.info(f"Checking {full_name} for changes...")

        try:
            repo = g.get_repo(full_name)
        except GithubException as e:
            logger.warning(f"Could not access {full_name}: {e}")
            continue

        manifest = repo_info.get("manifest", {})
        signals = manifest.get("watch", {}).get(
            "signals", ["releases", "prs", "commits"]
        )
        branches = manifest.get("watch", {}).get("branches", ["main", "master"])

        # Determine the "since" timestamp
        last_checked = repo_info.get("last_checked")
        if last_checked:
            since = datetime.fromisoformat(last_checked).replace(tzinfo=timezone.utc)
        else:
            # First scan: look back a limited window
            since = datetime.now(timezone.utc) - timedelta(days=FIRST_SCAN_LOOKBACK_DAYS)

        changes = []

        if "releases" in signals:
            changes.extend(get_recent_releases(repo, since))

        # Fetch PRs first so we can deduplicate commits
        prs = []
        if "prs" in signals:
            prs = get_merged_prs(repo, since)
            changes.extend(prs)

        if "commits" in signals:
            # Collect PR commit SHAs so we don't double-count
            pr_shas = set()
            if prs:
                pr_shas = _collect_pr_commit_shas(repo, prs)

            raw_commits = get_recent_commits(repo, since, branches, pr_shas)

            # Group related commits (solo dev / AI-assisted workflows)
            grouped = group_commits(raw_commits)
            changes.extend(grouped)

            if raw_commits:
                n_raw = len(raw_commits)
                n_grouped = len(grouped)
                if n_grouped < n_raw:
                    logger.info(
                        f"  Grouped {n_raw} commits into {n_grouped} logical changes"
                    )

        # Always check for README changes (lightweight)
        if manifest.get("preferences", {}).get("summarize_readme", True):
            readme_change = check_readme_changed(repo, since)
            if readme_change:
                changes.append(readme_change)

        if changes:
            all_changes[full_name] = changes
            logger.info(f"  Found {len(changes)} changes in {full_name}")
        else:
            logger.info(f"  No new changes in {full_name}")

        # Update last_checked timestamp
        state["repos"][full_name]["last_checked"] = datetime.now(
            timezone.utc
        ).isoformat()
        if not state["repos"][full_name].get("first_seen"):
            state["repos"][full_name]["first_seen"] = datetime.now(
                timezone.utc
            ).isoformat()

    return all_changes
