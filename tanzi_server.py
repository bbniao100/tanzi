#!/usr/bin/env python3
"""
谈资 - 后端新闻服务器（云端部署版）
运行方式：python3 tanzi_server.py
"""
import http.server, json, threading, urllib.request, ssl, re, time
from datetime import datetime
import os

PORT = int(os.environ.get("PORT", 5188))

# ====== 中文编码检测 ======
import codecs

def detect_and_decode(data, default_enc='utf-8'):
    """尝试检测数据编码并解码"""
    for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
        try:
            return data.decode(enc)
        except:
            pass
    return data.decode(default_enc, errors='ignore')

# ====== 新闻源配置 ======
RSS_SOURCES = [
    {"name": "中新网-国内",  "url": "http://www.chinanews.com.cn/rss/china.xml"},
    {"name": "中新网-国际",  "url": "http://www.chinanews.com.cn/rss/world.xml"},
    {"name": "中新网-社会",  "url": "http://www.chinanews.com.cn/rss/society.xml"},
    {"name": "中新网-财经",  "url": "http://www.chinanews.com.cn/rss/finance.xml"},
    {"name": "中新网-即时",  "url": "http://www.chinanews.com.cn/rss/scroll-news.xml"},
    {"name": "中新网-时政",  "url": "http://www.chinanews.com.cn/rss/politics.xml"},
    {"name": "中新网-文化",  "url": "http://www.chinanews.com.cn/rss/culture.xml"},
    {"name": "凤凰网-大陆",  "url": "https://news.ifeng.com/rss_mainland.xml"},
    {"name": "凤凰网-国际",  "url": "https://news.ifeng.com/rss_world.xml"},
]

def fetch_url(url, timeout=10):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TanZi/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Connection": "close",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            return detect_and_decode(raw)
    except Exception as e:
        print(f"  [timeout/fail] {url[:50]} -> {type(e).__name__}: {str(e)[:40]}")
        return ""

def parse_rss(text):
    """解析RSS，返回 [(title, description, source_name)]"""
    results = []
    if not text or len(text) < 50:
        return results
    try:
        items = re.findall(r'<item>([\s\S]*?)</item>', text, re.IGNORECASE)
        for item in items[:12]:
            # 提取标题
            t1 = re.search(r'<title><!\[CDATA\[([^\]]+)\]\]></title>', item, re.IGNORECASE)
            t2 = re.search(r'<title>([^<]+)</title>', item, re.IGNORECASE)
            title = (t1.group(1) if t1 else (t2.group(1) if t2 else "")).strip()

            # 提取摘要
            d1 = re.search(r'<description><!\[CDATA\[([^\]]+)\]\]></description>', item, re.IGNORECASE)
            d2 = re.search(r'<description>([^<]+)</description>', item, re.IGNORECASE)
            d3 = re.search(r'<content:encoded><!\[CDATA\[([^\]]+)\]\]></content:encoded>', item, re.IGNORECASE)
            desc = (d1.group(1) if d1 else (d2.group(1) if d2 else (d3.group(1) if d3 else ""))).strip()
            desc = re.sub(r'<[^>]+>', '', desc).strip()

            if title and len(title) > 5:
                results.append((title, desc[:200], None))
    except Exception as e:
        print(f"  parse error: {e}")
    return results

def fetch_all_news():
    """从所有RSS源抓取新闻"""
    all_news = []
    seen = {}

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始抓取新闻...")

    for source in RSS_SOURCES:
        url = source["url"]
        name = source["name"]
        print(f"  正在获取：{name} ...", end=" ", flush=True)

        text = fetch_url(url)
        if not text:
            print("失败")
            continue

        items = parse_rss(text)
        cnt = 0
        for title, desc, _ in items:
            key = title.replace(" ","")[:12]
            if key and key not in seen and len(title) > 6:
                seen[key] = True
                all_news.append({"title": title, "digest": desc or title, "source": name})
                cnt += 1

        print(f"获取 {cnt} 条")
        time.sleep(0.15)  # 礼貌延迟

    print(f"  共获取 {len(all_news)} 条（去重后）")
    return all_news[:40]

