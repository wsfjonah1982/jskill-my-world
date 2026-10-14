# Scoring method (reusable)

How a project is scored, written so that any project (a world, a story, a design system) can reuse it. The numbers
live in a template, `templates/scoring.json`; the code (`scripts/evaluate_world.py`, `scripts/build_overview.py`)
only applies them. To reuse: copy `scoring.json`, change the criteria, parts and thresholds, and keep the rules
below. **Every new project starts with the default template unchanged.** Only when the user asks to customize the
scoring, copy it into the project (a world: its own `scoring.json` at the world root, which then wins) and change it
there; the default stays as it is.

## The parts

| Part | Scored? | Who measures it | Formula |
|---|---|---|---|
| **Quality** | yes, weight `weights.quality` (50%) | the reviewer, after looking at (and listening to) every asset | Σ(weight × (score − 1) / 4) / Σ weight × 100 |
| **Breadth** | yes, weight `weights.breadth` (50%) | counted by the script | Σ(weight × part score) / Σ weight; part score = min(count, full) / full × 100 |
| **Checklist** | no, a gate | counted by the script | items done / items checked × 100 |
| **Approvals** | no, a gate | the user (`approved` {path: date}) | approved / assets |

**Overall** = `weights.quality` × quality + `weights.breadth` × breadth, given only once every quality criterion is
scored. The band comes from `bands` (first one whose threshold the overall reaches).

**Gates:** a missing checklist item or an unapproved asset means "not ready", whatever the score. An approval is
void once the asset changes after the approval date.

## Quality rubric

Each criterion in `quality.criteria` has an `id`, a `label`, a `weight` and `means_5` (what a perfect score looks
like). The reviewer scores 1–5: 1 fails, 3 usable with visible flaws, 5 no flaw found. Rules:
- Score only what was checked. Whatever the reviewer could not check (a voice, an accent) is 3 at most, and the note
  says so, until the user approves it.
- Never score your own work up. Each note names the evidence.
- A review older than the newest change to the canon or the assets is stale: review again.

## Breadth parts

Each part in `breadth.parts` has a `weight`, a `minimum` and `full` marks. Counting stops at `full`. A count below
`minimum` is also a missing checklist item. `"per_location"` ties a part to another count: one per location, so its
minimum and full marks equal the number of locations.

## Colour coding (`status`)

| Colour | Badge | Scores 0–100 (`status.score`) | Criteria 1–5 (`status.criterion`) | Breadth part | Checklist area | Approvals |
|---|---|---|---|---|---|---|
| green | Pass | ≥ pass (75) | ≥ pass (4) | count ≥ full | all done | all approved |
| amber | Check | ≥ check (60) | ≥ check (3) | minimum ≤ count < full | – | some waiting |
| red | Fail | below check | below check | count < minimum | an item missing | – |

In Markdown reports the colours are 🟢 🟡 🔴.

## The report

- **Short summary:** the date, the band, one card per part (value, badge, weight) and one line of what's left
  (missing items, assets to approve, open issues).
- **Score details popup:** the overall formula with its numbers, then quality (formula, table of criteria with
  badges and notes), breadth (formula, table: weight, count, minimum, full marks, part score, points), the checklist
  (per area: done / checked, what's missing), approvals and issues. A legend explains the colours.
- **Markdown:** one table (status, score, value, calculation) and one line each for missing items, issues and
  assets waiting for approval.
- **Data:** `evaluation.json` holds every number above, plus `weights`, `status` and `scoring_file`, so a page can
  be rebuilt without recalculating.
