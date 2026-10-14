---
name: my-world
description: >
  Build and maintain a "My World": the canon of an animated series (characters, their looks, sizes, personalities
  and voices; the world, its locations and recurring props; the art style and video format) as one project folder
  with Identities.md, Setting.md and world.json, the reference pictures (three-view character sheets, empty location
  sets, prop pictures, group pictures, a height chart), designed character voices, and world.html, the
  summary page every story links back to. Use whenever the user wants to create a new world / series / cast / set of
  characters for videos, add or change a character, location, prop or voice in an existing world, redraw a sheet or
  set, or rebuild the overview page. Stories made in the world (topic → keyframes → videos) use the companion skill
  world-stories.
---

# My World

**There is only one world**, and `_world/` is that world's folder. Everything a story needs to stay consistent lives
in it, and every render reads it:

```
my-world/               (this skill)
  _input/               the user's raw material (name depends on the environment, see below; git-ignored)
  _world/               the world (git-ignored):
    world.json            manifest: name, tagline, format (ratio, sizes, durations, audio), characters, group pictures
    Identities.md         canon: style, each character (look, size, personality, voice), the cast together, audio rule
    Setting.md            canon: the world, its look, locations, recurring props, rules
    world.md              status, lessons learned, session log, pending tasks
    world.html            the "My World" page (build_overview.py): characters, voices, world, locations, props, tasks
    _asset/               only what generation uses: <char>.png sheets, settings/<loc>.png, props/<prop>.png,
                          voices/<char>.wav, group pictures, height_chart.png
    _reference/           prompts, logs, source photos (*/refs/), input/ (copy of the raw input), voice samples, archive/
    _tasks/               stories (world-stories skill), one folder per topic
```

**The raw input folder.** The user's raw material (brief, notes, photos, sketches, voice samples) arrives in a
folder whose name depends on the environment: `_input/`, `upload/`, `mnt/`, `input/`, `in/`, or wherever the user
says. **The user decides which folder it is.** `worldlib.py inputs` lists the candidates (env `MY_WORLD_INPUT`
wins); if it finds none or several, ask the user, never guess. Read everything in it before interviewing: a brief
there answers most questions, and sheets or photos there are the strongest references. The raw folder may be
archived or emptied later, so the world must never point at it: `new_world.py --input [DIR]` copies it to the
world's `_reference/input/` (with `SOURCE.txt` naming where it came from), and every path in the canon and
world.json points inside `_world/`. For material added to an existing world, copy it into `_reference/input/` the
same way. Then sort the pictures: photos and sketches → `_reference/*/refs/`; a raw picture goes to `_asset/` only
after it passes the checks below. Every script finds `_world/` on its own (`--world DIR` overrides).

**Raw pictures used directly as assets.** A user's character sheet, set or prop picture may be good enough to use
as is (redrawing loses details the user wants). Validate it first, and say what you found:
1. `worldlib.py inspect <file> sheet|set|any`: resolution at least 1080 px on the short side (the generated assets
   are 2K), 16:9 like the other assets, RGB, and for a sheet a plain light background at the edges.
2. Look at it (Read the image): full figures not cropped, the three views (front, side, back) all present and
   showing the same outfit and colours, sharp hands, faces, hair and feet, no text, logos, watermark or borders, no
   extra characters, and the same art style as the rest of the world.
3. It matches the canon, or you change the canon to match it (e.g. hair parting, outfit), so text and picture agree.
If it passes, copy it into `_asset/` (the old asset is archived) and redraw what depends on it: group pictures, the
height chart. If it fails, use it as a reference for a redraw instead and tell the user why.

**One world only.** Never create a second world or a sub-folder per world. When `_world/world.json` exists and the
user asks for a "new world", a new cast or new characters, places or props, **merge them into the existing world**
(see Changing an existing world): new character and location sections in the canon, entries in world.json, then draw
what is new. If the new material conflicts with the canon (another art style, format or setting), ask the user which
wins before changing it. `new_world.py` refuses to run over an existing world.

**The canon contract.** In `Identities.md` and `Setting.md`, a `<!-- prompt:<key> -->` marker followed by a fenced
block is pasted word for word into prompts. Required: `style`, `characters`, `video-defs`, `video-rules`, `audio`,
`world`, `location:<key>` (one or more), and `voice` when the format has audio. Per character: `sheet:<char>` (sheet
design brief) and `voice:<char>` (voice design). Optional: `props`, `prop:<key>`, `group:<name>`. Full description of
every block and of world.json: `references/world_format.md`. Read it before writing the canon.

Scripts are in `scripts/` (run with `python <skill>/scripts/<name>.py …`; they use `_world/` unless `--world DIR` is given):

