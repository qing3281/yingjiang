# Worked Structural Pattern

Use this as a pattern, not a mandatory template. It is derived from the user's supplied multi-reference, single-take character-and-cup example.

## Why the structure works

- `subject_definitions` binds each numbered picture to a stable entity and establishes relative scale.
- `summary` states the entire causal arc and declares the single continuous take.
- `retention_analysis` names which traits and scene objects must persist.
- `detailed_description` establishes global rendering, lighting, material, physics, and exclusions once.
- `[Shot 1]` contains every beat because there is no cut; camera moves are synchronized with action.
- `overall_soundscape` and `non_diegetic_music` separate in-world sound from score.

## Reusable skeleton

```text
subject_definitions:
<Subject 1> is [identity and immutable visual traits] from <Image 1>. [Scale relationship].
<Subject 2> is [environment/object and immutable layout traits] from <Image 2>.

summary:
[reference generation] A [duration, ratio] [single continuous take / edited sequence] in which [ordered causal arc and visible final state].

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - [face, body, wardrobe, texture, proportions, voice if referenced].
<Subject 2> (appears in [Shot 1]): fully_preserved - [layout, geometry, product details, persistent object rule].

detailed_description:
[Production style: format/scale, camera or virtual camera, lens behavior, depth of field, exposure/highlight roll-off, motivated lighting, color grade, texture/grain, motion cadence, aspect ratio and composition. State visible consequences rather than equipment names alone.]
[Performance direction for every visible character: initial emotional atmosphere; trigger; eyes; brows/eyelids; mouth/jaw; breathing/voice; posture/hands; timed emotional transition; final-frame expression. Never omit silent or background reactions.]
[Overall physics, global continuity, essential prohibitions].

[Shot 1] [Initial framing and positions]. [Beat 1 action -> reaction]. [Motivated camera move]. [Beat 2 action -> reaction]. [Dialogue: independently state each speaker's language, dialect/accent, pace, timbre, volume, and current emotion before every line. Ensure each reply directly answers, acknowledges, accepts/refuses, or bridges from the preceding line.] [Beat 3]. [Object state transition]. [Final action and exact final frame].

overall_soundscape:
[Ambience, synchronized footsteps/impacts/liquid/material sounds, voices].

non_diegetic_music:
[Genre, instrumentation, tempo, cue changes, ending behavior].
```

## Key correction to the sample

Scope continuity rules precisely. If an object must eventually move, do not say it is stationary throughout. Write: `The cup remains stationary during the three pushing attempts. Only after S1 lands inside does it rock, tip, and spill.` This preserves the intended failed attempts without contradicting the later tip-over.

When adapting cute character voices, use neutral performance language such as `cute, high-pitched anime-style voice` rather than sexualized age labels.

## Approval gate example

First response:

```text
中文剧本
角色：……
第 1 场（8 秒）：……
台词：S1：“……”
情绪弧线：……

请确认剧本；确认后我再转换为 H3 结构化提示词。
```

Only after the user approves, produce the structured prompt skeleton above. Never place both stages in one response.

## Dialogue continuity example

Bad:

```text
洛桑：“你在和树打架吗？”
扎西：“我自己能弄开。”
```

The second line refuses help that was never offered.

Good:

```text
洛桑（用带藏族口音、温和缓慢、低沉平稳的普通话说）：“你在和树打架吗？要不要帮忙？”
扎西（用带藏族口音、略快、少年音色、带一点逞强的普通话说）：“不用，我自己能弄开。”
```

Repeat the full delivery note inside every independently generated segment. Do not reduce later segments to `洛桑说` or `扎西回答`.
