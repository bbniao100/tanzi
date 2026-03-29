#!/usr/bin/env python3
"""谈资 - 后端新闻服务器（最终版，干净无重复代码）"""
import http.server, json, urllib.request, ssl, re, time
from datetime import datetime
import os

PORT = int(os.environ.get("PORT", 5188))

def detect_decode(data):
    for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
        try: return data.decode(enc)
        except: pass
    return data.decode('utf-8', errors='ignore')

RSS_SOURCES = [
    {"name":"中新网-国内",  "url":"http://www.chinanews.com.cn/rss/china.xml"},
    {"name":"中新网-国际",  "url":"http://www.chinanews.com.cn/rss/world.xml"},
    {"name":"中新网-社会",  "url":"http://www.chinanews.com.cn/rss/society.xml"},
    {"name":"中新网-财经",  "url":"http://www.chinanews.com.cn/rss/finance.xml"},
    {"name":"中新网-即时",  "url":"http://www.chinanews.com.cn/rss/scroll-news.xml"},
    {"name":"中新网-时政",  "url":"http://www.chinanews.com.cn/rss/politics.xml"},
    {"name":"凤凰网-大陆",  "url":"https://news.ifeng.com/rss_mainland.xml"},
]

def fetch_url(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; TanZi/1.0)',
            'Accept': 'application/rss+xml, application/xml, */*',
            'Connection': 'close',
        })
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return detect_decode(r.read())
    except Exception as e:
        print(f'  [fail] {url[:50]} -> {e}')
        return ''

def parse_rss(text):
    results = []
    if not text or len(text) < 50: return results
    for item in re.findall(r'<item>([\s\S]*?)</item>', text, re.I)[:12]:
        t1 = re.search(r'<title><!\[CDATA\[([^\]]+)\]\]></title>', item, re.I)
        t2 = re.search(r'<title>([^<]+)</title>', item, re.I)
        d1 = re.search(r'<description><!\[CDATA\[([^\]]+)\]\]></description>', item, re.I)
        d2 = re.search(r'<description>([^<]+)</description>', item, re.I)
        d3 = re.search(r'<content:encoded><!\[CDATA\[([^\]]+)\]\]></content:encoded>', item, re.I)
        title = (t1.group(1) if t1 else (t2.group(1) if t2 else '')).strip()
        desc = (d1.group(1) if d1 else (d2.group(1) if d2 else (d3.group(1) if d3 else ''))).strip()
        desc = re.sub(r'<[^>]+>', '', desc).strip()
        if title and len(title) > 5:
            results.append((title, desc[:200]))
    return results

def fetch_all_news():
    all_news = []
    seen = {}
    print(f'[{datetime.now().strftime("%H:%M:%S")}] 开始抓取新闻...')
    for src in RSS_SOURCES:
        print(f'  -> {src["name"]}', end=' ', flush=True)
        text = fetch_url(src['url'])
        if not text: print('失败'); continue
        cnt = 0
        for title, desc in parse_rss(text):
            key = title.replace(' ','')[:12]
            if key and key not in seen and len(title) > 6:
                seen[key] = True
                all_news.append({'title': title, 'digest': desc or title, 'source': src['name']})
                cnt += 1
        print(f'{cnt}条')
        time.sleep(0.15)
    print(f'  共获取 {len(all_news)} 条')
    return all_news[:40]

