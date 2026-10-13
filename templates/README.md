# {{NAME}}

A "My World" project: characters, places and voices that every story is built on.

- **Start page:** [`project_overview.html`](project_overview.html) (rebuild: my-world `build_overview.py`).
- **Canon:** [`Identities.md`](Identities.md) (characters, voices) and [`Setting.md`](Setting.md) (world, locations,
  props). Every keyframe and video prompt takes its style, characters, location and props from their
  `<!-- prompt:... -->` blocks. Change a character or a place there, never in a single prompt.
- **Manifest:** [`world.json`](world.json): names, format (ratio, sizes, durations), characters, group pictures.
- **Stories:** made with the world-stories skill, one folder per topic in `_tasks/<date>_<slug>/`.

## Folders

| Path | What |
|---|---|
| `_asset/` | only what generation uses: character sheets, group pictures, `settings/`, `props/`, `voices/`, height chart |
| `_reference/` | prompts, logs, source photos (`*/refs/`), voice design files, `archive/` (old versions) |
| `_tasks/` | one folder per story topic |

## Lessons learned

- (what drifted and how it was fixed)

## Session log — {{DATE}}

- World created.

## Pending tasks — continue here next time

1. Fill the canon, draw the sheets and sets, design the voices.
