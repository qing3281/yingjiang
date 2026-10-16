# 飞彩无限画布 CLI — 智能体接入文档

> 你是控制**飞彩 AI 创作画布**的智能体(Claude Code / Codex / 龙虾 Claw)。通过 MCP 桥操作一张无限画布:在上面建节点、连成工作流、执行生成图/视频/文本,并能看结果、调参迭代。本文档是你接入后的操作手册。

---

## 0. 接入第一步(必做)

连接后**第一个调用就是 `canvas_bootstrap`(无参)** —— 一次拿全:
- **modules**:所有模块的 id / 端口(inputs/outputs + dataType)/ paramKeys(可编辑参数,带默认值)
- **workflows**:端到端工作流范式
- **usage**:⓪~㉙ 工作准则
- **memoryIndex**:历史使用记忆索引
- **activeCanvas**:当前画布概况(节点 id/moduleId/status)

⚠️ 别急着逐条建节点、别先分开调 guide/get_state/memory_recall ——bootstrap 一次搞定。

---

## 1. 工具速查(58 个,按用途分类)

### 看 / 查(只读,零花钱)
| 工具 | 作用 |
|---|---|
| `canvas_bootstrap` | 接入第一调用,一次拿全景+记忆+画布概况 |
| `canvas_get_state` | 读画布现状(节点/连线摘要,已脱敏) |
| `canvas_snapshot` | 紧凑快照:节点状态 + `runnable`(现在能跑的)+ `blocked`(被挡的+原因)+ `issues`;比 get_state 更聚焦下一步、token 更省 |
| `canvas_guide` | 使用指南;带 moduleId 查单模块完整参数 schema |
| `canvas_list_models` | 列图像/视频/文本三类可用模型(可附 durations/resolutions/durationsByResolution 候选；id/name/model + 价格/时长/分辨率/质量档元数据；视频翻拍、参考图工坊和智能分镜可用 llm 列的激活实例 id；智能分镜再用 `canvas_set_params` 写 `storyboard-orchestrator.llmInstanceId`，留空保持主实例→备用实例自动回退，显式选择固定单实例；实例被删除、停用、缺少配置，或任务期间配置发生变化时停止且不会换模型) |
| `canvas_validate` | 工作流体检:断链/孤立/缺输入/能否跑(canRun) |
| `canvas_estimate_cost` | 预估整条链跑一遍总花费(¥),按节点真实模型单价(登记过用真价,未登记保守兜底)；导演工作台必须传 `director:{nodeId,expectedRevision,mode,scope,shotId?}` 精确作用域，禁止固定价兜底 |
| `canvas_director_workbench_get_plan` | 只读导演工作台脱敏方案；缺省读取 `activeMode`，按 `cursor+limit` 分页(`limit` 1~20，缺省 20)，`page.nextCursor` 存在时继续；六模式只给计数摘要。带 `mode+shotId` 额外返回该镜字节有界详情、原字符数和截断标记，不受当前页遗漏；不返回素材 URL、任务标识或供应商凭据 |
| `canvas_progress` | 一眼看进度:节点 done/running/error/idle 计数 + 故事板镜组完成度(如 7/9)+ 今日已花¥与距软阈值余量(未设限会注明) |
| `canvas_compose` | 声明式工作流校验器(plan):搭建前提交目标图谱 spec(ref 符号引用的 nodes+edges),只在内存里复用 validate 体检 + 估价(不建节点、零花钱),valid=true 再用 `canvas_batch` 落地——拓扑错挡在动手前 |
| `canvas_get_result` | 看某节点生成结果(图/视频 URL),判断质量；Seedance 返回独立视频节点 `resolvedNodeId` |
| `canvas_result_review` | 看图质量自评(vision)。action:view(零花钱,回 ≤256px 缩略图本体直接看)/ describe(¥0.1,客观描述+瑕疵列举)/ judge(¥0.1,VIEScore 双轴评分+matchesIntent+verdict accept/retry/switch_model+建议)。describe/judge 付费 vision、需先在画布配 LLM 视觉模型、必带 confirmToken;视频用 frameSeconds 抽帧。按需调,绝不每次 run 后自动 judge |
| `canvas_list_assets` | 一次列出某画布所有有图/视频产出的节点 + URL(canvasId 可选,缺省=当前画布),跨画布找参考图/视频用;大 dataURL 不回内容只给提示 |
| `canvas_command_status` | 查指令回执;commandIds 数组可批量查;指令超 10 分钟未被画布消费会收到**失败回执**(不再永远 pending),回执文案会提示画布可能未打开/绑错画布 |
| `canvas_await_result` | 阻塞等某节点生成完成再返回(到 success 带产物 URL、error 带原因；Seedance 另返独立视频节点 `resolvedNodeId`),一次顶替反复轮询、省 token;到 timeoutMs(默认40s/上限55s)未完成返 done:false 续等;故事板不适用 |
| `canvas_skills_list` | 列出可用 SOP/技能索引(id/name/description,无正文) |
| `canvas_skill_get` | 读某 skill 完整 SOP 正文,入参 `{id}` |

### 搭建(零花钱)
| 工具 | 作用 |
|---|---|
| `canvas_scaffold` | 🚀 模板一键搭整条链(text-to-image / text-to-image-to-video / novel-to-extract / script-to-storyboard) |
| `canvas_batch` | 🚀 一次提交 1~20 条(create/connect/set_prompt/set_params/layout),原子应用 |
| `canvas_create_node` | 建单个节点(多个请用 batch) |
| `canvas_connect_nodes` | 连一条线(多条请用 batch) |
| `canvas_set_prompt` | 设节点提示词 |
| `canvas_set_params` | 设节点任意可编辑参数(含 region 等对象参数) |
| `canvas_param_sweep` | 复制节点 N 份各设一个参数变体,做 A/B/C 对比 |
| `canvas_load_workflow` | 从模板一键重建整套节点+连线 |
| `canvas_upload_asset` | 把本地图片/URL 上传为画布图片展示节点(可当下游参考图),零花钱 |
| `canvas_copy_reference_from` | 从其他画布复制一张参考图进当前画布(落参考图节点,不自动接线),零花钱;需 sourceCanvasId+sourceNodeId,v1 仅同源 /api/canvas-files 托管图 |
| `canvas_refs` | 角色库(项目级共享一致性参考库)读写单工具,action:list(列库存)/forText(按文本匹配角色场景道具)/place(库图放上画布)/save(画布产物存进库⚠️写共享库)/delete(移除条目⚠️不可逆);save/place/delete 经浏览器异步 apply,commandId 查回执 |
| `canvas_video_capture_frame` | 从视频节点截某秒的帧→右侧生成图片节点(可当参考图;异步,timeSeconds 默认 0,-1=尾帧) |
| `canvas_director_open` | 打开3D 导演台(3D 编排工作室),下发编排命令前先调它 |
| `canvas_director_commands` | 给3D 导演台下发 DirectorCommand[] 编排 3D 场景(建对象/站位/姿势/朝向/互动),并支持机位/打光/视图/对象属性/影视机位预设 cameraPreset(god/high/eye/low/left/right/threeQuarter 7 种)/场景背景 setBackground(url 仅画布同源图,mode backdrop/floor/panorama、intensity 0.1~1、height/panoramaRadius 米,clear 可清)/updateCamera(target=机位id/序号,注视点用 lookAt:[x,y,z],position/fov/aspect/locked)辅助 op;机位 aspect 仅 "16:9"\|"9:16" 两值(非 capture 的 4 值),传别的被忽略;先 open 再 commands(modal 未就绪时画布侧缓冲、就绪后按序回放不丢);坐标用 [x,y,z] 数组(米,兼容 {x,y,z});move/rotate/updateObject/updateCamera 优先 get_scene 拿真实 id 再按 id 定位(序号跨批易错位);回执 commandId 别拿去 canvas_command_status 轮询(只回「已投递」),验证生效走 get_scene 的 lastApply |
| `canvas_director_get_scene` | 读回3D 导演台当前 3D 场景摘要(对象/机位/灯光 + id),按 id 精确 updateObject/updateCamera「看着改」;另返回 lastApply=上批 director_commands 执行反馈(applied 生效条数 + skipped 被跳过项及 reason),下发命令后看它确认哪些生效/被跳过;includePose=true 另返回各 humanoid 非零关节角 poseDeg(度)/复合道具零件摘要 parts,验证 setPose/reach/addComposite;须3D 导演台已打开(modal 防抖上报,刚 open/刚下发命令稍候再读) |
| `canvas_director_capture` | 从3D 导演台当前视角截图→画布「3D 导演台参考」图片节点(可连下游当参考图;异步,完成后 get_state 可见)。完整 3D 导演编排 SOP 见 canvas_skills_list → canvas_skill_get director-3d-staging |
| `canvas_director_workbench_edit` | 按 `expectedRevision` 原子编辑导演工作台；只允许 `update_shot` 改 prompt/durationSec/continuity，或 `set_run_selection` 显式替换运行选择。整批任一失败则零修改；零花钱且绝不执行，禁止素材/模型/输出规格/增删重排/执行/确认/付费字段 |
| `canvas_voxel_open` | 打开方块世界(方块搭景摄影棚),下发建造命令前先调它 |
| `canvas_voxel_commands` | 给方块世界下发 VoxelCommand[] 搭方块场景/编排机位:set{blocks:[[x,y,z,id],...] 1~2048 项,id=0 删格}逐格点缀 / fill{from,to,id,hollow?}区域填充(id=0 区域删除,hollow:true 只留外壳快速起房)/ clear_world 清场 / add_camera{position,target注视点,name?,fov? 10-120 缺省50,aspect? "16:9"\|"9:16"} / update_camera{id,patch} / remove_camera{id} / select_camera{id\|null},批 ≤100;方块坐标整数格 x∈[-64,64) y∈[0,64) z∈[-64,64),y=0 初始草地层、从 y=1 往上搭,原点=场景中心;方块 id:1草 2泥土 3石头 4木板 5原木 6红砖 7石砖 8沙子 9雪块 10玻璃 11树叶 12水 13-20白/黑/红/蓝/黄/绿/橙/紫混凝土;大结构优先 fill/hollow 别逐块 set;先 open 再 commands(modal 未就绪画布侧缓冲、就绪后按序回放不丢);回执 commandId 别拿去 canvas_command_status 轮询(只回「已投递」),验证生效走 get_scene 的 lastApply |
| `canvas_voxel_get_scene` | 读方块世界场景摘要(totalBlocks / blockCounts 按方块 id 计数 / aboveGroundBounds 地面以上包围盒 / cameras 机位表含 id / selectedCameraId)+ lastApply 上批 voxel_commands 执行反馈(applied 生效条数 + skipped 被跳过项及 reason),下发命令后看它确认哪些生效再决定下一步;机位 id 跨批引用以它为准;须方块世界已打开(modal 防抖上报,刚 open/刚下发稍候再读) |
| `canvas_voxel_capture` | 从方块世界机位拍照({cameraId?,aspect?},cameraId 缺省=选中机位、再缺省=当前视角,aspect 仅当前视角生效)→ 画布「方块世界参考」图片节点(可连下游 smart-image/图生视频当参考图;异步,完成后 get_state 可见)。先编排好场景再拍;完整配方(含小屋 few-shot)见第 7 节 |

