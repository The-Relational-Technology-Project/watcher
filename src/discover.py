"""
Discover repos that have opted into the relational tech network
by adding the 'relational-tech' GitHub topic.
"""

import copy
import json
import logging
import re
import yaml
from github import Github, GithubException
from .config import GITHUB_TOKEN, GITHUB_TOPIC, DEFAULT_MANIFEST, REPOS_STATE_FILE

logger = logging.getLogger(__name__)


def load_repos_state() -> dict:
    """Load the known repos state from disk."""
    try:
        with open(REPOS_STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"repos": {}}


def save_repos_state(state: dict):
    """Write the repos state to disk."""
    with open(REPOS_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def fetch_manifest(repo) -> dict:
    """
    Try to fetch and parse .reltech.yml from a repo.
    Returns the parsed manifest merged with defaults, or defaults alone
    if no manifest exists.
    """
    manifest = copy.deepcopy(DEFAULT_MANIFEST)

    try:
        content = repo.get_contents(".reltech.yml")
        parsed = yaml.safe_load(content.decoded_content.decode("utf-8"))
        if parsed and isinstance(parsed, dict):
            # Deep merge: override defaults with manifest values
            for key in ["project", "watch", "preferences"]:
                if key in parsed and isinstance(parsed[key], dict):
                    manifest[key] = {**manifest.get(key, {}), **parsed[key]}
            for key in ["tags", "interests"]:
                if key in parsed and isinstance(parsed[key], list):
                    manifest[key] = parsed[key]
            if "version" in parsed:
                manifest["version"] = parsed["version"]
            manifest["_has_manifest"] = True
    except GithubException:
        # No manifest file -- that's fine, use defaults
        manifest["_has_manifest"] = False
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse .reltech.yml in {repo.full_name}: {e}")
        manifest["_has_manifest"] = False

    # Fill in project defaults from repo metadata
    if not manifest["project"].get("name"):
        manifest["project"]["name"] = repo.name
    if not manifest["project"].get("description"):
        manifest["project"]["description"] = repo.description or ""

    return manifest


def fetch_contact_from_readme(repo):
    """
    Look for a ## Builder or ## Contact section in the repo's README.
    Returns the text of that section, or None if not found.
    """
    for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
        try:
            content = repo.get_contents(readme_name)
            text = content.decoded_content.decode("utf-8")

            # Look for ## Builder, ## Contact, ## Get in Touch (case-insensitive)
            pattern = r'(?:^|\n)##\s+(?:Builder|Contact|Get\s+in\s+Touch)\s*\n(.*?)(?=\n##\s|\Z)'
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                section = match.group(1).strip()
                # Cap at a reasonable length
                if section and len(section) < 1000:
                    return section
            return None
        except (GithubException, UnicodeDecodeError):
            continue
    return None


def discover() -> tuple[dict, list[str], list[str]]:
    """
    Search GitHub for repos with the relational-tech topic.
    Returns (updated_state, new_repo_names, removed_repo_names).
    """
    g = Github(GITHUB_TOKEN)
    state = load_repos_state()
    known_repos = set(state["repos"].keys())
    found_repos = {}

    logger.info(f"Searching GitHub for repos with topic '{GITHUB_TOPIC}'...")

    # Search for repos with our topic
    query = f"topic:{GITHUB_TOPIC}"
    results = g.search_repositories(query=query, sort="updated")

    for repo in results:
        full_name = repo.full_name
        logger.info(f"  Found: {full_name}")

        manifest = fetch_manifest(repo)

        # Try to pull contact info from README
        contact = fetch_contact_from_readme(repo)

        found_repos[full_name] = {
            "full_name": full_name,
            "url": repo.html_url,
            "description": repo.description or "",
            "manifest": manifest,
            "contact": contact,
            "last_checked": state["repos"].get(full_name, {}).get("last_checked"),
            "first_seen": state["repos"].get(full_name, {}).get("first_seen"),
        }

    found_names = set(found_repos.keys())
    new_repos = sorted(found_names - known_repos)
    removed_repos = sorted(known_repos - found_names)

    if new_repos:
        logger.info(f"New repos joined the network: {new_repos}")
    if removed_repos:
        logger.info(f"Repos left the network: {removed_repos}")

    # Update state
    state["repos"] = found_repos
    save_repos_state(state)

    return state, new_repos, removed_repos
