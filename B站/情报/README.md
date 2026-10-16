# B站 AI 动画/短片 · 选题情报系统

用公开接口抓数据，回答「现在什么题材最火、新号往哪个缝隙挤」。
**不登录、不用 cookie、只用公开接口，请求间隔 ≥1.2 秒。**

---

## 每天怎么跑

> ⚠️ 这台机器上 `pwsh` **不在 PATH 里**（`Get-Command pwsh` 找不到），
> 而 `powershell.exe`（5.1）随时可用。下面用 `powershell.exe`；
> 如果你在 PowerShell 7 会话里，把 `powershell.exe` 换成 `pwsh` 即可。
> `run_daily.ps1` 存为 **UTF-8 with BOM**，5.1 和 7 都能正确读中文。

```powershell
# 完整抓取（约 7 分钟，全量）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\B站\run_daily.ps1"

# 快速模式（约 3 分钟，页数与补全量减半）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\B站\run_daily.ps1" -Fast

# 不抓网，只用当天已存的 raw JSON 重新生成报告（秒级）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\B站\run_daily.ps1" -AnalyzeOnly

# 补跑某一天
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\B站\run_daily.ps1" -Date 20261012
```

最省事的方式 —— 直接调 python（不依赖任何 shell 版本）：

```powershell
& 'D:\DSHworkspace\B站\venv\Scripts\python.exe' 'D:\DSHworkspace\B站\抓热榜.py' --date 20261012
```

### 挂到 Windows 计划任务（每天 08:30）

```powershell
$a = New-ScheduledTaskAction -Execute 'powershell.exe' `
     -Argument '-NoProfile -ExecutionPolicy Bypass -File "D:\DSHworkspace\B站\run_daily.ps1"'
$t = New-ScheduledTaskTrigger -Daily -At 08:30
Register-ScheduledTask -TaskName 'B站选题情报' -Action $a -Trigger $t
```

---

## 产出物（都在 `D:\DSHworkspace\B站\情报\`）

| 文件 | 内容 |
|---|---|
| `题材分析_YYYYMMDD.md` | **主报告**，8 章带数据的结论 |
| `热榜日报_YYYYMMDD.csv` | 全量明细，UTF-8 with BOM，Excel 直接双击打开 |
| `raw_YYYYMMDD.json` | 原始数据 + 抓取元信息（含失败清单） |
| `运行日志.txt` | 每天一条运行记录 |
| `_last_run.log` | 最近一次运行的完整输出 |

---

## 抓了什么

| 数据源 | 接口 | 结果 |
|---|---|---|
| 全区排行榜 | `ranking/v2`（3 日榜） | ✅ 100 条 |
| 新人榜 | `ranking/v2` + `rid=0&type=rookie` | ✅ 100 条 |
| 分区排行榜 | 同上，按 `tid` 切分区 | ✅ 动画/鬼畜/生活/知识/科技/影视/娱乐/音乐/游戏，各 80–100 条 |
| 关键词搜索（综合排序） | `x/web-interface/wbi/search/type`，`order=totalrank` | ✅ 10 词 × 2 页 × 42 条 |
| 关键词搜索（近 30 天窗口） | 同上 + `pubtime_begin_s`/`pubtime_end_s` + `order=totalrank` | ✅ 每词 ~84 条 |
| 关键词搜索（最新投稿） | 同上 + `order=pubdate` | ✅ 每词 ~42 条 |
| 视频详情（投币/收藏/弹幕/分享） | `x/web-interface/wbi/view` | ✅ 180/180 |
| UP 主粉丝数 | `x/relation/stat` | ✅ 50/50 |
| 对标 UP 主近期投稿 | `x/space/wbi/arc/search` | ⚠️ 偶发 412 风控，本轮抓到 5 条 |

**wbi 签名**由 `bilibili-api-python` 内置处理（`bilibili_api.select_client(...)`），这是选这个库的主要原因。

**关键词**：AI动画、AI短片、AI视频、AI绘画、AI音乐、AI电影、Stable Diffusion、ComfyUI、AI漫剧、AI生成

---

## 容错设计

- 每个接口调用都过 `Fetcher.call()` 包装：失败只记录不抛错，**单条挂掉不影响整体**
- 连续 6 次失败触发 `CircuitBreak`，中止当前阶段而不是硬刚风控
- 命中 `-352` / `412` 时自动**降速**（间隔 ×1.5，上限 5 秒），成功后再逐步恢复
- 失败明细写进 `raw_*.json` 的 `meta.failures`，并渲染到报告第一章的表格里

---

## ⚠️ 口径说明（读报告前必看）

1. **`numResults` 字段被 B 站截断在 1000**——除 `Stable Diffusion` 外所有关键词都顶到上限，
   所以「供给量」这个维度**区分不出竞争强度**，报告第五章改用「进榜门槛（P25）」来代替。
2. **榜单和搜索头部样本存在幸存者偏差**——它们都是「已经跑出来」的视频。
   报告里的「播放中位数」应读作「要挤进这个位置需要多少播放」，
   **不是**「随便发一条能拿多少播放」。
3. **搜索接口不返回投币数**——投币数据来自排行榜字段 + 详情接口补全，
   只有约 1100 条样本有投币数据，投币率结论基于这批样本。
4. 「近 30 天」是抓取当天往前推 30 天，按 `pubdate` 过滤。

---

## 环境

- venv：`D:\DSHworkspace\B站\venv`（Python 3.13.12，基座为 ComfyUI standalone-env）
- 依赖：`bilibili-api-python==17.4.2`、`curl_cffi`（TLS 指纹伪装，绕开部分风控）
- **与 ComfyUI 的出图环境完全隔离，不共用 site-packages**
