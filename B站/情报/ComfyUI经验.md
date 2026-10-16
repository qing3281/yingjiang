# ComfyUI 本地出片经验（踩过的坑 + 可复用的参数）

> 全部来自本机实测，每条都带证据（命令 / 报错 / 耗时）。
> 环境：`D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI`，Python 3.13.12 / torch 2.12.1+cu130 / av 18.1.0，
> RTX 5080 16 GB，manifest `ref v0.34.0` / `variant win-nvidia`。

---

## 〇、总览：本机有什么、该怎么选

| 任务 | 用什么 | 实测速度 |
|---|---|---|
| 静帧（分镜、人设、场景） | **Qwen-Image 2512**（`qwen_image_2512_fp8_e4m3fn`） | 1536×864 / 40 步 ≈ **90 秒** |
| 静帧（要快、可以糙） | Z-Image-Turbo（`z_image_turbo_int8_convrot`） | 1024×1408 / 8 步 ≈ **5 秒** |
| 图改图 / 参考图驱动 | Qwen-Image-Edit 2511（另下） | —— |
| **带对白的动态** | **MiniMax H3 fl2va**（`minimax_h3_fl2va_pruned_w6a8`） | 5.17 秒 / 4 步 ≈ **145 秒** |
| 无对白动态 | Wan 2.2 14B 双模型（高噪+低噪） | 5 秒 ≈ **240 秒**，且无声 |
| 配音（如果模型不出声） | IndexTTS-2（`D:\tts\venv`） | 2~5 秒/句 |

**第一原则：要中文对白就直接上 MiniMax H3 fl2va。** 它一次出「画面 + 口型 + 音频」，
省掉「Wan 出画面 → IndexTTS 配音 → 对齐口型」三个环节。实测 Whisper 能听懂，
首帧逐像素差 3.7~4.2 / 255。

---

## 一、启动与环境

### 1.1 Desktop 版没有 exe，用 main.py 直启

`D:\Comfy-Desktop\` 下**找不到 Electron exe**，也**全盘没有 `extra_model_paths.yaml`**。
但 `logs\comfyui.log` 开头会把所有实际生效的搜索路径逐条打出来：

```
Adding extra search path checkpoints D:\Comfy-Desktop\ComfyUI-Shared\models\checkpoints
...
```

把 27 条全抄成一份 yaml，就能用 main.py 复现 Desktop 的模型可见性。

**`D:\DSHworkspace\B站\制作\启动ComfyUI.py`** 已经把这套封好了：写死了
`--extra-model-paths-config` / `--output-directory` / `--input-directory` / `--port 8188`，
并会先探测「是不是已经在跑」。日志落 `D:\DSHworkspace\B站\制作\ComfyUI启动.log`。

**注意端口是 8188，不是 8000。**

### 1.2 venv 里的 python 才带 torch

```
D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe
```

系统 python 里没有 `av` / `torch`。所有脚本都得用这个。

### 1.3 PowerShell 里跑 Python 一定要先设编码

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'
```

不设的话进度条里的方块字符会抛 `UnicodeEncodeError`，日志里全是
`鈻堚枅鈻堚枅`（GBK 解 UTF-8 的乱码）。

---

## 二、静帧：Qwen-Image 2512（主力）

### 2.1 官方参数（来自 `comfyui_workflow_templates_json` 里的 MarkdownNote）

> You can test and find the best setting by yourself. The following table is for reference.
> | Steps | Qwen 40 | Comfy 20 |
> | CFG | 4.0 | 4.0 |

模板 `image_qwen_Image_2512.json` 子图里的实际 KSampler 是
`[seed,'randomize', 50, 4, 'euler', 'simple', 1]`。

**我犯过的最大错误：为了快用 4 步 + CFG 1.0（挂 Lightning 蒸馏 LoRA）。**
结果细节全崩、人物不像。那个 LoRA 只是「加速档」，不是这个模型的正常跑法。

### 2.2 可用工作流（`D:\DSHworkspace\B站\制作\出图_纯文本.py`）

```
UNETLoader(qwen_image_2512_fp8_e4m3fn, weight_dtype=default)
CLIPLoader(qwen_2.5_vl_7b_fp8_scaled, type="qwen_image")
VAELoader(qwen_image_vae)
CLIPTextEncode(pos) / CLIPTextEncode(neg)          ← 注意是普通 CLIPTextEncode
EmptySD3LatentImage(宽, 高)                         ← ★ 必须用 SD3，不是 EmptyLatentImage
ModelSamplingAuraFlow(shift=3.1)
KSampler(seed, steps=40, cfg=4.0, "euler", "simple", denoise=1.0)
VAEDecode → SaveImage(prefix="DSH_纯文本")
```

