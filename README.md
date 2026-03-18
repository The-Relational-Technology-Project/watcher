# Relational Tech Watcher

A network feed for the relational tech ecosystem. Watches public GitHub repositories that have opted in via the `relational-tech` topic tag, surfaces meaningful changes, and helps community technology builders learn from each other's work across neighborhoods.

Built by the [Relational Tech Project](https://relationaltechproject.org).

## How it works

The watcher runs on a schedule (via GitHub Actions) and:

1. **Discovers** repos with the `relational-tech` GitHub topic
2. **Watches** for new releases, merged PRs, and significant commits
3. **Filters** out noise (bot commits, dependency bumps, trivial changes)
4. **Summarizes** meaningful changes in plain language using AI
5. **Matches** changes to other projects that share interests
6. **Publishes** a feed to [updates.relationaltechproject.org](https://updates.relationaltechproject.org)

## Joining the network

Add the topic `relational-tech` to your GitHub repository. That's it.

For richer participation, add a [`.reltech.yml`](reltech-manifest-spec.md) file to your repo root. This lets you describe your project, set privacy preferences, and declare interests.

## Setup (for maintainers)

### Requirements

- Python 3.11+
- A GitHub personal access token (for API access)
- An Anthropic API key (for AI-powered summaries)

### Local development

```bash
pip install -r requirements.txt

export GITHUB_TOKEN=your_github_token
export ANTHROPIC_API_KEY=your_anthropic_key

python -m src.main
```

### GitHub Actions

The watcher runs automatically via GitHub Actions. You'll need to add two repository secrets:

- `WATCHER_GITHUB_TOKEN`: A GitHub personal access token with `public_repo` scope
- `ANTHROPIC_API_KEY`: Your Anthropic API key

### Deploying the site

The site deploys to GitHub Pages automatically when `site/` or `state/feed.json` changes on the `main` branch. To set up:

1. Go to Settings > Pages in this repo
2. Set Source to "GitHub Actions"
3. (Optional) Add a custom domain: `updates.relationaltechproject.org`

## Principles

- **Consent-first.** Repos must actively opt in via the topic tag.
- **Celebrate, don't surveil.** The tone is "look what this builder shipped."
- **Respect boundaries.** The watcher reads public metadata, never source code.
- **Low friction.** Join in 2 minutes, leave by removing a tag.

## Architecture

See [reltech-watcher-architecture.md]([../reltech-watcher-architecture.md](https://github.com/The-Relational-Technology-Project/watcher/blob/main/reltech-watcher-architecture.md)) for the full design document.

## License

MIT