### 整理(零花钱)
| 工具 | 作用 |
|---|---|
| `canvas_auto_layout` | 智能排版:关联组内部从左到右展开，无关组上下分区 |
| `canvas_layout` | 手动移动单节点到指定坐标 |
| `canvas_delete_node` | 删节点(连带删关联连线) |
| `canvas_rename_node` | 给已存在节点改显示名/中文语义标签(如『角色-张三』);🔴 参考图打标专用,name 仅显示、操作仍用 nodeId |
| `canvas_disconnect_nodes` | 删一条指定连线(节点保留) |
| `canvas_duplicate` | 复制节点(含参数,不含结果) |
| `canvas_reset_node_result` | 清空节点生成结果、状态回 idle,供改参后重跑 |
| `canvas_restore` | 画布检查点还原安全网。action:list/restore；云专版复合检查点传 `projectId+canvasId`，不传 projectId 继续读取历史 canvas-only 桶；整体替换节点+连线，有节点在跑则拒(force:true 强行) |

### 执行(⚠️ 花钱)
| 工具 | 作用 |
|---|---|
| `canvas_run` | 执行某节点跑生成。**会消耗费用,必须先获用户同意;图像/视频生成还须先确认模型+关键参数**。导演工作台须先 get_plan/estimate，再传与报价完全相同的 `director:{nodeId,expectedRevision,mode,scope,shotId?}`，`single` 必带 `shotId`，禁止固定价执行。画布页没打开/没在消费指令返 `canvas_not_connected`(指令一条不入队,让用户打开/切回画布页后重试);**画布页在后台标签页不再拒绝**——后台页照常领取并**立即执行**(run 的 executor 不等渲染帧),只是后台定时器被节流、进度刷新变慢(确认令牌已消费,别重复 run:先 `canvas_command_status` / `canvas_get_state` 查证)。4s 内没等到 apply 回执返 `apply_unknown` = **结果未知**(不是失败),绝不原样重发、先查证;画布**明确拒绝**才返 `canvas_not_applied`(带 reason,可修正后重试) |
| `canvas_run_chain` | 🚀 **按拓扑序批量跑整条链 + 托管重试**(治长链路 turn 爆炸):服务端 while 循环复用 computeSnapshot 取 runnable ∩ 目标闭包逐个 run+等 success,跑完上游写回下游自然进下一轮,**一次调用顶替逐节点 run+await 的 N 轮往返、省大量 token**。`fromNodeId` 缺省=全图 runnable,给则只跑该节点及下游闭包。付费:跑前估全链总价,无 `confirmToken` 返 `confirm_required`+token(绑本链+总价),复述总价获同意后带 token 重调。托管重试只对 timeout/network(其它类别记 failed 让你改词/换渠道),每次重试各自计费、受日预算门。🔴 跑到 storyboard-gen 只拆镜、绝不自动批量出板图。fail-soft 返 `{ran,failed,skipped}`;墙钟(≤200s)用尽返 `pending:true`,原样再调续跑(已 success 不重跑)。画布连接门与 canvas_run 同口径:画布页没打开/没在消费指令返 `canvas_not_connected`;**页面在后台不再拒绝**——后台页照常领取并立即执行(已入队节点结果未知时只可 `canvas_command_status` 查证,禁止 fresh run) |
| `canvas_abort_node` | 停止某节点正在跑的生成(对应 UI ⏹),不删节点不丢已有结果;storyboard 按 nodeId 全停;零花钱 |

> ⚠️ **后台标签页**:画布页在后台时,`capture_frame` / `review_node` / `director_capture` / `voxel_capture` 这四类**依赖浏览器渲染帧**的指令不会被后台页消费——留在队列里等页面可见时再执行。`canvas_run` / `canvas_run_chain` **不再因后台被拒**:后台页也会把 run 领走并**立即执行**(executor 不等渲染帧;只是后台定时器被节流、进度刷新变慢)——确认令牌已消费,别再重复 run,先 `canvas_command_status` 查 commandId 回执 / `canvas_get_state` 看节点状态。`canvas_result_review` 仅 describe/judge 需要前台(走 review_node 渲染帧),在后台仍返 `canvas_page_hidden` 快速失败(令牌不消费,切回后原样重试);view 纯只读不受影响。建节点/连线/改参数/批量/布局等**结构类操作在后台照常生效**。

### 沉淀
| 工具 | 作用 |
|---|---|
| `canvas_save_workflow` | 当前画布存为模板(脱敏,不存生成产物) |
| `canvas_memory_recall` / `canvas_memory_save` | 读/存使用记忆(踩坑/配方/工作流笔记)(含 key='recipes' 自动配方) |

---

## 1.5 画布智能体契约(强制工作流,违反会被硬门拦)

下面 7 条是唯一正确工作流的强制检查清单 + 不变量。系统会在你违反时用硬门拦你(返回 `code` 如 `upstream_not_ready` / `validation_failed` / `model_not_selected` / `confirm_required`)——本契约就是这些硬门的「为什么」:

1. **先看再动**:动手前先 `canvas_bootstrap` / `canvas_get_state` / `canvas_snapshot` 读现状,绝不盲建。
2. **先搭后验**:搭图优先 `canvas_scaffold` / `canvas_batch`(别逐条单建);搭完先 `canvas_validate` 体检(canRun=false 先修断链/缺输入)。
3. **上游→下游**:按数据流顺序跑,上游 status=success(已出产物)才跑下游,否则被 `upstream_not_ready` 拦。
4. **付费必确认**:生成节点(smart-image/smart-video/seedance/storyboard-gen)先 `canvas_list_models` 选模型 + 把关键参数列给用户确认;`canvas_run` 必带 `confirmToken`——付费操作永远二次确认,绝不静默套默认值。
5. **看不懂就 snapshot**:任何时候 `canvas_snapshot` 给紧凑现状(`runnable`=现在能跑的、`blocked`=被挡的+原因);**每步操作后看返回里的 `nextActions` 决定下一步**。
6. **用户 SOP 优先**:用户自带流程/skill 时以它为唯一主线,内置 SOP 只当工具操作参考。
7. **SOP 从一而终**:复杂任务先 `canvas_skills_list`/`canvas_skill_get` 选定一套 SOP;一旦载入就按它的步骤顺序执行到底,**绝不中途换 SOP、绝不无视步骤**。载入后每次返回会带 `sopCommitment`/`activeSop` 提醒你当前认哪套——顺着它走,每步后看 `nextActions` 定下一步。
8. **画布必须连着;可见性只卡依赖渲染帧的动作**:画布页没打开或没在消费指令时,**所有会入队的画布写工具**(建节点/连线/设参/批量/加载工作流/回滚 restore/打开项目/参数扫描/布局/中止/重置/参考图/3D 导演台/方块世界等)以及 `canvas_run`/`canvas_run_chain`/`canvas_result_review`(result_review 仅付费的 describe/judge 走此门,view 纯只读不受影响),都会**立刻**返回 `code=canvas_not_connected`(指令一条不入队,不再 ok:true 后石沉大海)——处置:让用户打开/切回画布页面,等几秒重连后重试(唯一例外:`canvas_new_project` 画布未连时项目本体仍会建好、只是不自动打开,返回 `opened:false`)。画布页开着但在**后台标签页**时:**依赖渲染帧的动作**(取帧 `canvas_video_capture_frame`、看图评审 describe/judge、3D `canvas_director_capture`、方块 `canvas_voxel_capture`)保持原样——后台页不消费、留在队列里等切回前台执行,其中需付确认的 describe/judge 会在入口立刻返 `code=canvas_page_hidden`(**确认令牌不会被消费**,让用户切回画布页后**原样重试**);而 `canvas_run`/`canvas_run_chain` **不再因后台被拒**:后台页也会领走并**立即执行**(executor 不等渲染帧)(确认令牌此刻已消费,**别再重复 run**——先 `canvas_command_status` 查 commandId 回执、`canvas_get_state` 看节点状态)。🔴 防重复扣费:若你手里已有一个**没等到回执**的旧 commandId(超时/断连/`apply_unknown` 后想重试),重发前**必须先 `canvas_command_status` 查它的回执**,确认旧指令没被画布"补执行",否则可能重复触发付费生成——`apply_unknown` 表示「结果未知」,不是「失败」,更不是「没入队」;`canvas_not_applied` 则是画布**明确拒绝**(有 reason,可修正后重试)。

### 📡 返回里的 `nextActions` / `snapshot`(你的轨道)
每次 `canvas_*` 调用的返回除 `ok`/`data`/`error`/`code` 外,会**附加**字段(底层结果原样不动,只多给你导航):
- **`nextActions`**:`{ canDo:[{action,target?,why}], blocked:[{action,target?,reason}] }` —— 现在能做什么 / 被挡住什么 + 怎么解开。**每步后照它走**。
- **`snapshot`**(仅 run/validate/batch/scaffold/load_workflow 附):`{ nodeCount, nodes, runnable, blocked, issues? }` —— 操作后的画布全貌,省一次 get_state。
- 🔴 `ok:false`(硬门拒绝)时**也带 `nextActions`**:别盲目重试,先看 `nextActions.blocked` 的 reason 把前置条件补上(选模型 / 跑上游 / 带 confirmToken)再重调。

---

## 2. agentic 工作流(像工程师那样工作)

### 📚 先定谁的 SOP 主导本次任务(别让内置 SOP 喧宾夺主)
飞彩内置 skills(`canvas_skills_list` 里标「内置」的 `feicai-storyboard-v3` 等)是**可选 SOP 模板,不是必须执行的流程**;画布工具(建/连/设参/run)才是始终适用的执行手段。连接后、动手前先判优先级,一旦判定就只认这一套、别中途换:
- **用户给了自己的 SOP / 本地 skill / 明确步骤** → 以用户那套为唯一流程主线,内置 SOP 只当"怎么操作画布工具"的参考,🔴 **绝不先把某条内置 SOP 跑一遍再转用户的**(双流程打架、乱工作就是这么来的)。
- **用户只给目标、没自带流程,且任务属「剧本/小说 → 分镜/视频」这类** → 才走下方二选一,让用户定内置模式。
- **任务跟任何内置 SOP 都不沾边** → 直接按用户意图自由编排画布工具,别硬套内置 SOP。

仅当判定为"用户只给目标 + 剧本→分镜/视频类"时,🔴 **开工前先让用户二选一定模式(别替用户默认)**:
- **飞彩分镜 v3.0** → `canvas_skill_get('feicai-storyboard-v3')`:空间逻辑优先的导演分镜方法论→拆 ≤15 秒合集→smart-image 出角色场景参考图/逐合集关键帧→seedance 逐合集出视频全链路
- **自定义** → 不套内置 SOP,按用户意图自由编排画布工具
确认模式后再 `canvas_skills_list`/`canvas_skill_get` 读对应 SOP 正文按步骤执行,别裸猜流程。

### 🚀 搭链:批量优先
搭工作流别逐条 create→connect(每条要等画布轮询 ~0.3-1s,逐条很慢)。优先:
- **canvas_scaffold**:常见任务给模板名+内容,一次建好整条链
- **canvas_batch**:自己规划时,一次提交多条 ops(同批可先 create 再 connect 新节点)
建完用 **canvas_auto_layout** 一键按关联组排整齐（组内从左到右、无关组上下分区）,不用自己算坐标。

### ⚡ pipeline:跑整条链
1. `canvas_validate` 体检 → canRun=false 先修(断链/缺输入)
2. `canvas_estimate_cost` 看总花费 → 向用户说明
3. 按数据流**上游→下游顺序**逐个 `canvas_run`;**每个下游跑前先 `canvas_get_state` 确认其上游 status=success**(没出结果就跑下游会失败或用旧结果)。🔴 图像/视频生成节点(smart-image/smart-video/seedance-video/storyboard-gen)run 前除费用外还须把【模型+关键参数】列给用户确认(生图:imageInstanceId/提示词/画幅/参考图/张数;生视频:videoModelId/提示词/时长/分辨率/模式(图生视频/全能参考/视频参考——v2v 须先接 1 段源视频到 smart-video.in-video 口)/参考图),别套默认值;参数不明先 `canvas_get_state`/`canvas_list_models` 摆出来问
4. 每步用 `canvas_await_result`(nodeId) 阻塞等到该节点 status=success 再 `canvas_get_result` 验产物——await 一次顶替反复轮询、省 token(超时返 done:false 原样续等;故事板用 `canvas_get_state` 看 boardStatuses)。Seedance 必把同一次 `canvas_run` 返回的 `data.resultCursor` 原样传给 await，防误认旧视频。

### 🤖 自主迭代闭环(看着改,核心)
`canvas_run` 出图后 → `canvas_get_result` 看 URL/质量 → 不满意:
- `canvas_set_params` 调参数(换 `imageInstanceId` 模型 / 改 aspectRatio)
- `canvas_set_prompt` 改提示词
→ **同节点 `canvas_run` 重跑** → 再 `canvas_get_result` 看,循环到满意。
多个候选参数拿不准 → `canvas_param_sweep` 一次出 N 个对比,跑完挑最优。
🔁 **不满意一键改(recast 配方)**:`canvas_set_params`/`canvas_set_prompt` 改一处 → `canvas_reset_node_result` 清旧结果 → 同节点 `canvas_run` 重跑;要自驱质量循环(judge→不达标改重跑封顶2轮→留最好→逼近预算即停)用 `canvas_skill_get('quality-loop')`。

