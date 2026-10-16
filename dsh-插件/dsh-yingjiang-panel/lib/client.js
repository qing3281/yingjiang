// 影匠面板 —— 浏览器那一半。侧栏放两个面板：「记忆」和「依据」。
//
//   「记忆」→ http://127.0.0.1:8792/   记忆台（经验/坑/台账/原话，每次请求重扫）
//   「依据」→ http://127.0.0.1:8794/   依据台（这一轮读了哪些文件、做了哪些动作）
//
// 数据从哪来：DSH 自己写在会话存档里的 tool/call 记录 —— 我改不了，所以它能当证据。
// 我说「我查过了」，你在这一页能看见我到底开没开那个文件。
//
// ============================================================================
// ★★★ 2026-10-16 02:0x —— 形状推倒重来，依据是用户指的那一句
//
// 用户原话：
//   「你看一下那个 IG5 逆向工作台，他是怎么做的？为什么他就能放到上边，
//     你不放到右边，你放到上边不行吗？」
//
// 照他这句话去读 `dsh-infinite-gen-5\client.js`（那个真在跑、真能看见的插件），
// 它挂界面**根本不用 `sidebarRightTabs` 那个服务**，用的是 **slots 槽位**：
//
//     ctx.slots.inject("sidebar.panellist", function () {
//       return ctx.slots.register(
//         { name: "sidebar.panellist", id: PANEL_ID, order: 55,
//           label: function () { return "面板名字"; } },
//         function () { return el("svg", ...); }        // ← 侧栏里的图标
//       );
//     });
//     ctx.slots.inject("main", function () {
//       return ctx.slots.register(
//         { name: "main", key: PANEL_ID },               // ← key 跟上面的 id 对上
//         function (props) { return el(内容组件, props); }
//       );
//     });
//     exports.inject = ["slots"];      // ← 只要 slots 这一个服务
//
// 它自己也只用 `ctx.slots`，**全篇没有一处 `ctx.inject(...)`**。
//
// 我原来那份错在哪儿：拿 `ctx.inject(["sidebarRightTabs"], ...)` 去要一个服务，
// 再去 `sidebarRightTabs.register(...)` + `slots.inject("sidebar.right.pane.tab", ...)`。
// 那套形状是从 `dsh-better-sidebar` / `dsh-context` 的**打包产物**里逆出来的 ——
// **打包产物和手写插件不是一种写法**，我照着逆出来的抄，抄错了一层。
//
// ★ 判据：`dsh-infinite-gen-5\client.js` 是**手写的**（文件头就是中文注释），
//   跟我要写的是一种东西。以后照它抄，不要照打包产物抄。
//
// 下面这些是 01:0x 逐字对出来的**另一批**错（都改了，留着当判据）：
//   ① `sidebarRightTabs.register` 的 `title` 要「返回字符串的函数」，不是 React 组件
//   ② `guide[].title` / `guide[].description` 要的也是函数，每条 guide 还要有 `id`
//   ③ `slots.inject(名, cb)` 里 **register 要直接在 cb 里调**：写 `(s) => () => s.register(...)`
//      就是多套一层，register 永远不执行。cb 的返回值本身才是注销函数。
//   ④ 槽从 `ctx.slots` 拿，且 `inject` 里必须点名要 `"slots"`（写过空的 `inject = []`，等于没要）
// ============================================================================
//
// 埋点：每走一步往本机 8796 发一个 GET（台子见 `D:\DSHworkspace\_埋点台.py`）。
// 为什么需要它：页签不出现时我**一尺都量不到**（抓屏全黑、`/plugins/.../client.js` 对所有插件都 404）。
//   · 有「载入」= 这个包进了浏览器模块图，脚本语法能过
//   · 没有「载入」= 包根本没进模块图
//   · 有「错-」= 拿到确切报错了
// 报信绝不能影响面板：全在 try 里，fetch 不成退化成 <img>。

function 报信(什么) {
  try {
    var u = "http://127.0.0.1:8796/?_=" + encodeURIComponent(String(什么));
    if (typeof fetch === "function") {
      fetch(u, { mode: "no-cors", cache: "no-store" });
    } else {
      new Image().src = u;
    }
  } catch (e) {
    /* 报信失败不许影响面板 */
  }
  try {
    console.info("[影匠面板·埋点] " + 什么);
  } catch (e2) {
    /* 没有 console 也不能抛 */
  }
}
报信("载入");

