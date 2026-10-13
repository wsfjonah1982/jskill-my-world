# Identities — {{NAME}}

The canonical description of every character. **Every image or video generated for this world must take its
character descriptions from this file** (together with [`Setting.md`](Setting.md) for the environment). If something
here changes, it changes for all future renders.

- Reference sheets (front / side / back): `_asset/<key>.png`, one per character (paths in `world.json`).
  Always pass them as image references; the text below backs them up, it does not replace them.
- Blocks marked `<!-- prompt:... -->` are pasted word for word into prompts (my-world `worldlib.py canon`).
  Keep them short, concrete and positive; say the things the model gets wrong in every block that needs them.

## Overall style

<!-- prompt:style -->
```text
REPLACE: one line, e.g. 3D Western animation style, Pixar-like stylized cartoon, bright saturated colours, clean CG cartoon shading, soft daylight
```

- What the style is not (e.g. no photorealism, no anime). Photo references pull towards realism, so the style line
  always comes first in a prompt.
- Characters keep exactly their sheet look in every shot: no costume changes unless the story asks for one.

---

## REPLACE Hero Name — the girl (`<Hero>`)

<!-- Copy this whole section once per character. The key (`hero`) must match world.json. -->

| | |
|---|---|
| Role | Their place in the cast. |
| Who | Age, background. |
| Size | Height (standing, or shoulder height for animals) and size relative to the others. |
| Sheet | `_asset/hero.png` · colour `#f4a6c1` |

**Appearance**
- Face, hair, eyes, body, outfit — the details that must never drift. Bold what the model gets wrong.

**Personality and acting**
- Personality, what makes them funny, how they move and react.

**Voice and speech**
- How they talk (language, accent, vocabulary), pitch and texture, example lines.

**Never:** what must never happen to this character (wrong colour, wrong size, wrong food, …).

Design brief for the character sheet (my-world `world_images.py sheet hero`):

<!-- prompt:sheet:hero -->
```text
REPLACE: full appearance for a three-view character sheet: who, age, build, face, hair, eyes, outfit, colours, signature details.
```

Voice design (my-world `voices.py`):

<!-- prompt:voice:hero -->
```text
REPLACE: the voice in 2–4 sentences: age and gender of the voice, pitch, texture, accent, pace, attitude.
```

---

## The cast together

- Count rule: exactly one of each character in every shot where they appear.
- Size order and ratios (height chart: `_asset/height_chart.png`).
- The dynamic: who is the warm centre, who is the comic foil, where the humour comes from.

<!-- prompt:characters -->
```text
REPLACE: one paragraph with every character's key look and size, e.g. Name: age, height, hair, eyes, outfit. Name2: ...
```

Video prompts define the characters from the first frame (`@image1`):

<!-- prompt:video-defs -->
```text
REPLACE: Define the <signature features> of the <kind> in @image1 as <Hero>. (one sentence per character) Every character keeps exactly its look from @image1 in every shot.
```

<!-- prompt:video-rules -->
```text
REPLACE: Throughout the entire video there must be exactly one <Hero> (… one of each) visible at any time they are on screen. Do not duplicate, clone or mirror any character. (plus the world's hard rules)
```

Video prompts with audio add the voice block:

<!-- prompt:voice -->
```text
REPLACE: <Hero> speaks as …; <Other> speaks as … (one sentence per character, how they talk and sound).
```

## Audio rule

<!-- prompt:audio -->
```text
Audio: only the characters' spoken conversation, clear and natural. No background music, no music of any kind, no songs, no musical stings, no sound-effects track.
```

## Open items

- (decisions waiting for the user)
