// 影匠依据面板 —— 服务端这一半什么都不做。
// 真正干活的是 lib/client.js（浏览器那一半）：往 DSH 右侧栏挂一个「依据」页签。
export const name = "dsh-yingjiang-panel";

export function apply() {
  // 故意留空：这个插件不注册任何服务端工具、不改任何配置。
}
