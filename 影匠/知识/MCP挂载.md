# 影匠MCP 挂载指南

> 把 `D:\DSHworkspace\影匠\影匠MCP.py` 挂到 DeepSeek Harness 上。
> 全部结论来自本机实测（app.asar 里的 `@deepseek-ai/dsh-mcp-client` v0.2.0-rc.2 的 README + 你现有的 `profiles\desktop\cordis.patch.yml`），不是照抄文档。

---

## 0. 一句话结论

**DSH 的 MCP 配置不在 `settings.yaml`**，而是**每个 server 一行插件补丁**，写进 profile 的 `cordis.patch.yml`。
本机是：

```
D:\DSH\home\profiles\desktop\cordis.patch.yml
```

（DSH Desktop 正在跑的就是 `desktop` 这个 profile —— 实测其 `billion-context` 进程命令行是
`...\profiles\desktop\node_modules\billion-context\dist\index.js start --host 127.0.0.1 --port 18787`。）

---

## 1. 直接粘贴的配置片段

追加到 `D:\DSH\home\profiles\desktop\cordis.patch.yml` **末尾**即可（顶层是 YAML 数组，`- id:` 是数组元素）：

```yaml
# 影匠 —— 本地 AI 影视流水线（stdio MCP 服务器，标准库实现，零第三方依赖）
- id: mcp-yingjiang
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: yingjiang
    transport: stdio
    command: 'D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe'
    args:
      - '-X'
      - 'utf8'
      - 'D:\DSHworkspace\影匠\影匠MCP.py'
    cwd: 'D:\DSHworkspace\影匠'
    env:
      PYTHONIOENCODING: utf-8
      PYTHONUTF8: '1'
    toolCallTimeoutMs: 1800000
    failOnStartupError: false
```

三个**必须这么写**的字段，理由如下（踩过就知道）：

| 字段 | 值 | 为什么 |
|---|---|---|
| `command` | **本机 venv 的 python.exe 绝对路径** | 本机 PATH 里的 `python.exe` 只是 Microsoft Store 的占位 stub，实测直接报 `Python was not found; run without arguments to install from the Microsoft Store...`。**不要**写裸 `python`。 |
| `toolCallTimeoutMs` | `1800000` | DSH 默认 **60,000 ms**（60 秒）。影匠的 `开镜`（出图）与 `让镜动`（出视频）要一直等 ComfyUI 跑完，影匠内部上限就是 1800 秒。**不改这一项，出图必然超时**。 |
| `env.PYTHONUTF8` / `PYTHONIOENCODING` | `1` / `utf-8` | Windows 中文环境下 Python 的 stdio 会退化成 GBK，JSON-RPC 里的中文会变乱码甚至 `UnicodeEncodeError`。显式锁 UTF-8。 |

`args` 里的 `-X utf8` 是同一目的的第二道保险（等效于 `PYTHONUTF8=1`）。

### 字段全表（`@deepseek-ai/dsh-mcp-client` 实际接受的）

| 字段 | 缺省 | 含义 |
|---|---|---|
| `transport` | 必填 | `stdio` 或 `streamable-http`。影匠用 `stdio`。 |
| `serverName` | 必填 | 工具命名空间，**只允许 `[A-Za-z0-9_-]{1,32}`**，同一注册域内唯一。所以这里是 `yingjiang`（拼音），不能写中文。 |
| `command` / `args` / `env` / `cwd` | — | stdio 专用。`env` 会**合并覆盖**在「已擦除的父环境」之上。 |
| `url` / `headers` | — | streamable-http 专用。 |
| `toolCallTimeoutMs` | `60000` | 每次 `tools/call` 的超时。**影匠必须调大。** |
| `maxInstructionBytes` | `32768` | 服务器 instructions 的 UTF-8 字节上限，超了直接拒绝连接。 |
| `failOnStartupError` | `false` | 为 true 时初始连接失败会让插件激活失败。保持 false，影匠起不来不该把 DSH 拖下去。 |
| `reconnect.enabled` | `true` | 断线自动重连。 |
| `reconnect.initialDelayMs` / `maxDelayMs` / `maxAttempts` | `500` / `30000` / `10` | 退避 500ms 起、每次翻倍、封顶 30s；连续失败 10 次后卸载工具并停止重连（重载配置或重启 DSH 可恢复）。 |

