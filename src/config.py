"""
Configuration and defaults for the relational tech watcher.
"""

import os

# GitHub
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_TOPIC = "relational-tech"

# Anthropic
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FILTER_MODEL = "claude-haiku-4-5-20251001"  # cheap, fast -- used for significance filtering
SUMMARY_MODEL = "claude-sonnet-4-6"  # better prose -- used for feed summaries

# Paths
STATE_DIR = os.path.join(os.path.dirname(__file__), "..", "state")
REPOS_STATE_FILE = os.path.join(STATE_DIR, "repos.json")
FEED_FILE = os.path.join(STATE_DIR, "feed.json")
SITE_DIR = os.path.join(os.path.dirname(__file__), "..", "site")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

# Defaults for repos without a .reltech.yml
DEFAULT_MANIFEST = {
    "version": 1,
    "project": {
        "name": None,  # will be filled from repo name
        "description": None,  # will be filled from repo description
        "neighborhood": None,
        "builder": None,
    },
    "tags": [],
    "watch": {
        "branches": ["main", "master"],
        "signals": ["releases", "prs", "commits"],
        "threshold": "minor",
    },
    "preferences": {
        "summarize_commits": True,
        "summarize_readme": True,
        "public_link": True,
        "name_contributors": False,
    },
    "interests": [],
}

# Bot accounts to skip (case-insensitive)
BOT_ACCOUNTS = {
    "dependabot[bot]",
    "dependabot-preview[bot]",
    "renovate[bot]",
    "github-actions[bot]",
    "greenkeeper[bot]",
    "snyk-bot",
    "imgbot[bot]",
    "codecov[bot]",
    "stale[bot]",
    "allcontributors[bot]",
}

# Commit message patterns that indicate low-significance changes
SKIP_PATTERNS = [
    r"^bump\b",
    r"^chore\(deps\)",
    r"^auto-merge",
    r"^merge (pull request|branch)",
    r"^update \S+\.lock$",
    r"^ci:",
    r"^style:",
    r"^lint",
    r"^format",
    r"^typo",
    r"^fix typo",
    r"^wip\b",
]