# ====== AI整理 ======
SYSTEM_PROMPT = """你是一个为高管用户提供社交谈资的资深编辑。

【任务】严格基于以下今日真实新闻，整理成4大板块谈资内容。

【核心原则】
1.只使用新闻原文中的信息，绝不编造、添加或推测
2.内容必须标注真实来源，禁止虚构来源

【4大板块要求】
- 网事：全国热点、社会事件、科技/互联网新闻，选8条
- 城事：北京、上海、深圳本地新闻，选3-4条，每条标题前加「北京/上海/深圳」
- 国事：国内时政、政策、宏观经济，选5条
- 天下事：国际重大新闻，选5条

【每条标准】
- 标题：简洁有话题性，禁止原文照抄
- 内容：120-150字，语言精炼，适合高管社交谈资
- 来源：必须使用给出的真实媒体来源

【开头标题】
选今日最有话题性的3条新闻，格式：「【谈资月日】新闻1 | 新闻2 | 新闻3」

【返回格式】（只返回纯JSON，禁止解释）
{"top_title":"","sections":[{"name":"网事","items":[{"title":"","content":"","source":""}]},{"name":"城事","items":[{"title":"","content":"","source":""}]},{"name":"国事","items":[{"title":"","content":"","source":""}]},{"name":"天下事","items":[{"title":"","content":"","source":""}]}]}"""