---

## 2. 挂载后长什么样

工具以 **`mcp__<serverName>__<原始工具名>`** 注册，所以：

```
mcp__yingjiang__列风格
mcp__yingjiang__列戏
mcp__yingjiang__查进度
mcp__yingjiang__审片
mcp__yingjiang__看镜
mcp__yingjiang__剧本
mcp__yingjiang__立戏
mcp__yingjiang__定角
mcp__yingjiang__开镜
mcp__yingjiang__连镜
mcp__yingjiang__让镜动
```

共 11 个工具。原名就是中文，DSH 侧的名字也是中文 —— 中文在函数名里是合法的，但**最终以 DSH 实际列出的名字为准**；如果某个客户端对非 ASCII 函数名做了有损规范化，DSH 会退化成「原名 + 12 位 SHA-256 十六进制后缀」的稳定形式，不会两个工具撞名。

影匠的 `instructions`（`tools/list` 之前那次 `initialize` 返回的服务器说明）会作为**字面文本**并进系统提示词，所以「先看再动 / 种子锁脸 / 阶段门」那些铁律 AI 一挂上就能看见，不需要额外写 system prompt。

---

## 3. 生效与验证

### 3.1 生效方式

`D:\DSH\home\profiles\desktop\package.json` 里写的是：

```json
"dsh": { "profile": { "patchReload": "live" } }
```

即补丁是 **live 重载**的。实际操作里最稳的两条路：

1. **改完文件后在设置页里改一下任意配置再改回来**（或触发一次 profile 重载），让 DSH 重新读补丁；
2. 拿不准就**重启 DSH Desktop** —— 一定生效，代价只是几十秒。

> 注意：`mcp-client` 文档特别提到「stdio 协商会**先起一个临时探针进程**再起正式进程」。
> 这意味着影匠MCP 必须能承受「被启动 → initialize → 被关掉」而不报错退出 —— 它是的（见交付物 `影匠MCP.py` 的 `main()`：`sys.stdin` EOF 即干净退出，退出码 0）。

### 3.2 验证一：不挂 DSH，先单独喂 JSON-RPC（最快）

```powershell
$py = 'D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'

$init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1.0"}}}'
$list = '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

@($init, $list) -join "`n" | & $py -X utf8 'D:\DSHworkspace\影匠\影匠MCP.py'
```

期望：stdout 上正好两行 JSON，`id:1` 的 `result.serverInfo.name` 是 `影匠`，`id:2` 的 `result.tools` 是 11 个元素。
第一行 `[影匠MCP] 就绪 · 11 个工具 · 影匠目录 D:\DSHworkspace\影匠` 走的是 **stderr**，不污染协议流（stdout 只出协议帧，这是铁律）。

### 3.3 验证二：进 DSH 后确认工具已注册

挂上并生效后，直接问 DSH：

- 「列出你现在能用的影匠工具」→ 应能报出 11 个 `mcp__yingjiang__*`；
- 或者让 AI 干最轻的一步：**「用影匠列一下有哪些风格」** → 应触发 `mcp__yingjiang__列风格`，零成本、不连 ComfyUI，是最好的连通性探针。

`列戏` / `列风格` / `查进度` / `审片` / `看镜` / `剧本(读)` 这 6 个是**只读零成本**的，专门用来验证链路安全；`开镜` / `连镜` / `让镜动` 才会真的烧算力。验证连通性时**只用前一组**。

---

## 4. 权限与提示词

### 4.1 允许清单

MCP 工具名固定，可以直接写进 DSH 的工具允许/拒绝规则（名字稳定，重启、重载都不变）：

```yaml
# 只读组：永远放行
- 'mcp__yingjiang__列风格'
- 'mcp__yingjiang__列戏'
- 'mcp__yingjiang__查进度'
- 'mcp__yingjiang__审片'
- 'mcp__yingjiang__看镜'
- 'mcp__yingjiang__剧本'

