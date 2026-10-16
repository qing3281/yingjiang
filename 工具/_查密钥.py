# -*- coding: utf-8 -*-
"""上 GitHub 之前：把「绝不能传上去的东西」逐条找出来。

**只报位置和命中片段的前 6 个字符**，不打印完整密钥 —— 这个脚本的输出我可能要贴给用户看。

查五类：
  ① 邮箱授权码 / SMTP 密码
  ② 各种 API key / token（sk- / ghp_ / hf_ / AIza / xai- …）
  ③ 明文密码赋值
  ④ .env / credentials 一类的文件本身
  ⑤ 私钥文件（id_rsa / id_ed25519，**不是** .pub）

用法： python 工具\_查密钥.py [根 ...]      缺省扫「工具 / 影匠 / B站」
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

缺省根 = [
    r"D:\DSHworkspace\工具",
    r"D:\DSHworkspace\影匠",
    r"D:\DSHworkspace\B站",
]
# 不进的目录（体积大 + 不可能有源码密钥）
跳过目录 = {
    ".git", "__pycache__", "node_modules", "venv", ".venv", "site-packages",
    "_网盘整理", "_work", "作品", "_bin", "dist", "build", ".idea", ".vscode",
    "ms-playwright", "chromium-", "downloads",
}
要看的后缀 = {
    ".py", ".js", ".mjs", ".ts", ".ps1", ".cmd", ".bat", ".json", ".yaml", ".yml",
    ".ini", ".cfg", ".conf", ".md", ".txt", ".env", ".toml", ".sh",
}
# 只报位置的文件名（一眼就知道不该进库）
敏感文件名 = re.compile(
    r"(\.env(\.|$)|credentials|secret|passwd|password|\.pem$|\.pfx$|\.key$|"
    r"id_rsa$|id_ed25519$|id_ecdsa$|\.netrc$|token.*\.json$|cookies?\.(txt|json)$)",
    re.I,
)

规则 = [
    ("邮箱授权码/SMTP密码", re.compile(r"(授权码|smtp_pass|mail_pass|auth_?code|邮箱密码)\s*[:=]\s*['\"]([^'\"]{4,})", re.I)),
    ("OpenAI 风格 key", re.compile(r"\b(sk-[A-Za-z0-9_\-]{16,})")),
    ("GitHub token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})")),
    ("HuggingFace token", re.compile(r"\b(hf_[A-Za-z0-9]{20,})")),
    ("Google API key", re.compile(r"\b(AIza[0-9A-Za-z_\-]{30,})")),
    ("xAI / Anthropic key", re.compile(r"\b(xai-[A-Za-z0-9]{16,}|sk-ant-[A-Za-z0-9_\-]{20,})")),
    ("微信/QQ 等 webhook", re.compile(r"(https://qyapi\.weixin\.qq\.com/[^\s'\"]+|https://oapi\.dingtalk\.com/[^\s'\"]+)")),
    ("明文密码赋值", re.compile(r"(password|passwd|pwd|密码)\s*[:=]\s*['\"]([^'\"\s]{6,})['\"]", re.I)),
    ("Authorization 头", re.compile(r"Authorization['\"]?\s*[:=]\s*['\"]?(Bearer|Basic)\s+[A-Za-z0-9._\-]{12,}", re.I)),
]


def 遮(s):
    s = s.strip()
    return (s[:6] + "…") if len(s) > 6 else "…"


def 扫(根们):
    命中 = {名字: [] for 名字, _ in 规则}
    敏感文件 = []
    扫过 = 0
    for 根 in 根们:
        if not os.path.isdir(根):
            print(f"· 不在：{根}")
            continue
        for 底, 目录们, 文件们 in os.walk(根):
            目录们[:] = [d for d in 目录们 if d not in 跳过目录 and not d.startswith("chromium-")]
            for f in 文件们:
                p = os.path.join(底, f)
                rel = os.path.relpath(p, r"D:\DSHworkspace")
                if 敏感文件名.search(f):
                    敏感文件.append(rel)
                if os.path.splitext(f)[1].lower() not in 要看的后缀:
                    continue
                try:
                    if os.path.getsize(p) > 2 * 1024 * 1024:
                        continue
                    with io.open(p, "r", encoding="utf-8", errors="ignore") as fh:
                        文 = fh.read()
                except OSError:
                    continue
                扫过 += 1
                for 名, 正 in 规则:
                    for m in 正.finditer(文):
                        g = m.groups()
                        val = g[-1] if g else m.group(0)
                        # 占位/示例不算
                        if any(t in val.lower() for t in ("你的", "xxx", "***", "example", "todo", "placeholder", "填", "<")):
                            continue
                        行 = 文[:m.start()].count("\n") + 1
                        命中[名].append((rel, 行, 遮(val)))
    return 命中, 敏感文件, 扫过


if __name__ == "__main__":
    根们 = sys.argv[1:] or 缺省根
    print("══ 上 GitHub 前的密钥体检 ══")
    print("扫的根：" + "、".join(根们) + "\n")
    命中, 敏感文件, 扫过 = 扫(根们)
    print(f"看了 {扫过} 个文本文件\n")
    总 = 0
    for 名, 列表 in 命中.items():
        if not 列表:
            print(f"✓ {名}：0 处")
            continue
        总 += len(列表)
        print(f"★★ {名}：{len(列表)} 处")
        for rel, 行, v in 列表[:8]:
            print(f"     {rel}:{行}　{v}")
        if len(列表) > 8:
            print(f"     …… 还有 {len(列表)-8} 处")
    print()
    if 敏感文件:
        总 += len(敏感文件)
        print(f"★★ 一眼就不该进库的文件：{len(敏感文件)} 个")
        for rel in 敏感文件[:20]:
            print(f"     {rel}")
        if len(敏感文件) > 20:
            print(f"     …… 还有 {len(敏感文件)-20} 个")
    else:
        print("✓ 没有 .env / 私钥 / credentials 一类文件")
    print()
    print("═" * 60)
    print(f"结论：{总} 处要处理　{'★ 先处理干净再传' if 总 else '干净，可以传'}")
    sys.exit(1 if 总 else 0)