**★ `qwen_image_vae` 的 latent 是 16 通道**（`decoder.conv1.weight [384,16,3,3,3]`）。
用 `EmptyLatentImage`（4 通道）会出错乱结果。**必须 `EmptySD3LatentImage`。**

### 2.3 负向提示词要写死这两句

```
text, watermark, signature, letters, words, chinese characters, subtitles,
logo, ui, collage, split screen, multiple panels, grid, border, frame,
side by side, divided, photorealistic, 3d render, blurry, low quality
```

**`collage / split screen / multiple panels` 是关键**——不写的话 Qwen-Image-Edit
会把参考图和生成结果并排画进一张图。

---

## 三、★★ 最大的坑：Qwen-Image-Edit 的「拼贴癖」

### 3.1 现象

给它一张参考图 + 一个「画新场景」的提示词，它**一定会输出
【参考图 | 生成结果】的并排 / 三联 / 四宫格**。

- 提示词里写「不要拼贴、不要边框、不要第二个人」→ **完全无效**
- 换种子、换画布尺寸、换参考图 → 还是拼贴

### 3.2 尝试过的四种解法

| 解法 | 结果 |
|---|---|
| 提示词否定 | ❌ 无效 |
| 参考图当起始潜变量 + `denoise=1.0` | ❌ 过曝乱码（起始潜变量和 `ReferenceLatent` 同源，自我放大） |
| 大画布（3072×1728）+ 自动拆联 | ⚠️ 能用，但每联只有 834×1728，构图受限，还得写拆图代码 |
| **纯文本出图（T2I）** | ✅ **彻底解决** |

### 3.3 结论

**只要角色设计锁写得够细（发色渐变 / 耳朵位置 / 围裙图案 / 尾巴形状逐条列死），
纯文本就能画对，根本不需要参考图。**

《不烧心》七个角色的定妆图全部是纯文本出的，没有一张用参考图。

> 教训：**参考图驱动只在「角色设计无法用文字描述」时才值得。**
> 能用文字说清楚的，T2I 又稳又快又不会有拼贴。

### 3.4 如果确实要用参考图：拆联参数

```python
# 找连续的高亮竖带当分隔缝
colmean = 像素均值(轴0, 2)
缝 = colmean > 232 且 连续宽 >= 6px
# 每联宽度须 > W*0.08，否则当没拆
```
1536×864 下缝在 x=346-450 与 x=1068-1180；3072×1728 下每联约 900×1536。
**中间最宽的那联是原图翻版，丢掉。**

---

## 四、动态：MiniMax H3 fl2va

### 4.1 参数（`D:\DSHworkspace\B站\制作\MiniMax动态.py`）

```python
工作流 = r"D:\DSHworkspace\素材\本地AI\workflows\MiniMaxH3_api.json"
节点   = class_type == "MiniMaxH3ImageToVideo"   # 实测是 #30
帧     = 124                                      # 124 帧 @24fps = 5.17 秒
步数   = 4
# 改 inputs.prompt / inputs.length / inputs.first_frame
# RandomNoise.noise_seed、BasicScheduler.steps、SaveVideo.filename_prefix
```

### 4.2 ★ 长度绝对不能超过 5 秒

| 长度 | 帧数 | 结果 |
|---|---|---|
| 5.17 秒 | 124 | ✅ **141~151 秒跑完** |
| 15.08 秒 | 362 | ❌ 跑了 **30 分 14 秒**还没完 4 步（≥450 秒/步），token 只涨 2.8 倍但时间涨 19 倍 |

**长镜头靠多条 5 秒拼，不要一次出长。**

### 4.3 显存与内存

- 跑之前显存 1183 / 16303 MiB
- 峰值 **15412 MiB**（只余 891）、内存峰值 **32.8 / 46.8 GB**
- **生成期间这台机器不能再干重活**

**必须先 free**：不 free 的话第一次要 46~151 秒才起跑。用 `/api/free`
（`{"unload_models": true, "free_memory": true}`）。

### 4.4 提示词写法

**英文写动作，中文引号原样写台词**（模型靠这个对口型）：

