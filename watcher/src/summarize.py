"""
LLM-powered summarization of significant changes.

Uses Claude Haiku for quick significance scoring,
and Claude Sonnet for the actual prose summaries that builders will read.
"""

import json
import logging
import os
from anthropic import Anthropic
from .config import ANTHROPIC_API_KEY, FILTER_MODEL, SUMMARY_MODEL, TEMPLATES_DIR

logger = logging.getLogger(__name__)

client = None


def get_client() -> Anthropic:
    global client
    if client is None:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return client


def load_prompt_template() -> str:
    """Load the summary prompt template from disk."""
    path = os.path.join(TEMPLATES_DIR, "summary_prompt.txt")
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        # Fallback prompt if template file is missing
        return (
            "You are summarizing changes in community technology projects "
            "for other builders in the relational tech network. "
            "Write a warm, concise 2-3 sentence summary of what changed "
            "and why it might matter to other community builders."
        )


def score_significance(change: dict, repo_info: dict) -> str:
    """
    Use a fast LLM to score whether a change is interesting enough
    to surface in the feed. Returns 'highlight', 'mention', or 'skip'.
    """
    # Already marked as highlight by structural filter
    if change.get("_significance") == "highlight":
        return "highlight"

    project_name = repo_info.get("manifest", {}).get("project", {}).get("name", "")
    project_desc = repo_info.get("manifest", {}).get("project", {}).get("description", "")

    change_text = change.get("body") or change.get("message") or change.get("title", "")
    change_title = change.get("title", change.get("message", "")[:100])

    prompt = f"""You are evaluating whether a change in a community technology project would be interesting to other builders in the relational tech network -- people building apps and tools for neighborhood connection, mutual aid, community calendars, local information, and civic engagement.

Project: {project_name}
Project description: {project_desc}
Change type: {change.get("type")}
Change title: {change_title}
Change details:
{change_text[:1500]}

Would another community tech builder find this change interesting or useful to know about?

Respond with exactly one word:
- "highlight" if this is notably interesting (new feature, accessibility improvement, integration, community-facing change)
- "mention" if it's worth a brief note (solid improvement, meaningful refactor)
- "skip" if it's not interesting to other builders (internal cleanup, minor fix, routine maintenance)"""

    try:
        response = get_client().messages.create(
            model=FILTER_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.content[0].text.strip().lower()
        if result in ("highlight", "mention", "skip"):
            return result
        return "mention"  # default to inclusion if response is unclear
    except Exception as e:
        logger.warning(f"Significance scoring failed: {e}")
        return "mention"  # err on the side of inclusion


def generate_summary(change: dict, repo_info: dict) -> dict:
    """
    Generate a human-readable summary of a change using Claude Sonnet.
    Returns a dict with 'summary' text and 'tags' list.
    """
    project = repo_info.get("manifest", {}).get("project", {})
    project_name = project.get("name", "")
    project_desc = project.get("description", "")
    neighborhood = project.get("neighborhood", "")
    existing_tags = repo_info.get("manifest", {}).get("tags", [])

    change_text = change.get("body") or change.get("message") or change.get("title", "")
    change_title = change.get("title", change.get("message", "")[:100])
    change_type = change.get("type", "change")

    template = load_prompt_template()

    prompt = f"""{template}

Project: {project_name}
Description: {project_desc}
Neighborhood: {neighborhood or "not specified"}
Existing project tags: {", ".join(existing_tags) if existing_tags else "none"}
Change type: {change_type}
Change title: {change_title}

Change details:
{change_text[:2000]}

Respond in JSON format:
{{
  "summary": "A warm, concise 2-3 sentence summary of the change and why it matters for community tech builders. Do not use em-dashes.",
  "tags": ["relevant", "topic", "tags", "for", "matching"]
}}"""

    try:
        response = get_client().messages.create(
            model=SUMMARY_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Parse JSON from response (handle markdown code blocks)
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(text)
        return {
            "summary": result.get("summary", ""),
            "tags": result.get("tags", []),
        }
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Summary generation failed: {e}")
        # Fallback: use the change title as summary
        return {
            "summary": f"{project_name} updated: {change_title}",
            "tags": list(existing_tags),
        }


def summarize_new_repo(repo_info: dict) -> str:
    """Generate a welcome summary for a repo that just joined the network."""
    project = repo_info.get("manifest", {}).get("project", {})
    project_name = project.get("name", repo_info.get("full_name", ""))
    project_desc = project.get("description", "")
    neighborhood = project.get("neighborhood", "")

    prompt = f"""A new project just joined the relational tech network. Write a warm, brief 2-3 sentence welcome summary for the network feed. Celebrate that they've joined. Do not use em-dashes.

Project: {project_name}
Description: {project_desc}
Neighborhood: {neighborhood or "not specified"}
Repository: {repo_info.get("url", "")}"""

    try:
        response = get_client().messages.create(
            model=SUMMARY_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Welcome summary failed: {e}")
        location = f" from {neighborhood}" if neighborhood else ""
        return f"Welcome to the network, {project_name}{location}! {project_desc}"


def process_changes(changes: list[dict], repo_info: dict) -> list[dict]:
    """
    Score and summarize a list of filtered changes.
    Returns changes that pass significance scoring, with summaries attached.
    """
    results = []

    for change in changes:
        # Score significance
        significance = score_significance(change, repo_info)
        if significance == "skip":
            logger.debug(f"  LLM skipped: {change.get('title', '')[:60]}")
            continue

        change["_significance"] = significance

        # Generate summary
        summary_data = generate_summary(change, repo_info)
        change["_summary"] = summary_data["summary"]
        change["_tags"] = summary_data["tags"]

        results.append(change)

    logger.info(
        f"  Semantic filter: {len(changes)} -> {len(results)} changes summarized"
    )
    return results
