"""
Publish feed entries and generate the static site.
"""

import json
import logging
import os
from datetime import datetime, timezone
from .config import FEED_FILE, SITE_DIR, TEMPLATES_DIR

logger = logging.getLogger(__name__)


def load_feed() -> list[dict]:
    """Load the existing feed from disk."""
    try:
        with open(FEED_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_feed(entries: list[dict]):
    """Write the feed to disk."""
    with open(FEED_FILE, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def make_entry_id(repo_name: str, change: dict) -> str:
    """Generate a stable ID for a feed entry."""
    change_type = change.get("type", "change")
    # Use PR number, release tag, or commit sha for uniqueness
    identifier = (
        change.get("tag")
        or str(change.get("number", ""))
        or change.get("sha", "")
        or change.get("timestamp", "")[:10]
    )
    slug = f"{repo_name}-{change_type}-{identifier}".lower()
    # Clean up for use as an ID
    return "".join(c if c.isalnum() or c == "-" else "-" for c in slug).strip("-")


def create_change_entry(
    change: dict,
    repo_info: dict,
    matches: list[dict],
) -> dict:
    """Create a feed entry from a processed change."""
    manifest = repo_info.get("manifest", {})
    project = manifest.get("project", {})

    # Respect public_link preference
    repo_url = repo_info.get("url", "")
    if not manifest.get("preferences", {}).get("public_link", True):
        repo_url = None

    return {
        "id": make_entry_id(project.get("name", "unknown"), change),
        "timestamp": change.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "entry_type": "change",
        "repo": {
            "name": project.get("name", repo_info.get("full_name", "")),
            "full_name": repo_info.get("full_name", ""),
            "url": repo_url,
            "neighborhood": project.get("neighborhood"),
            "builder": project.get("builder"),
            "description": project.get("description", ""),
        },
        "change": {
            "type": change.get("type"),
            "title": change.get("title", change.get("message", "")[:100]),
            "url": change.get("url"),
            "significance": change.get("_significance", "mention"),
        },
        "summary": change.get("_summary", ""),
        "tags": change.get("_tags", []),
        "matches": matches,
    }


def create_welcome_entry(repo_info: dict, summary: str) -> dict:
    """Create a feed entry welcoming a new repo to the network."""
    manifest = repo_info.get("manifest", {})
    project = manifest.get("project", {})

    repo_url = repo_info.get("url", "")
    if not manifest.get("preferences", {}).get("public_link", True):
        repo_url = None

    return {
        "id": f"welcome-{project.get('name', 'unknown').lower()}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry_type": "welcome",
        "repo": {
            "name": project.get("name", repo_info.get("full_name", "")),
            "full_name": repo_info.get("full_name", ""),
            "url": repo_url,
            "neighborhood": project.get("neighborhood"),
            "builder": project.get("builder"),
            "description": project.get("description", ""),
        },
        "summary": summary,
        "tags": manifest.get("tags", []),
        "matches": [],
    }


def generate_site(feed: list[dict], repos: dict):
    """Generate the static site HTML from feed data and repo info."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(os.path.join(TEMPLATES_DIR, "site")),
        autoescape=True,
    )

    # Sort feed: newest first
    sorted_feed = sorted(feed, key=lambda e: e.get("timestamp", ""), reverse=True)

    # Build project directory from repos state
    projects = []
    for full_name, info in repos.items():
        manifest = info.get("manifest", {})
        project = manifest.get("project", {})
        if not manifest.get("preferences", {}).get("public_link", True):
            continue
        projects.append({
            "name": project.get("name", full_name),
            "full_name": full_name,
            "url": info.get("url", ""),
            "description": project.get("description", ""),
            "neighborhood": project.get("neighborhood"),
            "builder": project.get("builder"),
            "tags": manifest.get("tags", []),
            "has_manifest": manifest.get("_has_manifest", False),
        })
    projects.sort(key=lambda p: p["name"].lower())

    # Collect all unique tags for filtering
    all_tags = set()
    for entry in sorted_feed:
        all_tags.update(entry.get("tags", []))
    all_tags = sorted(all_tags)

    # Render pages
    pages = {
        "index.html": env.get_template("index.html").render(
            feed=sorted_feed[:50],  # last 50 entries on the homepage
            all_tags=all_tags,
            total_projects=len(projects),
            last_updated=datetime.now(timezone.utc).strftime("%B %d, %Y"),
        ),
        "projects.html": env.get_template("projects.html").render(
            projects=projects,
            total_projects=len(projects),
            last_updated=datetime.now(timezone.utc).strftime("%B %d, %Y"),
        ),
        "about.html": env.get_template("about.html").render(
            total_projects=len(projects),
        ),
    }

    for filename, content in pages.items():
        path = os.path.join(SITE_DIR, filename)
        with open(path, "w") as f:
            f.write(content)
        logger.info(f"  Generated {filename}")

    # Also write feed.json into the site directory for programmatic access
    feed_site_path = os.path.join(SITE_DIR, "feed.json")
    with open(feed_site_path, "w") as f:
        json.dump(sorted_feed, f, indent=2, default=str)

    logger.info(f"  Site generated with {len(sorted_feed)} feed entries, {len(projects)} projects")


def generate_rss(feed: list[dict]):
    """Generate RSS/Atom feed."""
    from feedgen.feed import FeedGenerator

    fg = FeedGenerator()
    fg.title("Relational Tech Network Updates")
    fg.link(href="https://updates.relationaltechproject.org", rel="alternate")
    fg.link(href="https://updates.relationaltechproject.org/feed.xml", rel="self")
    fg.description(
        "Meaningful changes across the relational tech ecosystem -- "
        "community tools, neighborhood apps, and civic technology."
    )
    fg.language("en")

    sorted_feed = sorted(feed, key=lambda e: e.get("timestamp", ""), reverse=True)

    for entry in sorted_feed[:30]:  # last 30 entries in RSS
        fe = fg.add_entry()
        fe.id(entry["id"])
        fe.title(
            f"{entry['repo']['name']}: {entry.get('change', {}).get('title', 'Update')}"
        )
        fe.summary(entry.get("summary", ""))

        link = entry.get("change", {}).get("url") or entry["repo"].get("url")
        if link:
            fe.link(href=link)

        if entry.get("timestamp"):
            fe.published(entry["timestamp"])

    rss_path = os.path.join(SITE_DIR, "feed.xml")
    fg.rss_file(rss_path)
    logger.info(f"  Generated RSS feed with {min(len(sorted_feed), 30)} entries")


def publish(
    new_entries: list[dict],
    repos: dict,
):
    """
    Append new entries to the feed and regenerate the site.
    """
    feed = load_feed()

    # Deduplicate: skip new entries whose ID already exists in the feed
    existing_ids = {entry.get("id") for entry in feed}
    deduplicated = [e for e in new_entries if e.get("id") not in existing_ids]
    if len(deduplicated) < len(new_entries):
        logger.info(
            f"  Skipped {len(new_entries) - len(deduplicated)} duplicate entries"
        )
    feed.extend(deduplicated)

    # Cap feed at 500 entries (oldest get dropped)
    if len(feed) > 500:
        feed = sorted(feed, key=lambda e: e.get("timestamp", ""), reverse=True)[:500]

    save_feed(feed)
    logger.info(f"Feed now has {len(feed)} entries ({len(new_entries)} new)")

    generate_site(feed, repos)
    generate_rss(feed)
