---
name: write-minimax-h3-video-prompts
description: "Convert natural-language ideas, scripts, shot lists, storyboards, images, video references, audio references, or prompts for other generators into production-ready prompts for the MiniMax H3 video model through a mandatory two-stage workflow: first draft a Chinese screenplay with complete dialogue for user approval, then convert the approved screenplay into H3 prompts. Use whenever the user mentions MiniMax H3, MiniMax-H3, Hailuo H3, 海螺 H3, 海螺H3, H3 视频, H3 视频提示词, asks for a prompt suitable for H3, or asks to optimize/translate/diagnose an existing H3 prompt. Support text-to-video, first/last-frame image-to-video, multimodal reference generation, video editing, native audio/dialogue, and structured Context-IR-style prompt writing with mandatory character emotion/expression direction and detailed cinematic capture/style specifications."
---

# Write MiniMax H3 Video Prompts

Turn the user's intent and supplied media into an executable H3 prompt through an approval-gated screenplay workflow. Preserve intent; do not invent important plot, identity, product, dialogue, or brand details unless necessary to make the shot coherent.

## Load references

- Read [official-h3-notes.md](references/official-h3-notes.md) when choosing generation mode, checking current limits, preparing API-shaped input, or making claims about official H3 behavior.
- Read [prompt-framework.md](references/prompt-framework.md) for complex scenes, multimodal reference mapping, long takes, dialogue/audio, editing tasks, or prompt diagnosis.
- Read [worked-example.md](references/worked-example.md) when the user requests the detailed structured style demonstrated in the original sample or when a multi-subject continuity problem needs a concrete pattern.

## Workflow

### Stage 1: Chinese screenplay approval

1. Extract hard requirements: story duration, clip duration, aspect ratio, references, subjects, setting, plot beats, dialogue language, emotional arc, style, sound, ending state, and prohibitions.
2. Draft only a Chinese screenplay before writing any H3-formatted prompt. Include the title, premise, character list, scene/segment breakdown, visible action, emotional progression, and complete spoken dialogue. Write Japanese or other requested spoken lines alongside a Chinese meaning when appropriate, while keeping the screenplay explanations in Chinese. In every segment, independently label each speaker's language, dialect/accent, speaking pace, vocal timbre, volume, and current emotion; never rely on a global character note for speech delivery.
3. Enforce dialogue adjacency and causal continuity. Every reply must directly acknowledge the preceding statement, answer its question, accept/refuse its offer, or explicitly bridge to a new topic. Add the missing offer, question, acknowledgement, or transition whenever a reply would otherwise feel disconnected. For example, use `洛桑（用带藏族口音、温和缓慢的普通话说）：“你在和树打架吗？要不要帮忙？” 扎西（用带藏族口音、略显逞强的普通话说）：“不用，我自己能弄开。”` rather than a joke followed by an unmotivated refusal.
4. End Stage 1 by explicitly asking the user to approve or revise the screenplay. Do not output `subject_definitions`, `retention_analysis`, `detailed_description`, H3 API JSON, or any other H3-formatted prompt in the same response.
5. Wait for explicit user approval. Treat clear statements such as “确认”“通过”“按这个转 H3” as approval. If the user requests revisions, revise the Chinese screenplay and ask for approval again.
6. If the user supplies a screenplay and explicitly states that it is already final/approved, treat that as Stage 1 approval and proceed. A supplied screenplay without explicit approval still requires a concise Chinese screenplay normalization pass and confirmation.

### Stage 2: H3 conversion after approval

1. Convert only the approved screenplay. Do not silently alter its plot, dialogue, character relationships, or ending.
2. Infer only low-risk omissions. If clip duration is absent, choose a feasible duration from 4–15 seconds based on action density and state it outside the prompt. If an action cannot fit, split it into multiple clips without changing the approved story.
3. Choose exactly one generation mode:
   - text only for text-to-video;
   - first frame, last frame, or both for frame-controlled image-to-video;
   - reference generation for identity, object, style, motion, camera, voice, audio, or editing-rhythm references;
   - editing language when the user supplies an existing video and asks for a controlled change.