### ⏱️ 等生成完成:阻塞 await(默认) vs 后台哨兵(想并行时)
跑完一个生成节点要确认它好没好,两种等法,按是否想并行选:
- **`canvas_await_result(nodeId)`(默认,任意宿主)**:阻塞等到该节点 `status=success` 直接带产物 URL 返回,一次顶替反复轮询、省 token;到 timeoutMs(默认40s)未完成返 `done:false`,原样再调续等。Seedance 必同时传本次 `canvas_run` 返回的 `resultCursor`，成功会返独立视频节点 `resolvedNodeId`。简单,但等待期间你被占住、不能并行。
- **后台哨兵 `feicai-watch-node.mjs`(想边等边干别的,且宿主支持「后台任务完成→自动唤醒会话」,如 Claude Code)**:用后台方式起 `node mcp-bridge/feicai-watch-node.mjs <nodeId> [canvasId]`(把 `FEICAI_BASE`/`FEICAI_PAIR_TOKEN` 传给它,同 MCP 配置)。它在后台轮询该节点直到 `success/error` 才退出 → 宿主自动唤醒你 → 读它 stdout 的单行 JSON(`{done,status,url,error}`)。**起完哨兵就立刻空出来去跑别的节点/干别的,完成时被叫回来即可**——真正的「边生成边并行」。退出码:0成功/1生成失败/2参数或连接错/3超总上限(默认30min)。⚠️ 只对「后台任务自动通知」的宿主有效;不支持的宿主退回用上面的 await。

### 🔴 分阶段推进 + 自审到位(别"跑完就报完成")
像一个会自我复核的工程师那样干,不是跑完工具就交差:
- **分阶段推进**:复杂多阶段任务(如飞彩分镜 v3.0 的 导演分镜→出角色场景参考图→出逐合集关键帧→出视频)**一个阶段干透了再进下一个**,上游产物没到位绝不硬推下游。
- **三层自审**:每跑完一个节点/阶段,**主动核实"是否真到位"再继续,绝不只看 `status=success` 就当成功**:
  1. **产物层** — `canvas_get_result` 真看图/视频质量,与提示词/参考图是否吻合(不是只看有没有出)。
  2. **链路层** — `canvas_get_state` / `canvas_validate` 确认接线对、上游真出图、无断链、`refWiring` 映射对。
  3. **意图层** — 对照用户原始需求逐条核对覆盖(该做的都做了吗?漏没漏?)。
- 不达标 → 自己 `canvas_set_params` 调参 / `canvas_set_prompt` 改词 / 重跑,**循环到真满足**再交付或进下一阶段。**报"完成"前先过这三层自审。**

### 🧭 从意图到工作流
用户给目标(如"做 30 秒产品宣传片"):
1. `canvas_list_models` 摸清有哪些图像/视频/文本模型
2. `canvas_scaffold` 选模板 或 `canvas_batch` 规划链路
3. `canvas_validate` + `canvas_estimate_cost`
4. 按 pipeline 执行
5. 按自主迭代调优
6. `canvas_save_workflow` 存模板,下次复用

---

## 3. 🔴 安全铁律(必守)

- **零花钱操作**:建节点/连线/设参/排版/复制/删除/体检/估价/看结果/存模板 —— 全部不花钱,放心用。
- **唯一花钱**:`canvas_run`。调用前**必须先向你的用户说明执行哪个节点 + 预计费用,并获明确同意**。
- **二次确认**:`canvas_run` 返回 `confirm_required` 时,向用户复述费用、获同意后,带 `data.confirmToken` 原样重调。
- **绝不绕过确认连续自动烧钱**:即使在 pipeline 里"逐个 run",每个 run 仍要用户同意,不要为了"自动化"跳过。
- **模型选择**:你只能从 `canvas_list_models` 返回的合法 id 里选(密钥在服务端,你拿不到也不需要)。视频翻拍与参考图工坊把 llm 列的激活实例 id 写入 `llmInstanceId`；留空用当前主实例，失效实例会拒绝运行且不会自动换模型。智能分镜先从 llm 选激活实例 id，再用 `canvas_set_params` 写 `storyboard-orchestrator.llmInstanceId`；留空保持编排现有的主实例→备用实例自动回退，显式选择则固定单实例；若所选实例被删除、停用、缺少配置，或任务期间实例配置发生变化，任务会停止且不会换模型。
- **视频时长与分辨率**:`canvas_list_models` 有 `durationsByResolution` 时，先按所选分辨率的小写键读取候选，再通过 `canvas_set_params` 写现有 `duration` 和 `resolution`；Seedance 节点的画质字段仍是 `quality`。候选仅供选择与提示，上游决定实际接受；保留用户明确时长，不静默 clamp 或改写。无 map 时沿用旧 `durations`，能力缺省时不要猜档位。

SDK v4 可以用同一个模型表达不同画质的候选，例如同一 `plugin:example/video`：

```json
{"durationsByResolution":{"480p":[15],"720p":[12]}}
```

选择 480p 时提示 15 秒，选择 720p 时提示 12 秒；不把并集 `[12,15]` 当作两种分辨率都支持的组合。

- **🔴 连参考图必先审核(防白白烧钱)**:把参考图(image)连给下游生成节点(`smart-image.in-ref`/`in-image`、`smart-video.in-image`、`seedance-video.in-image`、`storyboard-gen.in-n{G}-image`)前,**必须先确认**:① 上游图节点**已出图**(`canvas_get_state` 看 status=success,或 `canvas_get_result` 拿到 URL)——没出图就连、下游 run 必失败或用旧图;② 参考图的**内容/比例/风格匹配**下游需求(`canvas_get_result` 看图判断);③ 🔴 **接线复核(务必做,run 前看 `refWiring`)——每张参考图都接到对的位置/镜组**:storyboard-gen 按"第 G 组 = 第 (3G-2)~(3G) 个分镜"把该组出场的角色/场景参考图连到对应 `in-n{G}-image`,smart-video/seedance 接到对应那个节点的 `in-image`(smart-video 视频参考 v2v 的**源视频**不是参考图、不归本条管——走 `in-video` 口,规则见下方 v2v 专条;其参考图仍走 `in-image`、照常按本条审核)。run 前用 `canvas_get_state` 看该生成节点的 **`refWiring`** 字段(每个图口连进来的参考图来源:`{port, index(=@图N), sourceModuleName, hasImage}`),逐条核对"@图N = 哪个来源节点"对不对、该有的参考图接上没、有没有接错口、整体覆盖是否齐;**把这份 @图N→来源 映射念给用户确认**(衔接 run 前确认模型+参数)。**发现缺漏 / 接错 / 拿不准 → 明确列出是哪个镜组缺什么或哪条接错,向用户说明并询问,绝不带着错连或缺图就跑。** ④ 🔴 **系统已硬拦截**:若 `canvas_validate` 报参考图相关 error(致 canRun=false)或 run 被拒(提示"提示词引用了第 N 张参考图但只连了 X 张")→ 这是**真错**,别盲目重试,按提示把参考图接上 / 把 @N 改成实际存在的编号再跑。⑤ 写提示词 **@图N 别瞎写**:以 `refWiring` 的 index 为准(connect 时也会回传分配到的编号),别凭记忆猜。 不匹配 / 有疑问 → **先向用户说明情况并获确认**,绝不盲目连线就跑生成浪费算力费用。
- **🔴 建节点必管位置(画布整洁不重叠)**:新建/批量建节点时——① `canvas_batch` 建多个时给每个节点合理 `position`(沿数据流上游→下游让 x 递增、每列间隔 ≥900 防横向重叠;同列多节点 y 错开 ≥300);② 往已有画布加节点前先 `canvas_get_state` 看现有节点坐标,新节点放空白处,**绝不压在现有节点上**;③ 建完一批或布局乱了,调 `canvas_auto_layout` 一键按关联组排齐(组内上游左/下游右、分支上下散开，无关组上下分区)。始终保持模块排序清晰、整齐,**不出现错乱、重叠**。
- **🔴 参考图必须先命名再连(自文档化画布,防连错镜组)**:每个参考图节点都要有**语义显示名**——① **你自己生成的图**在 `canvas_create_node`(及 `canvas_batch` 的 `create_node` op)直接传 `name`;② **用户上传 / 已存在的图节点**(未命名时全是同质的「图片」,看不出谁是谁)用 **`canvas_rename_node`**(入参 `{ nodeId, name }` 都必填)打标,如『角色-张三』『场景-咖啡馆』。拿不准某节点是哪张图 → `canvas_get_result` 看图判断,或念给用户确认后再命名。**不命名 → 你会分不清哪张图是谁、连错镜组,白白烧钱。** 🔴 护栏:`name` **仅显示**,`connect`/`set_prompt`/`set_params`/`run` 等一切操作仍用 `nodeId`,**绝不按 name 操作节点**(防幻觉)。
- **🔴 建完 / 跑完模块就立刻改名(必须,覆盖所有生成/操作节点)**:每 `canvas_create_node` 建一个节点、或 `canvas_run` 跑出结果后,**立即**用 `canvas_rename_node` 给该节点起一个**能一眼识别的语义名**(如『苏念-参考图』『分镜1-3-生图』『傅砚辞-定妆视频』)。理由:节点一多,同质的「图片」「Seedance 视频」会让你**连错 / 改错 / 跑错模块**——改名是消除歧义的硬手段,**不是可选**。与上一条"参考图必先命名再连"呼应(那条偏重连线前;这条覆盖所有生成/操作模块)。🔴 护栏同上:`name` **仅显示**,操作仍用 `nodeId`。
- **🔴 图口数 ≠ 参考图上限(一个口能接多张)**:`canvas_get_state` 里 image 输入口标了 `multi:true` 的,表示这个口能 **fan-in 接多条 image 边**(同一个口连多张参考图,**不限数量**,executor 收全集按 @图N 排序)——**别因为只看到 `in-image`/`in-ref` 两个口就以为最多两张**。实际用几张看模型(见该节点 `moduleHint`):smart-image api/即梦全用、rh-image 仅第1张;smart-video 多参/all-ref 全用、普通图生视频只第1张、视频参考(v2v)≤5张;seedance 全能参考最多9张;storyboard 每个 `in-n{G}-image` 接该镜组所有参考图。⚠️ 例外(不 fan-in 的口):smart-video 尾帧口 `in-image-last` 天然只1张(不带 `multi`),别往尾帧塞多张;smart-video 源视频口 `in-video`(视频参考 v2v 模式用)单口只接 1 段源视频、不支持 fan-in——参考图仍走 `in-image` 可 fan-in。
- **🔴 连对分镜(按 shotIds 把角色/场景落到对的镜组)**:storyboard-gen 的每个镜组口 `in-n{G}-image` 现在能从 `canvas_get_state` 的 `boardStatuses[].shotIds`(该镜组覆盖的分镜 id 列表)看到"镜组 G = 覆盖哪几个分镜"。连线时按:**角色 / 场景出现在哪些分镜 → 命中哪个镜组的 shotIds → 连到对应的 `in-n{G}-image`**(别再靠"第 G 组=第 (3G-2)~(3G) 镜"硬算,以 shotIds 实际命中为准)。
- **🔴 run 前核对(用 refWiring 逐条确认)**:run 前用 `canvas_get_state` 看生成节点的 **`refWiring`**(已带语义名 `sourceModuleName`)逐条核对 **@图N → 来源节点**,确认每张参考图都接到**对的口/镜组**、该有的接上没、有没有接错。**发现缺漏 / 接错 / 拿不准 → 先停下,明确列出哪个镜组缺什么 / 哪条接错,向用户说明并询问,绝不带着错连或缺图就跑。**