```
Cinematic anime shot, cel-shaded 3D style, consistent character design.
Shot 03 of a short drama. Action: <英文动作描述> Expression: <英文表情>
She speaks Chinese clearly and naturally, lip-synced,
with the exact words: "一个 token 一个价。不还价。"
Audio: clean Chinese dialogue, subtle room tone, no music.
```

### 4.5 已验证的三条

1. **首帧钉得住**：输出第 1 帧 vs 输入图逐像素平均差 **3.70 / 4.24**（满分 255）
2. **动作跟随**：提示词写 "slowly looks up toward the ceiling"，抽帧看确实头仰起来了
3. **中文对白可懂**：Whisper `base` 和 `small` 两个模型一致识别出对白内容
   （用词会被轻微改写，语义正确）

---

## 五、稳定性的坑

### 5.1 ★ 后台任务被中断会连带弄死 ComfyUI

实测过一次：正在跑第二镜时 `job_output` 被中断，重查发现
- `job_list` 报 no background jobs
- 8188 / 8000 端口均无响应
- 日志停在第二镜第 1 步：`25%|…| 1/4 [00:34<01:43, 34.53s/it]`

**对策**：
1. 长任务要么前台跑，要么在每镜之间查一次 `/system_stats`
2. 每镜的产物落到磁盘后**跳过已存在的**（`os.path.getsize(出来路) > 10240` 就 skip）
   → 断了重跑不用从头来
3. 把「每镜一条独立请求」设计成幂等的，别搞一个巨大的批请求

### 5.2 ★ PyAV 音频的三个连环坑（拼片时全踩了一遍）

**坑① `from_ndarray` 的 packed / planar 之分**

```python
# ❌ ValueError: Expected packed `array.shape[0]` to equal `1` but got `2`
av.AudioFrame.from_ndarray(x, format="s16", layout="stereo")
# ✅ 平面数据（c.decode(a) 出来的就是 (声道, 样本)）要用带 p 的格式名
av.AudioFrame.from_ndarray(x, format="fltp", layout="stereo")
```
`format="s16"` 是**交错打包**的，要求 `shape[0] == 1`；
带 `p` 后缀（`s16p` / `fltp`）才是**平面**的，`shape[0]` 是声道数。

**坑② 解出来的是 `fltp`，不是 `int16`**

```python
# ❌ ValueError: Expected numpy array with dtype `int16` but got `float32`
x.astype(np.int16)   # AAC 解出来本来就是 float32 平面
```
AAC 解码的 `to_ndarray()` 给的是 **float32**。别自作主张转 int16 —— format 和 dtype 必须对上。

**坑③ ★ 同一个容器里解完视频再解音频，音频是空的**

```python
# ❌ 样 == []，音轨一帧都拿不到
with av.open(p) as c:
    for f in c.decode(c.streams.video[0]): ...
    for af in c.decode(c.streams.audio[0]): 样.append(...)
```
`Container.decode()` 会把**解复用器推到 EOF**，之后再去解另一条流就什么都没了。

**对策：音频单独开一次容器。**
```python
with av.open(p) as ca:                      # 先单独把音频全解出来
    for af in ca.decode(ca.streams.audio[0]): 样.append(af.to_ndarray())
with av.open(p) as c:                       # 再开一次解视频
    for f in c.decode(c.streams.video[0]): ...
```

输出流的格式也要设死，否则编码器不认明文：
```python
oa = 输出.add_stream("aac", rate=sr)
oa.layout = "stereo"
oa.format = "fltp"
重采 = av.AudioResampler(format="fltp", layout="stereo", rate=sr)
```

**验证方法**：先造两条 1 秒的合成片（24 帧 + 正弦音）跑一遍拼接，
`av.open(出).streams` 应该看到 `[('video','h264'), ('audio','aac')]` 两条流。
不先验证的话，跑到最后一步才发现整条片子没声音。

### 5.3 PyAV 的 API 变化

| 老写法 | PyAV 18 写法 |
|---|---|
| `add_stream(template=...)` | `add_stream_from_template(...)` |
| `stream.duration` | 容器 `duration` 是微秒；流级经常是 `None` |

### 5.3 读视频时长要防 `None`

```python
def 读时长(路):
    with av.open(路) as c:
        if c.duration:                      # 容器时长最可靠
            return float(c.duration / 1000000.0)
        return max(float(s.duration * s.time_base) for s in c.streams if s.duration)
```
**只读视频轨会得到 0**（纯视频文件流级 duration 常为 None），
曾经因此把 7.81 秒的动态算成 5.17 秒，整个时间轴全错。

