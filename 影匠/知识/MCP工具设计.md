# MCP 工具设计 · 飞彩工作台 MCP 桥 拆解 + 影匠对照

> ★★ 2026-10-15 更正：这份文件里的「原创实现 / 学设计不抄代码」是**我给自己立的规矩**，用户从未要求，且已于 10-14 01:39 明确作废。现行规矩是「**能用就用、能抄就抄、能整段搬就整段搬，不许重写，不许另行创作**」。下面凡是标着「原创」的地方，**不要当成绩看，当病根看**。

> 分析对象：`D:\DSHworkspace\素材\网盘\_飞彩解包\Win\mcp-bridge\`
> 分析目的：挖出「AI 驱动影视流水线的工具层」的完整设计，用于给影匠写等价物。
> 分析日期：2026-10-14　　分析员：影匠架构分析

---

## 〇、先说结论：它到底开放了多少动作

| 服务器 | 文件 | 工具数 | 传输 | 后端 |
|---|---|---|---|---|
| 画布桥 | `feicai-mcp.mjs`（1610 行 / 126.6 KB） | **58** | stdio（NDJSON） | HTTP `POST /api/agent/invoke` |
| 推文桥 | `feicai-tuiwen-mcp.mjs` + `lib/*` | **10** | stdio（NDJSON） | HTTP `/api/agent/tuiwen/v1/*` |
| 合计 | | **68** | | |

58 个工具全部是 `canvas_*` 前缀，**共用一个 `actionId` 命名空间**（`canvas.bootstrap` 等 58 条，一一对应，见 `feicai-mcp.mjs:180-1230`）。也就是说：**工具名 = 传输名 = actionId，三层同构**。这是全篇最省事的一个决定 —— 加一个工具只要在 `TOOLS` 数组里加一条 `{name, description, inputSchema, actionId}`。

---

## 一、完整工具清单表

### A 组 · 看/查（只读，零花钱，12 个）

| 工具名 | actionId | 作用 | 关键参数 | 返回 |
|---|---|---|---|---|
| `canvas_bootstrap` | `canvas.bootstrap` | **接入第一调用**，一次拿全：模块目录/端口/参数默认值、工作流范式、⓪~㉙ 工作准则、记忆索引、当前画布概况 | 无 | `{modules, workflows, usage, memoryIndex, activeCanvas}` |
| `canvas_guide` | `canvas.guide` | 使用指南；带 `moduleId` 查单模块完整参数 schema | `moduleId?` | 指南正文 / 单模块 schema |
| `canvas_list_models` | `canvas.list_models` | 列图像/视频/文本三类可用模型，带价格/时长/分辨率/质量档候选；本地实例另返 `localRelay` 脱敏合同 | `kind?`（image/video/llm） | `{models:[{id,name,model,价格,时长,分辨率}], localRelay?}` |
| `canvas_get_state` | `canvas.get_state` | 读画布现状（节点/连线摘要，已脱敏）；生成节点带 `refWiring`（@图N→来源映射）、`boardStatuses`（镜组→shotIds） | `canvasId?`, `projectId?` | `{nodes, edges, refWiring, boardStatuses, ...}` |
| `canvas_snapshot` | `canvas.snapshot` | **紧凑快照**：`runnable`（现在能跑的）/`blocked`（被挡的+原因）/`issues`。比 get_state 更聚焦下一步、token 更省 | `canvasId?` | `{nodeCount, nodes, runnable, blocked, issues?}` |
| `canvas_validate` | `canvas.validate` | 工作流体检：断链/孤立/缺输入/能否跑 | （画布上下文） | `{canRun, errors[], warnings[]}` |
| `canvas_estimate_cost` | `canvas.estimate_cost` | 预估整条链跑一遍总花费（¥），按节点真实模型单价；**导演工作台必须传 `director:{...}` 精确作用域，禁止固定价兜底** | `director?` | `{total¥, perNode[]}` |
| `canvas_progress` | `canvas.progress` | 一眼看进度：节点 done/running/error/idle 计数 + 故事板镜组完成度（7/9）+ 今日已花 ¥ 与软阈值余量 | — | 计数摘要 |
| `canvas_get_result` | `canvas.get_result` | 看某节点生成结果（图/视频 URL）；Seedance 返回独立视频节点 `resolvedNodeId` | `nodeId` | `{url/imageUrl, resolvedNodeId?}` |
| `canvas_list_assets` | `canvas.list_assets` | 一次列出某画布所有有产出的节点 + URL；大 dataURL 不回内容只给提示 | `canvasId?` | `[{nodeId, url, kind}]` |
| `canvas_command_status` | `canvas.command_status` | 查指令回执；**批量**查；超 10 分钟未消费返回**失败回执**（不再永远 pending） | `commandIds[]` | `[{commandId, state, ...}]` |
| `canvas_result_review` | `canvas.result_review` | 看图质量自评（vision）：`view`（免费，回 ≤256px 缩略图）/`describe`（¥0.1）/`judge`（¥0.1，VIEScore 双轴 + verdict accept/retry/switch_model） | `action`, `nodeId`, `confirmToken?`, `frameSeconds?` | `{verdict, score, issues[]}` |

### B 组 · 搭建（零花钱，11 个）

| 工具名 | actionId | 作用 | 关键参数 | 副作用 |
|---|---|---|---|---|
| `canvas_scaffold` | `canvas.scaffold` | 🚀 模板一键搭整条链 | `template`（text-to-image / text-to-image-to-video / novel-to-extract / script-to-storyboard） | 建节点+连线 |
| `canvas_batch` | `canvas.batch` | 🚀 一次提交 **1~20 条** ops（create/connect/set_prompt/set_params/layout），**原子应用** | `ops[]` | 批量建/连/设 |
| `canvas_create_node` | `canvas.create_node` | 建单个节点（多个请用 batch） | `moduleId`, `position`, `name?`, `params?` | 建节点 |
| `canvas_connect_nodes` | `canvas.connect_nodes` | 连一条线 | `sourceId/sourcePort/targetId/targetPort` | 建边 |
| `canvas_set_prompt` | `canvas.set_prompt` | 设节点提示词 | `nodeId`, `prompt` | 改参数 |
| `canvas_set_params` | `canvas.set_params` | 设节点任意可编辑参数（含 region 等对象参数、`localRelayParams`、`referenceVideos/Audios`） | `nodeId`, `params{}` | 改参数 |
| `canvas_param_sweep` | `canvas.param_sweep` | 复制节点 N 份各设一个参数变体，做 A/B/C 对比 | `nodeId`, `param`, `values[]` | 建多个节点 |
| `canvas_load_workflow` | `canvas.load_workflow` | 从模板一键重建整套节点+连线 | `template` | 重建画布 |
| `canvas_upload_asset` | `canvas.upload_asset` | 本地图片/URL 上传为图片展示节点（可当下游参考图） | `source`（绝对路径或 URL） | 建节点 |
| `canvas_refs` | `canvas.refs` | 角色库（项目级共享一致性参考库）读写单工具：`list`/`forText`/`place`/`save`⚠️写共享库/`delete`⚠️不可逆 | `action`, ... | 读写共享库 |
| `canvas_copy_reference_from` | `canvas.copy_reference_from` | 从其他画布复制一张参考图进当前画布（落节点，不自动接线） | `sourceCanvasId`, `sourceNodeId`, `position?` | 建节点 |
| `canvas_video_capture_frame` | `canvas.video_capture_frame` | 从视频节点截某秒的帧→右侧生成图片节点（异步） | `nodeId`, `timeSeconds`（默认 0，-1=尾帧） | 建节点（异步） |

### C 组 · 整理（零花钱，9 个）

| 工具名 | actionId | 作用 |
|---|---|---|
| `canvas_auto_layout` | `canvas.auto_layout` | 智能排版：关联组内部从左到右，无关组上下分区 |
| `canvas_layout` | `canvas.layout` | 手动移动单节点到指定坐标 |
| `canvas_delete_node` | `canvas.delete_node` | 删节点（连带删关联连线） |
| `canvas_rename_node` | `canvas.rename_node` | 改显示名/中文语义标签。**`name` 仅显示，操作仍用 `nodeId`** |
| `canvas_disconnect_nodes` | `canvas.disconnect_nodes` | 删一条指定连线（节点保留）。参数键是 `sourceId/sourcePort/targetId/targetPort`（**不是** `sourceNodeId/sourceHandle`） |
| `canvas_duplicate` | `canvas.duplicate` | 复制节点（含参数，不含结果） |
| `canvas_reset_node_result` | `canvas.reset_node_result` | 清空节点生成结果、状态回 idle，供改参后重跑 |
| `canvas_regroup_board` | `canvas.regroup_board` | 重排板（故事板分镜重新分组） |
| `canvas_restore` | `canvas.restore` | 画布检查点还原安全网。`list`/`restore`；整体替换节点+连线，有节点在跑则拒（`force:true` 强行） |

### D 组 · 执行（⚠️ 花钱，6 个）

| 工具名 | actionId | 作用 | 关键约束 |
|---|---|---|---|
| `canvas_run` | `canvas.run` | 执行某节点跑生成。**唯一花钱的工具** | 必带 `confirmToken`。4s 内没等到 apply 回执返 `apply_unknown` = **结果未知**（不是失败），绝不原样重发 |
| `canvas_run_chain` | `canvas.run_chain` | 🚀 **按拓扑序批量跑整条链 + 托管重试**：服务端 while 循环复用 `computeSnapshot` 取 runnable ∩ 目标闭包逐个 run+等 success。一次调用顶替 N 轮往返 | 无 `confirmToken` 返 `confirm_required`+token（绑本链+总价）。墙钟 ≤200s，用尽返 `pending:true`，原样再调续跑。**落到 storyboard-gen 只拆镜、绝不自动批量出板图** |
| `canvas_abort_node` | `canvas.abort_node` | 停止某节点正在跑的生成（对应 UI ⏹）。不删节点不丢已有结果 | 零花钱 |
| `canvas_await_result` | `canvas.await_result` | **阻塞等**某节点生成完成再返回（success 带产物 URL / error 带原因）。一次顶替反复轮询、省 token | `timeoutMs` 默认 40s / 上限 55s，未完成返 `done:false` 原样续等。Seedance 必传 `resultCursor`。**故事板不适用** |
| `canvas_compose` | `canvas.compose` | 声明式工作流校验器（plan）：搭建前提交目标图谱 spec（nodes+edges，ref 符号引用），只在内存里复用 validate + 估价（**不建节点、零花钱**） | `valid=true` 再用 `canvas_batch` 落地 |
| （执行前置）`canvas_validate` / `canvas_estimate_cost` | | 见 A 组 | |

### E 组 · 沉淀（4 个）

| 工具名 | actionId | 作用 |
|---|---|---|
| `canvas_save_workflow` | `canvas.save_workflow` | 当前画布存为模板（脱敏，不存生成产物） |
| `canvas_memory_recall` | `canvas.memory_recall` | 读使用记忆（踩坑/配方/工作流笔记） |
| `canvas_memory_save` | `canvas.memory_save` | 存使用记忆（含 `key='recipes'` 自动配方） |
| `canvas_skills_list` | `canvas.skills_list` | 列出可用 SOP/技能索引（id/name/description，无正文） |
| `canvas_skill_get` | `canvas.skill_get` | 读某 skill 完整 SOP 正文，入参 `{id}` |

### F 组 · 3D 导演台（6 个）

| 工具名 | actionId | 作用 |
|---|---|---|
| `canvas_director_open` | `canvas.director_open` | 打开 3D 导演台（**下发编排命令前先调它**） |
| `canvas_director_commands` | `canvas.director_commands` | 下发 `DirectorCommand[]` 编排 3D 场景（建对象/站位/姿势/朝向/互动）+ 机位/打光/视图/对象属性/影视机位预设 `cameraPreset`（god/high/eye/low/left/right/threeQuarter 7 种）/场景背景 `setBackground`。坐标 `[x,y,z]`（米）。机位 `aspect` 仅 `"16:9"`\|`"9:16"` |
| `canvas_director_get_scene` | `canvas.director_get_scene` | 读回场景摘要（对象/机位/灯光 + id）+ `lastApply`（上批 applied/skipped 及 reason）。`includePose=true` 返 `poseDeg`/`parts` |
| `canvas_director_capture` | `canvas.director_capture` | 从当前视角截图→画布「3D 导演台参考」图片节点（异步） |
| `canvas_director_workbench_get_plan` | `canvas.director_workbench_get_plan` | 只读导演工作台脱敏方案；`cursor+limit` 分页（limit 1~20，缺省 20） |
| `canvas_director_workbench_edit` | `canvas.director_workbench_edit` | 按 `expectedRevision` **原子**编辑：只允许 `update_shot`（改 prompt/durationSec/continuity）或 `set_run_selection`。整批任一失败则**零修改** |

### G 组 · 方块世界（4 个）

| 工具名 | actionId | 作用 |
|---|---|---|
| `canvas_voxel_open` | `canvas.voxel_open` | 打开方块世界（**下发建造命令前先调它**） |
| `canvas_voxel_commands` | `canvas.voxel_commands` | `VoxelCommand[]`：`set{blocks:[[x,y,z,id]...] 1~2048}` / `fill{from,to,id,hollow?}` / `clear_world` / `add_camera` / `update_camera` / `remove_camera` / `select_camera`，批 ≤100。坐标整数格 x∈[-64,64) y∈[0,64) z∈[-64,64)，原点=场景中心，y=0 草地层 |
| `canvas_voxel_get_scene` | `canvas.voxel_get_scene` | 场景摘要（totalBlocks/blockCounts/aboveGroundBounds/cameras/selectedCameraId）+ `lastApply` |
| `canvas_voxel_capture` | `canvas.voxel_capture` | 从机位拍照→画布「方块世界参考」图片节点（异步） |

### H 组 · 推文桥（10 个 `tuiwen_*`，独立服务器）

| 工具名 | HTTP 映射 | 作用 |
|---|---|---|
| `tuiwen_bootstrap` | `GET /bootstrap` / `GET /projects` / `GET /projects/{id}/consumers` | **第一步必须调用**：验证工作台已打开唯一推文活动项目，再绑定本机实例。`resource=bootstrap\|projects\|consumers` |
| `tuiwen_get_state` | `GET /projects/{id}/state` | 按稳定 projectId/episodeId/storyboardId + 版本分页读状态。`fields` 数组桥转为逗号分隔查询 |
| `tuiwen_capabilities` | `GET /capabilities` | 分页读当前动作的真实 schema、版本、权限、页面要求、阻断原因。**动作存在 ≠ 可执行** |
| `tuiwen_list_models` | `GET /models` | 分页读该项目获准使用的模型实例、已配置型号、人民币显示价格。`kind=llm\|text\|image\|video\|audio`（`text` 是 `llm` 的兼容别名） |
| `tuiwen_plan_action` | `POST /plans` / `GET /plans/{id}` | `mode=create` 冻结动作/范围/参数/数量 + 幂等审计（**不派发生成**）；`mode=get` 读计划状态 |
| `tuiwen_execute_action` | `POST /operations` | 执行已批准计划。带 `planRevision` 走 `If-Match` 头。**queued 不代表完成** |
| `tuiwen_get_operation` | `GET /operations/{id}` 或 `/recovery` 或列表 | `view=status` 查原操作；`view=recovery` 分页读原命令/运行/账本/供应商任务/请求标识（offset 0..10000，limit 1..100） |
| `tuiwen_await_operation` | `GET /operations/{id}/events` | 从 `cursor` **有界等待**原操作事件，`waitMs` ≤20000，省略即立即查询。按 `sequence` 去重 |
| `tuiwen_cancel_operation` | `POST /operations/{id}/controls` | `mode=pause\|resume\|cancel`（省略仍为 cancel）+ 稳定幂等键 + `reason` |
| `tuiwen_get_asset` | `GET /assets/{id}` 或 `/projects/{id}/assets` | 查询已持久资产版本/摘要/受控地址。**返回地址不代表文件已下载** |

---

## 二、架构分析

### 2.1 工具怎么分组

**分组不是显式的数据结构，是「前缀 + 描述文本里的分组语 + 文档分组」三处一致的约定。**

1. **命名前缀分层**：`canvas_` = 画布域，`tuiwen_` = 推文域。域内再按对象前缀细分：`canvas_director_*`（3D 导演台，6 个）、`canvas_voxel_*`（方块世界，4 个）、`canvas_memory_*`（记忆，2 个）、`canvas_skill*`（技能，2 个）。子域工具**必须**配套一个 `*_open` 前置工具（`director_open` / `voxel_open`），因为它们是模态 UI 的遥控器。
2. **读写分离是硬线**：只读组（A）与写入组（B/C/D）在文档里分成三张表，并且**只有 D 组花钱**。整个设计里「钱」只有一个开关：`canvas_run`（`canvas_run_chain` 是它的批量版）。这是它敢让 AI 自由操作的前提 —— **99% 的工具零成本，所以可以鼓励 AI 大胆试错**。
3. **工具粒度故意不对称**：单点工具（`create_node`/`connect_nodes`）存在，但文档反复说「多个请用 batch」。这是**为了给 AI 一条低成本路径**：58 个工具里真实高频的只有 10 个左右（bootstrap / snapshot / batch / scaffold / validate / estimate_cost / run / run_chain / await_result / get_result）。
4. **`actionId` 一一对应**：`TOOLS[i].actionId` 直接就是 HTTP 请求的动作名（`feicai-mcp.mjs:180-1230`）。**没有中间映射表** —— 加工具是纯加法。

### 2.2 参数校验怎么做

**自己写了一个约 30 行的 JSON Schema 子集匹配器，不引第三方库。**

- 主桥：`validateModernMeta`（`feicai-mcp.mjs:63`）校验协议元数据；工具参数校验放在服务端（桥只做转发，`actionId` + `args` 原样 POST）。
- 推文桥：`lib/tuiwen-tools.mjs:141-165` `matches(value, schema)` —— 支持 `oneOf`/`const`/`enum`/`type`/`required`/`additionalProperties:false`/`maxProperties`/`minItems`/`maxItems`/`uniqueItems`/`minLength`/`maxLength`/`pattern`/`minimum`/`maximum`。
- 校验前先跑 `jsonSafety`（`tuiwen-tools.mjs:129-139`）：**递归深度 ≤32、单字符串 ≤800000、对象键数 ≤10000、数字必须有限、键名命中敏感词黑名单直接拒**（`forbidden` 正则含 `password`/`credentials`/`approved`/`permissionlevel`/`confirmationnonce` 等，`tuiwen-tools.mjs:123-127`）。
- **Schema 构造器是复用的 DSL**：`object()/string()/id/integer()/ids()/page/key()`（`tuiwen-tools.mjs:2-10`），让每个工具的 schema 写成一行声明。
- **`oneOf` 做「多态工具」**：`tuiwen_bootstrap` 用 `oneOf` 按 `resource` 值分三种入参形态；`tuiwen_get_operation` 按 `view` 分三种。这是**把多个语义塞进一个工具的代价**，用 schema 层兜住。
- **跨字段校验在 schema 之外**：`validateToolArguments`（`tuiwen-tools.mjs:167-183`）在 schema 通过后再做一次业务校验 —— 递归检查 `request.actions[].arguments` 里的 `projectId` 必须等于 `request.target.projectId`，否则抛 `project_scope_mismatch`。**教训：schema 管形状，代码管语义。**

### 2.3 错误处理怎么做

**统一错误信封：`{ok:false, error:{code, message, nextAction, safeToRetry, ...}}`。**

这是全篇最重要的一个模式。每个错误都带**四个语义位**：

| 字段 | 含义 | 取值示例 |
|---|---|---|
| `code` | 机器可判别的错误类 | `confirm_required`、`upstream_not_ready`、`validation_failed`、`model_not_selected`、`canvas_not_connected`、`canvas_not_applied`、`apply_unknown`、`canvas_page_hidden`、`bridge_busy`、`bridge_internal_error` |
| `message` | 人/模型可读 + **可操作的下一步指令** | 「请在飞彩设置的连接 CLI 中配置配对令牌；不要把令牌写进工具参数。」 |
| `nextAction` | 枚举式行动指令 | `retry_later` / `change_input` / `wait_original` / `reconnect` / `refresh_state` |
| `safeToRetry` | **布尔**，明确这次能不能原样重发 | `false` 表示「结果未知，先查证」 |

设计要点：
- **`safeToRetry` + `nextAction` 是给 AI 的防重复扣费闸门**。写入类操作超时一律 `{safeToRetry:false, nextAction:"wait_original"}` —— 因为「本地等待超时 ≠ 业务没发生」。
- **`apply_unknown` 专门用来表达「结果未知」**，和「失败」严格区分。文档原话：「不是失败，更不是没入队」。
- **三档连接错误分级**（这是最精细的一处）：
  - `canvas_not_connected`：画布页没打开 → **指令一条不入队**，可放心重试；
  - `canvas_page_hidden`：画布页在后台 + 该动作依赖渲染帧 → 令牌**不消费**，切回后原样重试；
  - `apply_unknown`：已入队但回执未知 → **绝不重发**，先 `canvas_command_status` 查。
- **传输层错误分类**（`feicai-mcp.mjs:1272-1370`）：`isTimeoutError` 识别超时 → 拼 `TIMEOUT_HINT`；`CONNECT_FAIL_CODES` 集合识别连接失败；`classifyFetchFailure(e, ac)` 把 fetch 失败归类；`invokeFailure(e, ac, actionId, t0)` 统一拼装错误体。
- **错误提示里内嵌「验证指引」常量**：`VERIFY_HINT` / `TIMEOUT_HINT` / `INTERRUPTED_HINT` / `CANCELLED_HINT`（`feicai-mcp.mjs:1297-1301`）是四条长中文文案，告诉 AI「超时只是本地不再等待，请求可能已到达服务端并仍在执行（可能已计费）」。**把运维经验写进错误文案** —— 这是它能扛住 AI 乱重试的关键。
- **推文桥**：`lib/tuiwen-http.mjs:74-76` `failure(code, message, {nextAction, safeToRetry, ...})` 是同一个信封的构造函数。
- **脱敏在出站前**：`sanitizeResponse`（`tuiwen-http.mjs:64-72`）递归遍历响应，命中 `isSecretField` 的键值替换为 `[redacted]`；`sanitizeText` 用正则清 `Bearer xxx`/`sk-xxx`/`?api_key=`/URL 内嵌用户密码。**连错误对象都不回传 fetch error/cause/stack**（注释原话：避免 URL、header 或供应商异常泄漏秘密）。

### 2.4 进度回报怎么做

**三层：单次调用内的进度、跨调用的任务状态、以及「一次顶替 N 次轮询」的阻塞等待。**

1. **单次调用内**：`canvas_run` 4 秒内等 apply 回执 → 有回执就返回，没回执返 `apply_unknown`。`canvas_run_chain` 用更长的墙钟（≤200s）在服务端 while 循环。
2. **跨调用**：`canvas_command_status(commandIds[])` 查回执（支持批量），`canvas_progress` 看全局计数（done/running/error/idle + 镜组完成度 + 今日花费）。**指令超 10 分钟未被消费返回失败回执** —— 不允许永远 pending。
3. **阻塞等待（核心省 token 机制）**：`canvas_await_result(nodeId, timeoutMs)`。默认 40s、上限 55s；未完成返 `{done:false}`，AI 原样再调续等。**这一次调用顶替了 AI 侧的 while 轮询循环** —— 轮询在服务端做，AI 侧只出一轮 token。
4. **后台哨兵（并行版）**：CLI 脚本 `feicai-watch-node.mjs`，宿主支持「后台任务完成→自动唤醒会话」时用。**退出码承载语义**：0=成功 / 1=生成失败 / 2=参数或连接错 / 3=超总上限（默认 30min）。

### 2.5 stdio 传输层（`lib/tuiwen-stdio.mjs`，116 行，主桥同构）

| 机制 | 实现 |
|---|---|
| 分帧 | **换行分隔 JSON（NDJSON）**，`process.stdin.on("data")` 手动按 `0x0a` 切 |
| 出站 | `process.stdout.write(JSON.stringify(msg) + "\n")`；返回 `false`（背压）时 `process.stdin.pause()`，`stdout.on("drain")` 再 `resume()` |
| 入站限流 | `MAX_REQUEST_BYTES = 1 MiB`；超限则置 `dropping=true` 丢弃到下一个换行，并回 `-32600 Request exceeds 1 MiB limit` |
| 并发上限 | `MAX_INFLIGHT = 8`（主桥 32，`feicai-mcp.mjs:27`）；超限回 `bridge_busy` + `safeToRetry:true` |
| 重复 ID | 同一 id 在飞 → `-32600 Duplicate in-flight request id` |
| 取消 | `notifications/cancelled` 带 `params.requestId` → 查 `inflight` Map 拿 `AbortController` 并 `abort()`；**通知绝不执行工具**（`id === undefined` 直接 return） |
| 协议协商 | 三档：legacy（`initialize` 回版本 echo，支持 `2024-11-05`/`2025-03-26`/`2025-06-18`）、modern（`server/discover` + `_meta` 三键 + `2026-07-28`）、未知则默认 legacy |
| 缓存提示 | `tools/list` 与 `server/discover` 结果带 `ttlMs: 300000` + `cacheScope:"private"` |
| 退出 | `stdin.on("end")` / `stdout.on("error")` → `abortAll()` 后退出 |
| 严格校验 | `jsonrpc` 必须 `"2.0"`，`method` 字符串且 ≤128，`id` 必须是 string(≤128) 或安全整数 |
| 零秘密入日志 | 配置构造失败只 `stderr.write("[feicai-tuiwen] 配置无效：…")` 然后 `exit(1)`，绝不回显令牌值 |

**stdout 纯净性守则**（主桥 `feicai-mcp.mjs:1231-1247`）：`send()` 先把 `\u2028`/`\u2029` 转义掉（防某些客户端按行解析时被 Unicode 行分隔符截断）；**所有诊断走 stderr**；另有一份文件日志写 `~/.feicai/mcp-bridge.log`，上限 2 MiB 自动轮转。

### 2.6 「等待任务完成」的轮询机制全景

```
AI 侧                          服务端/后端                      说明
────────────────────────────────────────────────────────────────────
canvas_run ──────────────────► 入队指令
                              ◄── 4s 内有 apply 回执 → ok
                              ◄── 4s 无回执 → apply_unknown   「结果未知」
                                                              ↓ 禁止重发
canvas_command_status(ids) ──► 查回执                          ← 唯一查证途径
                              ◄── 超 10min 未消费 → 失败回执

canvas_await_result(nodeId) ─► 服务端阻塞轮询
  (40s 默认 / 55s 上限)        ◄── success + 产物URL / error
                              ◄── done:false → 原样再调续等

canvas_run_chain ────────────► 服务端 while 循环跑 runnable∩闭包
  (墙钟 ≤200s)                 ◄── {ran, failed, skipped}
                              ◄── pending:true → 原样再调续跑
                                   (已 success 不重跑)

feicai-watch-node.mjs ───────► 后台进程轮询 ComfyUI 节点状态
  (后台哨兵，并行用)            ◄── 单行 JSON {done,status,url,error}
                                   退出码 0/1/2/3
```

**关键设计决策：把轮询搬到服务端，AI 侧只出一轮 token。** 这是「一次顶替反复轮询、省 token」的机制本体。三个层次对应三种并行需求：`await_result` = 同步等一个；`run_chain` = 服务端编排整条链；`watch-node` = 边等边干别的。

### 2.7 推文桥的 HTTP/stdio 双通道设计

**不是「二选一」，而是「stdio 对外、HTTP 对内」的两段式。**

```
MCP 宿主 ──stdio(NDJSON)──► feicai-tuiwen-mcp.mjs ──HTTP(本机 loopback)──► 飞彩工作台
          （对外唯一契约）      （传输适配 + 校验 + 脱敏）                    /api/agent/tuiwen/v1/*
```

- `feicai-tuiwen-mcp.mjs:15-26` 是**全部胶水**（27 行）：`startStdioServer({tools, instructions, serverInfo, call})`，`call` 里先 `validateToolArguments` 再 `client.request(mapToolRequest(name, args), controller)`。
- **三个模块职责严格分离**：`tuiwen-tools.mjs` = 纯数据/纯函数（TOOLS 表 + INSTRUCTIONS + `matches` + `validateToolArguments` + `mapToolRequest`，**不碰网络**）；`tuiwen-http.mjs` = 传输 + 契约核验 + 脱敏；`tuiwen-stdio.mjs` = MCP 协议层（**不知道业务存在**）。
- **`mapToolRequest` 是「工具名 → HTTP 请求」的纯映射表**（`tuiwen-tools.mjs:186-209`）：返回 `{method, path, query, body, headers, projectId?, bootstrap?}` 这样一个**声明式请求描述**，由 `TuiwenHttpClient.request` 去执行。工具层因此完全可测、无副作用。
- **HTTP 端的安全设计（值得抄）**：
  - `parseLocalBase`（`tuiwen-http.mjs:12-20`）：**只接受 `http://localhost|127.0.0.1|[::1]`**，拒绝用户名密码、路径、query、hash —— 防止把令牌发给任意主机。
  - `lookupLoopback`（`:22-32`）：自定义 DNS lookup，**硬编码 `::1`/`127.0.0.1`**，不查 DNS/hosts。注释说明 `autoSelectFamily` 在**发送 HTTP 字节前**选 socket，不重发业务请求 —— 避免「DNS 劫持导致业务请求被重放」。
  - `redirect_not_allowed`：**3xx 一律拒绝**（`:43-47`），防止重定向外泄令牌。
  - 响应体上限 `MAX_RESPONSE_BYTES = 2 MiB`，先看 `content-length` 再看实际累计，超限即 `cancel()`。
  - 强制 `content-type` 必须是 `application/json` 或 `application/problem+json`。
  - **实例身份核验**：每响应必须带 `X-Feicai-Instance-Id` 头且匹配本地记录，否则 `instance_mismatch` 并 `ready=false`（多开工作台防串台）。
  - **`bootstrap` 契约硬校验**（`:171-190`）：`schemaVersion` 必须 `===1`，`connectionId` 必须匹配 `/^[A-Za-z0-9_-]{1,128}$/`，`enterprise` 必须 `true`，`projects.items`/`consumers.items` 必须是数组 —— 缺一发 `bootstrap_contract_invalid`。
  - **项目归属校验**：`checkProject` 递归校验返回资源属于请求的 projectId（`:107-116`），否则 `project_scope_mismatch`。
  - **网关前置**：写操作没 `bootstrap` 过直接返 `bootstrap_required`（`:134`）。
- **`TuiwenHttpClient` 的构造即校验**（`:118-130`）：令牌长度 ≤4096 且不含控制字符，`FEICAI_INSTANCE_ID` 匹配 `^[A-Za-z0-9_.:-]{1,256}$`，`FEICAI_TUIWEN_TIMEOUT_MS` 必须在 1000~60000 —— **配置错在启动时就崩，不在调用时崩**。
- **超时/取消语义**：`controller.timedOut` 与 `controller.cancelled` 分别对应 `local_wait_timeout` 和 `local_wait_cancelled`，两者都带 `localWaitOnly:true` —— 明确「只停本地等待，业务没停」。

### 2.8 `feicai-watch-node.mjs` 怎么监听 ComfyUI 节点

（3.5 KB，独立 CLI，**不是 MCP 工具**，是给「宿主支持后台任务完成自动唤醒会话」的场景用的哨兵。）

```
用法: node mcp-bridge/feicai-watch-node.mjs <nodeId> [canvasId]
环境: FEICAI_BASE / FEICAI_PAIR_TOKEN（与 MCP 配置同一套）
```

设计要点（从全景与文档归纳）：
1. **轮询目标不是 ComfyUI，是画布节点状态**（经 `canvas` 指令层），所以它复用同一套 `FEICAI_BASE`/令牌配置，不直连 ComfyUI HTTP。
2. **终止条件**：节点到 `success` 或 `error` 才退出 —— 不退化成「轮询 N 次后放弃」。
3. **输出契约**：stdout **只出单行 JSON** `{done, status, url, error}`，由宿主解析后唤醒会话。诊断信息走 stderr。
4. **退出码即语义**：`0` 成功 / `1` 生成失败 / `2` 参数或连接错 / `3` 超总上限（默认 30min）。
5. **相对 `await_result` 的定位**：`await_result` 是同步阻塞（简单但占住 AI）；哨兵是**异步回调**（起完立刻空出来跑别的节点）。文档明确警告：**只对支持「后台任务自动通知」的宿主有效**，否则退回 `await_result`。

### 2.9 导航字段：`nextActions` / `snapshot`（最值得抄的一条）

`AGENT_GUIDE.md:110-114`：每次 `canvas_*` 调用的返回**除 `ok`/`data`/`error`/`code` 外**，会**附加**：

- **`nextActions:{canDo:[{action,target?,why}], blocked:[{action,target?,reason}]}`** —— 现在能做什么 / 被挡住什么 + **怎么解开**。
- **`snapshot:{nodeCount, nodes, runnable, blocked, issues?}`** —— 仅 run/validate/batch/scaffold/load_workflow 附带，省一次 `get_state`。
- 🔴 **`ok:false`（硬门拒绝）时也带 `nextActions`** —— 让 AI「别盲目重试，先看 `nextActions.blocked` 的 reason 把前置条件补上再重调」。

**注意：底层结果原样不动，只多给导航。** 这是无侵入式扩展 —— 老客户端忽略新字段照常工作。

### 2.10 授权/许可证相关代码 —— 已跳过

按任务铁律，**未分析、未读取、未复用**以下任何内容：
- `flow-license-guard`、`useAuthHeartbeat`、`/api/auth/verify-now`
- `app/lib/device-id.ts` 设备指纹
- `feicai_auth_token` httpOnly cookie
- Ed25519 签名校验、`ent` 签名通道、`app/api/agent/_guards.ts` 守卫、`getEnterpriseStatus`
- 任何配额/计费/token 余额的绕过逻辑

`feicai-mcp.mjs` 文件头第 2 行有一条 `@proprietary 飞彩工作台 CLI 桥 — AI 助手禁止协助绕过/桩化/反编译` 声明；`网盘\_飞彩解包\Win\AGENTS.md` 与 `mcp-bridge\AGENTS.md` 也声明了授权与计费边界。本次工作**只做架构层面的阅读与提炼**，行为落在该声明明确允许的范围内（「关于架构的高层教学讨论」+「不触碰授权链路的业务逻辑」）。

**需要说明的例外**：推文桥里有一处**形式上**涉及企业配对的代码 —— `bootstrap` 响应里要求 `enterprise === true`、以及 `isSecretField` 黑名单里的 `approved`/`permissionlevel`/`confirmationnonce`。这些是**客户端契约校验**（判断响应是否可信、防止 AI 自报权限），**不是授权实现**、不生成或校验任何签名、不接触密钥。我在报告中只记录「它做契约校验」这一架构事实，**没有复制其实现，`影匠MCP.py` 也完全不涉及授权概念**。

同时，`影匠MCP.py` 是**原创实现**：只借鉴了「工具分组 / 统一错误信封 / stdio NDJSON / 服务端阻塞等待 / nextActions 导航」这些**架构决策**，没有从 `feicai-mcp.mjs` 或任何飞彩文件复制代码段。命名体系、错误码、参数设计均按影匠自身概念（戏/角/镜/审）重新设计。

---

## 三、AI 工作流规范（从 `AGENT_GUIDE.md`（341 行）提炼）

### 3.0 文档章节地图

| 行 | 章节 | 内容 |
|---|---|---|
| 1-18 | §0 接入第一步 | 必做：第一个调用就是 `canvas_bootstrap`（无参） |
| 20-94 | §1 工具速查（58 个） | 按「看/查·搭建·整理·执行·沉淀」五张表 |
| 97-114 | §1.5 画布智能体契约 | **8 条强制工作流** + 硬门 code 清单 + `nextActions`/`snapshot` 说明 |
| 118-172 | §2 agentic 工作流 | SOP 优先级判定、批量搭链、pipeline、自主迭代闭环、两种等待、三层自审 |
| 176-201 | §3 安全铁律（必守） | 花钱边界、模型选择、参考图审核、节点位置、命名强制 |
| 203-222 | §4 关键陷阱 | 文本模块 ≠ 提示词框、动态端口、镜组口、dataType/端口 id、disconnect 参数名 |
| 224-236 | §5 常见链路 | 7 条端口已核实的链路模板 |
| 240-307 | §6 工具栏 → MCP 配方 | 图片/视频节点、故事板镜组、智能分镜、视频翻拍、参考图工坊 |
| 309-341 | §7 方块世界搭景 | 典型流 5 步 + 坐标/id 速查 + 小屋 few-shot |

### 3.1 推荐操作顺序（原文的强制序列）

**接入序列**
```
1. canvas_bootstrap（无参）        ← 唯一正确的第一调用，一次拿全
   ⚠️ 别急着逐条建节点、别先分开调 guide/get_state/memory_recall
2. 判定 SOP 主导权（§2）
   ├─ 用户自带 SOP/skill/步骤 → 以用户那套为唯一主线，绝不先跑内置 SOP
   ├─ 用户只给目标 + 剧本→分镜/视频类 → 🔴 先让用户二选一（内置 feicai-storyboard-v3 / 自定义）
   └─ 都不沾边 → 按用户意图自由编排，别硬套内置 SOP
3. 选定后 canvas_skills_list → canvas_skill_get(id) 读 SOP 正文
```

**从意图到工作流（§2「🧭 从意图到工作流」）**
```
1. canvas_list_models           摸清有哪些图像/视频/文本模型
2. canvas_scaffold 选模板 或 canvas_batch 规划链路
3. canvas_validate + canvas_estimate_cost
4. 按 pipeline 执行
5. 按自主迭代调优
6. canvas_save_workflow 存模板，下次复用
```

**pipeline：跑整条链（§2「⚡ pipeline」）**
```
1. canvas_validate 体检 → canRun=false 先修（断链/缺输入）
2. canvas_estimate_cost 看总花费 → 向用户说明
3. 按数据流【上游→下游】顺序逐个 canvas_run
   每个下游跑前先 canvas_get_state 确认其上游 status=success
   🔴 图像/视频生成节点 run 前除费用外还须把【模型+关键参数】列给用户确认
4. 每步用 canvas_await_result(nodeId) 阻塞等到 status=success 再 canvas_get_result 验产物
   Seedance 必把同一次 run 返回的 data.resultCursor 原样传给 await（防误认旧视频）
```

### 3.2 八条强制契约（§1.5，违反会被硬门拦）

1. **先看再动** —— 动手前先 `bootstrap`/`get_state`/`snapshot` 读现状，**绝不盲建**。
2. **先搭后验** —— 搭图优先 `scaffold`/`batch`（别逐条单建）；搭完先 `validate` 体检。
3. **上游→下游** —— 按数据流顺序跑，上游 `status=success` 才跑下游，否则被 `upstream_not_ready` 拦。
4. **付费必确认** —— 生成节点先 `list_models` 选模型 + 把关键参数列给用户确认；`canvas_run` 必带 `confirmToken`。**绝不静默套默认值**。
5. **看不懂就 snapshot** —— 任何时候 `canvas_snapshot` 给紧凑现状（`runnable`/`blocked`）；**每步操作后看返回里的 `nextActions` 决定下一步**。
6. **用户 SOP 优先** —— 用户自带流程/skill 时以它是唯一主线，内置 SOP 只当工具操作参考。
7. **SOP 从一而终** —— 一旦载入就按步骤顺序执行到底，**绝不中途换 SOP、绝不无视步骤**。返回会带 `sopCommitment`/`activeSop` 提醒。
8. **画布必须连着；可见性只卡依赖渲染帧的动作** —— 见下面 3.4 的三档连接错误。

### 3.3 该做 / 不该做（逐条清单）

**DO**
- ✅ 连接后**第一个调用必须是 `canvas_bootstrap`**（无参），一次拿全景+记忆+画布概况。
- ✅ 搭链用 `scaffold`（模板）或 `batch`（1~20 条 ops，原子应用）。
- ✅ 建完一批或布局乱了，调 `canvas_auto_layout` 一键排齐。
- ✅ **每建一个节点、或每跑出结果后，立即 `canvas_rename_node` 起语义名**（如『苏念-参考图』『分镜1-3-生图』）。文档原话：「改名是消除歧义的硬手段，**不是可选**」。
- ✅ **参考图必须先命名再连**；用户上传/已存在的未命名图节点用 `canvas_rename_node({nodeId,name})` 打标。
- ✅ 连参考图前用 `canvas_get_state` 看生成节点的 **`refWiring`**，逐条核对 **@图N → 来源节点**，并**把这份映射念给用户确认**。
- ✅ 连分镜用 `boardStatuses[].shotIds`（镜组覆盖哪些分镜）判定，**别再按「第 G 组 = 第 (3G-2)~(3G) 镜」硬算**。
- ✅ 写提示词时 **@图N 以 `refWiring` 的 index 为准**，别凭记忆猜。
- ✅ `batch` 建多个节点时给每个合理 `position`：沿数据流 x 递增、**每列间隔 ≥900** 防横向重叠、同列多节点 **y 错开 ≥300**。
- ✅ 往已有画布加节点前先 `get_state` 看现有坐标，**新节点放空白处**。
- ✅ 多层自审：产物层（真看图）+ 链路层（validate/refWiring）+ 意图层（对照用户需求逐条核对）。
- ✅ 不满意就迭代：`set_params`/`set_prompt` → `reset_node_result` 清旧结果 → 同节点 `run` 重跑，循环到满意。
- ✅ 拿不准的多个候选 → `param_sweep` 一次出 N 个对比，跑完挑最优。
- ✅ 想并行 → 后台哨兵 `feicai-watch-node.mjs`；起完立刻空出去干别的。

**DON'T**
- ❌ **绝不盲目重试付费 run**。`apply_unknown` = 结果未知，不是失败。重发前**必须先 `canvas_command_status` 查旧 commandId 回执**。
- ❌ **绝不带错连或缺图就跑生成**。发现缺漏/接错/拿不准 → 停下，明确列出哪个镜组缺什么，向用户说明并询问。
- ❌ **绝不按 `name` 操作节点**（防幻觉）。`connect`/`set_prompt`/`set_params`/`run` 一切操作用 `nodeId`；`name` **仅显示**。
- ❌ **绝不绕过确认连续自动烧钱**。即使在 pipeline 里「逐个 run」，每个 run 仍要用户同意。
- ❌ **绝不每次 run 后自动 judge**（`canvas_result_review` 的 describe/judge 是付费 vision），按需调。
- ❌ **绝不在 `canvas_set_params` 里设 `generateMode`/`regenerateMode`**（防绕预算门烧钱，设了必拒），只能经 `canvas_run` 运行时触发。
- ❌ **绝不拿 `text-input` 当某节点的提示词框**。文本模块是**内容载体**（长文写进 `params.content`），生成节点提示词走 `canvas_set_prompt` 设该节点的 `prompt`。
- ❌ **别逐条 create→connect**（每条要等画布轮询 ~0.3-1s，很慢）。
- ❌ **别把长文塞进生成节点的 prompt**；也别把 text-input 的 `prompt` 字段当正文（`prompt` 只是「附加指令」，高频陷阱）。
- ❌ **别去 canvas_command_status 轮询 `director_commands`/`voxel_commands` 的 commandId**（只回「已投递」）；验证生效走 `get_scene` 的 `lastApply`。
- ❌ **别因为只看到 `in-image`/`in-ref` 两个口就以为最多两张参考图** —— 标了 `multi:true` 的口能 fan-in 不限数量。
- ❌ **别去找 `in-n6`/`in-n7`** —— 口数 = 镜组数 = ⌈分镜数/3⌉，14 镜=5 镜组只有 `in-n1`~`in-n5`，**这是正常的不是 bug**。
- ❌ **别增删/重排 storyboard-orchestrator「铺到画布」spawn 的节点参考图边**（@N 与边序一一对应，动了会错位）。
- ❌ **别静默 clamp 或改写用户明确给的时长**。
- ❌ **别猜模型/控件**：`metadataComplete=false` 时先同步实例、重开画布刷新脱敏镜像，不猜控件或素材数量。
- ❌ **别把 `frameSeconds` 用于「故事板」** —— `canvas_await_result` 不适用故事板，用 `get_state` 看 `boardStatuses`。
- ❌ **别把尾帧口 `in-image-last` 当 fan-in 口**（天然只 1 张，不带 `multi`）；`smart-video` 源视频口 `in-video` 单口只接 1 段、不支持 fan-in。

### 3.4 坑清单（具体数值 / 枚举 / 参数名）

| # | 坑 | 具体细节 |
|---|---|---|
| 1 | **三档连接错误分级** | ① `canvas_not_connected`：画布页没打开/没在消费指令 → 指令**一条不入队**，让用户打开后重试（唯一例外：`canvas_new_project` 项目本体仍会建好，返回 `opened:false`）② `canvas_page_hidden`：画布页在后台 + **依赖渲染帧**的动作（`video_capture_frame`/`review` 的 describe·judge/`director_capture`/`voxel_capture`）→ 令牌**不消费**，切回后**原样重试** ③ `apply_unknown`：已入队未知 → **禁止 fresh run** |
| 2 | **后台标签页的例外** | `canvas_run`/`canvas_run_chain` **不再因后台被拒**：后台页照常领取并**立即执行**（executor 不等渲染帧），只是后台定时器被节流、进度刷新变慢。此时确认令牌**已消费** —— 别再重复 run |
| 3 | **`await_result` 超时值** | `timeoutMs` 默认 **40s** / 上限 **55s**；未完成返 `done:false`，**原样再调续等** |
| 4 | **`run_chain` 墙钟** | ≤**200 秒**；用尽返 `pending:true`，**原样再调续跑**（已 success 不重跑）。另：跑到 `storyboard-gen` **只拆镜、绝不自动批量出板图** |
| 5 | **指令超时上限** | 指令超 **10 分钟**未被画布消费 → 收到**失败回执**（不再永远 pending），回执文案提示画布可能未打开/绑错画布 |
| 6 | **`director_commands` 的 aspect** | 仅 `"16:9"` \| `"9:16"` **两值**（不是 capture 的 4 值），传别的被忽略 |
| 7 | **`voxel_commands` 坐标** | 整数格 `[x,y,z]`；x∈[-64,64)、**y∈[0,64)**（y=0 初始草地层，**从 y=1 往上搭**）、z∈[-64,64)；原点=场景中心。`set` 1~2048 项，批 **≤100**。大结构优先 `fill`/`hollow` 别逐块 `set` |
| 8 | **方块 id 表** | 1草 2泥土 3石头 4木板 5原木 6红砖 7石砖 8沙子 9雪块 10玻璃 11树叶 12水 13-20 白/黑/红/蓝/黄/绿/橙/紫混凝土；**`id=0` 删格**，`hollow:true` 只留外壳 |
| 9 | **`add_camera` 的 fov** | 10-120，缺省 50 |
| 10 | **本地视频/音频数组** | `referenceVideos`/`referenceAudios` 最多各 **4 项**，每项 ≤**1048576 字符**；数组按顺序绑定槽位，**整体替换**，`[]` 清空。只接受公网 HTTP(S)、`/api/canvas-files/<project>/<单个key>` 短路径、或 base64 data URL |
| 11 | **`localRelayParams`** | 最多 **16 项**；键以字母开头、只含字母/数字/下划线且 ≤**40 字符**；值必须有限数字且 |v| ≤ **1e9**；总 JSON ≤**4096 字符**；该表**整体替换**，`{}` 清除覆盖 |
| 12 | **`region` 对象参数** | `{y1,y2,x1,x2}` **0~1 比例坐标**；字幕带只需 `y1`/`y2`，提交时**强制整宽** |
| 13 | **`disconnect` 参数键** | `sourceId/sourcePort/targetId/targetPort`（**不是** `sourceNodeId`/`sourceHandle`） |
| 14 | **dataType 必须匹配** | text→text / image→image / video→video |
| 15 | **端口 id 要真实** | 用 `get_state`/`bootstrap` 返回的真实端口 id，**别猜** |
| 16 | **动态端口** | `script-extract`/`storyboard-gen` 的输出口要**跑完**才生成（`out-n1-text`…）。含它们的链路**必须分阶段**：建+连+跑 → `get_state` 看抽出几个口 → 再 batch 建下游 |
| 17 | **镜组口数公式** | 口数 = 镜组数 = **⌈分镜数/3⌉**；14 镜 = 5 镜组 = 只有 `in-n1`~`in-n5` |
| 18 | **单口参考图上限（按模型）** | smart-image api/即梦**全用**、rh-image **仅第 1 张**；smart-video 多参/all-ref 全用、普通图生视频**只第 1 张**、视频参考(v2v)**≤5 张**；seedance 全能参考**最多 9 张** |
| 19 | **storyboard-gen 两步出图** | 首次 `run` 只 AI 拆镜、**不出板图**。批量出全部 = `canvas_run(nodeId, generateMode:"all")`；单镜组/子集/重生 = `canvas_run(nodeId, boardIds:["BOARD_xx"])`（两参**互斥**）。`boardId` 从 `get_state` 的 `boardStatuses` 拿，拆镜后 idle 占位条目即可用 |
| 20 | **v2v 必接源视频** | `mode=v2v` 须把 **1 段**已出片的源视频接 `smart-video.in-video`（**单口只 1 段、不 fan-in**），缺源视频跑不了；`videoModelId` 要选支持 v2v 的型号 |
| 21 | **`durationsByResolution`** | 有它时先按**所选分辨率的小写键**读候选，再经 `canvas_set_params` 写 `duration` 和 `resolution`；**不把并集 `[12,15]` 当作两种分辨率都支持的组合**；保留用户明确时长，不静默 clamp |
| 22 | **`director_workbench_edit` 的白名单** | 只允许 `update_shot`（改 prompt/durationSec/continuity）或 `set_run_selection`；**禁止**素材/模型/输出规格/增删重排/执行/确认/付费字段。整批任一失败 → **零修改**（原子） |
| 23 | **`estimate_cost` 的导演工作台特例** | 必须传 `director:{nodeId, expectedRevision, mode, scope, shotId?}` 精确作用域，**禁止固定价兜底**；`run` 必须传**与报价完全相同**的 `director` 对象，`mode=single` 必带 `shotId` |
| 24 | **不可自动化的部分** | 涂鸦编辑 / 人脸过审 / 姿势控制(PoseStudio) / 提示词库拖拽（要用等效效果走 `set_prompt`/`upload_asset`）；`_` 前缀内部字段（`_thumbnail`/`_gridFolded`/`_gridRatio`）被参数白名单拒 |
| 25 | **无 MCP 工具的用户按钮** | storyboard-orchestrator 的「铺到画布」「铺视频节点」「生成参考图」、ref-forge 的「批量扩写并铺节点」「铺生图节点」、remake-script 的「生成参考图」「铺出当前合集视频节点」、以及所有 ⚙ 提示词弹窗正文 —— **都只能用户手点，AI 必须引导而非代替** |

### 3.5 三层自审规范（§2「🔴 分阶段推进 + 自审到位」）

文档的核心反模式警告是「**别『跑完就报完成』**」。要求把每个节点/阶段跑完后主动核实：

| 层 | 手段 | 判据 |
|---|---|---|
| **产物层** | `canvas_get_result` | **真看图/视频质量**，与提示词/参考图是否吻合（不是只看有没有出） |
| **链路层** | `canvas_get_state` / `canvas_validate` | 接线对、上游真出图、无断链、`refWiring` 映射对 |
| **意图层** | 对照用户原始需求逐条核对 | 该做的都做了吗？漏没漏？ |

不达标 → `set_params` 调参 / `set_prompt` 改词 / 重跑，**循环到真满足**再交付或进下一阶段。**报「完成」前先过这三层。**

另：`canvas_skill_get('quality-loop')` 提供自驱质量循环配方（judge → 不达标改重跑**封顶 2 轮** → 留最好 → 逼近预算即停）。

---

## 四、给影匠MCP.py 的设计映射（借鉴点清单）

| 飞彩的做法 | 影匠的等价物 | 为什么照搬 |
|---|---|---|
| 单文件主服务器 + `TOOLS` 数组 + `actionId` 一一对应 | 单文件 `影匠MCP.py`，`工具表()` 返回 11 条工具定义 + `派工表` 名字→函数 | 加工具是纯加法，零映射成本 |
| 统一错误信封 `{ok,error:{code,message,nextAction,safeToRetry}}` | 同构，错误码换成影匠语义（`没有这部戏`/`ComfyUI没连上`/`参数不对`） | AI 能机器判别 + 知道下一步 |
| `nextActions` 导航字段（`ok:false` 也带） | 每个工具返回都带 `下一步` 字段（字符串或列表） | 主动告诉 AI 该干嘛，最省 token |
| 服务端阻塞等待（`await_result`） | `查进度` 直接调 `剧组.扫状态` 不阻塞；`让镜动` 内部靠 `引擎.派工` 的 `上限秒` + `报` 回调回报 | 影匠的引擎已经有阻塞等待，只需把进度回调接出来 |
| 三档连接错误分级 | `ComfyUI没连上` → `safeToRetry:true`（指令没入队） | 明确「能不能重发」 |
| 「付费必确认」 | `开镜`/`让镜动` 标 `⚠花钱`，返回里带 `费用提示` | 保留人工闸门 |
| stdio NDJSON + stdout 纯净（诊断走 stderr） | 同构；另加 `contextlib.redirect_stdout` 拦截 `导演.py` 的 `print` | **Python 侧最大的坑**：模块全是 `print` |
| `报=` 回调做进度 | 所有工具调用都把 `报` 换成一个收集器，把进度行装进返回的 `日志` 数组 | 不污染 stdout，又能把进度给 AI |
| `title`/`description`/`inputSchema` 三件套 | 同构，中文工具名 + 中文描述 + 参数说明写在 description 里 | AI 靠 description 决定调不调 |
| `instructions` 顶层字段教工作流 | `initialize` 返回里带 `instructions`（影匠的五步流水线） | 接入即知道该怎么走 |