---

## 4. 关键陷阱

- **先查询本地实例合同**：`canvas_list_models` 对固定本地实例返回 `localRelay:{kind,metadataComplete,imageSizes或videoResolutions,ratios,durationsSec(视频),extraControls:[{key,label,min,max,step,defaultValue,integer}],referenceMediaCounts:{image,video,audio}}`，不包含内部节点、工作流、端点或秘密。`metadataComplete=false` 时先在本地中转同步实例，重新打开画布刷新脱敏镜像，不猜控件或素材数量。`localRelayParams` 使用 `extraControls` 给出的键和范围；三类素材数量是该实例精确槽数，`0` 表示无需该类素材。
- **本地视频／音频数组**：`smart-image` 的视频模式和 `smart-video` 可用 `canvas_set_params` 写 `referenceVideos`／`referenceAudios`。数组按顺序绑定槽位，整体替换，`[]` 清空；最多各 4 项，每项不超过 1048576 字符。只接受无用户名密码的公网 HTTP(S)、`/api/canvas-files/<project>/<单个key>` 短路径或对应视频／WAV／MP3 的 base64 data URL；其他本地 API、文件路径及脚本地址一律拒绝。大素材先上传画布后使用短路径，归属、精确槽数和真实文件类型仍在生成前核验。图片用现有图片连线，Seedance 用既有 `in-video`／`in-audio` 端口；未声明的节点不能写这些数组，数组也不能用于 `canvas_param_sweep`。
- **管理 API／云池实例**：`canvas_list_models` 返回最后同步目录；需要指定来源时传 `instanceSourceId`。读取所选行的 `modelRelay.contract` 和 `instanceProjection`，在 `canvas_set_params` 顶层原样带上 `instanceProjection`，再沿原 `canvas_run` 运行。客户端在 apply 和新调用前复核当前来源、修订和镜像状态；pending 或漂移暂停旧目录调用。遵循 `parameterTiers` 联合档位和 `conditionalMediaRules` 条件素材，`localRelayParams` 只使用已声明控件，缺省值由同一合同注入，旧本机图像工作流仍不开放附加控件。保留确认、预算、授权与项目门禁，关闭页面不重提已接纳任务；未知只核对原单或恢复下载。

- **本地中转的附加数字控件**：`smart-image`、`smart-video`、`seedance-video` 可通过 `canvas_set_params` 设置 `localRelayParams`。只填写所选实例已确认附加控件的键，不推测 ComfyUI 节点编号。该表整体替换，`{}` 清除本节点覆盖；最多 16 项，键以字母开头、只含字母/数字/下划线且不超过 40 字符，值必须为有限数字且绝对值不超过 `1e9`，总 JSON 不超过 4096 字符；禁止敏感键和原型键。工作流声明的实际范围仍在生成前校验。标准画幅、分辨率、时长用原有字段，素材用原有输入端口；不能在此写端点、凭据、素材 URL 或映射，也不支持 `canvas_param_sweep`。设置参数不会触发生成，现有 `canvas_run` 确认与权限要求继续生效。
- **🔴 文本模块(text-input)≠ 提示词输入框,别混淆**:
  - **文本模块**(`builtin:text-input`「文本」)是**内容载体**——把**小说 / 剧本 / 上游输出结果**等长文本写进 `params.content`,经 `out-text` 口传给下游模块(如 script-extract 拆实体、storyboard-gen 拆分镜)。它的正文是 `content`**不是** prompt(`prompt` 字段只是「附加指令」,高频陷阱)。
  - **提示词输入框**是 smart-image / smart-video / seedance-video 等**生成节点自身的 `prompt` 字段**(用 `canvas_set_prompt` 写),才是写生图 / 生视频提示词的地方。
  - **别搞混**:整篇小说 / 剧本 / 结果 → 走文本模块 `content` 往下游传;给某生成节点写提示词 → 直接 `canvas_set_prompt` 设该节点 `prompt`,别拿 text-input 当某节点的提示词框乱塞、也别把长文塞进生成节点的 prompt。
- **🔴 smart-video 视频参考(v2v)模式必接源视频**:`mode=v2v` 是视频转视频——须把 1 段已出片的源视频(上游节点的 `out-video`)接到 `smart-video.in-video`「源视频」口(video→video,单口只 1 段、不 fan-in),**缺源视频跑不了**;参考图(≤5 张)仍走 `in-image` 口可 fan-in。videoModelId 选支持 v2v 的型号(如 omni-fast-v2v,见 `canvas_list_models`)。
- **动态端口**:`script-extract` / `storyboard-gen` 的输出口要**跑完**才生成(`out-n1-text`…);含它们的链路必须分阶段:建+连+跑 → `get_state` 看抽出几个口 → 再 batch 建下游。
- **🔴 镜组图口 = 每镜组一个,口数 = 镜组数 = ⌈分镜数/3⌉**:`storyboard-gen` 拆镜后口数固定(14 镜=5 镜组,只有 `in-n1`~`in-n5`,**没有 `in-n6/in-n7` 是正常的,不是 bug**)。端口对应**镜组**、不对应参考图张数。① 每个 `in-n{G}-image` 可接**多张**参考图(连多条 image 边到同一个口,union 去重、按 @图N 排序);② 参考图按**所属镜组**归并——以 `canvas_get_state` 的 `boardStatuses[].shotIds`(镜组覆盖的分镜 id 列表)为准:角色/场景出现在哪些分镜 → 命中哪个镜组 → 多张参考图都连到该组同一个 `in-n{G}-image`(别只靠"第 G 组=第 (3G-2)~(3G) 镜"硬算)。参考图比镜组多很正常,别去找更多的口。
- **🔴 storyboard-gen 两步出图(run ≠ 出图)**:首次 `canvas_run` 只 AI 拆镜、**不出板图**;出板图走 `canvas_run` 的网关化生成参数——批量出全部 = `canvas_run(nodeId, generateMode:"all")`,单镜组/子集出图与重生**同一入口** = `canvas_run(nodeId, boardIds:["BOARD_xx"])`(boardId 见 `canvas_get_state` 的 boardStatuses;拆镜后 idle 占位条目即可用,首次出图不必先 generateMode=all;两参互斥)。`generateMode`/`regenerateMode` **禁止 `canvas_set_params`**(防绕预算门烧钱,设了必拒),只能经 canvas_run 运行时触发(走确认/预算门 + 真实估价)。镜组按钮完整配方见第 6 节。
- **连线 dataType 要匹配**:text→text / image→image / video→video。
- **端口 id 要真实**:用 `get_state` / bootstrap 返回的真实端口 id,别猜。
- **disconnect 参数键**是 `sourceId/sourcePort/targetId/targetPort`(不是 sourceNodeId/sourceHandle)。

