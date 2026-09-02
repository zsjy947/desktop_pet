# -*- coding: utf-8 -*-
"""本地角色上传网页：浏览器传图 + 填台词 → 生成新角色（仅监听 127.0.0.1）。

    python tools/character_server.py
    # 浏览器打开 http://127.0.0.1:8765

表单提交后调用 add_character.add_character()：抠图（须已装 rembg；透明底
PNG 免抠图）→ 生成精灵帧 → 写入 custom_characters.json。宠物右键菜单
重新打开时即可看到新角色（无需重启）。
"""
import cgi
import json
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from pet import custom  # noqa: E402

PORT = 8765

PAGE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>桌面宠物 · 添加角色</title>
<style>
 body { font-family: "Microsoft YaHei UI", sans-serif; max-width: 560px;
        margin: 24px auto; color: #333; }
 h1 { font-size: 20px; }
 label { display: block; margin-top: 12px; font-weight: 600; }
 input[type=text], select, textarea { width: 100%; box-sizing: border-box;
        padding: 6px; margin-top: 4px; }
 textarea { height: 56px; }
 button { margin-top: 16px; padding: 8px 24px; font-size: 15px; }
 #msg { margin-top: 14px; white-space: pre-wrap; }
 .hint { color: #888; font-size: 12px; }
</style></head><body>
<h1>添加桌面宠物角色</h1>
<form id="f">
 <label>角色图片（带背景自动抠图；透明底 PNG 免抠图）</label>
 <input type="file" name="image" accept="image/*" required>
 <label>角色 id（小写字母开头，仅小写字母/数字/下划线）</label>
 <input type="text" name="id" placeholder="mychar" required>
 <label>显示名</label>
 <input type="text" name="name" placeholder="我的角色">
 <label>抠图模型</label>
 <select name="model">
  <option value="u2net">u2net（真人照片）</option>
  <option value="isnet-anime">isnet-anime（动漫插画）</option>
  <option value="isnet-general-use">isnet-general-use（通用）</option>
 </select>
 <label>台词（每行一句；留空的类别用通用台词）</label>
 <textarea name="talk" placeholder="碎碎念……"></textarea>
 <textarea name="feed" placeholder="被喂食时……"></textarea>
 <textarea name="pet" placeholder="被摸头时……"></textarea>
 <textarea name="switch" placeholder="被选中登场时……"></textarea>
 <button type="submit">生成角色</button>
</form>
<div id="msg"></div>
<script>
 f.onsubmit = async (e) => {
   e.preventDefault();
   msg.textContent = '处理中（抠图约需几秒到几十秒）……';
   const fd = new FormData(f);
   const r = await fetch('/add', {method: 'POST', body: fd});
   const j = await r.json();
   msg.textContent = j.ok ? ('完成！右键宠物菜单即可选择「' + j.name +
                            '」') : ('失败：' + j.error);
 };
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        data = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', f'{ctype}; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/list':
            presets = custom.load_custom()
            self._send(200, json.dumps(
                {'characters': [{'id': p['id'], 'name': p.get('name')}
                                for p in presets]}, ensure_ascii=False),
                'application/json')
        else:
            self._send(200, PAGE, 'text/html')

    def do_POST(self):
        if self.path != '/add':
            self._send(404, json.dumps({'ok': False, 'error': 'not found'}),
                       'application/json')
            return
        try:
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers,
                                    environ={'REQUEST_METHOD': 'POST'})
            upload = form['image']
            if not getattr(upload, 'file', None):
                raise ValueError('请选择图片')
            suffix = os.path.splitext(upload.filename or '')[1] or '.png'
            fd, tmp = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, 'wb') as out:
                shutil_copy(upload.file, out)

            phrases = {}
            for key in ('talk', 'feed', 'pet', 'sleep', 'wake', 'drop',
                        'switch'):
                raw = form.getvalue(key)
                if raw is None:
                    continue
                values = raw if isinstance(raw, list) else [raw]
                lines = [s.strip() for v in values
                         for s in str(v).splitlines() if s.strip()]
                if lines:
                    phrases[key] = lines
            from add_character import add_character
            preset = add_character(
                tmp, (form.getvalue('id') or '').strip(),
                (form.getvalue('name') or '').strip() or None,
                form.getvalue('model') or 'u2net', phrases)
            self._send(200, json.dumps(
                {'ok': True, 'id': preset['id'], 'name': preset['name']},
                ensure_ascii=False), 'application/json')
        except Exception as e:                       # noqa: BLE001
            self._send(400, json.dumps({'ok': False, 'error': str(e)},
                                       ensure_ascii=False),
                       'application/json')


def shutil_copy(src, dst):
    import shutil
    shutil.copyfileobj(src, dst, 1024 * 1024)


def main():
    server = HTTPServer(('127.0.0.1', PORT), Handler)
    print(f'角色上传页：http://127.0.0.1:{PORT}  （Ctrl+C 退出）', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