| Script | Does |
|---|---|
| `new_world.py [--name "…"] [--input [DIR]]` | skeleton from `templates/` in `_world/`, plus a copy of the raw input; refuses if a world exists |
| `worldlib.py check [groups]` | dependencies + canon completeness (`world` group lists every REPLACE left); `canon [key]`; `info`; `inputs` (raw input folders); `inspect <img>` (fit to use as an asset?) |
| `world_images.py sheet\|set\|prop\|group\|height …` | draws the reference pictures from the canon (`--dry-run` = prompts only) |
| `voices.py [script.json] design\|dialogue\|page\|all` | character voices (Seed Audio) → `_asset/voices/` |
| `build_overview.py` | `world.html` + nav bars on every page |

Generation needs no other skill: `scripts/ark/` holds the Seedream (images) and Seedance (videos) scripts, the
skill's `config.json` the endpoints and default model ids (`image_model_id`, `video_model_id`,
`audio_model_id`; a world's `models` overrides them). Keys go in the
skill's `credential.json` (git-ignored; template `credential_tmp.json`): `model_ark_key` for images and videos,
`speech_model_api_key` for voices (Seed Audio; the ARK key is rejected there). Env vars of the same names win. Run
`worldlib.py check` first; **if it prints `DEPENDENCY ERROR`, stop and give the user the message verbatim**, do not
work around it.

## Prerequisites: check them before any work starts

Before building (or adding to) a world, check the list below against what the user has given and **tell the user
in one message everything mandatory that is still missing**, with where to put it. Do not start generating until
the mandatory items are there; ask for the recommended ones in the same message, but they do not block.

**Setup (mandatory, once):** `worldlib.py check` passes. It needs:

| Item | For | Where |
|---|---|---|
| Python 3 with `requests`, `Pillow` (`numpy` for post-processing) | every script | `pip install requests pillow numpy` |
| BytePlus ARK API key | images (Seedream), videos (Seedance) | `model_ark_key` in the skill's `credential.json` |
| BytePlus speech API key (a different key: the ARK key is rejected) | voices (Seed Audio), when the format has audio | `speech_model_api_key` in the same file |
| `ffmpeg` on PATH | voice and video processing | system install |

`credential.json` is git-ignored; copy `credential_tmp.json` to make it. Never ask the user to paste a key in chat:
ask them to put it in the file (or the env var of the same name) themselves.

**Content (mandatory):** a brief, in the raw input folder or in chat, that gives:
- **The input folder:** which folder holds the raw material (`_input/`, `upload/`, `mnt/`, `input/`, `in/`, …); ask
  if `worldlib.py inputs` finds none or several.
- **The cast:** each character's name, species and age, looks (hair/fur, eyes, clothes, colours), personality, how
  they talk, and **real sizes as numbers** (height in cm; shoulder height for animals).
- **The world:** place and era, the home base, and 3–6 other locations.
- **The art style** (e.g. 3D Pixar-like cartoon).
- **The format:** aspect ratio, short-clip and long-take lengths, audio or not (music, or conversation only).
- **Languages:** what each character speaks, and any accent or dialect rule.

**Recommended (strongly; they anchor the results far better than text):**
- **Character sheets or photos** (front, side, back): a good sheet is used directly once it passes the raw-picture checks.
- **One picture per location:** it fixes the layout of the set.
- **Prop photos** for recurring objects.
- **Voice recordings, 30 s or less per character:** voices are cloned from them; otherwise they are designed from text.

**Decided along the way, with the user:** approve the character sheets, then the location sets, then the group
pictures and height chart, then the voices.

## Building the world (only when `_world/` has no world.json)

1. **Interview** (short; skip what the user already said): fill the gaps in the mandatory content above, item by
   item, and ask once for the recommended pictures and recordings.
2. **Skeleton:** `new_world.py --input [DIR]` (the world is called "My World"; keep `name`, the tagline and the file
   headings general, without character names, since more casts may be merged in). Put the user's photos in `_reference/characters/refs/<char>*.jpg`,
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
8. **Overview:** `build_overview.py`, then open `world.html` for the user. Update world.md (session log,
   pending tasks, open questions).

Pictures are cheap previews: render them without asking, then present them. Never redraw an approved asset without
the user asking; an old version is archived automatically when one is redrawn.

## Changing an existing world (also: adding a "new" cast or world to it)

- Change the canon first (the block and the prose around it), then redraw what depends on it (sheet, set, prop),
  then `build_overview.py`. A new location = a new `#### Title (`key`)` section with its `location:<key>` block +
  `world_images.py set <key>`. Never patch a description inside one story's prompt.
- Decisions the user makes ("keep the pictures as they are", "no music") go into the canon and world.md right away.

## Lessons that apply to every world

`references/lessons.md`: style drift from photo references, sizes, counts, colours on warm backgrounds, text in
pictures, editing vs. regenerating. Read it before writing prompt blocks.