def call_ai(news_list, api_key, api_base, model):
    txt = '【今日真实新闻】：\n\n'
    for i, n in enumerate(news_list, 1):
        txt += f'【{i}】{n["title"]}\n摘要：{n["digest"]}\n来源：{n["source"]}\n\n'
    prompt = (
        '你是一个资深编辑，将新闻整理成谈资JSON。'
        '4板块：网事8条、城事3-4条（标城市）、国事5条、天下事5条。'
        '每条120-150字，语言精炼有话题性，只用原文信息，标注真实来源。'
        '开头标题：【谈资月日】新闻1 | 新闻2 | 新闻3'
        '只返回JSON：'
        '{"top_title":"","sections":[{"name":"网事","items":[{"title":"","content":"","source":""}]},'
        '{"name":"城事","items":[{"title":"","content":"","source":""}]},'
        '{"name":"国事","items":[{"title":"","content":"","source":""}]},'
        '{"name":"天下事","items":[{"title":"","content":"","source":""}]}]}'
    )
    post_data = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': prompt + '\n\n' + txt}],
        'temperature': 0.2,
        'max_tokens': 2000
    }).encode('utf-8')
    req = urllib.request.Request(
        f'{api_base}/chat/completions',
        data=post_data,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json; charset=utf-8'},
        method='POST'
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
        result = json.loads(r.read().decode('utf-8'))
    content = result['choices'][0]['message']['content'].strip()
    content = re.sub(r'^```json\s*', '', content, flags=re.I).strip()
    content = re.sub(r'```\s*$', '', content, flags=re.I).strip()
    return json.loads(content)

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>谈资</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:#f4f6fb;color:#222;line-height:1.7}
.wrap{max-width:900px;margin:0 auto;padding:20px}
.hd{text-align:center;padding:30px 0 18px}
.hd h1{font-size:30px;color:#2c3e50;letter-spacing:3px;margin-bottom:5px}
.hd p{color:#bbb;font-size:13px}
.cfg{background:white;border-radius:14px;padding:20px 24px;margin-bottom:14px;box-shadow:0 2px 10px rgba(0,0,0,0.06)}
.lbl{font-size:13px;font-weight:600;color:#555;margin-bottom:8px}
input{flex:1;min-width:160px;padding:10px 14px;border:1.5px solid #e0e0e0;border-radius:8px;font-size:14px;outline:none;width:100%}
input:focus{border-color:#667eea}
.r{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.r:last-child{margin-bottom:0}
select{flex:0 0 auto;padding:9px 12px;border:1.5px solid #e0e0e0;border-radius:8px;font-size:14px;background:white}
.btn{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;min-width:120px;display:inline-block;text-align:center;transition:opacity 0.2s}
.btn:hover{opacity:0.88}
.btn:disabled{opacity:0.5;cursor:not-allowed}
.btn2{background:white;color:#667eea;border:1.5px solid #667eea;padding:10px 18px;border-radius:8px;font-size:13px;cursor:pointer;font-weight:500;display:inline-block}
.btn2:hover{background:#f0f2ff}
.slist{margin-top:10px;padding:10px 14px;background:#f8f9ff;border-radius:8px;font-size:12px;color:#555;line-height:2}
.st{padding:11px 16px;border-radius:8px;font-size:13px;margin-bottom:12px;display:none;line-height:1.8}
.st.sr{border:1px solid #c8e6c9;background:#f1f8f1;color:#2e7d32}
.st.se{border:1px solid #ffcdd2;background:#fff0f0;color:#c62828}
.st.si{border:1px solid #90caf9;background:#f0f4ff;color:#1565c0}
.st.sw{border:1px solid #ffe082;background:#fff8e1;color:#e65100}
.top{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:16px 22px;border-radius:14px;margin-bottom:22px;font-size:15px;line-height:1.9}
.sec{background:white;border-radius:14px;padding:20px;margin-bottom:16px;box-shadow:0 2px 12px rgba(0,0,0,0.07)}
.sec h2{font-size:18px;color:#2c3e50;margin-bottom:14px;padding-left:10px;border-left:5px solid #667eea;font-weight:600}
.item{margin-bottom:18px;padding-bottom:18px;border-bottom:1px solid #f0f0f0}
.item:last-child{margin-bottom:0;padding-bottom:0;border-bottom:none}
.item h3{font-size:15px;color:#333;margin-bottom:5px;font-weight:600}
.item p{font-size:14px;color:#555;margin-bottom:4px;line-height:1.7}
.item span{font-size:12px;color:#bbb}
.ft{text-align:center;padding:20px;color:#ccc;font-size:12px}
.ld{text-align:center;padding:44px}
.spin{width:32px;height:32px;border:3px solid #e8e8e8;border-top-color:#667eea;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 12px}
@keyframes spin{to{transform:rotate(360deg)}}
.bdg{background:#e8f5e9;color:#2e7d32;font-size:11px;padding:1px 6px;border-radius:10px;margin-right:4px;font-weight:700}
.eb{background:#fff0f0;border:1px solid #ffcdd2;border-radius:10px;padding:22px;text-align:center;color:#c62828;line-height:2;font-size:14px}
.pb{height:3px;background:#eee;border-radius:2px;margin-top:8px;overflow:hidden}
.pb div{height:100%;background:linear-gradient(90deg,#667eea,#764ba2);width:0%;transition:width 0.6s}
</style>
</head>
<body>
<div class="wrap">
<div class="hd"><h1>谈资</h1><p id="hdr">每日资讯 · AI 自动整理</p></div>

<div class="cfg">
<div class="lbl">基础配置</div>
<div class="r"><input type="password" id="apiKey" placeholder="SiliconFlow API Key（sk-开头）"></div>
<div class="r">
<input type="text" id="apiBase" placeholder="https://api.siliconflow.cn" style="max-width:250px">
<select id="modelSelect">
<option value="deepseek-ai/DeepSeek-R1">DeepSeek R1（推荐）</option>
<option value="deepseek-ai/DeepSeek-V2.5">DeepSeek V2.5</option>
<option value="Qwen/Qwen2.5-7B-Instruct">Qwen2.5-7B</option>
</select>
</div>
<div class="slist">📡 新闻来源（实时RSS）：🌐 中新网（国内/国际/社会/财经/时政） · 🌐 凤凰网</div>
<div class="r" style="margin-top:12px">
<span class="btn" id="genBtn">🔍 搜集+生成</span>
<span class="btn2" id="prevBtn">👁 预览</span>
</div>
<div class="pb"><div id="pfill"></div></div>
</div>

<div class="st" id="statusBox"></div>
<div class="top" id="topTitle">填写上方 API Key，点击「搜集+生成」</div>
<div id="body"></div>
<div class="ft">谈资 · 服务器实时抓取官方RSS · 数据绝对新鲜</div>
</div>

<script>
(function() {
var $ = function(id) { return document.getElementById(id); };
var busy = false;

function setStatus(html, type) {
    var el = $('statusBox');
    el.className = 'st ' + (type || 'si');
    el.innerHTML = html;
}
function clearStatus() { $('statusBox').className = 'st'; }
function setProgress(p) { $('pfill').style.width = (p || 0) + '%'; }
function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtDate() {
    var d = new Date();
    return d.getFullYear() + '年' + String(d.getMonth()+1).padStart(2,'0') + '月' + String(d.getDate()).padStart(2,'0') + '日';
}
function monthDay() {
    var d = new Date();
    return String(d.getMonth()+1).padStart(2,'0') + String(d.getDate()).padStart(2,'0');
}

function renderNews(news) {
    var h = '<div class="sec"><h2 style="border-left-color:#f093fb">今日RSS新闻（共' + news.length + '条）</h2>';
    for (var i = 0; i < Math.min(news.length, 15); i++) {
        var n = news[i];
        var isOff = n.source.indexOf('中新') !== -1 || n.source.indexOf('新华网') !== -1 || n.source.indexOf('央视') !== -1 || n.source.indexOf('人民日报') !== -1;
        h += '<div class="item"><h3>' + (isOff ? '<span class="bdg">官</span>' : '') + esc(n.title) + '</h3><p>' + esc(n.digest) + '</p><span>来源：' + esc(n.source) + '</span></div>';
    }
    h += '</div>';
    $('body').innerHTML = h;
}

function renderResult(r, cnt) {
    clearStatus();
    $('topTitle').textContent = r.top_title || ('【谈资' + monthDay() + '】');
    var colors = {'网事':'#667eea','城事':'#f093fb','国事':'#4facfe','天下事':'#43e97b'};
    var h = '';
    var total = 0;
    for (var si = 0; si < (r.sections || []).length; si++) {
        var sec = r.sections[si];
        var c = colors[sec.name] || '#667eea';
        var items = sec.items || [];
        total += items.length;
        var ih = '';
        for (var ji = 0; ji < items.length; ji++) {
            var it = items[ji];
            var bdg = it.source && (it.source.indexOf('中新') !== -1 || it.source.indexOf('新华网') !== -1 || it.source.indexOf('央视') !== -1) ? '<span class="bdg">官</span>' : '';
            ih += '<div class="item"><h3>' + bdg + esc(it.title || '') + '</h3><p>' + esc(it.content || '') + '</p><span>（' + esc(it.source || '') + '）</span></div>';
        }
        h += '<div class="sec"><h2 style="border-left-color:' + c + '">' + sec.name + ' <span style="font-size:13px;color:#aaa;font-weight:normal">(' + items.length + '条)</span></h2>' + ih + '</div>';
    }
    $('body').innerHTML = h;
    setStatus('完成！共整理 <b>' + total + '</b> 条谈资 | 来源 <b>' + cnt + '</b> 条实时新闻', 'sr');
}

function doGenerate() {
    if (busy) return;
    var key = $('apiKey').value.trim();
    var base = $('apiBase').value.trim() || 'https://api.siliconflow.cn';
    var model = $('modelSelect').value;
    if (!key) {
        alert('请先填写 SiliconFlow API Key\n\n获取地址：https://account.siliconflow.cn');
        return;
    }
    busy = true;
    var btn = $('genBtn');
    btn.disabled = true;
    btn.textContent = '搜集新闻...';
    clearStatus();
    setProgress(10);
    $('topTitle').textContent = '正在从官方RSS源抓取今日新闻...';
    $('body').innerHTML = '<div class="ld"><div class="spin"></div><p>正在从官方RSS源实时获取新闻...</p></div>';
    try { localStorage.setItem('tk', key); localStorage.setItem('tb', base); } catch(e) {}

    var newsCache = null;
    var fetcher = fetch('/api/news');
    var timer = new Promise(function(_, rej) { setTimeout(function() { rej(new Error('新闻获取超时（20秒），请稍后重试')); }, 20000); });

    Promise.race([fetcher, timer]).then(function(resp) {
        if (!resp || !resp.ok) throw new Error('服务器响应异常，请确认服务器已启动');
        setProgress(50);
        return resp.json();
    }).then(function(news) {
        newsCache = news;
        if (!news || news.length === 0) throw new Error('新闻获取为0，请稍后重试');
        btn.textContent = 'AI 整理...';
        $('topTitle').textContent = '已获取 ' + news.length + ' 条，AI 整理中...';
        setProgress(60);
        setStatus('已获取 ' + news.length + ' 条新闻，AI 整理中（约20-40秒）...', 'si');

        var txt = '【今日真实新闻（' + news.length + '条）】：\n\n';
        for (var i = 0; i < news.length; i++) {
            txt += '【' + (i+1) + '】' + news[i].title + '\n摘要：' + news[i].digest + '\n来源：' + news[i].source + '\n\n';
        }

        return fetch(base + '/chat/completions', {
            method: 'POST',
            headers: {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
            body: JSON.stringify({model: model, messages: [{role: 'user', content: txt}], temperature: 0.2, max_tokens: 2000})
        }).then(function(r) { return r.json(); });
    }).then(function(data) {
        if (!data.choices) throw new Error('AI返回格式异常，请尝试切换其他模型');
        var raw = data.choices[0].message.content || '';
        // DeepSeek R1 可能在思考，提取JSON部分
        var txt = raw.trim();
        // 去掉 <think>...</think> 标签
        txt = txt.replace(/<think>[\s\S]*?<\/think>/gi, '');
        // 去掉 markdown 代码块标记
        txt = txt.replace(/^```json\s*/i, '').replace(/```\s*$/i, '').trim();
        // 找第一个 { 和最后一个 }
        var l = txt.indexOf('{');
        var r2 = txt.lastIndexOf('}');
        if (l !== -1 && r2 !== -1 && r2 > l) txt = txt.substring(l, r2 + 1);
        var r;
        try { r = JSON.parse(txt); }
        catch(e) { throw new Error('AI返回内容无法解析为JSON，请重试一次（模型首次响应可能不完整）'); }
        setProgress(100);
        renderResult(r, newsCache ? newsCache.length : 0);
        btn.textContent = '重新生成';
    }).catch(function(err) {
        setProgress(0);
        clearStatus();
        $('topTitle').textContent = '出错了';
        var msg = err.message || String(err);
        $('body').innerHTML = '<div class="eb">出错：' + esc(msg) + '<br><br><span class="btn" id="retryBtn">重新生成</span></div>';
        $('retryBtn').onclick = doGenerate;
        setStatus('❌ ' + msg, 'se');
        btn.textContent = '搜集+生成';
    }).finally(function() {
        busy = false;
        btn.disabled = false;
    });
}

function doPreview() {
    var btn = $('prevBtn');
    clearStatus();
    setProgress(0);
    $('topTitle').textContent = '正在获取新闻（最长20秒）...';
    $('body').innerHTML = '<div class="ld"><div class="spin"></div><p>正在从RSS源获取...</p></div>';
    btn.disabled = true;
    btn.textContent = '获取中...';

    var fetcher = fetch('/api/news');
    var timer = new Promise(function(_, rej) { setTimeout(function() { rej(new Error('获取超时，请稍后重试')); }, 20000); });
    Promise.race([fetcher, timer]).then(function(resp) { return resp.json(); }).then(function(news) {
        clearStatus();
        if (!news || news.length === 0) {
            $('body').innerHTML = '<div class="eb">未能获取到新闻，请稍后重试</div>';
            return;
        }
        $('topTitle').textContent = '获取到 ' + news.length + ' 条新闻';
        setStatus('获取到 <b>' + news.length + '</b> 条 | 来源：中新网RSS', 'sr');
        renderNews(news);
    }).catch(function(e) {
        $('body').innerHTML = '<div class="eb">获取失败：' + esc(e.message || String(e)) + '</div>';
    }).finally(function() {
        btn.disabled = false;
        btn.textContent = '预览';
    });
}

// 绑定按钮点击
$('genBtn').onclick = doGenerate;
$('prevBtn').onclick = doPreview;

// 页面加载
window.onload = function() {
    var ds = fmtDate();
    document.title = '谈资 - ' + ds;
    var hd = $('hdr');
    if (hd) hd.textContent = '每日资讯 · ' + ds + ' · AI 自动整理';
    try {
        var k = localStorage.getItem('tk');
        var b = localStorage.getItem('tb');
        if (k) $('apiKey').value = k;
        if (b) $('apiBase').value = b;
    } catch(e) {}
};
})();
</script>
</body>
</html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode('utf-8'))
        elif self.path == '/test':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            msg = ('\u670d\u52a1\u5668\u6b63\u5e38\u8fd0\u884c\u4e2d\uff01\u65f6\u95f4\uff1a' + datetime.now().strftime('%Y-%m-%d %H:%M:%S')).encode('utf-8')
            self.wfile.write(msg)
        elif self.path == '/api/news':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            news = fetch_all_news()
            self.wfile.write(json.dumps(news, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f'[{datetime.now().strftime("%H:%M:%S")}] {args[0]}')

if __name__ == '__main__':
    print(f'\n\u2699\ufe0f \u8c08\u8d44\u670d\u52a1\u5668\u542f\u52a8\uff01')
    print(f'   \u4e3b\u9875\uff1ahttp://localhost:{PORT}')
    print(f'   \u65b0\u95fbAPI\uff1ahttp://localhost:{PORT}/api/news\n')
    server = http.server.HTTPServer(('', PORT), Handler)
    server.serve_forever()
