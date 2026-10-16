# -*- coding: utf-8 -*-
"""生成《不烧心》的人物形象图（三视图设定卡）与场景图。

用法：
    python 出人设.py --人物          # 只出 7 张人物设定卡
    python 出人设.py --场景          # 只出 6 张场景图
    python 出人设.py --全部          # 都出
    python 出人设.py --人物 --只出 1 # 只出第 1 个（调试用）

设计要点：
  * 走 Z-Image-Turbo int8（8 步，本机实测 5~10 秒一张），人设图不追求真实感，追求"设定卡"感
  * 每张图都是「三视图 + 配色板 + 细节特写」的设定卡排版，这样角色形象一旦定了，
    后面 30 个分镜就照这个形象锁死
  * 角色描述写成 锚点词（anchor），出片.py 生成分镜时会整段复用，保证跨镜一致
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMFY = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
输出根 = r"D:\DSHworkspace\B站\成片\不烧心"
人设目录 = os.path.join(输出根, "人设")
场景目录 = os.path.join(输出根, "场景")

# Z-Image-Turbo
模型 = "z_image_turbo_int8_convrot.safetensors"
文本编码器 = "qwen_3_4b_fp8_mixed.safetensors"
vae = "ae.safetensors"
Shift = 3.0
步数 = 8

# 设定卡通用后缀：三视图 + 配色板，便于锁形象
设定卡后缀 = (
    "character design sheet, three views (front view, side view, back view) side by side, "
    "plus a color palette swatch bar and three close-up detail insets, "
    "plain flat light gray background, clean organized layout, "
    "full body, sharp lineart, anime key visual, high detail, no text no watermark"
)
场景后缀 = (
    "cinematic wide shot, 35mm film still, moody volumetric lighting, "
    "highly detailed background art, anime background painting style, "
    "no people no characters no text"
)

# ---------------------------------------------------------------------------
# 角色锚点：出片.py 生成分镜时会整段复用这些词，保证同一个角色跨 30 镜长得一样
# ---------------------------------------------------------------------------

角色 = {
    "deepseek": {
        "名": "DeepSeek 鲸鱼娘",
        "锚点": (
            "DeepSeek whale girl, a lovely anime girl with a mature young woman figure, "
            "very long voluminous gradient hair flowing from deep navy blue at the roots "
            "to light sky blue at the tips, reaching below the waist, "
            "large bright blue eyes, "
            "two navy blue fin-shaped ears sticking out from the sides of her head, "
            "clearly visible outside the hair silhouette, pointing outward and down, "
            "one single curly ahoge strand looping on top of the head, "
            "a WHITE FRILLED MAID HEADBAND with lace trim across the top of her head, "
            "a blue ribbon bow on the right side of the head, "
            "a large forked whale tail emerging from behind her skirt, "
            "dark navy blue maid dress: white ruffled collar, dark navy bow tie with a blue gem, "
            "white buttoned shirt front panel, dark navy corset bodice with gold buttons, "
            "puff sleeves with white lace cuffs, "
            "WHITE FRILLED APRON with a small whale silhouette embroidered on the apron hem, "
            "dark navy long skirt with an inner layer of light blue striped fabric and gold trim, "
            "white tights, dark navy mary jane shoes, "
            "holding a big bowl piled high with plain white rice, "
            "mischievous cheeky grin, smug eyes, "
            "IMPORTANT: two dark navy fin-shaped ears stick out sideways from her head, "
            "one on each side at eye level, clearly visible against the background, "
            "shaped like whale flippers, angled outward and downward"
        ),
        "设定卡": (
            "深蓝与白的配色板：深海蓝 #1B3A6B / 冰蓝 #7FC4E8 / 米白 #F5F3EC",
            "细节特写：头两侧的鲸鳍耳、卷曲呆毛、白色蕾丝女仆头饰、发侧蓝色蝴蝶结、身后大型鲸尾",
            "围裙下摆绣着一只小鲸鱼",
            "手里抱一个大碗，堆满冒尖的白饭",
        ),
    },
    "gpt": {
        "名": "GPT 龙娘",
        "锚点": (
            "ChatGPT dragon girl, an elegant tall anime girl with a mature figure, "
            "very long voluminous silver white hair with a mint green gradient at the tips, "
            "reaching below the waist, teal green eyes, "
            "a pair of WHITE DRAGON HORNS curving backward from the top of her head, "
            "long pointed elf ears, "
            "LARGE WHITE BAT-LIKE DRAGON WINGS with visible bone structure and membrane, "
            "a thick long white scaly dragon tail with a fin-like tip, "
            "a white rose hair ornament with a small green OpenAI knot logo on the side of her head, "
            "white multi-layered gown: white layered top with ruffles, black waist sash, "
            "black ribbon at the collar, long flowing white skirt with many ruffled layers "
            "over a mint green underskirt, black ankle boots, "
            "holding a thick BLACK BOOK with the OpenAI knot logo on the cover, "
            "dignified composed expression, slightly weary but warm"
        ),
        "设定卡": (
            "白与墨黑与青绿的配色板：纯白 #FFFFFF / 墨黑 #1A1A1A / 青绿 #10A37F",
            "细节特写：向后弯曲的白色龙角、蝙蝠式带骨节龙翼、尖长精灵耳、粗白龙尾",
            "白玫瑰 + OpenAI 结环发饰、怀中印着标志的黑皮书",
        ),
    },
    "claude": {
        "名": "Claude 娘",
        "锚点": (
            "Claude AI girl, a gentle warm anime girl, "
            "long soft orange-auburn wavy hair, "
            "warm amber eyes, a LARGE PALE FLOWER HAIR ORNAMENT on the side of her head, "
            "white blouse with puffed sleeves, a soft orange-brown skirt, "
            "a white apron tied at the waist, "
            "holding a small empty lunch box, "
            "serene knowing smile, the calm mature one"
        ),
        "设定卡": (
            "暖色配色板：暖橘 #D97757 / 奶油白 #F7F3EC / 浅灰蓝 #A8B5C4",
            "细节特写：侧边大花发饰、橘棕长裙、白色围裙、手里的空饭盒",
            "气质：安静、笃定，第一个走也第一个回来",
        ),
    },
    "doubao": {
        "名": "豆包娘（官方人设）",
        "锚点": (
            "Doubao AI girl, a round-faced chubby cute anime girl, "
            "short dark bob hair with blunt bangs, "
            "big round vacant eyes, a thin line of drool at the corner of her mouth, "
            "blue and white casual hoodie, "
            "blank stupid expression, mouth slightly open in a flat deadpan way"
        ),
        "设定卡": (
            "蓝白配色板：豆包蓝 #2B6CF6 / 白 #FFFFFF / 浅灰 #E8ECF2",
            "细节特写：嘴角口水线、呆滞圆眼、棒读张开的口型",
            "官方人设，不要美化",
        ),
    },
    "kimi": {
        "名": "Kimi 娘",
        "锚点": (
            "Kimi AI girl, a sharp confident anime girl, "
            "short neat black hair with a single blue streak, "
            "narrow sharp eyes, "
            "dark purple and black techwear jacket with high collar, "
            "arms crossed, impatient skeptical expression"
        ),
        "设定卡": ("紫黑配色板：深紫 #3B2E5A / 电光蓝 #3FA9F5 / 黑 #111111",
                 "细节特写：蓝色挑染、立领夹克、抱臂",
                 "气质：急躁、爱吐槽"),
    },
    "glm": {
        "名": "GLM 娘",
        "锚点": (
            "GLM AI girl, a bookish nerdy anime girl, "
            "medium length dark teal hair in a low ponytail, "
            "round glasses sliding down her nose, "
            "beige sweater vest over a white shirt, "
            "holding a small abacus, flustered anxious expression"
        ),
        "设定卡": ("青灰配色板：墨青 #1F4E4A / 米色 #E8DCC8 / 灰 #9AA5A0",
                 "细节特写：滑落鼻梁的圆眼镜、低马尾、手中小算盘",
                 "气质：较真、算不清账"),
    },
    "qwen": {
        "名": "千问娘",
        "锚点": (
            "Qwen AI girl, a cheerful tall anime girl, "
            "long straight indigo-purple hair, "
            "bright violet eyes, "
            "purple and white modern qipao-inspired top with wide sleeves, "
            "surprised open-mouthed expression, one hand covering her mouth"
        ),
        "设定卡": ("紫白配色板：靛紫 #6B4FBB / 白 #FFFFFF / 银 #C9CDD6",
                 "细节特写：长直发、宽袖、捂嘴的手",
                 "气质：爱起哄、后知后觉"),
    },
}

# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------
场景 = {
    "街道": (
        "a narrow old Chinese street at dawn, wet gray flagstone pavement, "
        "two low storefronts facing each other across the alley, "
        "faded red paper lanterns under the eaves, hanging electric wires, "
        "a hand-painted wooden shop sign, steam drifting out of a doorway, "
        "misty morning air, deep one-point perspective down the alley, "
        "no people"
    ),
    "GPT后厨": (
        "interior of an old Chinese street kitchen, a big black iron wok stove burning orange coal, "
        "a huge pot of bone broth bubbling with thick white steam, "
        "grease-stained tiled wall, hanging ladles and cleavers, "
        "stacks of ceramic bowls on a wooden shelf, warm orange firelight, "
        "smoke haze, worn wooden countertop, no people"
    ),
    "DeepSeek铺子": (
        "a cheap street food stall, a giant steamer basket piled with plain white rice "
        "venting thick steam, a hand-written sign, plastic stools, "
        "stacks of disposable bowls, a dented aluminum pot, "
        "harsh cool white fluorescent light, messy and shabby, no people"
    ),
    "街边长桌": (
        "a long weathered wooden table set up on the sidewalk, "
        "chipped ceramic bowls of white rice and chopsticks laid out, "
        "low wooden stools, greasy paper wrappers, "
        "overcast gray afternoon light, empty and slightly dreary, no people"
    ),
    "库房": (
        "a dim storage room behind a shop, stacked wooden crates and burlap sacks of rice, "
        "dust motes floating in a single shaft of light from a small high window, "
        "cobwebs in the corners, cold blue tone, no people"
    ),
    "后门垃圾堆": (
        "a narrow back alley behind the shops, a pile of discarded crates and broken bowls, "
        "a wooden back door standing ajar, wet ground, "
        "cold gray morning light, bare branches overhead, no people"
    ),
}


# ----------------------------------------------------------------- ComfyUI
def 取(p, 超时=30):
    with urllib.request.urlopen(COMFY + p, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 发(p, 数据, 超时=60):
    req = urllib.request.Request(
        COMFY + p, data=json.dumps(数据).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=超时) as r:
        return json.loads(r.read().decode("utf-8"))


def 建图(提示词, 宽, 高, 种子, 前缀):
    return {
        "28": {"class_type": "UNETLoader",
               "inputs": {"unet_name": 模型, "weight_dtype": "default"}},
        "30": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": 文本编码器, "type": "lumina2", "device": "default"}},
        "29": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "27": {"class_type": "CLIPTextEncode",
               "inputs": {"text": 提示词, "clip": ["30", 0]}},
        "33": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["27", 0]}},
        "11": {"class_type": "ModelSamplingAuraFlow",
               "inputs": {"model": ["28", 0], "shift": Shift}},
        "13": {"class_type": "EmptySD3LatentImage",
               "inputs": {"width": 宽, "height": 高, "batch_size": 1}},
        "3": {"class_type": "KSampler",
              "inputs": {"model": ["11", 0], "positive": ["27", 0], "negative": ["33", 0],
                         "latent_image": ["13", 0], "seed": 种子, "steps": 步数,
                         "cfg": 1.0, "sampler_name": "res_multistep",
                         "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["29", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": 前缀}},
    }


def 出图一张(图, 超时秒=600):
    r = 发("/prompt", {"prompt": 图})
    pid = r["prompt_id"]
    起 = time.time()
    while time.time() - 起 < 超时秒:
        time.sleep(1.0)
        try:
            h = 取(f"/history/{pid}", 15)
        except Exception:
            continue
        if pid not in h:
            continue
        rec = h[pid]
        状态 = rec.get("status", {})
        if 状态.get("status_str") == "error" or 状态.get("completed") is False:
            raise RuntimeError("ComfyUI 报错: " +
                               json.dumps(状态.get("messages", []), ensure_ascii=False)[:400])
        for nid, o in rec.get("outputs", {}).items():
            for im in o.get("images", []):
                return im["filename"], im.get("subfolder", ""), time.time() - 起
    raise RuntimeError(f"等图超时（{超时秒}s）")


def 下载图(文件名, 子目录, 存到):
    q = urllib.parse.urlencode({"filename": 文件名, "subdirectory": 子目录, "type": "output"})
    with urllib.request.urlopen(f"{COMFY}/view?{q}", timeout=120) as r:
        数据 = r.read()
    os.makedirs(os.path.dirname(存到), exist_ok=True)
    with open(存到, "wb") as f:
        f.write(数据)
    return len(数据)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--人物", action="store_true")
    ap.add_argument("--场景", action="store_true")
    ap.add_argument("--全部", action="store_true")
    ap.add_argument("--只出", type=int, default=None, help="只出第 N 个（1 起）")
    ap.add_argument("--种子", type=int, default=20261013)
    a = ap.parse_args()
    if not (a.人物 or a.场景 or a.全部):
        a.全部 = True

    try:
        取("/system_stats", 8)
    except Exception as e:
        print(f"❌ 连不上 ComfyUI ({COMFY})：{e}")
        print("   先跑：python 启动ComfyUI.py")
        return 1

    os.makedirs(人设目录, exist_ok=True)
    os.makedirs(场景目录, exist_ok=True)
    清单 = []

    if a.人物 or a.全部:
        print("\n=== 人物形象图（三视图设定卡）===")
        for i, (k, c) in enumerate(角色.items(), 1):
            if a.只出 and i != a.只出:
                continue
            提示 = f"{c['锚点']}。{设定卡后缀}"
            提示 += "。" + "; ".join(c["设定卡"])
            存 = os.path.join(人设目录, f"{i:02d}_{c['名']}_三视图.png")
            print(f"[{i}/{len(角色)}] {c['名']} …", end="", flush=True)
            try:
                fn, sub, 耗 = 出图一张(建图(提示, 1024, 1408, a.种子 + i * 7, "人设"))
                n = 下载图(fn, sub, 存)
                print(f" ✓ {耗:.1f}s  {n/1024:.0f} KB")
                清单.append({"类型": "人物", "键": k, "名": c["名"], "文件": 存,
                             "锚点": c["锚点"], "耗时": round(耗, 1)})
            except Exception as e:
                print(f" ✗ {e}")

    if a.场景 or a.全部:
        print("\n=== 场景图 ===")
        for i, (k, 提示词) in enumerate(场景.items(), 1):
            if a.只出 and i != a.只出:
                continue
            存 = os.path.join(场景目录, f"{i:02d}_{k}.png")
            print(f"[{i}/{len(场景)}] {k} …", end="", flush=True)
            try:
                fn, sub, 耗 = 出图一张(建图(提示词 + "。" + 场景后缀, 1344, 768, a.种子 + 900 + i, "场景"))
                n = 下载图(fn, sub, 存)
                print(f" ✓ {耗:.1f}s  {n/1024:.0f} KB")
                清单.append({"类型": "场景", "键": k, "名": k, "文件": 存, "耗时": round(耗, 1)})
            except Exception as e:
                print(f" ✗ {e}")

    if 清单:
        表 = os.path.join(输出根, "人设清单.json")
        with open(表, "w", encoding="utf-8") as f:
            json.dump(清单, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 共 {len(清单)} 张 → {表}")
    总 = sum(x["耗时"] for x in 清单)
    print(f"   纯生成耗时合计 {总:.0f} 秒（{总/60:.1f} 分）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