window.__ModuleLoader__.load({
  id: "dsh-yingjiang-panel",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
    报信("工厂跑了");

    var react = require("react");
    var el = react.createElement;

    var inject = ["slots"];
    var PLUGIN_ID = "dsh-yingjiang-panel";

    // ── 要挂的面板：改这里就能加/减 ──
    var 面板们 = [
      {
        号: "yingjiang-jiyi",
        题: "记忆",
        址: "http://127.0.0.1:8792/",
        序: 55,
        注: "经验 · 踩过的坑 · 台账 · 你说过的话（每次打开都重扫，不是快照）",
        // 侧栏图标（16x16，跟 IG5 同一套写法）
        图: "M8 1.2A3.3 3.3 0 0 0 4.7 4.5v4.1a1.6 1.6 0 0 0 1.6 1.6h.5v3.1l3-3.1h1.9a1.6 1.6 0 0 0 1.6-1.6V4.5A3.3 3.3 0 0 0 10 1.2H8zm-1.5 3.3h5v1.2h-5V4.5zm0 2.4h3.4V8H6.5V6.9z",
      },
      {
        号: "yingjiang-yiju",
        题: "依据",
        址: "http://127.0.0.1:8794/",
        序: 56,
        注: "这一轮读了哪些文件、做了哪些动作（DSH 记的，不是我上报的）",
        图: "M3.2 1.6h6.4l3.2 3.2v9.6H3.2V1.6zm1.3 1.3v10.2h7V5.3H8.3V2.9H4.5zm1.4 5h5.4v1.2H5.9V7.9zm0 2.4h5.4v1.2H5.9V10.3z",
      },
    ];

    // ── 面板里显示的东西：一条细标题栏 + 整块 iframe ──
    function 造面板(签) {
      return function 面板(props) {
        var 高 = "100%";
        if (props && typeof props.size === "number" && props.size > 0) {
          高 = props.size + "px";
        }
        return el(
          "div",
          { style: { display: "flex", flexDirection: "column", height: 高, minHeight: 0 } },
          el(
            "div",
            {
              style: {
                flex: "0 0 auto",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 10px",
                borderBottom: "1px solid var(--dsh-border, #262b36)",
                fontSize: "11.5px",
                opacity: 0.85,
              },
            },
            el("span", null, 签.注),
            el(
              "a",
              {
                href: 签.址,
                target: "_blank",
                rel: "noreferrer",
                style: { marginLeft: "auto", textDecoration: "underline" },
                title: "在新窗口打开（iframe 被拦时用这个）",
              },
              "新窗口"
            )
          ),
          el("iframe", {
            src: 签.址,
            title: 签.题,
            style: {
              flex: "1 1 auto",
              width: "100%",
              minHeight: 0,
              border: "0",
              display: "block",
              background: "#12141a",
            },
          })
        );
      };
    }

    function 造图标(签) {
      return function 图标() {
        return el(
          "svg",
          { width: 16, height: 16, viewBox: "0 0 16 16", fill: "currentColor" },
          el("path", { d: 签.图 })
        );
      };
    }

    // ── 挂载 ──
    // 形状逐字照抄 `dsh-infinite-gen-5\client.js` 的 apply（手写插件，真在跑）。
    // ★ 判据：不要凭感觉改回 sidebarRightTabs 那一套。
    function apply(ctx) {
      报信("apply 进来了");
      try {
        if (!ctx || !ctx.slots || typeof ctx.slots.inject !== "function") {
          报信("错-ctx.slots 没有 inject（ctx 的键=" + (ctx ? Object.keys(ctx).join(",") : "空") + "）");
          return;
        }
        var 收尾s = [];

        for (var n = 0; n < 面板们.length; n++) {
          (function (签) {
            // ① 会话顶部那个标签条（IG5 的「逆向工作台」就在这儿 —— 用户说的「上边」）
            try {
              收尾s.push(
                ctx.slots.inject("conversation.view", function () {
                  return ctx.slots.register(
                    {
                      name: "conversation.view",
                      id: 签.号,
                      order: 签.序,
                      label: function () {
                        return 签.题;
                      },
                    },
                    造面板(签)
                  );
                })
              );
            } catch (e) {
              报信("错-顶部标签注册失败 " + 签.题 + "：" + (e && e.message ? e.message : e));
            }

            // ② 侧栏图标
            try {
              收尾s.push(
                ctx.slots.inject("sidebar.panellist", function () {
                  return ctx.slots.register(
                    {
                      name: "sidebar.panellist",
                      id: 签.号,
                      order: 签.序,
                      label: function () {
                        return 签.题;
                      },
                    },
                    造图标(签)
                  );
                })
              );
            } catch (e) {
              报信("错-侧栏图标注册失败 " + 签.题 + "：" + (e && e.message ? e.message : e));
            }

            // ③ 面板本体
            try {
              收尾s.push(
                ctx.slots.inject("main", function () {
                  return ctx.slots.register({ name: "main", key: 签.号 }, 造面板(签));
                })
              );
            } catch (e) {
              报信("错-主区注册失败 " + 签.题 + "：" + (e && e.message ? e.message : e));
            }
          })(面板们[n]);
        }

        报信("注册完了，收尾函数 " + 收尾s.length + " 个");
        exports.__收尾 = 收尾s;
      } catch (e) {
        报信("错-apply 本身炸了：" + (e && e.message ? e.message : e));
        try {
          console.warn("[影匠面板] apply 失败（不影响主界面）", e);
        } catch (e2) {
          /* 无 console 也不能抛 */
        }
      }
    }

    exports.name = PLUGIN_ID;
    exports.inject = inject;
    exports.apply = apply;
    return module.exports;
  },
});