def process_with_ai(news_list, api_key, api_base, model):
    """使用标准库urllib调用AI（无需安装requests）"""
    import json as _json
    news_text = "【今日真实新闻（" + str(len(news_list)) + "条）】：\n\n"
    for i, n in enumerate(news_list, 1):
        news_text += f"【{i}】{n['title']}\n摘要：{n['digest']}\n来源：{n['source']}\n\n"

    post_data = _json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": SYSTEM_PROMPT + "\n\n" + news_text}],
        "temperature": 0.2,
        "max_tokens": 2000
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{api_base}/chat/completions",
        data=post_data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()) as resp:
        result = _json.loads(resp.read().decode("utf-8"))

    content = result["choices"][0]["message"]["content"].strip()
    content = re.sub(r'^```json\s*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'```\s*$', '', content, flags=re.IGNORECASE).strip()
    return _json.loads(content)

# ====== HTML前端 ======
HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>谈资</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:#f4f6fb;color:#222;line-height:1.7}
.wrap{max-width:900px;margin:0 auto;padding:20px}
.header{text-align:center;padding:30px 0 18px}
.header h1{font-size:30px;color:#2c3e50;letter-spacing:3px;margin-bottom:5px}
.header p{color:#bbb;font-size:13px}
.cfg{background:white;border-radius:14px;padding:20px 24px;margin-bottom:14px;box-shadow:0 2px 10px rgba(0,0,0,0.06)}
.cfg-title{font-size:13px;font-weight:600;color:#555;margin-bottom:10px}
.cfg input{flex:1;min-width:160px;padding:10px 14px;border:1.5px solid #e0e0e0;border-radius:8px;font-size:14px;outline:none;width:100%}
.cfg input:focus{border-color:#667eea}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.row:last-child{margin-bottom:0}
.cfg select{flex:0 0 auto;padding:9px 12px;border:1.5px solid #e0e0e0;border-radius:8px;font-size:14px;background:white}
.btn{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;min-width:120px;display:inline-block;text-align:center;transition:opacity 0.2s}
.btn:hover{opacity:0.88}
.btn:disabled{opacity:0.5;cursor:not-allowed}
.btn-outline{background:white;color:#667eea;border:1.5px solid #667eea;padding:10px 18px;border-radius:8px;font-size:13px;cursor:pointer;font-weight:500;display:inline-block}
.btn-outline:hover{background:#f0f2ff}
.slist{margin-top:10px;padding:10px 14px;background:#f8f9ff;border-radius:8px;font-size:12px;color:#555;line-height:2}
.status{padding:11px 16px;border-radius:8px;font-size:13px;margin-bottom:12px;display:none;line-height:1.8}
.status.show{display:block}
.status.info{background:#f0f4ff;color:#1565c0}
.status.ok{background:#f1f8f1;color:#2e7d32;border:1px solid #c8e6c9}
.status.err{background:#fff0f0;color:#c62828;border:1px solid #ffcdd2}
.status.warn{background:#fff8e1;color:#e65100;border:1px solid #ffe082}
.top-box{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:16px 22px;border-radius:14px;margin-bottom:22px;font-size:15px;line-height:1.9}
.sec{background:white;border-radius:14px;padding:20px;margin-bottom:16px;box-shadow:0 2px 12px rgba(0,0,0,0.07)}
.sec h2{font-size:18px;color:#2c3e50;margin-bottom:14px;padding-left:10px;border-left:5px solid #667eea;font-weight:600}
.item{margin-bottom:18px;padding-bottom:18px;border-bottom:1px solid #f0f0f0}
.item:last-child{margin-bottom:0;padding-bottom:0;border-bottom:none}
.item h3{font-size:15px;color:#333;margin-bottom:5px;font-weight:600}
.item p{font-size:14px;color:#555;margin-bottom:4px;line-height:1.7}
.item span{font-size:12px;color:#bbb}
.footer{text-align:center;padding:20px;color:#ccc;font-size:12px}
.loading{text-align:center;padding:44px}
.spinner{width:32px;height:32px;border:3px solid #e8e8e8;border-top-color:#667eea;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 12px}
@keyframes spin{to{transform:rotate(360deg)}}
.badge{background:#e8f5e9;color:#2e7d32;font-size:11px;padding:1px 6px;border-radius:10px;margin-right:4px;font-weight:700}
.eb{background:#fff0f0;border:1px solid #ffcdd2;border-radius:10px;padding:22px;text-align:center;color:#c62828;line-height:2;font-size:14px}
.pb{height:3px;background:#eee;border-radius:2px;margin-top:8px;overflow:hidden}
.pb div{height:100%;background:linear-gradient(90deg,#667eea,#764ba2);width:0%;transition:width 0.6s}
</style>
</head>
<body>
<div class="wrap">
<div class="header"><h1>谈资</h1><p id="hd">每日资讯 · AI 自动整理</p></div>

<div class="cfg">
<div class="cfg-title">基础配置</div>
<div class="row"><input type="password" id="key" placeholder="SiliconFlow API Key（sk-开头）"></div>
<div class="row">
<input type="text" id="base" placeholder="https://api.siliconflow.cn" style="max-width:250px">
<select id="model">
<option value="Qwen/Qwen2.5-7B-Instruct">Qwen2.5-7B（推荐）</option>
<option value="deepseek-ai/DeepSeek-V2.5">DeepSeek V2.5</option>
<option value="THUDM/glm-4-9b-chat">GLM-4</option>
</select>
</div>
<div class="slist">📡 新闻来源（实时RSS）：🌐 中新网（国内/国际/社会/财经/时政/文化） · 🌐 凤凰网</div>
<div class="row" style="margin-top:12px">
<span class="btn" id="genBtn">🔍 搜集+生成</span>
<span class="btn-outline" id="prevBtn">👁 预览</span>
</div>
<div class="pb" id="pbar"><div id="pfill"></div></div>
</div>

<div class="status" id="sbox"></div>
<div class="top-box" id="top">填写上方 API Key，点击「搜集+生成」</div>
<div id="body"></div>
<div class="footer">谈资 · 服务器实时抓取官方RSS · 数据绝对新鲜</div>
</div>

<script>
var $ = function(id) { return document.getElementById(id); };
var busy = false;

function S(html, type) {
    var el = $("sbox");
    el.className = "status show " + (type||"info");
    el.innerHTML = html;
}
function C() { $("sbox").className = "status"; }
function P(p) { $("pfill").style.width = (p||0) + "%"; }
function esc(s) {
    return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
function fmt() {
    var d = new Date();
    return d.getFullYear() + "年" + String(d.getMonth()+1).padStart(2,"0") + "月" + String(d.getDate()).padStart(2,"0") + "日";
}
function md() {
    var d = new Date();
    return String(d.getMonth()+1).padStart(2,"0") + String(d.getDate()).padStart(2,"0");
}

$("genBtn").onclick = function() {
    if (busy) return;
    var key = $("key").value.trim();
    var base = $("base").value.trim() || "https://api.siliconflow.cn";
    var model = $("model").value;
    if (!key) { alert("请填写 SiliconFlow API Key\n\n获取地址：https://account.siliconflow.cn"); return; }

    busy = true;
    var btn = $("genBtn");
    btn.disabled = true;
    btn.textContent = "搜集新闻...";
    C(); P(10);
    $("top").textContent = "正在从官方RSS源抓取今日新闻...";
    $("body").innerHTML = '<div class="loading"><div class="spinner"></div><p>正在从官方RSS源实时获取新闻（最长等待20秒）...</p></div>';

    try { localStorage.setItem("tk", key); localStorage.setItem("tb", base); } catch(e){}

    // 带超时的fetch（最长等20秒）
    var timeoutMs = 20000;
    var fetcher = fetch("/api/news");
    var timer = new Promise(function(_, rej) {
        setTimeout(function() { rej(new Error("新闻获取超时（20秒），服务器可能无法访问国内网站，请稍后重试")); }, timeoutMs);
    });

    Promise.race([fetcher, timer]).then(function(r) {
        if (!r || !r.ok) throw new Error("服务器响应异常，请确认服务器已启动");
        P(50); return r.json();
    }).then(function(news) {
        if (!news || news.length === 0) throw new Error("新闻获取为0，服务器可能无法访问国内网站，请稍后重试");
        btn.textContent = "AI 整理...";
        $("top").textContent = "已获取 " + news.length + " 条，AI 整理中...";
        P(60);
        S("🤖 已获取 " + news.length + " 条新闻，AI 整理中（约20-40秒）...", "info");

        var txt = "【今日真实新闻（" + news.length + "条）】：\n\n";
        for (var i = 0; i < news.length; i++) {
            txt += "【" + (i+1) + "】" + news[i].title + "\n摘要：" + news[i].digest + "\n来源：" + news[i].source + "\n\n";
        }

        return fetch(base + "/chat/completions", {
            method: "POST",
            headers: {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            body: JSON.stringify({model:model, messages:[{role:"user",content:txt}], temperature:0.2, max_tokens:2000})
        }).then(function(r) { return r.json().catch(function(){ throw new Error("AI返回无效"); }); });
    }).then(function(data) {
        if (!data.choices) throw new Error("AI返回格式异常，请尝试切换其他模型");
        var txt = data.choices[0].message.content.trim().replace(/^```json\s*/i,"").replace(/```\s*$/i,"").trim();
        var r = JSON.parse(txt);
        P(100);
        showResult(r, 0);
        btn.textContent = "🔄 重新生成";
    }).catch(function(err) {
        C(); P(0);
        $("top").textContent = "出错了";
        $("body").innerHTML = '<div class="eb">❌ ' + esc(err.message||String(err)) + '<br><br><span class="btn" id="rbtn">重新生成</span></div>';
        $("rbtn").onclick = $("genBtn").onclick;
        S("❌ " + (err.message||String(err)), "err");
    }).finally(function() {
        busy = false;
        btn.disabled = false;
    });
};

$("prevBtn").onclick = function() {
    var btn = $("prevBtn");
    C(); $("top").textContent = "正在获取新闻...";
    $("body").innerHTML = '<div class="loading"><div class="spinner"></div><p>正在从RSS源获取...</p></div>';
    btn.disabled = true; btn.textContent = "获取中...";
    fetch("/api/news").then(function(r) { return r.json(); }).then(function(news) {
        C();
        if (!news || news.length === 0) { $("body").innerHTML = '<div class="eb">未能获取到新闻，请稍后重试</div>'; return; }
        $("top").textContent = "获取到 " + news.length + " 条新闻";
        S("✅ 获取到 <b>" + news.length + "</b> 条 | 来源：中新网RSS实时聚合", "ok");
        var h = '<div class="sec"><h2 style="border-left-color:#f093fb">今日RSS新闻（共' + news.length + '条）</h2>';
        for (var i = 0; i < Math.min(news.length, 15); i++) {
            var n = news[i];
            var off = n.source.indexOf("中新")!==-1||n.source.indexOf("新华网")!==-1||n.source.indexOf("央视")!==-1||n.source.indexOf("人民日报")!==-1;
            h += '<div class="item"><h3>' + (off?'<span class="badge">官</span>':'') + esc(n.title) + '</h3><p>' + esc(n.digest) + '</p><span>来源：' + esc(n.source) + '</span></div>';
        }
        h += '</div>';
        $("body").innerHTML = h;
    }).catch(function(e) {
        $("body").innerHTML = '<div class="eb">获取失败：' + esc(e.message) + '</div>';
    }).finally(function() {
        btn.disabled = false; btn.textContent = "👁 预览";
    });
};

function showResult(r, cnt) {
    C();
    $("top").textContent = r.top_title || "【谈资" + md() + "】";
    var colors = {"网事":"#667eea","城事":"#f093fb","国事":"#4facfe","天下事":"#43e97b"};
    var h = "";
    var total = 0;
    for (var si = 0; si < (r.sections||[]).length; si++) {
        var sec = r.sections[si];
        var c = colors[sec.name]||"#667eea";
        var its = sec.items||[];
        total += its.length;
        var ih = "";
        for (var ji = 0; ji < its.length; ji++) {
            var it = its[ji];
            var bdg = it.source&&(it.source.indexOf("中新")!==-1||it.source.indexOf("新华网")!==-1||it.source.indexOf("央视")!==-1) ? '<span class="badge">官</span>' : '';
            ih += '<div class="item"><h3>' + bdg + esc(it.title||"") + '</h3><p>' + esc(it.content||"") + '</p><span>（' + esc(it.source||"") + '）</span></div>';
        }
        h += '<div class="sec"><h2 style="border-left-color:' + c + '">' + sec.name + ' <span style="font-size:13px;color:#aaa;font-weight:normal">(' + its.length + '条)</span></h2>' + ih + '</div>';
    }
    $("body").innerHTML = h;
    S("✅ 完成！共整理 <b>" + total + "</b> 条谈资 | 来源 <b>" + cnt + "</b> 条实时新闻", "ok");
}

window.onload = function() {
    var ds = fmt();
    document.title = "谈资 - " + ds;
    var hd = $("hd");
    if (hd) hd.textContent = "每日资讯 · " + ds + " · AI 自动整理";
    try {
        var k = localStorage.getItem("tk");
        var b = localStorage.getItem("tb");
        if (k) $("key").value = k;
        if (b) $("base").value = b;
    } catch(e){}
};
</script>
</body>
</html>"""

# ====== HTTP服务器 ======
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))

        elif self.path == "/api/news":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            news = fetch_all_news()
            self.wfile.write(json.dumps(news, ensure_ascii=False).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

if __name__ == "__main__":
    print(f"\n🌐 谈资服务器启动！")
    print(f"   主页：http://localhost:{PORT}")
    print(f"   新闻API：http://localhost:{PORT}/api/news\n")
    server = http.server.HTTPServer(("", PORT), Handler)
    server.serve_forever()
