# World format

## world.json

| Field | Meaning |
|---|---|
| `name`, `tagline`, `chips` | title, one-paragraph summary and fact chips on the overview page |
| `format.ratio` | `16:9`, `9:16` or `1:1`; `keyframe_size` must have the same shape (`2560x1440`, `1440x2560`, `2048x2048`) |
| `format.resolution` | video resolution, e.g. `720p` |
| `format.short_min/short_max/short_options` | short-footage length range and the choices on the keyframes page (seconds) |
| `format.segment_seconds` | long-take segment length (one video call each; ≤ the video model's maximum) |
| `format.audio` | `true` = videos have sound (then the `voice` block is required) |
| `characters[]` | `key` (used in files and story specs), `name`, `label` ("the cat"), `kind` (noun for count rules: "exactly one cat"), `tag` (`<Cat>`, used in video prompts), `pronoun`, `sheet` (path), `colour`, `height_cm` + `height_note`, `facts` (overview bullets), `voice_src`, `main` (false = not in the default cast) |
| `groups[]` | `{path, caption}` group pictures on the overview |
| `height_chart` | path of the height chart (default `_asset/height_chart.png`), passed as a reference whenever 2+ characters are in a frame |
| `style_refs` | pictures that carry the rendering style for new sets and props (default: the first location picture) |
| `world_cards[]` | `{title, text}` cards in the World section of the overview |
| `voices_lead`, `docs[]`, `workflow_diagram` | overview extras |
| `no_props_rule` | sentence used when a frame names no props (stops the model drawing every recurring prop) |
| `negative_image`, `negative_video` | negative lines appended to image / video prompts |
| `models` | override `image`, `video`, `speech`, `speech_endpoint` model ids |
| `speech_credential` | optional JSON file with `speech_model_api_key`; default: the skill's `credential.json` (or the env var) |
| `sheet_size`, `sheet_style` | character-sheet size (default `2K`) and style string (default the `style` block) |

## Canon blocks

Marker + fenced block, anywhere in Identities.md or Setting.md:

````
<!-- prompt:location:park -->
```text
Neighbourhood park: a smooth path through wide lawns …
```
````

Whitespace is collapsed to single spaces. Keep each block to one paragraph.

| Key | Used in | Write |
|---|---|---|
| `style` | first line of every prompt | the art style in one line |
| `characters` | every image prompt | every character's key look and size in one paragraph |
| `sheet:<char>` | character sheet | full appearance brief for a front/side/back sheet |
| `video-defs` | every video prompt | "Define the <features> of the <kind> in @image1 as <Tag>." per character + "keeps exactly its look" |
| `video-rules` | every video prompt | count rule (exactly one of each), no clones, the world's hard rules |
| `voice` | video prompts with audio | how each `<Tag>` sounds and talks |
| `voice:<char>` | voice design (voices.py) | the voice alone in 2–4 sentences |
| `audio` | every video prompt | what is heard (e.g. conversation only, no music) |
| `world` | sets | the place, palette, light, what never appears |
| `location:<key>` | keyframes, sets, storyboards, videos | the place as one paragraph |
| `props` | frames that name props | how each recurring prop looks |
| `prop:<key>` | prop pictures | one prop in detail |
| `group:<name>` | group pictures | the scene of that picture |

## Overview page parsing

- Locations: each `location:<key>` block; title and summary from the `#### Title (`key`)` heading and its bullets in
  Setting.md; a `Reference:` line containing "layout only" shows a warning badge.
- Props: the `## Recurring props` table (`| Prop | Look |`), with `Reference: `_asset/props/x.png`` in the Look
  cell for a picture; any other picture in `_asset/props/` is shown too.
- Voices: `_reference/voices/samples.json` and `voices_meta.json` (written by voices.py).
