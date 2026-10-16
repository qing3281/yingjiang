# H3 Prompt Framework

## 0. Mandatory two-stage gate

Never convert an unapproved idea directly into an H3 prompt.

### Stage 1 output: Chinese screenplay

Provide:

1. title and one-sentence premise;
2. character list and relationships;
3. scene or segment order with duration;
4. visible action and dramatic purpose for each scene;
5. complete dialogue, including speaker names and spoken language;
6. emotional arc and ending.

Ask the user to approve or revise it. Stop there. Do not include H3 field names.

### Stage 2 output: approved screenplay conversion

After explicit approval, preserve the approved plot and dialogue exactly while compiling the H3 prompt. If the user changes the story during Stage 2, return to Stage 1 for the affected screenplay sections and obtain approval again.

## 1. Intake map

Extract these fields from any natural-language idea, foreign-model prompt, screenplay, storyboard, or media bundle:

| Field | What to capture |
| --- | --- |
| Deliverable | clip count, duration, ratio, resolution if relevant |
| Mode | text, first/last frame, reference generation, editing |
| References | asset number, source role, retained traits, ignored traits |
| Subjects | identity, appearance, scale, wardrobe, persistent state |
| Environment | place, time, layout, persistent objects |
| Action | ordered beats, causal transitions, final state |
| Camera | framing, angle, movement, focus, cuts or continuous take |
| Look | medium, genre, texture, lighting, color, pace |
| Performance | each character's emotion, trigger, expression progression, posture, and final state |
| Capture style | IMAX-scale intent, camera/virtual camera, lens behavior, depth, exposure, light, grade, grain, motion cadence |
| Audio | ambience, effects, dialogue, each speaker's language/accent/pace/timbre/volume/emotion, music |
| Constraints | only likely or costly failure modes |

## 2. Reference binding

For each asset, write one sentence describing its authority:

```text
Image 1 defines the lead character's face, hair, costume, and body proportions.
Image 2 defines the room layout and the exact cup design.
Video 1 supplies only the running motion and camera cadence, not identity or setting.
Audio 1 supplies S1's voice timbre and delivery, while the spoken words follow this prompt.
```

Resolve conflicts explicitly. Give identity references priority for identity, product references for geometry/branding, environment references for layout, and motion/camera references only for their named traits.

## 3. Temporal design

Use a state chain for complex action:

`initial state -> trigger -> subject action -> object reaction -> subject reaction -> next action -> final state`

Every beat must leave the scene in a state that makes the next beat possible. Repeat critical persistent states at the moment they matter, not in every sentence.

For a 15-second clip, target roughly 3–6 readable action beats. Tiny gestures may share a beat. Split into multiple clips when dialogue, action, and camera changes would otherwise compete.

## 4. Camera logic

- State whether the video is a continuous take or edited sequence.
- Bind camera movement to visible action: track a run, tilt with a jump, dolly back from an impact, rack focus to transfer attention.
- Use shot scale and viewpoint where they matter: wide, medium, close-up, macro, first-person, eye-level, low angle, overhead.
- Keep screen direction and subject position stable when continuity matters.
- For a long take, replace hidden cuts with continuous pans, tilts, dollies, arcs, focus pulls, or motivated occlusion only if the user permits it.

## 5. Motion and physics

Name the physical mechanism and result. Prefer `jumps in a clear parabolic arc and lands inside the cup, splashing water over the rim` over `jumps dramatically`. Define squash-and-stretch, inertia, recoil, liquid behavior, cloth/hair response, collision, and object permanence only where relevant.

Avoid contradictions such as `the cup never moves` followed by `the cup tips over` without an intervening cause. Scope constraints by phase: `the cup stays fixed during all pushing attempts; it begins rocking only after S1 lands inside it`.

## 6. Dialogue and sound

Identify the speaker and language. Keep spoken text short enough for the duration. In every independent segment, repeat the complete voice direction for each speaker: language, dialect/accent, pace, timbre, volume, and current emotion. Never assume a previous segment supplies this information.

```text
S1 says in Mandarin, in a breathless young adult voice: “等等我！”
```

Preferred screenplay notation:

```text
洛桑（用带藏族口音、温和缓慢、低沉平稳的普通话说）：“你在和树打架吗？要不要帮忙？”
扎西（用带藏族口音、略快、少年音色、带一点逞强的普通话说）：“不用，我自己能弄开。”
```

### Dialogue logic gate

For every adjacent pair of lines, identify the first line's conversational function and verify that the reply fulfills it:

| First-line function | Required reply behavior |
| --- | --- |
| question | answer it directly before adding new information |
| offer/request | accept, refuse, negotiate, or ask for clarification |
| warning | acknowledge the danger, dispute it with a reason, or act on it |
| factual statement | acknowledge, interpret, question, or causally extend it |
| emotional disclosure | recognize the feeling before changing topic |
| joke/tease | show the listener understands it, then connect to the practical issue |

If the reply does not satisfy the function, rewrite the preceding line or insert a bridge. Do not leave direct questions unanswered unless silence is an intentional dramatic action explicitly described in the screenplay. Even intentional silence must have a visible response such as gaze avoidance, tightened jaw, or withdrawal.