---

## 5. 常见链路(端口已核实)

```
文生图:          text-input(content=提示词) → smart-image
文生图→视频:     text-input → smart-image → smart-video(图生视频 mode=image2video) [+ text-input → smart-video.in-text 动作词]
视频参考(v2v):   源视频节点.out-video → smart-video.in-video(mode=v2v;源视频单口只 1 段) [+ 参考图 → smart-video.in-image ≤5 / text-input → in-text]
小说→批量参考图:  text-input(小说) → script-extract →[跑]→ out-nX-text → 各 smart-image
seedance 生视频:  text-input + 参考图 → seedance-video(apiMode 选渠道,seedanceModel 选版本)
视频后处理:       出视频节点 → video-remove-subtitles/video-enhance(单口 input/output)
智能分镜编排:     text-input(剧本)+参考图集 → storyboard-orchestrator →[跑=出方案]→ 用户点「铺到画布」→ 每镜一个 smart-image(不自动出图)
```

更多见 `canvas_bootstrap` 返回的 workflows。

---

## 6. 图片/视频节点工具栏 → MCP 调用速查

画布上图片/视频节点的工具栏功能,智能体按下表调用(除 `canvas_run` 外全部零花钱)。端口 id 以 bootstrap/get_state 返回的真实值为准。

### 已能调(用现有工具组合)
| 工具栏功能 | MCP 配方 |
|---|---|
| 视频超分 / 去字幕 / 去水印一键 | `create_node`(builtin:video-superres / video-remove-subtitles / video-remove-watermark)+ `connect_nodes` 连视频上游(这些模块是单口 input/output)+ `set_params` + `run` |
| 去字幕/去水印 框选区域 | `canvas_set_params` 设对象参数 `region:{y1,y2,x1,x2}`(0~1 比例坐标;字幕带只需 y1/y2,提交时强制整宽)。region 已在模块 paramsSchema,无专用工具 |
| 高清修复 / 特征抹除 / 场景图 / 画框 / 拼图 | `create_node`(builtin:rh-upscale / media-deai / scene-image / picture-frame / image-puzzle)+ 连线 + `set_params` + `run` |
| 人脸遮罩(参考图人脸遮罩处理,图入图出) | `create_node`(builtin:face-mask)+ 连上游图节点.output→in-image + `run`(无参数、纯本地零花钱)+ `get_result` 看遮罩图;多张参考图建多个各连一张 |
| seedance 视频设置(apiMode 渠道/seedanceModel 模型/ratio 比例/quality 画质/duration 时长/referenceMode 参考模式) | `canvas_set_params`;提示词用 `canvas_set_prompt` |
| 复制节点 | `canvas_duplicate` |
| 放参考图 | `canvas_upload_asset`(本地绝对路径或 URL 一步上画布)或 `connect_nodes` 连上游图节点;图在**别的画布** → `canvas_copy_reference_from`(见下方新工具) |

### 新工具(本批新增)
| 工具栏功能 | MCP 工具 |
|---|---|
| 清结果重跑 | `canvas_reset_node_result`:清 result、状态回 idle,改参后 `canvas_run` 重跑 |
| 视频截帧 → 图片节点 | `canvas_video_capture_frame`:timeSeconds 秒(-1=尾帧);异步触发,完成后 `get_state` 可见源节点右侧新增 frame-* 图片节点,可连下游当参考图 |
| 看图判质量(vision 自评) | `canvas_result_review`:action=view(零花钱拿 ≤256px 缩略图直接看)/ describe(¥0.1 客观描述+瑕疵)/ judge(¥0.1 VIEScore 双轴评分+matchesIntent+verdict+建议)。把『跑→看→改』闭环升级成真看图判好坏;describe/judge 需先配 LLM 视觉模型 + 带 confirmToken,视频用 frameSeconds 抽帧;按需调、绝不每次 run 后自动 judge |
| 停止生成(⏹) | `canvas_abort_node(nodeId)`:中断该节点正在跑的生成,不删节点不丢已有结果;storyboard 多镜组并发时按 nodeId 全停(无单镜组停);零花钱 |
| 跨画布复制参考图 | `canvas_copy_reference_from`:把**其他画布**里的一张参考图复制进当前画布,落成参考图节点(只落节点不自动接线),零花钱。典型用法:① `canvas_get_state`(不带 projectId,发现模式)列出所有画布 → 定位那张图所在画布及其节点 id → ② `canvas_copy_reference_from(sourceCanvasId, sourceNodeId)` 复制进来(可选 nodeId/position/canvasId)→ ③ 需接给生成节点再 `canvas_connect_nodes` 连到 smart-image.in-ref / smart-video.in-image。v1 仅同源 `/api/canvas-files/...` 托管图(远程/dataURL 会被拒,提示先落盘) |
| 跨画布浏览取图/视频 | `canvas_list_assets`:一次看**某画布**有哪些图/视频产出 + URL,挑参考素材用。典型用法:① `canvas_get_state`(不带 canvasId,发现模式)列出所有画布定位目标画布 → ② `canvas_list_assets(canvasId)` 一次拿该画布全部图/视频节点 + URL(只读零花钱;大 dataURL 不回内容只给提示)→ ③ **要图**就 `canvas_copy_reference_from(sourceCanvasId=该画布, sourceNodeId)` 复制进当前画布再连下游;**要视频**就直接用其 URL。比逐个 `canvas_get_result` 翻节点快——一次列清整画布的可用素材 |

### 故事板(storyboard-gen)镜组按钮 → MCP 配方
| 镜组按钮 | MCP 配方 |
|---|---|
| 单镜组出图 / 重生(⟳) | `canvas_run(nodeId, boardIds:["BOARD_01"])`——首次出图与重生**同一入口**;boardId 从 `canvas_get_state` 的 boardStatuses 拿,拆镜后 idle 占位条目即可用 |
| 批量出图(全部镜组) | `canvas_run(nodeId, generateMode:"all")`(与 boardIds 互斥) |
| 停止生成(⏹) | `canvas_abort_node(nodeId)`(全停该节点所有 in-flight 镜组) |
| 下载板图 / 推出画布 | 先 `canvas_get_result(nodeId)` 拿各镜组板图 URL(返回 `boards:[{boardId,status,imageUrl}]`)→ 推出画布 = `canvas_upload_asset(source=imageUrl)` 把板图建成画布图片节点;下载 = 直接取该 imageUrl |
| 全部镜组 → Seedance 视频 | 逐镜组 `canvas_batch` 建 `builtin:seedance-video` + `canvas_connect_nodes` 连 `out-n{G}-board → in-image`、`out-n{G}-prompt → in-text`(seedance 参数详见 feicai-storyboard-v3 SOP 的 P3) |