### 5.4 中文路径会把某些库搞崩

`kaldifst` / `sentencepiece` 在含中文的路径下会挂。IndexTTS 装在
`D:\tts`（junction → `D:\DSHworkspace\B站\配音环境`）就是为这个。

---

## 六、脚本清单（`D:\DSHworkspace\B站\制作\`）

| 文件 | 干什么 |
|---|---|
| `启动ComfyUI.py` | 拉起 ComfyUI（端口 8188），`--只等` 只探测 |
| `extra_model_paths.yaml` | 27 条模型搜索路径 |
| `出图_纯文本.py` | **Qwen-Image 2512 纯文本出图**（40 步 / CFG 4.0） |
| `出镜_Qwen参考.py` | 参考图驱动出图（会拼贴，慎用；带 `--拆联`） |
| `出3D定妆.py` | 七个角色的 3D 卡渲定妆图 |
| `MiniMax动态.py` | **MiniMax H3 fl2va 批量动态**（带对白） |
| `做不烧心.py` | 总调度：`--出首帧` / `--出动态` / `--列` |
| `合成不烧心.py` | 拼 30 条 + 烧字幕（PyAV + PIL） |
| `审片.py` | 生成 `审核.html` |
| `配音.py` | BGM / 旁白混音（PyAV） |
| `配音生成.py` | IndexTTS-2 批量配音 |

### 模型清单（`D:\Comfy-Desktop\ComfyUI-Shared\models`）

```
[diffusion_models]
  19.0 GB  qwen_image_2512_fp8_e4m3fn          ← 主力静帧
  14.9 GB  minimax_h3_fl2va_pruned_w6a8        ← 主力动态（带对白）
  13.3 GB  wan2.2_i2v_{high,low}_noise_14B_fp8_scaled
   5.8 GB  z_image_turbo_int8_convrot           ← 快速静帧
[loras]
   1.6 GB  Qwen-Image-2512-Lightning-4steps-V1.0-fp32   ← 只是加速档
   1.8 GB  minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16
[text_encoders]
   8.7 GB  qwen_2.5_vl_7b_fp8_scaled            ← Qwen-Image 的 CLIP
  14.6 GB  qwen3vl_32b_minimax_h3_nvfp4_awq     ← MiniMax 的 CLIP
[vae]
  0.2 GB  qwen_image_vae（16 通道 latent！）
  2.6 GB  minimax_h3_video    1.3 GB  minimax_h3_audio
```

---

## 七、一句话总结

1. **纯文本 > 参考图**（在角色设计能写清楚的前提下）
2. **40 步 / CFG 4.0** 才是 Qwen-Image 的正常跑法
3. **MiniMax fl2va 一次出画面 + 对白**，5 秒是甜点
4. **每镜一条独立请求 + 幂等跳过**，断了能续
5. **长任务别放后台还去戳它**，或者至少每镜查一次健康

---

## 六、★★★ MiniMax H3 官方模板的权威参数（2026-10-13 从 ComfyUI 模板集挖出）

模板目录：`D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Lib\site-packages\comfyui_workflow_templates_json\templates\`
（**共 200+ 个官方模板**，覆盖 flux / qwen / z-image / wan / ltx / minimax 全线，以后做任何图或视频先来这里翻）

### 6.1 采样参数（官方 `video_minimax_h3_i2v.json`）

| 项 | 官方 | 说明 |
|---|---|---|
| `scheduler` | `simple` | 与官方一致 |
| `sampler_name` | `res_multistep` | 15 个模板的一致选择 |
| `steps` | **turbo 关 = 20；turbo 开 = 6** | 开关由 `PrimitiveBoolean` + 两个 `ComfySwitchNode` 驱动 |
| `cfg` | **不存在** | 用 `BasicGuider`（无 cfg 口），guidance 固定 1.0 且不暴露 |
| shift 节点 | **一个都不接** | 模板集对 `ModelSamplingSD3` / `ModelSamplingAuraFlow` 零命中 |

**LoRA 配对铁律**：`4step LoRA → 4 步`、`8step LoRA → 6 步`。
**我犯的错：4step LoRA 配了 8 步 —— 错配，步数必须贴合 LoRA 训练时的步数。**

### 6.2 ★ 帧数必须落在 `17k+5` 网格上

```
length: Int, 默认 124, min=5, max=3600, step=17
tooltip: "Frame count at 24 fps, snapped up to the model's 17k+5 grid
          (124 = ~5s; trained range is ~124-362, longer is untested)"
