# 飞彩推文外部智能体 CLI

此入口让外部终端智能体经 MCP 操作飞彩推文，供已获授权的企业版账号使用。企业配对后，智能体可直接计划并执行常规编辑和付费生成，无需逐计划人工审批。推文页面第一版需要保持打开，以执行已有页面业务。设置页「连接 CLI」统一管理画布与推文的连接、状态、结果和任务控制，只在真实破坏性变更时保留精确删除/恢复确认。

工具是否存在与业务是否可用分开判断。`tuiwen_capabilities` 返回每项动作的实际 schema、执行位置、条件和阻断原因；`blocked` 项不能计入已完成能力，更不能改走旧 `invoke` 绕过限制。

## 连接配置

使用 Node.js 22.13.0 或更高版本。MCP 客户端以 stdio 启动：

```json
{
  "mcpServers": {
    "feicai-tuiwen": {
      "command": "node",
      "args": ["/absolute/path/mcp-bridge/feicai-tuiwen-mcp.mjs"],
      "env": {
        "FEICAI_BASE": "http://127.0.0.1:3000",
        "FEICAI_PAIR_TOKEN": "<pair-token-from-feicai-settings>"
      }
    }
  }
}
```

推荐在设置页选择「推文」后复制配置；仍由同一个配对管理入口生成或吊销令牌。吊销会影响该令牌连接的画布和推文，不能把推文配置另配成普通账号入口。Windows 的 `args` 使用实际文件路径并按 JSON 转义反斜杠，例如 `"C:\\Feicai\\mcp-bridge\\feicai-tuiwen-mcp.mjs"`；Mac 例如 `"/Applications/Feicai/mcp-bridge/feicai-tuiwen-mcp.mjs"`。示例根目录需替换成真实安装位置，不依赖终端工作目录。

系统 Node 不符合版本时，可把 `command` 改为安装目录中已验证的内置 Node，路径按平台选择，不能在不同架构间照搬：

```text
Platform       Relative command path
-------------  -------------------------------------------------------
Windows x64    runtime/node-bundle/v22.23.2/win32-x64/node.exe
Mac arm64      runtime/node-bundle/v22.23.2/darwin-arm64/node
Mac x64        runtime/node-bundle/v22.23.2/darwin-x64/node
```

复制交付时同时保留 `lib/tuiwen-tools.mjs`、`lib/tuiwen-http.mjs`、`lib/tuiwen-stdio.mjs` 和本指南，不能只复制入口脚本。以上是配置模板；配对令牌由用户安全填入客户端配置，不发到聊天、源码、命令参数或普通日志。

`FEICAI_BASE` 固定一个实际工作台或多开槽位的本机端口，仅支持根路径的 HTTP `127.0.0.1`、`localhost` 或 `[::1]` 地址。`localhost` 仅尝试固定的本机 IPv4/IPv6 地址，不依赖 DNS/hosts，也不重复发送 HTTP 业务请求；不接受远端域名、URL 用户信息、路径、查询串或重定向。首次 `tuiwen_bootstrap` 绑定服务端返回的实例、企业权益和连接身份，后续请求携带 `X-Feicai-Instance-Id`，不能在同一 MCP 会话静默切到别的槽位。

可选 `FEICAI_INSTANCE_ID` 预先固定已读到的实例 ID，防止首次连接就选错。`FEICAI_TUIWEN_TIMEOUT_MS` 默认 `35000`，仅允许 `1000` 至 `60000`；将其设得短于 `waitMs` 会提前结束本地等待。实例 ID 来源是服务端受验数据根与品牌，不能用来代替配对授权。配对/实例/连接无效时按错误 `nextAction` 处理，重新确认实例后重连；不通过修改令牌或自报权益绕过后端检查。

## 10 个工具与 HTTP 映射

所有路径都位于 `/api/agent/tuiwen/v1`。列表使用 `cursor`、`limit`，每页 `1..100`；根据 `pagination.nextCursor` 续读，不把第一页当作全量。

```text
MCP tool                  Mode / input          Method  Resource
------------------------  --------------------  ------  --------------------------------------
tuiwen_bootstrap          default / bootstrap   GET     /bootstrap
tuiwen_bootstrap          resource=projects     GET     /projects
tuiwen_bootstrap          resource=consumers    GET     /projects/{projectId}/consumers
tuiwen_get_state          projectId             GET     /projects/{projectId}/state
tuiwen_capabilities       optional projectId    GET     /capabilities
tuiwen_list_models        projectId + kind?     GET     /models
tuiwen_plan_action        mode=create           POST    /plans
tuiwen_plan_action        mode=get               GET     /plans/{planId}
tuiwen_execute_action     planId + revision     POST    /operations
tuiwen_get_operation      view=status/default   GET     /operations/{operationId}
tuiwen_get_operation      view=recovery         GET     /operations/{operationId}/recovery
tuiwen_get_operation      projectId             GET     /operations
tuiwen_await_operation    operationId           GET     /operations/{operationId}/events
tuiwen_cancel_operation   mode=pause            POST    /operations/{operationId}/controls
tuiwen_cancel_operation   mode=resume           POST    /operations/{operationId}/controls
tuiwen_cancel_operation   mode=cancel/default   POST    /operations/{operationId}/controls
tuiwen_get_asset          assetId               GET     /assets/{assetId}
tuiwen_get_asset          projectId             GET     /projects/{projectId}/assets
```

