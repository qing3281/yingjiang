// dsh-yingjiang-panel —— 服务端这一半。
//
// ★★ 这个文件是干什么的（用户 2026-10-16 02:0x 立的规矩）：
//
//   用户原话：「你的这个记忆台，他就应该随着你的这个 DSH 这个应用的打开，它就自动开启了呀，
//             并自动运行加载了呀。为什么你还要在后边搞两个终端在这跑着？还要考虑搞什么开机启动。
//             你在想什么？有插件是这样用的吗？」
//
//   他说得对。上一版我在外面挂了「守护脚本 + 开机启动 + 每分钟计划任务」，
//   那三样都是错的 —— **插件自己就该把服务带起来**：
//
//     DSH 一开 → 插件 apply() 跑 → 起三个台 → 页面上的两个页签直接能用
//     DSH 一关 → 插件被 dispose → 把三个台杀掉，不留残留进程
//
//   所以外面那些东西已经全部拆掉了（_守护台.py / 开机自启快捷方式 / 计划任务）。
//   **判断这个文件有没有干活，看 `D:\DSHworkspace\_插件已加载.log`。**
//
// ★ 三个坑，都是踩过的，别凭感觉改回去：
//   ① 子进程必须 `windowsHide: true` —— 否则每起一个台就弹一个黑窗口（用户明确说烦）
//   ② 起之前先探端口 —— DSH 热重载时旧进程可能还占着口，重复起会 bind 失败
//   ③ apply() 里 **return 一个清理函数** —— cordis 认这个，DSH 关掉或重载插件时会调它

import { spawn } from "node:child_process";
import { appendFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import net from "node:net";

const 日志 = "D:\\DSHworkspace\\_插件已加载.log";
const 工作区 = "D:\\DSHworkspace";
const Python = "D:\\Comfy-Desktop\\ComfyUI-Installs\\ComfyUI\\ComfyUI\\.venv\\Scripts\\python.exe";

// ★ 归档会话的「今天跑过了吗」印记（用户 m37867 要「归档做成每天定时自动做的固定动作」）
//   为什么不挂 Windows 计划任务：用户 m38331 立的规矩 —— **插件自己就该把活带起来**，
//   外面挂计划任务、挂开机启动，都是他明确骂过的做法。
const 印记 = "D:\\DSHworkspace\\_归档日.txt";

const 时 = () => new Date().toLocaleString("zh-CN", { hour12: false });
function 记(msg) {
  try { appendFileSync(日志, `[${时()}] ${msg}\n`, "utf8"); } catch { /* 写不进去就算了 */ }
}

// ★ 要跟着 DSH 一起活的台。加新台就往这儿加一行。
const 台们 = [
  { 名: "影匠控制台", 口: 8791, 脚本: `${工作区}\\影匠\\_控台.py`, 参数: ["--口", "8791", "--不开"], 目录: `${工作区}\\影匠` },
  { 名: "记忆台", 口: 8792, 脚本: `${工作区}\\_记忆台.py`, 参数: [], 目录: 工作区 },
  { 名: "依据台", 口: 8794, 脚本: `${工作区}\\_依据台.py`, 参数: [], 目录: 工作区 },
];

function 在听吗(口) {
  return new Promise((好) => {
    const s = net.connect({ host: "127.0.0.1", port: 口 });
    const 完 = (v) => { try { s.destroy(); } catch {} 好(v); };
    s.setTimeout(700);
    s.once("connect", () => 完(true));
    s.once("timeout", () => 完(false));
    s.once("error", () => 完(false));
  });
}

export const name = "dsh-yingjiang-panel";
export const inject = [];

export function apply(ctx) {
  记("======== apply() 被调用了：开始带起三个台 ========");

  const 我起的 = [];

  // 立刻返回清理函数，剩下的异步做
  (async () => {
    for (const 台 of 台们) {
      try {
        if (await 在听吗(台.口)) {
          记(`${台.名}（口 ${台.口}）已经在听 —— 不重复起`);
          continue;
        }
        const p = spawn(Python, [台.脚本, ...台.参数], {
          cwd: 台.目录,
          windowsHide: true,          // ★ 坑①：不写这个就弹黑窗口
          stdio: "ignore",
          detached: false,            // 跟着 DSH 活，DSH 死它不该被带走（但会被下面的清理函数杀）
        });
        我起的.push({ 台, p });
        记(`起了 ${台.名}（口 ${台.口}）→ pid ${p.pid}`);
        p.on("exit", (码) => 记(`${台.名} 退出了，码 ${码}`));
        p.on("error", (e) => 记(`★ ${台.名} 起不来：${e && e.message}`));
      } catch (e) {
        记(`★ ${台.名} 出错：${e && e.message ? e.message : e}`);
      }
    }
    记("三个台处理完了");
  })();

  // ══════════════════════════════════════════════════════════════
  // 每天归档一次会话（用户 m37867 点的第一条活）
  // ══════════════════════════════════════════════════════════════
  // 判据：`D:\DSHworkspace\_归档日.txt` 里是不是今天。
  //   不是今天 → 起一次 `_归档会话.py` → 把今天写进去。
  //   DSH 今天开开关关十次，也只跑一次。
  // 它慢（翻 194 个压缩包、约 40 秒），所以 detached + stdio ignore，
  // 不拖慢 DSH 起来；写没写成看 `D:\DSHworkspace\会话存档\索引.md` 的 mtime。
  (async () => {
    try {
      const 今天 = new Date().toLocaleDateString("sv-SE"); // sv-SE 就是 YYYY-MM-DD
      let 上次 = "";
      try { if (existsSync(印记)) 上次 = readFileSync(印记, "utf8").trim(); } catch {}
      if (上次 === 今天) {
        记(`会话归档：今天（${今天}）已经跑过了，跳过`);
        return;
      }
      const p = spawn(Python, ["-X", "utf8", `${工作区}\\_归档会话.py`], {
        cwd: 工作区,
        windowsHide: true,
        stdio: "ignore",
        detached: true,
      });
      p.unref();
      记(`会话归档：起了一次（上次 ${上次 || "从来没跑过"}）→ pid ${p.pid}`);
      // 不等它跑完 —— spawn 出去就算交差，成没成看 会话存档\索引.md 的 mtime
      try { writeFileSync(印记, 今天, "utf8"); } catch (e) { 记(`★ 归档印记写不进去：${e && e.message}`); }
      p.on("exit", (码) => 记(`会话归档 跑完了，码 ${码}　（产物：D:\\DSHworkspace\\会话存档\\索引.md）`));
      p.on("error", (e) => 记(`★ 会话归档 起不来：${e && e.message}`));
    } catch (e) {
      记(`★ 会话归档 出错：${e && e.message ? e.message : e}`);
    }
  })();

  const 收摊 = () => {
    for (const { 台, p } of 我起的) {
      try { p.kill(); 记(`关掉 ${台.名}（pid ${p.pid}）`); } catch (e) { 记(`关 ${台.名} 出错：${e && e.message}`); }
    }
    我起的.length = 0;
  };

  // ★ 坑③：cordis 认 apply() 的返回值当注销函数
  try { if (ctx && typeof ctx.on === "function") ctx.on("dispose", 收摊); } catch {}
  return 收摊;
}

export default { name, inject, apply };
