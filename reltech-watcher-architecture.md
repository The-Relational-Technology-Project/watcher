# Relational Tech Watcher Agent
## Architecture & Design Document

**Purpose:** Monitor public GitHub repositories in the relational tech ecosystem, surface meaningful changes, and help builders learn from each other's work across neighborhoods.

**Guiding metaphor:** RTP is the river. This agent carries news of what's growing in each garden to other gardens that might benefit from knowing.

---

## 1. Core Principles

**Consent-first.** Repos must actively opt in. No surveillance of repos that haven't signaled they want to be part of the network. Opting out is as easy as removing a tag.

**Celebrate, don't surveil.** The tone is "look what this builder shipped" not "here's what changed in this codebase." Frame everything through the lens of community impact and builder craft.

**Respect licenses and boundaries.** The watcher reads public metadata, commit messages, PR descriptions, READMEs, and changelogs. It does not clone code, index source files, or reproduce proprietary logic. If a repo's license restricts derivative analysis, honor that.

**Low friction in, low friction out.** A builder should be able to join the network in under 2 minutes. Leaving should be instant (remove the topic tag).

**Meaningful over comprehensive.** Not every commit matters. The watcher's job is editorial: surface the changes that would make another builder say "oh, interesting."

---

## 2. How Repos Opt In

### Primary: GitHub Topic Tag

Repos add the topic `relational-tech` to their GitHub repository. This is the minimum viable opt-in. The watcher discovers repos by periodically searching GitHub for this topic.

**Why this works:**
- Zero new tooling required
- Visible in the GitHub UI (other builders can browse the topic)
- Instantly reversible
- GitHub already indexes topics for search

### Optional: `.reltech.yml` Manifest

For richer participation, a repo can include a `.reltech.yml` file at the root:

```yaml
# .reltech.yml -- Relational Tech Network Manifest
version: 1

# What is this project?
project:
  name: "Sunset Commons Calendar"
  description: "Community event calendar for the Outer Sunset neighborhood"
  neighborhood: "Outer Sunset, San Francisco"
  builder: "Maria Chen"

# What kind of project is this? (used for matching)
tags:
  - community-calendar
  - events
  - neighborhood-info
  - multilingual

# What should the watcher pay attention to?
watch:
  # Which branches matter? Default: main/master only
  branches: ["main"]
  # What counts as notable? Options: releases, prs, commits, readme-changes
  signals: ["releases", "prs"]
  # Minimum significance -- skip typo fixes etc. Options: patch, minor, major
  threshold: "minor"

# Privacy and boundaries
preferences:
  # Can the watcher summarize your commit messages? Default: true
  summarize_commits: true
  # Can the watcher read and summarize your README? Default: true
  summarize_readme: true
  # Can the watcher link to your repo publicly? Default: true
  public_link: true
  # Should the watcher mention specific contributors by name? Default: false
  name_contributors: false
  # Contact for the watcher maintainers
  contact: "maria@sunsetcommons.org"

# What are you interested in hearing about from OTHER projects?
interests:
  - community-calendar
  - event-aggregation
  - accessibility
  - translation
```

**What the manifest enables:**
- Builder controls what gets surfaced and how
- Interest tags enable matching ("you might care about this change")
- Privacy preferences are explicit and machine-readable
- Neighborhood context adds geographic meaning to changes

### Discovery Flow

```
GitHub Topic Search ("relational-tech")
        │
        ▼
  List of opted-in repos
        │
        ├── Has .reltech.yml? → Use rich config
        │
        └── No manifest? → Use sensible defaults
                            (watch main branch, releases + PRs,
                             minor threshold, no contributor names)
```

---

## 3. What the Watcher Does

### 3a. Scan Cycle

The watcher runs on a schedule (daily or twice-daily via GitHub Actions cron). Each cycle:

1. **Discover** -- Query GitHub API for repos with the `relational-tech` topic. Diff against the known repo list. Flag new repos (celebration!) and removed repos (quiet removal).

2. **Check for changes** -- For each repo, check for new activity since last scan:
   - New releases/tags
   - Merged PRs (not draft, not WIP)
   - Significant commits to watched branches
   - README changes (often signal new directions)
   - New or changed `.reltech.yml`

3. **Filter for significance** -- Not every change matters. Apply filters:
   - Skip automated/bot commits (dependabot, CI)
   - Skip changes below the repo's stated threshold
   - Group related commits into logical changes
   - Respect the repo's `watch.signals` preferences