首次必须调用 `tuiwen_bootstrap`，且工作台必须已经打开唯一的推文活动项目；没有活动推文页、同时打开多个推文项目，或传入的 `projectId` 与活动项目不一致，都会在第一道门禁被拒绝。bootstrap 返回 `activeProjectId`，之后所有目标项目都必须等于它；不能去设置页面另选历史项目。当前 bootstrap 返回 `schemaVersion/instanceId/connectionId/enterprise/activeProjectId` 及只含活动项目的 `projects/consumers` 分页资源。`resource=consumers` 必须显式提供活动项目；`get_state` 的 `fields` 使用字段名数组，桥映射为 HTTP 逗号分隔查询，例如 `['storyboards','bindings']`。`episodeId`、`storyboardId`、`sinceRevision` 和分页参数对应专用查询，不使用数组位置定位长期任务。状态的 `episodes/storyboards/entities/bindings/assets` 等字段各自带分页，按所读字段的游标继续查询。

查询单条 operation/asset 时可以额外提供 `projectId`；桥会检查返回归属。即使未提供额外归属提示，服务端仍必须验证连接真实项目 scope。新建项目计划产生的 operation 仍归属被冻结的来源页面：它的 `projectId` 是预留的新项目标识，`sourceProjectId` 才是来源活动项目，两者都通过桥的归属检查；与该 operation 的 `projectId`、`sourceProjectId` 都不同的项目仍被拒绝。计划内若存在显式 `arguments.projectId`，必须与 `target.projectId` 一致。空选择数组不能表示“全选”；批量选择含义按能力 schema 明确填写。

## 正确执行顺序

```text
Bootstrap -> State / Capabilities / Models -> Create Plan
                                                  |
                                    Server automatic approval
                                                  |
                                 Execute -> Events -> Saved assets

Only real destructive deletions:
Create Plan -> Exact deletion / recovery confirmation -> Execute
```

1. 读取实例、连接、项目、页面消费者、能力和模型目录，复用当前项目已配置的模型与明确任务范围。仅当缺少无法从现状确定的关键范围/参数时询问；不把创建每份计划变成一次人工作业。
2. `tuiwen_get_state` 获取稳定 ID 和最新 `scriptRevision`。`tuiwen_plan_action` 的 `request` 使用 `schemaVersion:1`、明确 `targetKind/target`、版本前提、能力返回的动作 schema、预算和意图。
3. 预算默认**不设金额上限**：使用 `currency:"CNY"`，`maxCnyMicros` 省略或显式 `null`；不要擅自填入金额额度。`maxGenerations/maxRegenerations` 仍按明确范围准备并冻结整数数量。若以后用户另行指定金额上限，可用整数 `maxCnyMicros`，`1000000` 表示人民币 1 元。计划用于后台校验、预演与审计；企业配对授权下，普通/付费计划创建后由服务端自动批准，不要求再点击审批按钮。
4. 新计划返回 `status:"approved"`、`approvalMode:"automatic"`、`approvalSource:"verified_enterprise_pairing"`；旧 `legacy_ui` 仅作历史兼容。读取 `requiresSeparateDeletionConfirmation/blockingCodes`，不能只凭 approved 跳过真实删除确认。常规修改文案、设置、导入新内容和模型生成无需人工 nonce，直接执行；只有服务端列出真实破坏性 `deletions`，例如删除、恢复、替换已有真实数据，才需列清精确目标、完整备份和恢复方法并取得独立确认。不能因动作名称带“修改”就额外申请确认，也不能跳过服务端明确的删除门禁。此桥没有审批工具，不接受 `approved`、`permissionLevel`、cookie、供应商密钥等自报字段。
5. 自动批准后，`tuiwen_execute_action` 直接使用原 `planId`、`planRevision`、稳定 `idempotencyKey` 和可选 `consumerId`。桥以 `planRevision` 生成强 `If-Match` 头；服务端继续核企业配对、scope、参数、数量、版本和一次性派发，之后返回持久操作。`mode:get` 仅供查询原计划，不是强制人工审批步骤。
6. 通过 `get_operation` 或 `await_operation` 查询真实进展。最终核对 `succeeded`、`persisted`、资产版本/摘要/归属，列出失败与未知项，再报告完成。

