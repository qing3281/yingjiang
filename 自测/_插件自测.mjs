// _插件自测.mjs —— 在不启动 DSH 的前提下，验证 dsh-yingjiang-panel 的客户端产物。
//
// 干什么：用一个假的 window.__ModuleLoader__ 把 client.js 装进来，
// 再用假的 ctx / slots / sidebarRightTabs 跑一遍 apply()，
// 看它到底注册了什么、失败时会不会抛。
//
// 跑法： node _插件自测.mjs
import fs from "node:fs";
import vm from "node:vm";

const 客 = process.argv[2] ||
  "D:\\DSH\\home\\profiles\\desktop\\node_modules\\dsh-yingjiang-panel\\lib\\client.js";

const 文 = fs.readFileSync(客, "utf8");
let 过 = 0, 败 = 0;
const 说 = (行, 好, 补) => {
  console.log(`   ${好 ? "✓" : "✗"} ${行}${补 ? "   " + 补 : ""}`);
  好 ? 过++ : 败++;
};

// ── 1. 语法 ──────────────────────────────────────────────
let 脚本;
try {
  脚本 = new vm.Script(文, { filename: 客 });
  说("语法能过", true);
} catch (e) {
  说("语法能过", false, String(e.message));
  process.exit(1);
}

// ── 2. 装载：模拟浏览器里的 window.__ModuleLoader__ ────────
let 载入 = null;
const 沙 = {
  window: {
    __ModuleLoader__: {
      load(m) { 载入 = m; },
    },
  },
  console,
};
沙.window.window = 沙.window;
try {
  vm.createContext(沙);
  vm.runInContext(文, 沙);
  说("能装进 __ModuleLoader__", !!载入, 载入 ? `id=${载入.id}` : "load() 没被调用");
} catch (e) {
  说("能装进 __ModuleLoader__", false, String(e.message));
  process.exit(1);
}
说("id 是 dsh-yingjiang-panel", 载入.id === "dsh-yingjiang-panel", 载入.id);

// ── 3. factory：只允许 require("react") ───────────────────
const 元素 = (t, p, ...c) => ({ $$型: t, 参: p, 子: c });
const 假react = { createElement: 元素 };
let 模;
try {
  模 = 载入.factory((名) => {
    if (名 === "react") return 假react;
    throw new Error("factory 要了不该要的模块：" + 名);
  });
  说("factory 跑得起来", true);
} catch (e) {
  说("factory 跑得起来", false, String(e.message));
  process.exit(1);
}
说("导出了 apply", typeof 模.apply === "function", typeof 模.apply);
说("导出了 inject", Array.isArray(模.inject), JSON.stringify(模.inject));

// ── 4. apply：真跑一遍，看注册了什么 ──────────────────────
function 造假ctx(有侧栏 = true) {
  const 记录 = [];
  const 注销s = [];
  const 收尾s = [];
  const 槽 = {
    inject(名, cb) { 记录.push(["slots.inject", 名]); cb(); return () => 注销s.push("slot:" + 名); },
    register(描述, 渲染) {
      if (!描述 || !描述.name) throw new Error("register 少了 name");
      记录.push(["slots.register", 描述.name, 描述.key ?? 描述.id ?? "", typeof 渲染]);
      return () => 注销s.push("reg:" + 描述.name);
    },
  };
  const 页签s = {
    register(o) {
      if (!o || !o.id || !o.kind) throw new Error("sidebarRightTabs.register 少了 id/kind");
      if (typeof o.title !== "function") throw new Error("title 必须是函数");
      记录.push(["sidebarRightTabs.register", o.id, o.kind, typeof o.title()]);
      return () => 注销s.push("tab:" + o.id);
    },
  };
  const ctx = {
    inject(名s, cb) {
      if (!Array.isArray(名s)) throw new Error("ctx.inject 第一个参数要是数组");
      记录.push(["ctx.inject", ...名s]);
      const 服 = { slots: 槽 };
      if (有侧栏) 服.sidebarRightTabs = 页签s;
      const f = cb(服);
      if (typeof f === "function") 收尾s.push(f);
      return () => {};
    },
  };
  return { ctx, 记录, 注销s, 收尾s };
}