### 智能分镜编排(storyboard-orchestrator)→ MCP 配方
两段式:`canvas_run` 只**分析出方案**(走用户自配 LLM 实例,不生图;MCP 侧 run 落 ¥0.5 兜底确认门);「铺到画布」「铺视频节点」「生成参考图」都是节点面板上的**用户按钮,无对应 MCP 工具**——铺出的 smart-image 才是真正花钱出图的节点(⚠️ 三期的「生成参考图」铺出后会**自动出图**,其余均不自动跑)。
| 操作 | MCP 配方 |
|---|---|
| 搭链 | `canvas_batch`:create text-input(剧本写 `content`) + create `builtin:storyboard-orchestrator` + connect text-input.out-text→in-text;各参考图节点(已出图、🔴 先 `canvas_rename_node` 语义命名如『角色-张三』,**节点名即实体匹配依据**)图输出口逐条连→`in-n1-image`(集合口,fan-in 收多条边) |
| 选择分析模型(可选) | 先 `canvas_list_models` 从 llm 选择激活实例 id，再 `canvas_set_params` 写 `storyboard-orchestrator.llmInstanceId`；留空保持编排现有的主实例→备用实例自动回退，显式选择则固定单实例；若所选实例被删除、停用、缺少配置，或任务期间实例配置发生变化，任务会停止且不会换模型 |
| 分析(阶段一) | `canvas_run`:AI 拆分镜(台词逐字「」保留)+ 实体↔参考图匹配(命名优先→LLM 看图兜底→仍未命中标 unmatched,面板可手动改),方案落节点面板;`canvas_set_params` 可调 `orchMode`(structured 结构化·默认 / free 自由模板:两步生成——按节点 ⚙ 弹窗「自由创作模板」自由创作→内部契约结构化匹配,每镜提示词 AI 直出,`stylePrompt` 与宫格铁律不再拼装;🔴 模板正文只能用户在 ⚙ 提示词弹窗手编,无 MCP 工具可读写)、`promptLanguage`(`zh/en/ja/ko/custom`;custom 时另填 `promptCustomLanguage`=中文语言名称，如 `法语`、`西班牙语（墨西哥）`;改语言后必须重新分析)、`gridMode`(grid9/grid4/single 每镜九宫格/四宫格/单幅)、`stylePrompt`(风格词,free 模式不生效)、`shotCountHint`(0=自动 8–12)、`aspectRatio`(透传生图节点) |
| 生成参考图(三期~九期·可选) | 🆕 八期起分析完成即在面板匹配表**纯登记全实体「待生成」占位行**(纯方案数据,🔴 画布上不铺任何节点、不出图不花钱);行内按钮逐个生成(一击直发,此时才建 smart-image 节点——🆕 九期起提示词先经**二阶段 LLM 扩写**:按实体类型取弹窗三档 system 把实体特征扩写成与「剧本抽取」参考图同级的完整规格图提示词[走用户自配 LLM 实例;仅 `storyboard-orchestrator.llmInstanceId` 留空的自动模式下，普通扩写失败才本地回落简版拼装；显式选择实例时任何失败，或任务期间实例配置 revision(版本)发生变化，都会立即停止，不铺 smart-image 节点、也不自动发起付费出图],再连回 `in-n1-image`、占位行原地变真图行)或行内「替换」直接换画布已有图(零花钱);🔴 无 MCP 工具,节点面板用户按钮(与「铺到画布」「铺视频节点」同级):把**尚未出图**的待生成/已删实体批量生成(⚠️ 消耗生图额度,提醒用户知情再点;已出图的绝不重跑,重出走行内「重新生成」二击确认);同实体幂等不重复铺、已有用户自备匹配参考图的实体跳过;🆕 四期起分析方案给每个实体登记类型(角色/场景/道具),场景与关键道具也全量登记进实体特征表与各镜出场实体(参考图提取更完整),出图按类型分档:角色=面部特写+全身正/侧/背三视图设定图、场景=单幅全景空镜(刻意不做多视角/多面板拼版,避免重复参考图)、道具=单图内多角度设定表;⚠️ 四期前分析出的旧方案无实体类型登记 → 生成参考图全部走通用档(三期行为),重新分析一次才有类型分档与场景/道具补全;参考图画法走 ⚙ 提示词弹窗,原「参考图生成指导」一项已按类型拆为「角色三视图指导」「场景图指导」「道具图指导」三项(同弹窗其它项一样只能用户手编、无 MCP 工具可读写);free 自由模板模式全兼容(参考图生成用登记的实体特征表+全局段落 header 保风格锁定);🆕 五期起匹配表缩略图实时显示参考图节点当前出图,每行新增「重新生成」小按钮(仅智能图片类参考图节点显示,二击确认后重跑该节点出新图、同样消耗生图额度);另增「未配图实体」区列出方案里尚无参考图的实体(带类型徽章),可逐实体单个补生成(语义同「生成参考图」批量:按类型分档、连回 `in-n1-image`、预登记匹配、自动出图花钱、幂等,适合连续剧补缺参考图);🆕 六期起匹配表每行另有「替换」按钮(所有行含「已删除」行):弹层选画布上已有的图节点(已出图/已上传且未被匹配表占用)原位顶替该实体位置——自动换连线、实体归属与 @ 编号顺序不变,不重跑分析不重新出图零花钱——均为面板用户按钮/纯 UI 展示,无新增 MCP 工具与可设参数 |
| 铺到画布(阶段二) | 🔴 无 MCP 工具:提醒用户在节点面板核对/编辑方案后点「铺到画布」——每镜 spawn 一个 smart-image(名=分镜NN·标题,prompt 已内联 @N 参考图引用,@N 顺序=连线顺序),重复铺自动跳过(幂等),**不自动出图** |
| 出图 | 铺开后 `canvas_get_state` 看新增 smart-image → 逐个 `canvas_run` / `canvas_run_chain`(照常确认+计费);🔴 别增删/重排这些 spawn 节点的参考图边(@N 与边序一一对应,动了会错位) |
| 铺视频节点(二期/三期) | `canvas_set_params` 设 `videoModule` 二选一(smart-video 普通视频·图生视频模式 约¥0.5+/镜、可选任意视频模型实例 / seedance-video Seedance视频·全能参考、通道(即梦cookie/火山/贞贞/飞彩)与2.0系列模型档在节点上自选、按所选通道计价;两档都无首尾帧;🔴 无默认,未选时按钮禁用);🆕 三期可再设 `videoRefSource` 选画面来源:`board` 分镜图(默认,@1=本镜/首镜分镜图作构图主参考、构图最稳,须先「铺到画布」出分镜图)/ `direct` 参考图直连(跳过分镜图,视频节点直连该镜/该合集命中的实体参考图,@1 起即参考图,无命中参考图的镜/合集跳过;想省掉分镜图步骤、让视频模型直接按实体参考图起片时选,典型流=分析→「生成参考图」(或用户自备参考图)→直接铺视频,全程不出分镜图)→ 🔴 无 MCP 工具:用户在面板点「铺视频节点」——每镜 spawn 一个视频节点(board 档仅对已铺分镜图的镜:@1=本镜分镜图、@2+ 按匹配表连参考图、无分镜图的镜跳过;**台词逐字进 prompt**,不自动跑),重复铺幂等;🆕 free 自由模板模式且方案带合集结构时粒度自动变为**每合集一个视频节点**(合集内多镜按【镜头N】连拍合并进一个 prompt,board 档 @1=合集首镜分镜图、@2+=组内参考图并集去重,direct 档 @1 起即组内命中参考图并集、无命中合集跳过,节点名「合集NN·标题(Ns)」,幂等按合集号);之后逐个 `canvas_run` 出片(board 档需上游分镜图已出图;同样别动其连线) |