Bad:

```text
洛桑：“你在和树打架吗？”
扎西：“我自己能弄开。”
```

The refusal has no stated offer or request to refuse.

Good:

```text
洛桑（用带藏族口音、温和缓慢的普通话说）：“你在和树打架吗？要不要帮忙？”
扎西（用带藏族口音、略显逞强的普通话说）：“不用，我自己能弄开。”
```

Do not use age-coded sexualized voice descriptions. When the desired quality is cute or high-pitched, describe vocal timbre, energy, and performance without sexual framing.

Separate:

- diegetic sound: room tone, footsteps, impacts, water, mechanisms, voices;
- non-diegetic music: genre, instrumentation, tempo, dynamics, cue points, ending.

Use the Stage 1 approved dialogue verbatim. If timing makes the approved line impossible within one clip, split the line across clips or return to Stage 1 for approval; do not silently shorten it.

Do not imitate an accent through misspellings, stereotyped grammar, or invented minority-language words. Describe the accent as performance direction and keep the wording intelligible unless the user supplies verified dialogue in that language.

## 7. Mandatory performance direction

Every `detailed_description` must describe every visible character. For each character, include:

- **initial emotional atmosphere**: the internal state and the social tension around it;
- **trigger**: the visible or audible event that changes the state;
- **eyes**: gaze target, focus, blink rate, moisture, widening or narrowing;
- **brows and eyelids**: lift, pinch, tension, relaxation, asymmetry;
- **mouth and jaw**: pressed lips, parted breath, restrained smile, jaw tension, swallowing;
- **breathing and voice**: pace, depth, hesitation, volume, timbre;
- **posture and gesture**: shoulders, spine, hands, weight shift, distance from others;
- **transition and final state**: how the expression evolves and the exact expression held in the final frame.

Do not write only abstract labels such as “sad” or “angry.” Convert emotion into visible, timed performance. Silent and background characters still need direction when their reaction is readable in frame.

## 8. Mandatory production style direction

Every `detailed_description` must define how the image is formed. Include:

- **format and scale**: for example, IMAX-scale spatial clarity, expansive negative space, large-format facial detail, or an intimate non-IMAX alternative;
- **camera language**: for example, ARRI ALEXA 65 large-format rendering or an equivalent virtual-camera emulation;
- **lens behavior**: focal length range, perspective, close-focus behavior, edge rendering, flare policy, and bokeh;
- **depth and exposure**: depth of field, focus transitions, shadow detail, highlight roll-off, and skin exposure;
- **lighting**: motivated source, direction, softness, color temperature, contrast ratio, practical lights, and atmosphere;
- **color and texture**: palette, saturation, skin-tone treatment, grain or clean digital texture, halation, and finishing intent;
- **motion cadence**: shutter/motion-blur character, camera stability, movement speed, and whether the shot feels observational or choreographed;
- **aspect ratio and composition**: frame ratio, headroom, negative space, foreground/midground/background separation.

Equipment names are shorthand, not sufficient instructions. Pair `IMAX` with its intended scale/composition and pair `ARRI ALEXA 65` with observable large-format depth, dynamic range, natural skin tone, and highlight behavior. For animation, specify the animation medium and use large-format/camera terms only as virtual cinematography references.

## 9. Constraint design

Put the desired outcome first. Add negatives only for likely failures:

```text
The cup remains present and intact throughout; after it tips, all water is visibly outside and the interior is empty. S1 keeps the same face, proportions, costume, and tail; no morphing, duplicate limbs, added props, or unmotivated cuts.
```

Avoid long generic negative lists. They dilute the action hierarchy.

## 10. Quality check

Before returning the prompt, verify:

- duration and action density are feasible;
- each reference has one stable label and explicit role;
- subjects cannot be confused or silently replaced;
- chronology is causal and the ending state is visible;
- camera instructions do not contradict the declared edit style;
- dialogue fits the duration and identifies speaker/language;
- every adjacent reply directly answers, acknowledges, accepts/refuses, or explicitly bridges from the preceding line;
- every independent segment repeats each speaker's language, dialect/accent, pace, timbre, volume, and current emotion;
- direct questions and offers are closed or intentionally answered through a described visible silence;
- sound effects coincide with actions;
- persistent objects do not disappear;
- negatives do not contradict later events;
- prompt is at most 7000 characters;
- no unsupported claim says this is official Context-IR output.
- Stage 1 screenplay received explicit approval before any H3 formatting;
- every visible character has a complete emotion and expression progression;
- every `detailed_description` contains capture format, camera, lens, depth/exposure, lighting, grade/texture, motion cadence, and composition;
- equipment names are paired with visible image consequences.

## 11. Diagnose existing prompts

When asked to review or optimize a prompt, report only actionable issues, then provide a rewritten prompt. Prioritize:

1. impossible duration or overloaded beat count;
2. conflicting reference roles or identity drift;
3. continuity and physics contradictions;
4. incompatible camera directions;
5. ambiguous pronouns, speakers, or dialogue timing;
6. excessive negative prompting and decorative detail.
