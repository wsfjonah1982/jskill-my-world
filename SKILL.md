---
name: my-world
description: >
  Build and maintain a "My World": the canon of an animated series (characters, their looks, sizes, personalities
  and voices; the world, its locations and recurring props; the art style and video format) as one project folder
  with Identities.md, Setting.md and world.json, the reference pictures (three-view character sheets, empty location
  sets, prop pictures, group pictures, a height chart), designed character voices, and project_overview.html, the
  summary page every story links back to. Use whenever the user wants to create a new world / series / cast / set of
  characters for videos, add or change a character, location, prop or voice in an existing world, redraw a sheet or
  set, or rebuild the overview page. Stories made in the world (topic → keyframes → videos) use the companion skill
  world-stories.
---

# My World

A world is one folder. Everything a story needs to stay consistent lives in it, and every render reads it:

```
<world>/
  world.json            manifest: name, tagline, format (ratio, sizes, durations, audio), characters, group pictures
  Identities.md         canon: style, each character (look, size, personality, voice), the cast together, audio rule
  Setting.md            canon: the world, its look, locations, recurring props, rules
  README.md             status, lessons learned, session log, pending tasks
  project_overview.html the "My World" page (build_overview.py): characters, voices, world, locations, props, tasks
  _asset/               only what generation uses: <char>.png sheets, settings/<loc>.png, props/<prop>.png,
                        voices/<char>.wav, group pictures, height_chart.png
  _reference/           prompts, logs, source photos (*/refs/), voice samples, archive/ (old versions)
  _tasks/               stories (world-stories skill), one folder per topic
```

**Where things go.** The user drops raw material (briefs, notes, photos, sketches, voice samples) in the skill's
`_input/`; read it before interviewing. Worlds are created in `_world/<world>/`. Both folders are git-ignored.

**The canon contract.** In `Identities.md` and `Setting.md`, a `<!-- prompt:<key> -->` marker followed by a fenced
block is pasted word for word into prompts. Required: `style`, `characters`, `video-defs`, `video-rules`, `audio`,
`world`, `location:<key>` (one or more), and `voice` when the format has audio. Per character: `sheet:<char>` (sheet
design brief) and `voice:<char>` (voice design). Optional: `props`, `prop:<key>`, `group:<name>`. Full description of
every block and of world.json: `references/world_format.md`. Read it before writing the canon.

Scripts are in `scripts/` (run with `python <skill>/scripts/<name>.py … --world <folder>`; inside the world folder
`--world` can be left out):

| Script | Does |
|---|---|
| `new_world.py <folder> --name "…"` | skeleton from `templates/` |
| `worldlib.py check [groups]` | dependencies + canon completeness (`world` group lists every REPLACE left); `canon [key]`; `info` |
| `world_images.py sheet\|set\|prop\|group\|height …` | draws the reference pictures from the canon (`--dry-run` = prompts only) |
| `voices.py [script.json] design\|dialogue\|page\|all` | character voices (Seed Audio) → `_asset/voices/` |
| `build_overview.py` | `project_overview.html` + nav bars on every page |

Generation runs through the **video-workflow** skill (`…/skill/video-workflow`, or env `VIDEO_WORKFLOW_DIR`):
Seedream for images, BytePlus ARK API key in its credential.json or env `model_ark_key`. Voices need the BytePlus
speech key (env `speech_model_api_key`, or a credential file named by world.json `speech_credential`). Run
`worldlib.py check` first; **if it prints `DEPENDENCY ERROR`, stop and give the user the message verbatim**, do not
work around it.

## Building a new world

1. **Interview** (short; skip what the user already said). The cast: who, how many, names, species/age, looks,
   personality, how each talks, relative sizes. The place and era; the home base and 3–6 other locations; the art
   style; the format (ratio, short-clip length, long-take length, music or conversation only); language(s). Ask for
   any photos or sketches (characters, rooms, props, voices): they anchor the pictures far better than text.
2. **Skeleton:** `new_world.py <folder> --name "…"`. Put the user's photos in `_reference/characters/refs/<char>*.jpg`,
   `_reference/settings/refs/<loc>_photo.jpg`, `_reference/props/refs/<prop>*.jpg`, voices in `_reference/voices/refs/`.
3. **Write the canon:** fill `world.json`, `Identities.md`, `Setting.md` (one section per character and per location;
   keep the `#### Title (`key`)` heading form). Replace every `REPLACE`. Prompt blocks are short, concrete, positive
   descriptions; put the style line first; state sizes as numbers and ratios; name the details models drift on
   (eye size, ear shape, colour on warm backgrounds…) in every block that needs them. `worldlib.py check world`
   lists what is still missing (sheets are drawn in step 4).
4. **Character sheets:** `world_images.py sheet` (all, or named). Show each sheet to the user (Read the image) and
   ask for approval. Redraw from a changed `sheet:<char>` block, never by editing the picture: edits keep old details.
   The sheets are the identity reference for every later render, so do not move on until they are approved.
5. **Locations and props:** `world_images.py set` (all or named; the first one sets the style for the rest, so draw
   the home base first and, once approved, list it in world.json `style_refs`). Props only when recurring:
   `world_images.py prop <key>`. Show and approve.
6. **Group pictures:** `world_images.py height` (from `height_cm` in world.json; check the scale, models draw small
   characters too big) and any group scenes (`group <name> --location <key>` with a `group:<name>` block or
   `--scene "…"`). Add the approved ones to world.json `groups`.
7. **Voices** (if the format has audio): write `_reference/voices/samples.json` (one sample line per character in
   their own voice, plus a short `turns` dialogue), `voices.py design`, then `voices.py dialogue` and `voices.py page`.
   The user listens on `_reference/voices/voices.html` and approves; delete a clip to redesign it.
8. **Overview:** `build_overview.py`, then open `project_overview.html` for the user. Update README.md (session log,
   pending tasks, open questions).

Pictures are cheap previews: render them without asking, then present them. Never redraw an approved asset without
the user asking; an old version is archived automatically when one is redrawn.

## Changing an existing world

- Change the canon first (the block and the prose around it), then redraw what depends on it (sheet, set, prop),
  then `build_overview.py`. A new location = a new `#### Title (`key`)` section with its `location:<key>` block +
  `world_images.py set <key>`. Never patch a description inside one story's prompt.
- Decisions the user makes ("keep the pictures as they are", "no music") go into the canon and README right away.

## Lessons that apply to every world

`references/lessons.md`: style drift from photo references, sizes, counts, colours on warm backgrounds, text in
pictures, editing vs. regenerating. Read it before writing prompt blocks.
