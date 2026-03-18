"""
Match changes to builders who might be interested,
based on tag overlap between change tags and repo declared interests.
"""

import logging

logger = logging.getLogger(__name__)


def find_matches(
    change_tags: list[str],
    source_repo: str,
    all_repos: dict,
) -> list[dict]:
    """
    Find repos whose declared interests overlap with a change's tags.

    Returns a list of match dicts:
      {"repo": full_name, "builder": name, "reason": "..."}
    """
    matches = []
    change_tag_set = {t.lower().strip() for t in change_tags}

    if not change_tag_set:
        return matches

    for full_name, repo_info in all_repos.items():
        # Don't match a repo to its own changes
        if full_name == source_repo:
            continue

        manifest = repo_info.get("manifest", {})
        interests = {i.lower().strip() for i in manifest.get("interests", [])}
        repo_tags = {t.lower().strip() for t in manifest.get("tags", [])}

        # Check interest overlap
        interest_overlap = change_tag_set & interests
        if interest_overlap:
            builder = manifest.get("project", {}).get("builder")
            # Respect name_contributors preference
            if not manifest.get("preferences", {}).get("name_contributors", False):
                builder = manifest.get("project", {}).get("name", full_name)

            matches.append({
                "repo": full_name,
                "builder": builder or full_name,
                "reason": f"Listed interest in: {', '.join(sorted(interest_overlap))}",
            })
            continue

        # Also check tag overlap (repos working on similar things)
        tag_overlap = change_tag_set & repo_tags
        if len(tag_overlap) >= 2:  # require at least 2 shared tags
            builder = manifest.get("project", {}).get("builder")
            if not manifest.get("preferences", {}).get("name_contributors", False):
                builder = manifest.get("project", {}).get("name", full_name)

            matches.append({
                "repo": full_name,
                "builder": builder or full_name,
                "reason": f"Working on similar topics: {', '.join(sorted(tag_overlap))}",
            })

    logger.info(f"  Found {len(matches)} interest matches")
    return matches
