// 影匠依据面板 —— 浏览器那一半。
//
// 干的事只有一件：往 DSH 右侧栏挂一个「依据」页签，里面嵌
// http://127.0.0.1:8794/ （本机 _依据台.py 起的只读页）。
//
// 数据从哪来：DSH 自己写在会话存档里的 tool/call 记录 —— 我改不了，
// 所以它能当证据。我说「我查过了」，你在这一页能看见我到底开没开那个文件。
//
// ⚠ 这个文件是**裸的客户端产物**，照抄 dsh-free-search/lib/client.js 的形状。
//    整体套在 try/catch 里：万一 DSH 的槽位 API 跟这里写的不一样，
//    最坏情况是这个页签不出现，**不能影响主界面**。

window.__ModuleLoader__.load({
  id: "dsh-yingjiang-panel",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;

    var react = require("react");

    var 台址 = "http://127.0.0.1:8794/";
    var 面板号 = "yingjiang";
    var 标题 = "依据";

    // ── 页签里显示的东西：一条细标题栏 + 整块 iframe ──
    function 面板(props) {
      var 高 = "100%";
      if (props && typeof props.size === "number" && props.size > 0) {
        高 = props.size + "px";
      }
      return react.createElement(
        "div",
        { style: { display: "flex", flexDirection: "column", height: 高, minHeight: 0 } },
        react.createElement(
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
          react.createElement("span", null, "这一轮我读了哪些文件 · 做了哪些动作"),
          react.createElement(
            "a",
            {
              href: 台址,
              target: "_blank",
              rel: "noreferrer",
              style: { marginLeft: "auto", textDecoration: "underline" },
              title: "在新窗口打开（iframe 被拦时用这个）",
            },
            "新窗口"
          )
        ),
        react.createElement("iframe", {
          src: 台址,
          title: 标题,
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
    }

    function 标题元素() {
      return react.createElement("span", null, 标题);
    }

    // ── 挂载 ──
    // 形状照抄 dsh-context 里的 cc()：收好每个 register 还回来的注销函数，
    // 中途失败就把已经挂上的收回去，绝不留半个。
    function apply(ctx) {
      try {
        if (!ctx || typeof ctx.inject !== "function") {
          return;
        }
        ctx.inject(["sidebarRightTabs"], function (i) {
          var 注销s = [];
          var 收 = function (x) {
            if (typeof x === "function") 注销s.push(x);
          };
          try {
            var 页签s = i && i.sidebarRightTabs;
            if (页签s === undefined || typeof 页签s.register !== "function") {
              return;
            }
            收(
              页签s.register({
                id: 面板号,
                kind: 面板号,
                title: function () {
                  return 标题;
                },
                guide: [
                  {
                    order: 60,
                    title: 标题,
                    description: "这一轮读了哪些文件、做了哪些动作（DSH 记的，不是我上报的）",
                  },
                ],
              })
            );

            var 槽 = i.slots;
            if (槽 && typeof 槽.inject === "function" && typeof 槽.register === "function") {
              收(
                槽.inject("sidebar.right.pane.tab", function () {
                  return 槽.register(
                    { name: "sidebar.right.pane.tab", key: 面板号 },
                    function (e) {
                      return react.createElement(面板, Object.assign({}, e, { host: "sidebar" }));
                    }
                  );
                })
              );
              收(
                槽.inject("sidebar.right.pane.tab.title", function () {
                  return 槽.register(
                    { name: "sidebar.right.pane.tab.title", key: 面板号 },
                    标题元素
                  );
                })
              );
            }
            // 挂上了就往控制台写一句 —— 用户在浏览器 F12 里能看见到底挂成没挂成
            try {
              console.info("[影匠依据] 已挂上右侧栏页签：" + 面板号 + " → " + 台址);
            } catch (e4) {
              /* 无 console 也不能抛 */
            }
          } catch (e) {
            for (var k = 0; k < 注销s.length; k++) {
              try {
                注销s[k]();
              } catch (e2) {
                /* 收尾失败也不能抛 */
              }
            }
            try {
              console.warn("[影匠依据] 侧栏注册失败（不影响主界面）", e);
            } catch (e3) {
              /* 无 console 也不能抛 */
            }
            return;
          }
          return function () {
            for (var k = 0; k < 注销s.length; k++) {
              try {
                注销s[k]();
              } catch (e) {
                /* 同上 */
              }
            }
          };
        });
      } catch (e) {
        try {
          console.warn("[影匠依据] apply 失败（不影响主界面）", e);
        } catch (e2) {
          /* 无 console 也不能抛 */
        }
      }
    }

    exports.apply = apply;
    exports.inject = [];
    return module.exports;
  },
});