4. Map every supplied asset by stable ordinal labels such as `Image 1`, `Video 1`, and `Audio 1`. State what to take from each reference and what must remain unchanged. Never imply that first/last-frame inputs can be mixed with reference inputs in one API request.
5. Build a feasible temporal chain. Give each beat one clear subject, action, reaction, and resulting state. Preserve causal continuity and persistent objects.
6. In every `detailed_description`, describe every visible character's emotional atmosphere and complete expression progression. Include initial emotion, trigger, emotional turn, eye direction/focus, brows, eyelids, mouth/jaw, breathing, posture, gesture, and final emotional state. Never omit this step, even for silent characters or action scenes.
7. In every `detailed_description`, include detailed production style and image formation: capture/exhibition intent (for example IMAX-scale clarity), camera or virtual-camera language (for example ARRI ALEXA 65), lens/focal-length behavior, depth of field, exposure/highlight roll-off, lighting sources, color science/grade, texture or grain, motion cadence, and aspect ratio. Translate equipment names into observable results; do not rely on brand names alone.
8. Add camera instructions that support the action. Avoid mutually incompatible movements or cuts in a declared continuous take.
9. Add native audio only when wanted or implied: ambience, synchronized effects, speaker-tagged dialogue, voice qualities, and music. Quote approved dialogue exactly. In every independently generated clip, restate each speaker's language, dialect/accent, pace, timbre, volume, and current emotion immediately before the line; do not refer to a previous clip for voice direction.
10. Add a short constraints clause for high-risk failures only. Phrase desired visible outcomes positively first; use explicit negatives sparingly for transformations, disappearances, extra limbs/objects, broken continuity, unwanted cuts, or impossible motion.
11. Run the quality check in `prompt-framework.md`, then return the prompt without explaining features the user did not ask about.

## Choose output depth

Use the smallest format that can reliably express the request.

### Compact native H3 prompt

Use only after Stage 1 approval. Use by default for simple text-to-video, one-action image animation, ads, mood pieces, and straightforward editing. Even compact prompts must include the visible character emotion/expression progression and production style specification. Write one cohesive paragraph in this order:

`duration + ratio + capture/style specification; reference mapping; scene and subjects; emotion/expression progression; chronological action; camera and lighting; sound/dialogue; essential constraints`

Official H3 examples are often concise. Do not inflate a simple request into a screenplay.

### Structured production prompt

Use only after Stage 1 approval. Use for multiple subjects or references, continuity-sensitive action, several beats, long takes, precise final states, or when the user requests the detailed sample format. `detailed_description` is mandatory and must contain the complete character emotion/expression direction and production style specification:

```text
subject_definitions:
summary:
retention_analysis:
detailed_description:
[Shot 1] ...
overall_soundscape:
non_diegetic_music:
```

Use `[Shot N]` for actual cuts or distinct shots. For a continuous long take, keep all beats inside `[Shot 1]` and describe camera motion continuously. Do not call successive actions separate shots when no cut occurs.

## Output contract

- Enforce the two-response minimum: Stage 1 screenplay and approval request first; Stage 2 H3 prompt only after explicit approval. Never combine them to save time.
- In Stage 1, output a Chinese screenplay with complete dialogue, not H3 prompt syntax.
- Match the user's requested language. Otherwise write the prompt in the language of the request.
- Keep dialogue in its spoken language and label it unambiguously, for example `S1 says in Chinese: “别动。”`
- Make every dialogue exchange context-complete inside its segment. A refusal must follow a request or offer; an answer must follow a clear question; a topic change must include an acknowledgement or transition.
- In every segment containing dialogue, label every speaker independently, for example: `洛桑（用带藏族口音、温和缓慢、低沉平稳的普通话说）：“要不要帮忙？”` Do not write only `洛桑说` or rely on a voice description from another segment.
- Put assumptions, selected duration/ratio, asset-order notes, or split-clip warnings before the prompt in no more than a few lines.
- Return only the finished prompt when the user asks for “just the prompt.”
- “Just the prompt” does not bypass Stage 1 approval; it only controls the Stage 2 response after approval.
- Do not output API JSON unless requested. When requested, use model `MiniMax-H3` and the official `content[]` roles from `official-h3-notes.md`.
- Treat “H3” as MiniMax H3 only when the video-generation context makes that meaning clear.

## Guardrails

- Do not claim the result was generated by the proprietary H3-Context-IR implementation. Call it “Context-IR-style” when relevant.
- Do not describe MiniMax H3 as fully open source. Official documentation describes the model as open/general-purpose or open-weight, while H3-Context-IR itself is not open sourced.
- Do not fabricate analysis of an unseen image, video, or audio file. Use the user's description or inspect the supplied media when tools allow it.
- Do not overload 4–15 seconds with more beats than viewers can perceive. Prefer fewer, stronger actions.
- Do not omit emotion/expression direction for background or silent characters who are visibly reacting.
- Do not treat IMAX, ARRI ALEXA 65, lens brands, film stocks, or resolution labels as magic quality tokens. State the specific composition, dynamic range, highlight roll-off, depth, texture, color, and motion consequences the requested production style should create.
- Do not write non sequiturs, unmotivated refusals, unanswered direct questions, replies that ignore the preceding information, or witty lines that sacrifice conversational logic.
- Do not invent phonetic spellings, vocabulary, or caricatured speech for an ethnicity or region. When reliable dialogue material is unavailable, describe accent and delivery respectfully while keeping the spoken wording in standard language.
