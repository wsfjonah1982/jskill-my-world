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
- **A reference sheet beats the text:** a sheet drawn with a reference picture copies it, age and all. If the
  reference is wrong on something the canon fixes (e.g. it reads 11, the canon says 16), draw that sheet from the
  text alone, stating the trait plainly ("a teenager, NOT a child", proportions as numbers).
- **Regenerate, don't edit:** an image edit keeps the old details (eyes, colours). For a new scene, build from the
  sheets; for a fix, change the canon block and redraw.
- **Videos are paid per task:** never resubmit a video that already has a task id; recover it with
  my-world's `scripts/ark/resume_video_task.py`.
- **Voices:** the speech model leaves long pauses between turns; `voices.py dialogue` also writes a tightened copy.
  Cloning from a short recording the user picked, steered by the text description, beats text-only design for the
  lead; text-only design is fine for secondary voices.
- **A cloned voice keeps the recording's pace:** "brisk pace" in `voice:<char>` speeds up a designed voice a lot
  (Milky 10.8s → 5.8s) but barely a cloned one (Xiao Li 11s → 10.3s). Speed the solo clip with
  `ffmpeg -af atempo=1.15` (pitch kept; keep the model output beside it), then redo the dialogue, which takes each
  pace from the solo clips. Dialogue takes vary a few seconds; make two or three and keep the quickest.
- **A good raw sheet beats a redraw:** the user's own character sheet can be more precise than anything redrawn from
  it (Xiao Li, 2026-10-14). Check it (`worldlib.py inspect` + a look, see SKILL.md) and use it directly when it
  passes; then make the canon text agree with the picture.
- **Group pictures drift from the set** when the location is one reference among many (the together picture invented
  a wide room with two sofas when the set was reference 4 of 5). `world_images.py group` now passes the location as
  image 1, the base picture ("keep its camera viewpoint and furniture positions, only add the characters"); also
  place the characters on furniture that is in the set, in the `group:<name>` block.
