import sys, os, datetime
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\DSHworkspace\记忆\经验\流程与脚本.md"
前 = os.path.getsize(p)
块 = """

## 2026-10-16 00:45 · ★★ 插件「做完了」但没生效 —— 真根因是它只挂了 1 个页签 + 没人重载

**用户原话（m35724）**：「**记忆台插件，你昨天晚上是怎么给我计划怎么定的目标的呢？
不是应该在今天早上7点就把它完成掉了吗？怎么现在又告诉我还要花这些时间？**」

### 实情
- **插件 10-15 03:04 就造好了**：`D:\\DSHworkspace\\_GitHub\\影匠工作台\\dsh-插件\\dsh-yingjiang-panel\\`
  （`package.json` 692 B + `cordis.patch.yml` 204 B + `lib\\client.js` + `lib\\index.js`），
  06:40 还改过一版。**假宿主自测脚本 `_插件自测.mjs` 也是那时候写的。**
- **它也确实注册进了 profile**：`D:\\DSH\\home\\profiles\\desktop\\package.json` **第 75 行**写着 `"dsh-yingjiang-panel"`，
  包也拷进了 `node_modules\\dsh-yingjiang-panel\\`（4 个文件）。
- **但 client.js 里只挂了一个页签：「依据」→ 8794。** 用户要的是**记忆台**（8792）。所以他打开侧栏看到的
  要么是空的、要么根本不是他要的那个。

### 修法（20 分钟，不是 40–70 分钟）
把 `lib\\client.js` 改成**一个数组驱动多个页签**：
```js
var 页签们 = [
  { 号: "jiyi", 题: "记忆", 址: "http://127.0.0.1:8792/", 序: 50 },
  { 号: "yiju", 题: "依据", 址: "http://127.0.0.1:8794/", 序: 60 },
];
```
循环里对每个页签做三件事：`sidebarRightTabs.register`、`slots.register("sidebar.right.pane.tab")`、
`slots.register("sidebar.right.pane.tab.title")`。**闭包用 IIFE 把 `槽` 和 `签` 裹进去**，
否则循环变量会被后一轮覆盖。

### 判据（可机器验）
```
& $node 'D:\\DSHworkspace\\_GitHub\\影匠工作台\\自测\\_插件自测.mjs'
```
实测 **全过 18 / 败 0**，其中：
- `✓ 挂了右侧栏页签（2 个）   挂了 2 个：jiyi, yiju`
- `✓ ★ 收尾后六样都注销了（不留半个）`（2 页签 × 3 处注册 = 6）
- `✓ 渲染出 iframe（函数组件已展开）` / `✓ iframe 指向 127.0.0.1:8794`
- `✓ ★ 没有 sidebarRightTabs 时也不抛（主界面安全）`

### ★★ 我犯的错（比技术错重要）
**我张口就给了「40–70 分钟、新输入 25 万 token」的预算表，还自估首次成功率 60% ——
而我根本不知道这个插件昨晚就造好了。** 这是 `AGENTS.md` 第 0.2 条
「**能用就用、能抄就抄、能整段搬就整段搬，不许重写**」的直接违反。
**定预算之前先搜一遍「这东西我是不是已经做过」** —— 判据：写任何「新建」计划之前，
先 `Get-ChildItem -Recurse` 搜一遍相关目录名。
"""
open(p, "a", encoding="utf-8").write(块)
print("  ✓ 流程与脚本.md %d → %d B" % (前, os.path.getsize(p)))