4. **Summarize** -- For changes that pass the filter, generate a human-readable summary:
   - What changed, in plain language (not git-speak)
   - Why it might matter to the relational tech ecosystem
   - Which project tags/interests this touches
   - Link to the relevant PR, release, or commit

5. **Match** -- Cross-reference the change's tags against other repos' stated interests. Flag potential connections: "Sunset Commons Calendar just added multilingual support -- Eastside Community Hub has 'translation' in their interests."

6. **Publish** -- Write the results to the feed.

### 3b. Significance Filtering

This is the editorial heart of the watcher. Not a simple keyword match -- it needs judgment. The approach:

**Structural signals (cheap, run first):**
- Is this a tagged release? → Likely significant
- Is this a merged PR with a description? → Likely significant
- Is this a single commit that touches only one file with < 5 lines changed? → Likely not significant
- Does the commit message match skip patterns? (deps, typo, lint, format, ci) → Skip
- Is this from a known automation bot account? (dependabot, renovate, github-actions[bot]) → Skip

**A note on AI-assisted commits:** Many relational tech builders use AI coding tools (Claude Code, Cursor, Copilot, etc.). These commits typically show the builder as author (or co-author) and represent real intentional work -- a builder deciding what to build and using AI to help build it. The watcher should treat AI-assisted commits the same as hand-written commits. The filter criteria is "is this change interesting?" not "how was it made?" The automation we skip is infrastructure automation (dependency bots, CI-generated files, auto-formatters) -- things with no human intent behind the specific change. If a builder uses an AI tool to implement a whole new feature, that's the builder's work and should be surfaced.

**Semantic analysis (more expensive, run on candidates):**
- Use an LLM to read the PR description / commit messages and answer: "Would another community tech builder find this interesting? Why?"
- The LLM prompt should be tuned for relational tech context: changes related to accessibility, multilingual support, community engagement features, new integrations, privacy improvements, etc. should score higher
- Output: a 2-3 sentence summary + a significance score (skip / mention / highlight)

**Builder-defined signals:**
- Repos can use conventional commits or PR labels to explicitly signal significance
- A `reltech: highlight` label on a PR = guaranteed inclusion
- A `reltech: skip` label = guaranteed exclusion

---

## 4. The Feed

### Data Model

Each feed entry:

```json
{
  "id": "sunset-commons-calendar-2026-03-15-multilingual",
  "timestamp": "2026-03-15T14:30:00Z",
  "repo": {
    "name": "sunset-commons-calendar",
    "url": "https://github.com/sunsetcommons/calendar",
    "neighborhood": "Outer Sunset, San Francisco",
    "builder": "Maria Chen"
  },
  "change": {
    "type": "pr_merged",
    "title": "Add Spanish and Chinese language support",
    "url": "https://github.com/sunsetcommons/calendar/pull/47",
    "significance": "highlight"
  },
  "summary": "Sunset Commons Calendar now supports Spanish and Chinese, with a language switcher and community-contributed translations. The translation workflow uses simple JSON files so neighbors can contribute without knowing code.",
  "tags": ["multilingual", "translation", "accessibility", "community-calendar"],
  "matches": [
    {
      "repo": "eastside-community-hub",
      "builder": "Devon Parks",
      "reason": "Listed 'translation' as an interest"
    }
  ]
}
```

### Website (updates.relationaltechproject.org)

A static site generated from the feed data. Could be as simple as a GitHub Pages site built with a static site generator (Astro, 11ty, or even plain HTML + a build script).

**Pages:**
- **Feed** -- Reverse-chronological list of meaningful changes across the ecosystem. Each entry shows the project name, neighborhood, summary, and tags. Filterable by tag.
- **Projects** -- Directory of all opted-in repos with their descriptions, neighborhoods, and recent activity. This becomes a lightweight "relational tech ecosystem map."
- **Builder view** -- (future) A filtered feed showing changes matched to a specific builder's interests.
- **About** -- What this is, how to join, the principles behind it.

**Design tone:** Warm, celebratory, neighborhood-newsletter energy. Not a corporate changelog.

### Feed Formats

The underlying data should be available as:
- **JSON feed** -- for programmatic consumption
- **RSS/Atom** -- for anyone using a feed reader
- **HTML** -- the website itself
- **Notion sync** -- (optional) write entries to an RTP Notion database for internal use

