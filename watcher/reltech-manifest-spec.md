# .reltech.yml Specification

**Version:** 1

A `.reltech.yml` file is an optional manifest that a repository can include at its root to participate more richly in the Relational Tech Network. Any public repo with the `relational-tech` GitHub topic is part of the network; the manifest lets you control how your project appears and what you hear about.

## Full Example

```yaml
# .reltech.yml
version: 1

project:
  name: "Sunset Commons Calendar"
  description: "Community event calendar for the Outer Sunset neighborhood"
  neighborhood: "Outer Sunset, San Francisco"
  builder: "Maria Chen"

tags:
  - community-calendar
  - events
  - neighborhood-info
  - multilingual

watch:
  branches: ["main"]
  signals: ["releases", "prs"]
  threshold: "minor"

preferences:
  summarize_commits: true
  summarize_readme: true
  public_link: true
  name_contributors: false
  contact: "maria@sunsetcommons.org"

interests:
  - community-calendar
  - event-aggregation
  - accessibility
  - translation
```

## Fields

### `version` (required)

Integer. Currently `1`. Allows future spec changes without breaking existing manifests.

### `project`

Describes the project. All fields are optional; if omitted, the watcher uses the repo name and GitHub description.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable project name |
| `description` | string | What the project does, in a sentence or two |
| `neighborhood` | string | Where this project lives (city, neighborhood, region) |
| `builder` | string | Name of the primary builder or organization |

### `tags`

List of strings. Topic tags that describe what this project is about. Used for matching with other projects' interests. Use short, lowercase, hyphenated tags.

Suggested tags (not exhaustive): `community-calendar`, `mutual-aid`, `events`, `neighborhood-info`, `civic-engagement`, `multilingual`, `accessibility`, `local-news`, `resource-directory`, `mapping`, `organizing`, `translation`, `communication`, `safety`, `food`, `housing`, `health`, `education`, `youth`, `elder-care`.

### `watch`

Controls what the watcher pays attention to.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `branches` | list of strings | `["main", "master"]` | Which branches to watch for commits |
| `signals` | list of strings | `["releases", "prs"]` | What types of changes to look for. Options: `releases`, `prs`, `commits`, `readme-changes` |
| `threshold` | string | `"minor"` | Minimum significance. `patch` = surface everything. `minor` = skip single-file commits (default). `major` = only releases and explicitly highlighted items. |

Setting `watch` to the string `"none"` (instead of an object) will keep the project in the directory but stop generating feed entries.

### `preferences`

Privacy and display preferences. All default to conservative values.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `summarize_commits` | boolean | `true` | Can the watcher read and summarize commit messages? |
| `summarize_readme` | boolean | `true` | Can the watcher read and summarize the README? |
| `public_link` | boolean | `true` | Can the watcher link to the repo publicly? |
| `name_contributors` | boolean | `false` | Can the watcher mention individual contributor names? |
| `contact` | string | none | Email or URL for the watcher maintainers to reach you |

### `interests`

List of strings. Tags describing what you want to hear about from other projects. When another project ships a change that matches your interests, it will be flagged as a potential connection.

Use the same tag vocabulary as the `tags` field.

## Joining the Network

1. Add the `relational-tech` topic to your GitHub repository
2. (Optional) Add a `.reltech.yml` file to your repo root
3. The watcher will discover your project on its next scan

## Leaving the Network

Remove the `relational-tech` topic from your repo. The watcher stops watching immediately on its next scan. To stay in the directory but stop generating feed entries, set `watch: "none"` in your manifest.