let 好 = 0;
try {
  const { ctx, 记录, 注销s, 收尾s } = 造假ctx(true);
  模.apply(ctx);

  const 名s = 记录.map((r) => r.slice(0, 3).join(" · "));
  console.log("\n   [注册轨迹]");
  for (const n of 名s) console.log("      " + n);

  const 有 = (s) => 记录.some((r) => r.join(" ").includes(s));
  说("申请了 sidebarRightTabs", 有("sidebarRightTabs"), "");
  说("挂了右侧栏页签", 记录.some((r) => r[0] === "sidebarRightTabs.register" && r[1] === "yingjiang"));
  说("挂了 pane.tab", 有("sidebar.right.pane.tab"), "");
  说("挂了 pane.tab.title", 有("sidebar.right.pane.tab.title"), "");

  // ── 5. 卸载路径：DSH 关掉这个插件时，三样都得收回去 ──
  说("apply 交出了一个收尾函数", 收尾s.length === 1, `${收尾s.length} 个`);
  if (收尾s.length === 1) {
    收尾s[0]();
    说("★ 收尾后三样都注销了（不留半个）", 注销s.length === 3,
      `注销了 ${注销s.length} 个：${注销s.join(", ")}`);
  }

  // ── 6. 渲染函数真能跑，而且吐出一个 iframe ──
  const 注 = 记录.find((r) => r[0] === "slots.register" && r[1] === "sidebar.right.pane.tab");
  说("pane.tab 的渲染是个函数", 注 && 注[3] === "function", 注 ? 注[3] : "没找到");

  // 真调一次渲染，看它吐出什么
  const 渲 = 记录.find((r) => r[0] === "slots.register" && r[1] === "sidebar.right.pane.tab");
  if (注) {
    const { ctx: c2 } = 造假ctx(true);
    let 渲2 = null;
    const 槽2 = {
      inject: (n, cb) => { cb(); return () => {}; },
      register: (d, r) => { if (d.name === "sidebar.right.pane.tab") 渲2 = r; return () => {}; },
    };
    c2.inject = (ns, cb) => {
      cb({ slots: 槽2, sidebarRightTabs: { register: () => () => {} } });
      return () => {};
    };
    模.apply(c2);
    if (typeof 渲2 === "function") {
      // createElement(组件, props) 返回的是「元素描述」，函数组件还没被调用。
      // 我的假 react 不渲染，所以这里自己把它展开成真正的树。
      const 展开 = (x) => {
        if (!x || typeof x !== "object") return x;
        if (typeof x.$$型 === "function") return 展开(x.$$型(x.参));
        return x;
      };
      const 树 = 展开(渲2({ size: 700 }));
      const 找 = (x, 型) => {
        x = 展开(x);
        if (!x || typeof x !== "object") return false;
        if (x.$$型 === 型) return true;
        return Array.isArray(x.子) && x.子.some((k) => 找(k, 型));
      };
      说("渲染出 iframe（函数组件已展开）", 找(树, "iframe"));
      const 拾 = (x, 型, 收 = []) => {
        x = 展开(x);
        if (!x || typeof x !== "object") return 收;
        if (x.$$型 === 型) 收.push(x);
        if (Array.isArray(x.子)) x.子.forEach((k) => 拾(k, 型, 收));
        return 收;
      };
      const fr = 拾(树, "iframe")[0];
      if (fr) {
        说("iframe 指向 127.0.0.1:8794", String(fr.参.src).includes("127.0.0.1:8794"), fr.参.src);
      } else {
        说("iframe 指向 127.0.0.1:8794", false, "没找到 iframe");
      }
      // 顺带确认「新窗口」那个链接在（iframe 被 CSP 拦时的逃生口）
      说("页面上有「新窗口」逃生链接", 拾(树, "a").length > 0,
        `找到 ${拾(树, "a").length} 个 <a>`);
    } else {
      说("拿到渲染函数", false, "没拿到");
    }
  }
  好 = 1;
} catch (e) {
  说("apply 不抛异常", false, String(e.message));
}

// ── 7. 最要紧的一条：槽位不存在时，绝不能抛 ──
try {
  const { ctx } = 造假ctx(false); // 没有 sidebarRightTabs
  模.apply(ctx);
  说("★ 没有 sidebarRightTabs 时也不抛（主界面安全）", true);
} catch (e) {
  说("★ 没有 sidebarRightTabs 时也不抛（主界面安全）", false, String(e.message));
}

// ── 8. ctx 是垃圾时也不能抛 ──
let 垃圾好 = true;
for (const 烂 of [undefined, null, {}, { inject: 5 }]) {
  try {
    模.apply(烂);
  } catch (e) {
    说(`ctx = ${JSON.stringify(烂)} 时不抛`, false, String(e.message));
    垃圾好 = false;
    break;
  }
}
if (垃圾好) 说("ctx 是垃圾时不抛", true);

console.log(`\n   ${败 === 0 ? "✓ 全过" : "✗ 有失败"}   过 ${过} / 败 ${败}`);
process.exit(败 === 0 ? 0 : 1);