```
官方用 `ComfyMathExpression` 强制对齐：
```
max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17
```
**换算表**：`2s→56`、`3s→73`、`5s→124`、`15s→362`。
**360 / 361 会掉出网格**；训练区间只有 **124–362 帧（5–15 秒）**。

### 6.3 分辨率支持表（官方 `Note: Size Settings Reference`）

| megapixels | 16:9 输出 |
|---|---|
| 0.2 | 608 x 352 |
| 0.4 | 864 x 480 |
| 0.6 | 1056 x 608 |
| 0.8 | 1216 x 672 |
| 0.98 | **1344 x 768（官方 768p）** |

> 原文：`H3's native canvas is a 768px short edge, capped at 768x1344 pixels, rounded to a multiple of 32`
> 官方 i2v 还有一层 `ImageScaleToTotalPixels(nearest-exact, 0.9, 32)` 做输入图预处理。
> `first_frame` 走 `disabled`（纯拉伸），`last_frame` 走 `center`（等比裁切）。

### 6.4 ★★★ 提示词必须写音频，而且是五段式

> 官方 note 原文：**`prompt`: describe the shots, camera moves, and the accompanying audio (dialogue, SFX, music) in one block**
> MiniMax H3「generates video with **native stereo audio**: voice, sound effects, and music are modeled jointly in a single forward pass, not layered on afterward」

官方指南：`https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md`

**骨架**：`风格/场景总述` → `镜头分段（[0s-1s] 时间轴 或 SHOT N）` → `转场与运镜约束` → `Audio: 具体音效与出现时刻` → `硬性禁令`

官方样例（节选）：
```
Vaporwave title sequence look: ... mood languid and nostalgic.

Timeline:
[0s-1s] VHS static opens the frame, the title "COMFYUI" appears with RGB split and a slight horizontal jitter.
[1s-2.5s] Hard cut, a Greek plaster bust close-up, pink-purple gradient sky, a pixelated sun.
[2.5s-4s] Clean "STARRING" credits appear ...

Hard cuts only, transitions landing with tape jumps, no push-ins, no dissolves.

Audio: lo-fi vaporwave score, slow drum machine with soft bass, VHS tape-noise sample joins at 2.5s, melody fading for the last 1s.

All text must be clearly legible, do not misspell English, no Chinese characters, ...
```
**音频行必须具体到乐器/音色/出现时刻**（`VHS tape-noise sample joins at 2.5s`），不能只写「有音效」。
官方**没有负向提示词节点** —— 「不要什么」直接写在正向提示词收尾（`no soft dissolves, no subtitle bars`）。
参考图用 `<Picture 1>` / `<Video 1>` / `<Audio 1>` 按连接顺序编号引用。

### 6.5 ★ fl2va 的「凭空造人」坑（实测）

**症状**：给一张无人的空镜首帧 + 只写动作的提示词，模型自己编了一个汉服少女进画面，画风还从 3D 变成了 2D。

**根因**：提示词没有锁主体时，fl2va 会自由发挥。

**解法：三段锁死**
```
Animate the given first frame exactly. The output must open on precisely the same
image, same characters, same art style, same lighting, same background as the provided first frame.
What happens: <动作>
Characters present: <这一镜有谁>          ← 没有人物时必须显式写 "No people ... at all."
Absolutely do not introduce any new character, person, animal or object that is not
already in the first frame. Do not change the art style. Do not cut to another scene.
```
**实测：加了三段锁之后，空镜老实了，有人物的镜头也稳了。**

### 6.6 其他对不上的项

| 项 | 官方 | 备注 |
|---|---|---|
| `CreateVideo.fps` | 24（15 个模板一律） | 模型固定 24fps 出帧，不是自由参数 |
| `CreateVideo.bit_depth` | 8（i2v/t2v） | 我原来没设 |
| `SaveVideo.format / codec` | `auto` / `auto` | 一致 |
| UNet | `minimax_h3_fl2va_pruned_int8_convrot` | 我用的 `w6a8` 在 15 个模板里零出现 |
| scheduler 备选 | r2v note 原文：`beta or normal scheduler tends to outperform simple for reference-heavy prompts` | 参考图信息重时值得试 |