# 花钱组：建议每次人工确认
- 'mcp__yingjiang__开镜'
- 'mcp__yingjiang__连镜'
- 'mcp__yingjiang__让镜动'
```

### 4.2 建议追加的提示词

影匠MCP 自己的 `instructions` 已经写全了铁律，通常不用再加。若想更硬地约束「别乱烧算力」，在项目 `AGENTS.md` 里补一句：

```markdown
调用 `mcp__yingjiang__开镜` / `连镜` / `让镜动` 之前，必须先说明要出什么、大约几镜，并取得用户同意。
出图/出片失败时先调 `mcp__yingjiang__查进度` 或 `看镜` 查证，禁止直接重发。
```

---

## 5. 其他客户端

### 5.1 Claude Desktop

`%APPDATA%\Claude\claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "yingjiang": {
      "command": "D:\\Comfy-Desktop\\ComfyUI-Installs\\ComfyUI\\ComfyUI\\.venv\\Scripts\\python.exe",
      "args": ["-X", "utf8", "D:\\DSHworkspace\\影匠\\影匠MCP.py"],
      "cwd": "D:\\DSHworkspace\\影匠",
      "env": { "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1" }
    }
  }
}
```

Claude Desktop 对工具名更保守（要求 `^[a-zA-Z0-9_-]{1,64}$`）。如果它拒绝中文工具名，就在 `影匠MCP.py` 的 `主工具表` / `工具说明书` 附近加一层**别名映射**（把 `立戏` 映射到 `create_play` 之类），
`tools/list` 里发别名字、`tools/call` 时再转回中文键 —— 分发逻辑不用动，因为 `不知道这个工具` 那条分支只查字典。

### 5.2 通用 stdio 客户端

- 传输：**换行分隔的 JSON-RPC 2.0**（NDJSON），一行一帧，**没有 `Content-Length` 头**。
- 支持方法：`initialize` / `notifications/initialized` / `ping` / `tools/list` / `tools/call`。
- 认的协议版本：`2024-11-05`、`2025-03-26`、`2025-06-18`、`2025-11-25`、`2026-07-28`；请求了不认识的就回 `2024-11-05`。
- 任何一帧解析失败只回 `-32700` 并**继续读下一行**，不会因为一行坏数据崩掉整个进程。

---

## 6. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| DSH 起来了但没有任何 `mcp__yingjiang__*` | 初始连接失败；`failOnStartupError: false` 让它静默 | 先用 §3.2 的命令单独跑一遍，看 stderr 的 `[影匠MCP]` 行 |
| 工具在，但一调就超时 | 没改 `toolCallTimeoutMs` | 设成 `1800000` |
| 中文变 `???` 或 `UnicodeEncodeError` | stdio 编码没锁 | 补 `PYTHONUTF8: '1'` + `args: ['-X','utf8']` |
| 报 `Python was not found; run without arguments to install from the Microsoft Store` | `command` 写了裸 `python`，命中了 Store stub | 换绝对路径 |
| 报 `serverName` 相关的加载错误 | 名字不合规 / 同域重名 | `serverName` 只能是 `[A-Za-z0-9_-]{1,32}`，且同域唯一 |
| 服务器 instructions 被拒绝 | 超过 `maxInstructionBytes`（32768） | 缩短 `instructions`，或调大该字段 |
| 改完配置没反应 | 补丁没重载 | 触发一次 profile 重载，或重启 DSH Desktop |

---

## 7. 安全边界（本交付物刻意不碰的东西）

飞彩工作台那套桥里含 `flow-license-guard`、`useAuthHeartbeat`、`device-id`、Ed25519 签名等**授权/许可证链路**，
按任务铁律，本轮分析**遇到即跳过**，`影匠MCP.py` 里**没有任何一行**与授权、许可、设备指纹、心跳、签名相关。

影匠MCP 的权限模型只有两层，且都在明面上：

1. **只读 vs 花钱**：6 个只读工具永不动文件、永不连 ComfyUI；3 个花钱工具（`开镜`/`连镜`/`让镜动`）会真的提交 ComfyUI 任务。
2. **路径**：`让镜动` 只接受本机绝对路径，相对路径直接拒绝并给出建议的绝对路径 —— 避免宿主的 cwd 和影匠的目录对不上时写错地方。