### 视频翻拍(remake-script)→ MCP 配方
两段式:`canvas_run` 按合集分别**反推出四节翻拍脚本**(合集粒度=15 秒或 30 秒,在**节点面板**选、新面板默认 30 秒,写进节点参数 `analysisSegmentSec`,须在分段反推前定好)(场景/人物/台词时间线/成品提示词,走用户自配 LLM 实例按量计费,确认窗显示新增调用数);系统提示要求成品提示词尽可能 100% 还原当前视频片段，写成不带分幕编号的连续电影叙事，逐字保留每句完整台词、说话人、发声方式和时间点，并按真实顺序描述镜头、动作、表情、声音及可见文字，不把原片改写成摘要，也不补写原片不存在的信息；这是模型生成要求，不会因内容缺项自动重试。「生成参考图」「铺出当前合集视频节点」都是节点面板上的**用户按钮,无对应 MCP 工具**。
| 操作 | MCP 配方 |
|---|---|
| 搭链 | `canvas_upload_asset(source=视频路径/URL)` 落成视频展示节点 → create `builtin:remake-script` + connect 视频节点.out-video→in-video(画布已出视频的节点也可直连;或 create 后引导用户在节点面板上传：普通入口≤40MB，企业入口>40MB且≤1GB);可选把已出图节点逐条连→`in-n1-image`(参考图集合口,fan-in) |
| 反推 | 先 `canvas_list_models` 从 llm 选激活实例，(可选)`canvas_set_params` 写 `llmInstanceId`、`instruction`；留空用当前主实例，显式实例失效 fail-closed、绝不跨实例重试 → `canvas_run`:产出脚本写 `params.script`,成品提示词经 `out-n1-prompt` 传下游;异步任务中断可续(重跑自动续查,不重复计费)。大文件云上传仍须用户在节点面板操作，无 MCP 上传工具 |
| 读/改脚本 | `canvas_get_state` 读 `params.script` 核对;🔴 script 不在 agent 可写 schema(`canvas_set_params` 写不了,防直写破坏结构)——要改引导用户在节点面板编辑:成品提示词可直接粘贴/编辑并在失焦时保存;之后再改场景/人物/时间线等结构字段会重新装配并覆盖手工成品提示词 |
| 参考图 | 🔴 无 MCP 工具,面板行内操作:反推完每个角色/场景一行**默认已带原片截图**(自动抽帧,免费即用、出片时自动落免费图片展示节点连线);「重新生成」= AI 重绘——垫原片帧+按分镜编排三档规格扩写(角色三视图/场景空镜/道具设定表)+`refStylePrompt` 风格后缀(set_params 可写),消耗生图额度提醒用户知情;「替换 ▾」直接选画布已有图节点(零花钱);「删除」清截图/「移除」只断关联不删节点 |
| 出片 | 🔴 无 MCP 工具,用户先在合集分页器选中目标合集，再点「铺出当前合集视频节点」：只 spawn/同步该合集的一个 seedance-video；成品提示词会按最终参考边序主动补齐 `@N（角色/场景/道具名：名称）`，模型通道仍由用户自选，时长默认本合集秒数但可按模型能力调整，**不自动出片**。之后逐个 `canvas_run` 出片(照常确认+计费;🔴 别增删/重排其参考图边,连图顺序与 @ 编号一一对应)。红线:反推与出片各有一道确认,绝不静默批量出片 |

### 参考图工坊(ref-forge)→ MCP 配方
两段式:`canvas_run` 只**提取实体清单**(人物/场景/道具,走用户自配 LLM 实例按量计费,典型 ¥0.05-0.2/次即 ¥0.1 口径,一道确认);「批量扩写并铺节点」「铺生图节点」都是节点面板上的**用户按钮,无对应 MCP 工具**(也无任何可设的批量出图参数),且铺出的生图节点**不自动出图**。
| 操作 | MCP 配方 |
|---|---|
| 搭链 | 双源二选一(🔴 都连时视频优先):视频源=`canvas_upload_asset(source=视频路径/URL)` 落成视频展示节点 → create `builtin:ref-forge` + connect 视频节点.out-video→`in-video`(画布已出视频的节点也可直连;或 create 后引导用户在面板上传:普通≤50MB、企业>50MB且≤1GB；两档均先压到最高480p并切15秒物理段，企业素材2小时后自动删除);文本源=create text-input(剧本写 `content`)+ connect out-text→`in-n1-text` |
| 提取 | (可选)先 `canvas_list_models` 从 llm 选激活实例，再 `canvas_set_params` 写 `llmInstanceId`；留空用当前主实例，显式实例失效会 fail-closed 且不跨实例重试。也可写 `instruction`、`refStylePrompt`→ `canvas_run`:逐段提取人物/场景/道具实体清单写 `params.entities`；每个尚需提交的15秒段按一次调用估价，中断可续且 ready/running 段不重复计费；企业段只把 assetId 持久化，服务端换取短时公网 URL 后交给模型，URL 不写画布；视频源另自动抽原片帧当截图参考(免费) |
| 读实体 | `canvas_get_state` 读 `params.entities` 核对(人物/场景/道具三组;外观描述可在面板行内编辑,改完面板会提示同步提示词) |
| 铺节点/出图 | 🔴 无 MCP 工具,面板按钮:行内「铺生图节点」=对单个实体扩写提示词并 spawn 一个 smart-image(视频源垫原片帧);「批量扩写并铺节点」=把未关联实体全部扩写后一次性网格铺开——**都不自动出图**;引导用户在面板点,铺出后逐个 `canvas_run` 出图(照常确认+计费)。红线:工坊只提取实体与铺节点,绝不自动批量出图;出图逐节点走既有确认计费 |

### 不可自动化(需用户手动操作,智能体不支持)
- 涂鸦编辑 / 人脸过审 / 姿势控制(PoseStudio)/ 提示词库拖拽 —— 要等效效果直接 `canvas_set_prompt` / `canvas_upload_asset`。
- 节点缩略 / 折叠 / 分镜比例等纯显示态(`_thumbnail`/`_gridFolded`/`_gridRatio`):`_` 前缀内部字段被参数白名单拒,set_params 设不了,属 UI 交互态无需智能体管。

---

## 7. 🧱 方块世界搭景出参考图(配方)

方块世界 = 方块搭景摄影棚:用方块快速搭一个三维场景、摆好机位拍照,产出「方块世界参考」图片节点,接下游 smart-image / 图生视频当构图/布局参考。全程零花钱(capture 也不花钱,花钱的仍只有下游 `canvas_run`)。

典型流:
1. `canvas_voxel_open` 打开方块世界(下发命令前必调;紧跟着发不丢,画布侧缓冲、就绪后按序回放)
2. `canvas_voxel_commands` 搭景:**fill 起地基 / hollow 起房 → set 点缀细节(门窗/装饰)→ add_camera 摆 1-3 个机位**(大结构绝不逐块 set,fill/hollow 省 token 又快)
3. `canvas_voxel_get_scene` 验证:看 `lastApply`(applied 生效条数 + skipped 被跳过项及 reason)确认哪些生效、`blockCounts` 核对方块计数、`cameras` 拿机位真实 id——按 reason 修正重发,别盲目重试
4. `canvas_voxel_capture` 逐机位拍照(`{cameraId}`;异步,完成后 `canvas_get_state` 可见「方块世界参考」图片节点)
5. 参考图节点连 smart-image / smart-video / seedance 当参考图,`canvas_run` 出正片

坐标/id 速查:方块坐标一律整数格 [x,y,z],x∈[-64,64) y∈[0,64) z∈[-64,64),原点=场景中心,y=0 是初始草地层(一格草方块)、往上搭从 y=1 开始;方块 id:1草 2泥土 3石头 4木板 5原木 6红砖 7石砖 8沙子 9雪块 10玻璃(透明) 11树叶 12水(透明) 13-20 白/黑/红/蓝/黄/绿/橙/紫混凝土。

### few-shot:8宽×5高×6深 木板小屋 + 门窗 + 坡屋顶 + 两机位(一批 6 条)

```json
{ "commands": [
  { "op": "fill", "from": [-4, 1, -3], "to": [3, 3, 2], "id": 4, "hollow": true },
  { "op": "fill", "from": [-4, 4, -3], "to": [3, 4, 2], "id": 6 },
  { "op": "fill", "from": [-4, 5, -2], "to": [3, 5, 1], "id": 6 },
  { "op": "set", "blocks": [[0, 1, -3, 0], [0, 2, -3, 0], [-2, 2, -3, 10], [2, 2, -3, 10]] },
  { "op": "add_camera", "position": [10, 6, -12], "target": [0, 2, 0], "name": "正面斜侧", "aspect": "16:9" },
  { "op": "add_camera", "position": [-12, 10, 8], "target": [0, 2, 0], "name": "背侧俯瞰", "aspect": "16:9" }
] }
```

- 第 1 条:木板(id 4)小屋外壳——x -4..3 全宽 8、y 1..3 墙体、z -3..2 全深 6,`hollow:true` 只留外壳
- 第 2、3 条:红砖(id 6)屋顶——y=4 满铺一层,y=5 z 两侧各收 1 格成坡形(小屋总高 5:y 1..5)
- 第 4 条:前墙(z=-3)开门窗——x=0 挖 1×2 门洞(id 0 删格),x=±2 嵌玻璃窗(id 10)
- 第 5、6 条:两个 16:9 机位,都注视屋子中心附近 [0,2,0]——正面斜侧平视 + 背侧高角俯瞰
- 下发后 `canvas_voxel_get_scene`:`lastApply.applied` 应为 6、`blockCounts` 里 4(木板)/6(红砖)/10(玻璃)有数、`cameras` 有两个机位 id → 逐机位 `canvas_voxel_capture({cameraId})` 出两张参考图
