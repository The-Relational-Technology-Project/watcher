"""
Watch repos for new activity since the last scan.
Checks releases, merged PRs, and significant commits.
"""

import logging
from datetime import datetime, timezone, timedelta
from github import Github, GithubException
from .config import GITHUB_TOKEN

logger = logging.getLogger(__name__)

# How far back to look on first scan of a new repo (don't flood the feed)
FIRST_SCAN_LOOKBACK_DAYS = 7


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
            })
    except GithubException as e:
        logger.warning(f"Failed to fetch PRs for {repo.full_name}: {e}")
    return prs


def get_recent_commits(repo, since: datetime, branches: list[str]) -> list[dict]:
    """
    Get commits since the given timestamp on watched branches.
    Only returns commits that aren't already represented by a PR.
    """
    commits = []
    seen_shas = set()

    for branch_name in branches:
        try:
            branch_commits = repo.get_commits(sha=branch_name, since=since)
            for commit in branch_commits:
                if commit.sha in seen_shas:
                    continue
                seen_shas.add(commit.sha)

                author_login = None
                if commit.author:
                    author_login = commit.author.login
                elif commit.commit.author:
                    author_login = commit.commit.author.name

                commits.append({
                    "type": "commit",
                    "sha": commit.sha[:8],
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
        signals = manifest.get("watch", {}).get("signals", ["releases", "prs"])
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

        if "prs" in signals:
            changes.extend(get_merged_prs(repo, since))

        if "commits" in signals:
            changes.extend(get_recent_commits(repo, since, branches))

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