无金额上限的新计划 `expiresAt:null`；这不会移除消费者及一次性派发票据的短期限。新自动计划不使用普通 `confirmationNonce`（若管理 DTO 保留该字段则为 `null`），真实删除的独立 nonce 继续有效。

创建计划、执行和每个控制动作分别使用各自稳定幂等键（16 至 128 位字母、数字、下划线或连字符）。同一请求的重传应沿用原键；不得为摆脱未知结果而换键重发。桥不自动重试任何 HTTP 调用。

结构编辑使用已确认的脚本 `3.1` 与 `contentStatus:"draft"` 合同。完整事务备份包含原脚本、参考绑定、媒体和页面状态；不能只备份脚本正文。草稿未满足内容前置条件时，不把它当作可执行生成的成功内容。旧 `3.0` 模型产物的生成期校验继续保留；回退恢复原文件及同一事务快照，不修改版本字符串冒充兼容。

## 断线、取消与响应边界

恢复原任务标识时，使用 `tuiwen_get_operation`，参数例如 `{"operationId":"原操作ID","view":"recovery","offset":0,"limit":100}`。这是固定的只读恢复视图，返回 `{operationId,projectId,sourceProjectId,commands,total,nextOffset}`。每条命令包含 `commandId/stepId/target/state/nativeRunId/originalJournalId/providerTaskId/submitted/requests`；`requests` 只列原请求的 `path/requestOperationId`，不是任意 API 代理或重新生成指令。可选 `recoveryCode` 表示需要进一步核对的恢复条件。按 `nextOffset` 继续，`offset` 限 `0..10000`，`limit` 限 `1..100`，省略分别为 `0/100`。默认或显式 `view:"status"` 不接受 `offset/limit`；普通项目操作列表继续使用 `cursor/limit`。

`tuiwen_await_operation` 的 `waitMs` 在 `0..20000` 内，省略为 `0`，即立即查询；需要等待时明确提供等待毫秒数。返回一页事件后保存 `nextCursor`，按 `sequence` 去重，再显式等待下一页。MCP `notifications/cancelled` 只中止对应本地 HTTP 等待；关闭终端或超时也不等于取消业务。

`tuiwen_cancel_operation` 保留原工具名，通过 `mode:"pause"|"resume"|"cancel"` 操作原任务；省略 `mode` 兼容原取消行为。桥发送 `POST /operations/{id}/controls`，JSON 为 `{action,reason?}`，幂等键放在请求头。`reason` 可省略。暂停响应中的 `pauseRequested` 与实际操作状态一起判断；恢复沿用原任务的已持久进度。`cancel_requested` 不是 `cancelled`；已派发任务或退款未对账时，费用仍可能发生。`chargedUnknown` 可能仅表示最终账单待核；如果业务已 `succeeded + persisted` 且资产匹配，业务可以完成，并继续原授权范围内的后续步骤，不因此强制暂停全部任务。此时仍须如实列出待核账单，不能写成零费用或已结清。真正提交/业务终态未知（如 `indeterminate`）及晚到结果，始终查询原操作，不重新派发同一收费任务。

HTTP 成功响应直接返回资源 DTO，列表是 `{items,nextCursor,pagination}`，不再套一层 `data`。事件每项是 `{cursor,sequence,type,state,at,details}`；不是包含整份操作的旧草案。桥再把 HTTP 资源放入 MCP 结果 `{ok,data,meta}`，错误则为 `{ok:false,error}`。HTTP `200/202` 本身不能证明业务完成。成功 `meta` 带已绑定实例、连接和可选 ETag。预算中的 `limitCnyMicros/remainingCnyMicros` 为 `null` 表示金额不限；`reservedCnyMicros:null` 表示仍有未知金额记录，不是零费用。错误保留稳定 `code`、`nextAction`、可读说明以及重试提示；服务端 `safeToRetry`（兼容旧 `retryable`）不构成重新生成的授权。

输入逐行最多 1 MiB，HTTP 响应最多 2 MiB，同时最多 8 个工具请求。输入/响应超限时缩小字段、EP/合集范围或分页；不要把整个媒体历史与 Base64 放进模型上下文。Stdout 只输出 JSON-RPC；诊断不记录请求体、响应体、令牌或供应商异常。资产工具返回受控引用，不自动下载、不访问任意文件，也不把“返回下载地址”报告为“导出已保存”。

## 验证与交付范围

运行 `node --test agent-work/tests/tuiwen-mcp-*.test.mjs` 可检查独立临时 HTTP 服务与真实 stdio 进程的握手、工具映射、幂等/版本头、归属、限额、取消、重定向与秘密保护。测试使用独立临时根，不读取真实项目或调用收费接口。

上述测试覆盖桥的协议和传输行为。完整业务、真实授权、Windows/Mac 安装端和最小收费样本仍须随主工程专用 API、页面消费者与自动计划/精确删除确认功能完成相应验收；不能以模拟 HTTP、工具目录或编译通过代替这些结果。
