# -*- coding: utf-8 -*-
"""把 8791 的页面抓下来，在最前面插一个 window.onerror 记录器 ——
出错就**用大红字顶在页面最上面**，然后截图看。

★ 为什么不用 --dump-dom：实测这里它回 0 字节（Edge 版本的关系），读不出东西。
  截图是唯一「一定能看见」的通道，所以让错误自己跑到画面上来。
"""
import io
import os
import re
import subprocess
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
根 = r"D:\DSHworkspace"

h = urllib.request.urlopen("http://127.0.0.1:8791/", timeout=15).read().decode("utf-8")

探针 = """
<script>
window.__错 = [];
function 报(s){
  window.__错.push(s);
  var d = document.getElementById('探错');
  if(!d){ d = document.createElement('div'); d.id='探错';
    d.style.cssText='position:fixed;left:0;top:0;right:0;z-index:99999;background:#c00;'
      +'color:#fff;font:16px/1.5 monospace;padding:10px;white-space:pre-wrap;max-height:70vh;overflow:auto';
    (document.body||document.documentElement).appendChild(d); }
  d.textContent = window.__错.join('\\n');
}
window.onerror = function (m, u, l, c, e) { 报('ERR ' + m + '  @' + (u||'').split('/').pop() + ':' + l + ':' + c); };
window.addEventListener('unhandledrejection', function (e) {
  报('PROMISE ' + (e.reason && e.reason.message ? e.reason.message : String(e.reason))); });
window.addEventListener('load', function () {
  setTimeout(function () {
    ['在跑','本机','看片身','jc门','进度'].forEach(function (id) {
      var el = document.getElementById(id);
      报('检查 ' + id + ' → ' + (!el ? '没有这个元素' : (el.innerHTML.trim() ? '有内容('+el.innerHTML.length+')' : '★空的')));
    });
  }, 3000);
});
</script>
"""

h2 = re.sub(r"(<body[^>]*>)", r"\1" + 探针, h, count=1)
if 探针 not in h2:
    h2 = 探针 + h
出 = os.path.join(根, "_控台_探.html")
io.open(出, "w", encoding="utf-8", newline="\n").write(h2)

图 = os.path.join(根, r"_归档\截图\_探控台.png")
if os.path.exists(图):
    os.remove(图)
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--window-size=1400,700", "--virtual-time-budget=20000",
                "--screenshot=" + 图, "file:///" + 出.replace("\\", "/")],
               capture_output=True, timeout=180)
print(f"  {'✓' if os.path.exists(图) else '✗'} {图}")
