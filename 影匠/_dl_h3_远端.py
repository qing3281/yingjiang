"""Remote side: download MiniMax-H3 models straight from hf-mirror.com.

Usage (on the remote):
    python -X utf8 _dl_h3.py --probe     speed probe only
    python -X utf8 _dl_h3.py             download the set
"""
import argparse
import os
import subprocess
import sys
import time

REPO = "Comfy-Org/MiniMax-H3"
ENDPOINT = "https://hf-mirror.com"
DEST = r"E:\影匠AI\ComfyUI-Shared\models"

WANT = [
    ("diffusion_models", "minimax_h3_fl2va_int8_convrot.safetensors"),
    ("text_encoders",    "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
    ("vae",              "minimax_h3_video_vae_fp16.safetensors"),
    ("vae",              "minimax_h3_audio_vae_fp32.safetensors"),
]


def say(s):
    sys.stdout.write(str(s) + "\n")
    sys.stdout.flush()


def deps():
    for pkg in ("huggingface_hub", "hf_transfer"):
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg],
                           capture_output=True, text=True)
        ok = "OK" if r.returncode == 0 else "FAIL " + (r.stderr or "")[-200:]
        say("  pip %s: %s" % (pkg, ok))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    os.environ["HF_ENDPOINT"] = ENDPOINT
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    say("HF_ENDPOINT=%s" % ENDPOINT)
    deps()

    from huggingface_hub import hf_hub_download

    if args.probe:
        sub, name = WANT[2]
        say("probe: %s" % name)
        t0 = time.time()
        p = hf_hub_download(repo_id=REPO, filename="%s/%s" % (sub, name),
                            local_dir=r"E:\_dl_probe")
        dt = max(0.001, time.time() - t0)
        mb = os.path.getsize(p) / 1e6
        say("  %.0f MB in %.1f s -> %.2f MB/s" % (mb, dt, mb / dt))
        return 0

    say("文件按顺序下；已存在的（>1e8 字节）直接跳过，所以断了重跑就是续传。")
    say("")

    total = 0
    for i, (sub, name) in enumerate(WANT, 1):
        d = os.path.join(DEST, sub)
        os.makedirs(d, exist_ok=True)
        to = os.path.join(d, name)
        if os.path.exists(to) and os.path.getsize(to) > 1e8:
            g = os.path.getsize(to) / 1e9
            say("[%d/%d] 已有 %s  %.2f GB" % (i, len(WANT), name, g))
            total += os.path.getsize(to)
            continue

        say("[%d/%d] 开始下 %s/%s" % (i, len(WANT), sub, name))
        t0 = time.time()
        # ★ local_dir 直接指最终目录，下完就地落地，不做 move
        #   （以前用 E:\_dl_tmp 中转 —— 结果 _dl_tmp 根本没被创建，白等）
        p = hf_hub_download(repo_id=REPO, filename="%s/%s" % (sub, name),
                            local_dir=DEST)
        dt = max(0.001, time.time() - t0)
        size = os.path.getsize(p)
        say("[%d/%d] 完成 %s  %.2f GB  %.1f 分  %.2f MB/s"
            % (i, len(WANT), name, size / 1e9, dt / 60, size / 1e6 / dt))
        total += size

    say("")
    say("全部完成：%.2f GB -> %s" % (total / 1e9, DEST))
    return 0


if __name__ == "__main__":
    sys.exit(main())
