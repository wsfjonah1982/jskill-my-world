# Lessons learned (from the first world, "Short Drama Workflow", 2026-10)

- **Style drift:** photo references pull pictures toward realism. Put the style line first in every prompt and say
  what to take from a photo ("layout only", "pose only") and what not to copy.
- **Sizes drift:** state sizes as numbers and ratios ("25 cm at the shoulder, about 60% of the dog") in the canon
  block, pass the height chart as a reference, and check every result. A generated height line-up is rarely to
  scale; fix it in post (scale the cut-outs) rather than regenerating many times.
- **Counts drift:** say "exactly one <kind>" for every character, in images and videos, and "do not duplicate,
  clone or mirror" in videos. In a beat where one character is alone in a corner, say "the one and only cat".
- **Signature details drift** (e.g. a dog's small almond eyes turning into big cartoon eyes): repeat them in the
  `characters` and `video-defs` blocks, in capitals if needed.
- **Colour depends on the background:** a pale blue-grey animal reads grey on warm peach walls. Keep the sets
  neutral or cool behind it, and write that into the world's look.
- **Never name a character in the `world` block:** it goes into every set prompt, and "so the blue cat stays
  blue" drew a cat into empty sets. Say "no people, no animals" there; keep colour rules about characters in prose.
- **No text anywhere:** models write signs, numbers and logos unless told not to; "no readable text" belongs in the
  `world` block, the location blocks and the negative lines.
- **Props:** pasting the full recurring-props list into every prompt makes the model draw all of them. Paste it only
  when a frame names props; otherwise use `no_props_rule`.
- **Regenerate, don't edit:** an image edit keeps the old details (eyes, colours). For a new scene, build from the
  sheets; for a fix, change the canon block and redraw.
- **Videos are paid per task:** never resubmit a video that already has a task id; recover it with
  my-world's `scripts/ark/resume_video_task.py`.
- **Voices:** the speech model leaves long pauses between turns; `voices.py dialogue` also writes a tightened copy.
  Cloning from a short recording the user picked, steered by the text description, beats text-only design for the
  lead; text-only design is fine for secondary voices.