This means the rendering is decoupled from the data. New output channels (email digest, Slack bot, etc.) can be added later without changing the core watcher.

---

## 5. Technical Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                   GitHub Actions (cron)                  │
│                    runs daily/2x daily                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  1. DISCOVER                             │
│  GitHub Search API → repos with "relational-tech" topic │
│  Diff against known repo list                           │
│  Fetch .reltech.yml from each (if present)              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  2. WATCH                                │
│  For each repo: check releases, PRs, commits since last │
│  scan. Use GitHub API (REST or GraphQL).                 │
│  Store last-checked timestamps in state file.            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  3. FILTER + SUMMARIZE                   │
│  Structural filters first (cheap)                       │
│  LLM summarization for candidates (Claude API)          │
│  Produce feed entries with summaries + tags              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  4. MATCH                                │
│  Cross-reference change tags with builder interests      │
│  from .reltech.yml files across the network             │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  5. PUBLISH                              │
│  Append to feed.json in the watcher repo                │
│  Trigger static site rebuild                            │
│  (Optional) Write to Notion, send digest                │
└─────────────────────────────────────────────────────────┘
```

### Repository Structure

The watcher itself lives in a GitHub repo (e.g., `relational-tech-project/watcher`):

```
watcher/
├── .github/
│   └── workflows/
│       ├── scan.yml          # Cron job: discover + watch + publish
│       └── build-site.yml    # Triggered by feed changes: rebuild site
├── src/
│   ├── discover.py           # Find repos with relational-tech topic
│   ├── watch.py              # Check repos for new activity
│   ├── filter.py             # Structural significance filtering
│   ├── summarize.py          # LLM-powered summarization
│   ├── match.py              # Cross-reference interests
│   └── publish.py            # Write feed entries, trigger outputs
├── state/
│   ├── repos.json            # Known repos + last-checked timestamps
│   └── feed.json             # The accumulated feed data
├── site/                     # Static site source
│   ├── index.html
│   ├── projects.html
│   └── about.html
├── templates/
│   └── summary_prompt.txt    # The LLM prompt for summarization
├── reltech-manifest-spec.md  # Spec for .reltech.yml
└── README.md
```

### Key Technical Decisions

**Language: Python.** Widely known among civic tech builders, good GitHub API libraries (PyGithub), easy to run in GitHub Actions.

**State management: JSON files committed to the repo.** At 40 repos, the state is small. No database needed. The feed.json file is both the data store and the source for the static site. Git history gives you a full audit trail of what was surfaced and when.

**LLM: Claude API (Haiku for filtering, Sonnet for summaries).** Haiku is cheap enough to run against every candidate change. Sonnet produces better prose for the actual summaries that builders will read. Cost at 40 repos with a few changes per day: likely under $5/month.

**Static site: 11ty or Astro.** Both are simple, fast, and can consume JSON data directly. The site rebuilds automatically when feed.json changes.

**GitHub API rate limits:** Authenticated requests get 5,000/hour. At 40 repos, a full scan uses maybe 200 requests. Plenty of headroom.

---

## 6. Privacy & Licensing

### What the Watcher Reads

| Data | Read? | Notes |
|------|-------|-------|
| Repo name, description, topics | Yes | Public GitHub metadata |
| README content | Yes (if permitted) | Summarized, not reproduced |
| Commit messages | Yes (if permitted) | Used for filtering + summary |
| PR titles and descriptions | Yes (if permitted) | Used for filtering + summary |
| Release notes | Yes | Public by nature |
| Source code | **No** | Never cloned, never indexed |
| Issues / discussions | **No** | Too noisy, privacy concerns |
| Contributor identities | **No** (unless permitted) | Default: attribute to project, not person |

### License Compliance

- The watcher only reads publicly available metadata (commit messages, PR descriptions, release notes, READMEs). It does not reproduce source code.
- Summaries are original text generated by the LLM, not copies of repo content.
- If a repo has no license, the watcher still works (it's reading metadata, not code) but the summary should note the project and link to it rather than describing implementation details.
- Repos can set `preferences.summarize_commits: false` in their manifest to prevent the watcher from reading their commit messages.

### Privacy Defaults

The defaults are designed to be conservative:

- **Don't name individual contributors** unless the manifest says `name_contributors: true`. Attribute work to the project/builder identity instead.
- **Don't surface draft PRs, WIP branches, or issues.** Only watch merged/completed work on declared branches.
- **Don't editorialize about project quality.** The watcher celebrates what shipped, it doesn't review or critique.
- **Don't track contributor activity patterns.** The watcher checks what changed, not who's working when.

### Opting Out

- **Remove the `relational-tech` topic** from the repo. The watcher's next scan will notice the repo is no longer tagged and stop watching it. Previous feed entries remain (they describe public events that happened) but no new entries are created.
- **Add `watch: none` to `.reltech.yml`** to stay in the directory but stop generating feed entries.
- **Contact the watcher maintainers** to request removal of historical entries if needed.

---

## 7. Matching & Routing

The matching system connects changes to builders who'd care. This starts simple and can grow.

### Phase 1: Tag-based matching

Each change produces tags (from the repo's manifest + LLM-inferred tags from the summary). Each repo declares interests in its manifest. A match happens when a change's tags overlap with another repo's interests.

Matches appear as a "you might be interested" note on feed entries and on the projects page.

### Phase 2: Builder profiles (future)

Builders can have a profile beyond their repos -- declaring interests at a personal level. This enables matching even when a builder's repo tags don't fully capture what they care about. (e.g., a builder with a mutual aid app might also be interested in community calendar changes for integration reasons.)

### Phase 3: Subscriptions (future)

Builders can subscribe to specific tags, projects, or builders. Subscriptions generate personalized digests (email, RSS filter, or a custom feed URL like `updates.relationaltechproject.org/feed/maria`).

---

## 8. Celebrating New Repos

When a new repo appears with the `relational-tech` topic, it's a moment worth marking. The watcher should:

1. **Generate a welcome entry** in the feed: "New project in the network: [name]. [Summary from README]. Built by [builder] in [neighborhood]."
2. **Check for interest matches** with existing repos and note them.
3. **Add to the projects directory** on the site.

This makes joining the network feel like arriving somewhere, not just flipping a switch.

---

## 9. Getting Started -- Implementation Phases

### Phase 0: Seeding (1-2 days)
- Create the `watcher` repo
- Write the `.reltech.yml` spec and publish it
- Ask 3-5 friendly builders to add the `relational-tech` topic to their repos and optionally add a manifest
- Manually test: can we discover these repos and read their recent activity?

### Phase 1: Core pipeline (1-2 weeks)
- Implement discover + watch + filter (Python scripts)
- Add LLM summarization (Claude API)
- Output feed.json
- Set up GitHub Actions cron job
- Build minimal static site (even just a styled HTML page reading from feed.json)
- Deploy to updates.relationaltechproject.org

### Phase 2: Matching + polish (1-2 weeks)
- Implement tag-based matching
- Add the projects directory page
- Add RSS/Atom feed
- Refine the significance filter based on real data
- Write the "about" page and joining guide

### Phase 3: Network effects (ongoing)
- Invite more builders to tag their repos
- Add builder profiles / subscriptions
- Consider email digests
- Consider Notion sync for RTP internal use
- Iterate on what "meaningful" means based on builder feedback

---

## 10. Open Questions

1. **Naming:** Is "relational-tech" the right topic tag? It's clear but not widely used yet. Alternatives: `relational-technology`, `community-tech`, `civic-tech` (too broad?). Could use multiple: `relational-tech` + a more specific one like `rtp-network`.

2. **Who runs it?** The watcher needs a GitHub account with API access and a Claude API key. Is this an RTP infrastructure concern, or could it be community-maintained?

3. **Digest frequency:** Daily feed updates on the site, but should there be a weekly digest email? What's the right rhythm for builders who don't check a website regularly?

4. **Cross-pollination prompts:** Beyond "you might be interested," should the watcher actively suggest conversations? e.g., "Maria and Devon are both working on multilingual community tools -- consider connecting them." This is powerful but crosses from informing into matchmaking.

5. **Non-GitHub repos:** What about projects on GitLab, Codeberg, or self-hosted? Phase 1 is GitHub-only, but the architecture should leave room for other forges.

6. **Quality of LLM summaries:** The summaries are the main thing builders will read. They need to be warm, accurate, and useful. This requires good prompt engineering and probably some human review early on. The `templates/summary_prompt.txt` file should be iterable.
