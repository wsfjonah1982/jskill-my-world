# Setting — {{NAME}}

The canonical world, locations and props. **Every image or video generated for this world must take its environment
from this file** (and its characters from [`Identities.md`](Identities.md)). New locations are added here first,
then used in a story.

Blocks marked `<!-- prompt:... -->` are pasted word for word into prompts.

## The world

- **Where:** the place, the home, the neighbourhood.
- **Who else:** who is never shown (e.g. parents implied, never on screen).
- **When:** era, climate, seasons and holidays.
- **Mood:** e.g. cosy, safe, lightly funny. No danger, no tragedy.

## Look of the world

- Palette inside and outside; the colours the characters must stand out against.
- Light: default daylight, endings, night.
- **No text anywhere:** no readable signs, numbers, posters, logos, brand packaging or screens with content.

<!-- prompt:world -->
```text
REPLACE: one paragraph: the place, its palette and light, what it never has (e.g. no readable text, logos or brand packaging).
```

## Locations

Each location has a reference picture (`_asset/settings/<key>.png`, my-world `world_images.py set <key>`) and a
prompt block. Put a real photo at `_reference/settings/refs/<key>_photo.jpg` to fix the layout.
Keep the heading form `#### Title (`key`)`: the overview page reads it.

#### REPLACE Home base (`home`)
Reference: `_asset/settings/home.png`.
- Layout, furniture, colours, where the characters usually are.

<!-- prompt:location:home -->
```text
REPLACE: the place as one paragraph: room shape, walls, floor, furniture with colours and materials, windows, light.
```

## Recurring props

These look the same every time they appear. Draw a reference with `world_images.py prop <key>` (needs a
`prompt:prop:<key>` block) and add `Reference: `_asset/props/<key>.png`` to its row.

| Prop | Look |
|---|---|
| REPLACE prop | colour, material, shape |

<!-- prompt:props -->
```text
REPLACE: When any of these props appears it keeps the same look (do not add props the scene does not need): ...
```

## Rules of the world

- Hard rules every story keeps (what characters never eat or do, no real brands or landmarks, no religion or politics, …).
