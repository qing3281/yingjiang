# Official MiniMax H3 Notes

Checked against MiniMax official documentation on 2026-08-12.

## Sources

- [Video Generation](https://platform.minimax.io/docs/guides/video-generation.md)
- [H3 Feature Highlights](https://platform.minimax.io/docs/guides/video-prompt.md)
- [Create Video Generation V2 Task](https://platform.minimax.io/docs/api-reference/video-generation-v2-create.md)
- [Create H3-Context-IR Task](https://platform.minimax.io/docs/api-reference/video-generation-v2-h3-context-ir.md)
- [Official Hailuo AI product](https://hailuoai.video/)

## Verified capabilities

- Official model name: `MiniMax-H3`.
- H3 accepts text, image, video, and audio in a unified multimodal `content[]` input.
- Modes: text-to-video; first/last-frame image-to-video; reference generation using images, videos, and/or audio; video editing workflows.
- It can interpret references for character, motion, camera, style, voice, sound, emotion, and editing rhythm.
- Output: 768P or 2K; duration is an integer from 4 through 15 seconds; common or adaptive aspect ratios are supported.
- Prompt length limit: 7000 characters.

## Input limits

- First/last-frame mode: zero to two images, at most one for each role.
- Reference mode: up to 9 images, 3 videos, and 3 audio clips; mixed media is capped at 12 files.
- Each reference video/audio clip is 2–15 seconds; total reference video duration is at most 15 seconds and total reference audio duration is at most 15 seconds.
- Images: JPG/JPEG/PNG/WEBP/HEIC/HEIF, each at most 30 MB.
- Videos: MP4/MOV using H.264/H.265; each at most 50 MB.
- Audio: WAV/MP3; each at most 15 MB.
- First/last-frame mode and reference mode are mutually exclusive in one request.

## API role map

Every request needs a non-empty text item. Use these roles only when JSON is requested:

```json
{"type":"text","text":"..."}
{"type":"image_url","image_url":{"url":"..."},"role":"first_frame"}
{"type":"image_url","image_url":{"url":"..."},"role":"last_frame"}
{"type":"image_url","image_url":{"url":"..."},"role":"reference_image"}
{"type":"video_url","video_url":{"url":"..."},"role":"reference_video"}
{"type":"audio_url","audio_url":{"url":"..."},"role":"reference_audio"}
```

## Official prompt evidence

Official examples favor direct, production-oriented prose rather than mandatory keyword syntax. They commonly begin with duration and ratio, map references by ordinal number, specify story/action, tone, shot scale or camera behavior, visual treatment, and sound. Example patterns include:

- `15s, 16:9. Live-action ... Subtle handheld shake ... Sound: ...`
- `Image 1: mood and setting. Image 2: character. Image 3: product. Core story: ...`
- `First-person, eye-level, handheld gameplay camera ... advancing ... firing ... then pressing forward.`

Square-bracket camera commands such as `[Pedestal up]` and `[Static shot]` remain present in legacy Hailuo API examples, but H3 official examples also accept natural camera prose. Prefer clear natural prose; preserve bracket commands when the user already uses them or explicitly requests command syntax.

## Context-IR boundary

The official `H3-Context-IR` endpoint accepts multimodal context and returns an enhanced structured prompt, not a generated video. Its documented example uses:

- `integrated_multimodal_description:` with `[Shot N]` blocks;
- chronological timestamps where useful;
- `overall_soundscape:`;
- `non_diegetic_music:`.

MiniMax explicitly states that H3-Context-IR is a complex system whose implementation is not open sourced. A locally written structured prompt can follow the public style but must not be represented as an identical reproduction of the official system.
