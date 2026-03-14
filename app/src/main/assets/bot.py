#!/usr/bin/env python3
"""
GoLike Bot v9 - Multi Account + TikTok + Pause/Resume + Auto Retry
- Đa tài khoản: chạy song song nhiều token cùng lúc
- Hỗ trợ: Shopee + Lazada + TikTok
- Tạm dừng/Tiếp tục: điều khiển từ Web UI
- Tự động thử lại khi mạng lỗi
- Lịch sử: lưu vào history.json, xem qua web UI
- Gemini AI: tự giải captcha (getDisplayMedia + Termux screencap)
- Chạy ngầm: Wake Lock API
- Tự khởi động sau khi khởi động lại thiết bị
"""
import requests, time, json, re, base64, threading, queue, os, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from datetime import datetime

# ══ CONFIG ══════════════════════════════════════════════════
GEMINI_KEY   = "AIzaSyB04DoRbSJH7efErVsANUoBuLAa9-vzkJQ"
GEMINI_URL   = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
RCAP_SITEKEY = "6Leo5PMrAAAAAArIr7KjV49Pz4zRgLq05wIZy33w"
GW           = "https://gateway.golike.net"
HISTORY_FILE = "golike_history.json"

PLATFORMS = {
    'shopee': {
        'jobs'    : f'{GW}/api/advertising/publishers/shopee/jobs',
        'complete': f'{GW}/api/advertising/publishers/shopee/complete-jobs',
        'skip'    : f'{GW}/api/advertising/publishers/shopee/skip-jobs',
        'icon'    : '🛍️',
    },
    'lazada': {
        'jobs'    : f'{GW}/api/advertising/publishers/lazada/jobs',
        'complete': f'{GW}/api/advertising/publishers/lazada/complete-jobs',
        'skip'    : f'{GW}/api/advertising/publishers/lazada/skip-jobs',
        'icon'    : '🟠',
    },
    'tiktok': {
        'jobs'    : f'{GW}/api/advertising/publishers/tiktok/jobs',
        'complete': f'{GW}/api/advertising/publishers/tiktok/complete-jobs',
        'skip'    : f'{GW}/api/advertising/publishers/tiktok/skip-jobs',
        'icon'    : '🎵',
    },
}

# ══ PAUSE / RESUME ══════════════════════════════════════════
bot_paused = threading.Event()
bot_paused.set()  # Not paused by default (set = running)

R='\033[0;31m';G='\033[0;32m';Y='\033[1;33m'
C='\033[0;36m';P='\033[0;35m';W='\033[1;37m';N='\033[0m'
def log(c,i,m): print(f"{c}[{time.strftime('%H:%M:%S')}] {i} {m}{N}",flush=True)

def genT():
    ts=str(int(time.time()))
    return base64.b64encode(base64.b64encode(base64.b64encode(ts.encode()).decode().encode()).decode().encode()).decode()

# ══ HISTORY ═════════════════════════════════════════════════
hist_lock = threading.Lock()

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE,'r',encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return {'sessions':[],'total':{'ok':0,'sk':0,'xu':0,'cap':0}}

def save_history(h):
    try:
        with open(HISTORY_FILE,'w',encoding='utf-8') as f:
            json.dump(h,f,ensure_ascii=False,indent=2)
    except Exception as e:
        log(Y,'!',f'Lưu history lỗi: {e}')

def record_job(acc_label, platform, jtype, uid, coin, success, cap_used):
    with hist_lock:
        h = load_history()
        entry = {
            'time'    : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'account' : acc_label,
            'platform': platform,
            'type'    : jtype,
            'job_id'  : uid,
            'coin'    : coin if success else 0,
            'success' : success,
            'cap_used': cap_used,
        }
        if 'jobs' not in h: h['jobs'] = []
        h['jobs'].insert(0, entry)
        h['jobs'] = h['jobs'][:500]  # Giữ 500 job gần nhất
        t = h.setdefault('total',{'ok':0,'sk':0,'xu':0,'cap':0})
        if success: t['ok']+=1; t['xu']+=coin
        else:       t['sk']+=1
        if cap_used: t['cap']+=1
        save_history(h)

# ══ ACCOUNT MANAGER ═════════════════════════════════════════
class Account:
    def __init__(self, idx, token, acc_id, platforms, delay=5):
        self.idx       = idx
        self.token     = token
        self.acc_id    = str(acc_id)
        self.platforms = platforms  # ['shopee','lazada']
        self.delay     = delay
        self.label     = f'Acc{idx+1}({acc_id})'
        self.stats     = {'ok':0,'sk':0,'xu':0,'cap':0}
        self.running   = False
        self.sess      = requests.Session()
        self.sess.headers.update({
            'User-Agent'     :'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            'Accept-Language':'vi-VN,vi;q=0.9',
            'Origin'         :'https://app.golike.net',
            'Referer'        :'https://app.golike.net/',
        })

    def api(self, method, url, body=None, retries=3):
        auth = self.token if self.token.startswith('Bearer ') else 'Bearer '+self.token
        h = {'Authorization':auth,'t':genT(),'Accept':'application/json'}
        if body: h['Content-Type']='application/json;charset=UTF-8'
        for attempt in range(retries):
            try:
                r = self.sess.request(method,url,headers=h,json=body,timeout=20)
                return r.json()
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                if attempt < retries - 1:
                    wait = 5 * (attempt + 1)
                    log(Y,'!',f'[{self.label}] Mạng lỗi ({e.__class__.__name__}), thử lại sau {wait}s...')
                    time.sleep(wait)
                else:
                    raise
            except Exception:
                raise

    def get_jobs(self, platform):
        url = PLATFORMS[platform]['jobs']
        return self.api('GET', f'{url}?account_id={self.acc_id}')

    def complete(self, platform, ads_id, obj_id, cap_token, url=None):
        url = url or PLATFORMS[platform]['complete']
        return self.api('POST', url, {
            'ads_id':ads_id, 'account_id':int(self.acc_id),
            'async':True, 'data':None, 'captcha_token':cap_token,
        })

    def skip(self, platform, ads_id, obj_id, jtype):
        try:
            self.api('POST', PLATFORMS[platform]['skip'], {
                'ads_id':ads_id, 'object_id':str(obj_id),
                'account_id':int(self.acc_id), 'type':jtype,
            })
        except: pass

# ══ SHARED STATE ════════════════════════════════════════════
accounts     = []          # List[Account]
tok_q        = queue.Queue()
need_tok     = threading.Event()
current_jobs = {}          # acc_label → job info
all_stats    = {}          # acc_label → stats
actual_port  = 8080

# ══ CAPTCHA TOKEN ════════════════════════════════════════════
def get_cap_token(acc_label, timeout=90):
    while not tok_q.empty():
        try: tok_q.get_nowait()
        except: break
    need_tok.set()
    log(P,'!',f'[{acc_label}] === CẦN TOKEN → browser giải ===')
    try:
        t = tok_q.get(timeout=timeout)
        need_tok.clear()
        log(G,'✓',f'[{acc_label}] Token OK ({len(t)}c)')
        return t
    except queue.Empty:
        need_tok.clear()
        log(R,'✗',f'[{acc_label}] Timeout token!')
        return None

# ══ GEMINI ═══════════════════════════════════════════════════
def gemini_solve(imgs_b64, is_screenshot=False):
    if not imgs_b64: return [], ''
    try:
        if is_screenshot:
            prompt = ('Google reCAPTCHA screenshot. Tìm grid 3x3 trong ảnh.\n'
                      '1. Đọc tiêu đề yêu cầu\n2. Ô nào (0-8) chứa đối tượng?\n'
                      'Format: CHALLENGE: <tên>\nINDICES: [x,y,z]')
        else:
            prompt = (f'{len(imgs_b64)} ảnh reCAPTCHA (0-{len(imgs_b64)-1}).\n'
                      'Ảnh nào chứa đối tượng yêu cầu?\n'
                      'Format: CHALLENGE: <tên>\nINDICES: [x,y,z]')
        parts = [{'text':prompt}]
        for b64 in imgs_b64:
            parts.append({'inline_data':{'mime_type':'image/jpeg','data':b64}})
        gr = requests.post(
            GEMINI_URL+'?key='+GEMINI_KEY,
            json={'contents':[{'parts':parts}],'generationConfig':{'temperature':0,'maxOutputTokens':80}},
            timeout=15
        )
        gd = gr.json()
        if 'error' in gd:
            log(R,'✗',f'Gemini: {gd["error"].get("message","?")}')
            return [],''
        txt = (((gd.get('candidates',[{}])[0]).get('content',{})).get('parts',[{}])[0]).get('text','')
        log(G,'🤖',f'Gemini: {txt.strip()[:60]}')
        indices,challenge='',''
        mc = re.search(r'CHALLENGE[:\s]+(.+)',txt,re.I)
        if mc: challenge=mc.group(1).strip()
        mi = re.search(r'INDICES[:\s]+(\[[\d,\s]*\])',txt,re.I)
        if mi:
            try: indices=json.loads(mi.group(1))
            except: pass
        if not indices:
            m2=re.search(r'\[[\d, ]+\]',txt)
            if m2:
                try: indices=json.loads(m2.group(0))
                except: pass
        return indices, challenge
    except Exception as e:
        log(R,'✗',f'gemini_solve: {e}')
        return [],''

# ══ HTML ═════════════════════════════════════════════════════
def make_html(port):
    return f'''<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>GoLike Bot v9</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}}
body{{background:#07070d;color:#d0d8e8;font-family:monospace;min-height:100vh}}
.wrap{{padding:12px;max-width:520px;margin:0 auto;padding-bottom:30px}}
h2{{color:#ee4d2d;font-size:14px;margin-bottom:10px;letter-spacing:1px}}
.box{{padding:10px 12px;border-radius:9px;margin:6px 0;font-size:11px;line-height:1.8}}
.ok{{background:rgba(0,229,160,.07);border:1px solid rgba(0,229,160,.25);color:#00e5a0}}
.warn{{background:rgba(255,179,0,.07);border:1px solid rgba(255,179,0,.25);color:#ffb300}}
.err{{background:rgba(255,68,68,.07);border:1px solid rgba(255,68,68,.25);color:#ff5252}}
.pu{{background:rgba(179,157,219,.07);border:1px solid rgba(179,157,219,.25);color:#b39ddb}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.sp{{display:inline-block;width:9px;height:9px;border:2px solid rgba(255,255,255,.1);
     border-top-color:#ee4d2d;border-radius:50%;animation:spin .6s linear infinite;
     margin-right:4px;vertical-align:middle}}
hr{{border:none;border-top:1px solid #1a1a2e;margin:8px 0}}
/* TABS */
.tabs{{display:flex;gap:0;border-bottom:1px solid #1a1a2e;margin-bottom:10px}}
.tab{{flex:1;padding:9px 4px;text-align:center;font-size:11px;color:#3a3a5c;
       cursor:pointer;border-bottom:2px solid transparent;transition:.2s}}
.tab.on{{color:#ee4d2d;border-color:#ee4d2d}}
.page{{display:none}}.page.on{{display:block}}
/* ACCOUNTS TABLE */
.acc-table{{width:100%;border-collapse:collapse;font-size:10px}}
.acc-table th{{background:#0f0f1a;color:#3a3a5c;padding:6px 4px;text-align:left;
               border-bottom:1px solid #1a1a2e;letter-spacing:.5px}}
.acc-table td{{padding:6px 4px;border-bottom:1px solid rgba(255,255,255,.03)}}
.badge{{display:inline-block;padding:1px 6px;border-radius:10px;font-size:9px}}
.b-run{{background:rgba(0,229,160,.12);color:#00e5a0;border:1px solid rgba(0,229,160,.2)}}
.b-wait{{background:rgba(255,179,0,.1);color:#ffb300;border:1px solid rgba(255,179,0,.2)}}
.b-stop{{background:rgba(255,68,68,.1);color:#ff5252;border:1px solid rgba(255,68,68,.2)}}
.plt-tag{{display:inline-block;padding:1px 5px;border-radius:4px;font-size:9px;margin:1px}}
.plt-sp{{background:rgba(238,77,45,.1);color:#ee4d2d}}
.plt-lz{{background:rgba(255,140,0,.1);color:#ff8c00}}
.plt-tk{{background:rgba(105,66,232,.1);color:#a259ff}}
/* CAPTCHA */
#cap-sec{{display:none;background:#0f0f1a;border:2px solid #ee4d2d;
          border-radius:12px;padding:12px;margin:8px 0}}
#cap-sec.on{{display:block}}
.cap-hdr{{color:#ee4d2d;font-size:11px;font-weight:700;letter-spacing:1px;
           margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;gap:4px}}
#rcap{{background:#fff;border-radius:8px;min-height:74px;
       display:flex;align-items:center;justify-content:center;padding:4px}}
#cap-imgs{{display:none;margin:6px 0}}
#cap-imgs img{{width:calc(33.3% - 3px);height:65px;object-fit:cover;
               border-radius:4px;margin:1px;border:2px solid transparent}}
#cap-imgs img.sel{{border-color:#00e5a0}}
#cap-log{{font-size:9px;color:#4a4a6a;background:#030308;border-radius:5px;
          padding:5px;max-height:60px;overflow-y:auto;margin-top:5px}}
.tb{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
     color:#777;border-radius:5px;padding:3px 7px;font-size:9px;cursor:pointer;white-space:nowrap}}
/* STATS */
.stats-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin:8px 0}}
.sc{{background:#0f0f1a;border:1px solid #1a1a2e;border-radius:7px;padding:8px 3px;text-align:center}}
.sv{{font-size:20px;font-weight:800;line-height:1}}
.sl{{font-size:8px;color:#3a3a5c;margin-top:2px}}
/* CONSOLE */
.con{{background:#030308;border:1px solid #1a1a2e;border-radius:8px;
      padding:8px;height:150px;overflow-y:auto;font-size:10px;line-height:1.7}}
.con::-webkit-scrollbar{{width:2px}}
.con::-webkit-scrollbar-thumb{{background:#1a1a2e}}
.ll{{border-bottom:1px solid rgba(255,255,255,.02);padding:1px 0}}
.li{{color:#4fc3f7}}.ls{{color:#00e5a0}}.le{{color:#ff5252}}
.lw{{color:#ffb300}}.lp{{color:#ee4d2d}}.lc{{color:#b39ddb}}
/* HISTORY */
.hist-item{{background:#0a0a14;border:1px solid #1a1a2e;border-radius:8px;
            padding:8px 10px;margin:5px 0;font-size:10px}}
.hist-ok{{border-left:3px solid #00e5a0}}
.hist-sk{{border-left:3px solid #3a3a5c}}
.hist-time{{color:#3a3a5c;font-size:9px}}
.hist-xu{{color:#ee4d2d;font-weight:700}}
/* BG BADGE */
#bg-b{{position:fixed;top:8px;right:8px;background:rgba(0,229,160,.12);
        border:1px solid rgba(0,229,160,.25);color:#00e5a0;border-radius:20px;
        padding:3px 9px;font-size:9px;display:none}}
#bg-b.on{{display:block}}
/* TOTAL BANNER */
.total-banner{{background:linear-gradient(135deg,rgba(238,77,45,.1),rgba(255,179,0,.08));
               border:1px solid rgba(238,77,45,.2);border-radius:10px;
               padding:12px;margin:8px 0;display:grid;
               grid-template-columns:repeat(3,1fr);gap:6px;text-align:center}}
.tb-val{{font-size:24px;font-weight:800}}
.tb-lbl{{font-size:8px;color:#3a3a5c;margin-top:2px}}
</style>
</head>
<body>
<div id="bg-b">🔋 Chạy ngầm</div>

<div class="wrap">
<h2>🛍️ GOLIKE BOT v9 — AI AUTO</h2>

<!-- TABS -->
<div class="tabs">
  <div class="tab on" onclick="showTab('main')">📊 Chính</div>
  <div class="tab"    onclick="showTab('accs')">👥 Tài khoản</div>
  <div class="tab"    onclick="showTab('hist')">📋 Lịch sử</div>
</div>

<!-- TAB MAIN -->
<div id="tab-main" class="page on">
  <div id="st" class="box warn">⏳ Chờ bot...</div>
  <div id="job" class="box pu" style="display:none">
    Job: <b id="jtxt"></b> <span id="jacc" style="color:#3a3a5c"></span>
  </div>

  <!-- Captcha -->
  <div id="cap-sec">
    <div class="cap-hdr">
      🤖 GEMINI AI CAPTCHA
      <div style="display:flex;gap:4px;flex-wrap:wrap">
        <button class="tb" onclick="requestScreenCapture()" id="scbtn"
          style="background:rgba(238,77,45,.12);border-color:rgba(238,77,45,.3);color:#ee4d2d">
          📱 Cho phép chụp
        </button>
        <button class="tb" onclick="toggleImgs()" id="tbtn">👁 Ảnh</button>
      </div>
    </div>
    <div id="rcap"></div>
    <div id="cap-imgs">
      <div style="font-size:9px;color:#ee4d2d;margin-bottom:3px" id="cap-chal"></div>
      <div id="img-grid"></div>
      <div style="font-size:9px;color:#4fc3f7;margin-top:3px" id="ai-pick"></div>
    </div>
    <div id="cap-st" style="color:#ffb300;font-size:10px;margin:5px 0">⏳ Đang tải...</div>
    <div id="audio-text-display" style="display:none;background:rgba(0,229,160,.08);border:1px solid rgba(0,229,160,.2);border-radius:6px;padding:6px 8px;font-size:11px;color:#00e5a0;margin-top:4px;font-weight:700"></div>
    <div id="cap-log"></div>
  </div>

  <!-- Total -->
  <div class="total-banner" id="total-banner">
    <div><div class="tb-val" id="t-ok" style="color:#00e5a0">0</div><div class="tb-lbl">✓ TỔNG DONE</div></div>
    <div><div class="tb-val" id="t-xu" style="color:#ee4d2d">0</div><div class="tb-lbl">⭐ TỔNG XU</div></div>
    <div><div class="tb-val" id="t-sk" style="color:#ffb300">0</div><div class="tb-lbl">↷ TỔNG SKIP</div></div>
  </div>
  <!-- Pause/Resume -->
  <div style="display:flex;gap:6px;margin:6px 0">
    <button class="tb" id="pause-btn" onclick="togglePause()"
      style="flex:1;background:rgba(255,179,0,.12);border-color:rgba(255,179,0,.3);color:#ffb300">
      ⏸ Tạm dừng
    </button>
    <button class="tb" onclick="fetch('/status').then(function(r){{return r.json();}}).then(function(d){{log(d.paused?'w':'s','Bot '+(d.paused?'đang tạm dừng':'đang chạy')+' | '+d.version);}})"
      style="flex:1">
      📊 Trạng thái
    </button>
  </div>
  <hr>
  <div class="con" id="con">
    <div class="ll"><span class="li">›</span> <span class="li">GoLike Bot v9 — Sẵn sàng</span></div>
  </div>
</div>

<!-- TAB ACCOUNTS -->
<div id="tab-accs" class="page">
  <table class="acc-table">
    <thead><tr>
      <th>#</th><th>Account ID</th><th>Platform</th>
      <th>Done</th><th>Xu</th><th>Status</th>
    </tr></thead>
    <tbody id="acc-tbody"></tbody>
  </table>
</div>

<!-- TAB HISTORY -->
<div id="tab-hist" class="page">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
    <span style="font-size:10px;color:#3a3a5c" id="hist-count">0 jobs</span>
    <button class="tb" onclick="loadHistory()">🔄 Tải lại</button>
  </div>
  <div id="hist-list"></div>
</div>
</div><!-- /wrap -->

<script src="https://www.google.com/recaptcha/api.js?render=explicit" async defer></script>
<script>
'use strict';
var PORT    = {port};
var SITEKEY = '{RCAP_SITEKEY}';

var wid          = null;
var solving      = false;
var showImg      = true;
var wakeLock     = null;
var screenStream = null;
var screenGranted= false;

// ── Tabs ────────────────────────────────────────────────────
function showTab(name) {{
  document.querySelectorAll('.page').forEach(function(p){{p.classList.remove('on');}});
  document.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('on');}});
  document.getElementById('tab-'+name).classList.add('on');
  event.target.classList.add('on');
  if(name==='hist') loadHistory();
  if(name==='accs') loadAccounts();
}}

// ── Pause / Resume ───────────────────────────────────────
var _botPaused = false;
function togglePause(){{
  var endpoint = _botPaused ? '/resume' : '/pause';
  fetch(endpoint).then(function(r){{return r.json();}}).then(function(d){{
    _botPaused = d.paused;
    var btn = document.getElementById('pause-btn');
    if(btn){{
      if(_botPaused){{
        btn.textContent = '▶ Tiếp tục';
        btn.style.background = 'rgba(0,229,160,.12)';
        btn.style.borderColor = 'rgba(0,229,160,.3)';
        btn.style.color = '#00e5a0';
      }} else {{
        btn.textContent = '⏸ Tạm dừng';
        btn.style.background = 'rgba(255,179,0,.12)';
        btn.style.borderColor = 'rgba(255,179,0,.3)';
        btn.style.color = '#ffb300';
      }}
    }}
    log(_botPaused?'w':'s', _botPaused ? '⏸ Bot đã tạm dừng' : '▶ Bot tiếp tục chạy');
  }}).catch(function(e){{log('e','togglePause: '+e);}});
}}

// ── Wake Lock ────────────────────────────────────────────
async function acquireWakeLock(){{
  try{{
    if('wakeLock' in navigator){{
      wakeLock=await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release',function(){{wakeLock=null;setTimeout(acquireWakeLock,1000);}});
      document.getElementById('bg-b').classList.add('on');
    }}
  }}catch(e){{}}
}}
document.addEventListener('visibilitychange',function(){{
  if(document.visibilityState==='visible'){{
    if(!wakeLock) acquireWakeLock();
    // Quan trọng: khi tab hiện lại, kiểm tra trạng thái solving
    checkSolvingState();
  }}
}});

// ── WATCHDOG: phát hiện solving bị stuck ─────────────────
// Đây là fix chính cho lỗi "phải nhập tay"
var lastSolveActivity = 0;
var watchdogTimer     = null;

function markActivity(){{ lastSolveActivity = Date.now(); }}

function startWatchdog(){{
  if(watchdogTimer) clearInterval(watchdogTimer);
  watchdogTimer = setInterval(function(){{
    if(!solving) return;
    var idle = Date.now() - lastSolveActivity;
    // Nếu solving=true nhưng không có activity 45s → reset
    if(idle > 45000){{
      clog('⚠ Watchdog: solving stuck '+Math.round(idle/1000)+'s → force reset');
      log('w','Captcha stuck → tự reset...');
      forceResetCaptcha();
    }}
  }}, 5000);
}}

function forceResetCaptcha(){{
  solving = false;
  bfReported = false;
  if(bfWatcher){{ clearInterval(bfWatcher); bfWatcher = null; }}
  // Reset widget
  try{{
    if(wid!==null){{ grecaptcha.reset(wid); }}
  }}catch(e){{}}
  // Nếu Python vẫn cần token → solve lại ngay
  setTimeout(function(){{
    fetch('/need_token').then(function(r){{return r.json();}}).then(function(d){{
      if(d.need && !d.received){{
        clog('Auto re-solve sau watchdog reset');
        doSolve();
        watchForBframe();
      }}
    }}).catch(function(){{}});
  }}, 1000);
}}

// Kiểm tra state khi tab visible lại
function checkSolvingState(){{
  if(!solving) return;
  // Nếu bframe không còn nhưng solving vẫn true → reset
  setTimeout(function(){{
    var bf = document.querySelector('iframe[src*="bframe"]');
    if(!bf && solving){{
      clog('Tab visible: không có bframe nhưng solving=true → check lại');
      fetch('/need_token').then(function(r){{return r.json();}}).then(function(d){{
        if(!d.need || d.received){{
          solving = false;
          clog('Token đã nhận xong → reset solving');
        }}
      }}).catch(function(){{}});
    }}
  }}, 500);
}}

// ── Screen Capture ───────────────────────────────────────
async function requestScreenCapture(){{
  try{{
    screenStream = await navigator.mediaDevices.getDisplayMedia({{
      video:{{displaySurface:'browser',width:{{ideal:720}},height:{{ideal:1280}},frameRate:{{ideal:5}}}},
      audio:false,preferCurrentTab:true,
    }});
    screenGranted = true;
    screenStream.getVideoTracks()[0].addEventListener('ended',function(){{
      screenGranted=false; screenStream=null;
      clog('Screen share ended → cần cho phép lại khi cần');
      var btn=document.getElementById('scbtn');
      if(btn){{btn.textContent='📱 Cho phép chụp';btn.style.color='#ee4d2d';}}
    }});
    var btn=document.getElementById('scbtn');
    if(btn){{btn.textContent='✓ Đã cấp quyền';btn.style.color='#00e5a0';}}
    clog('✓ Screen capture OK');
    log('s','Screen capture sẵn sàng ✓');
  }}catch(e){{
    clog('getDisplayMedia: '+e);
    screenGranted=false;
  }}
}}

async function captureScreen(bfEl){{
  if(!screenStream||!screenGranted) return null;
  try{{
    var track=screenStream.getVideoTracks()[0];
    // Kiểm tra track còn sống không
    if(track.readyState!=='live'){{
      screenGranted=false;screenStream=null;
      clog('Track ended → cần cấp quyền lại');
      return null;
    }}
    var imgCap=new ImageCapture(track);
    var bm=await imgCap.grabFrame();
    var c=document.createElement('canvas');
    c.width=bm.width;c.height=bm.height;
    c.getContext('2d').drawImage(bm,0,0);
    if(bfEl){{
      var r=bfEl.getBoundingClientRect();
      var sx=r.left*bm.width/window.innerWidth;
      var sy=r.top*bm.height/window.innerHeight;
      var sw=r.width*bm.width/window.innerWidth;
      var sh=r.height*bm.height/window.innerHeight;
      if(sw>50&&sh>100){{
        var cr=document.createElement('canvas');cr.width=sw;cr.height=sh;
        cr.getContext('2d').drawImage(c,sx,sy,sw,sh,0,0,sw,sh);c=cr;
      }}
    }}
    markActivity();
    return c.toDataURL('image/jpeg',0.92).split(',')[1];
  }}catch(e){{clog('captureScreen: '+e);return null;}}
}}

// ── reCAPTCHA widget ─────────────────────────────────────
function renderWidget(){{
  var box=document.getElementById('rcap');
  if(!box)return;
  if(wid!==null){{try{{grecaptcha.reset(wid);}}catch(e){{}}wid=null;}}
  function doRender(){{
    try{{
      wid=grecaptcha.render(box,{{
        sitekey:SITEKEY,size:'invisible',
        callback:function(token){{
          markActivity();
          clog('✓ Token '+token.length+'c');
          solving=false;tokenReceived(token);
        }},
        'error-callback':function(){{
          clog('error-cb → reset 2s');
          solving=false;
          markActivity();
          setTimeout(renderWidget,2000);
        }},
        'expired-callback':function(){{
          clog('expired → re-execute');
          solving=false;
          // QUAN TRỌNG: expired không có nghĩa là fail
          // Token hết hạn → execute lại ngay
          setTimeout(function(){{
            if(need_solving){{  // vẫn cần token
              doSolve();
              watchForBframe();
            }}
          }},500);
        }}
      }});
    }}catch(e){{setTimeout(renderWidget,1000);}}
  }}
  if(window.grecaptcha&&typeof grecaptcha.render==='function')doRender();
  else{{var iv=setInterval(function(){{
    if(window.grecaptcha&&typeof grecaptcha.render==='function'){{clearInterval(iv);doRender();}}}},200);
  }}
}}

// Flag để biết có đang cần solve không
var need_solving = false;

function doSolve(){{
  if(solving)return;
  solving=true; need_solving=true;
  markActivity();
  setSt('<span class="sp"></span>Lấy token...');
  try{{
    if(wid===null){{renderWidget();setTimeout(doSolve,1500);return;}}
    grecaptcha.reset(wid);
    setTimeout(function(){{
      try{{
        grecaptcha.execute(wid);
        markActivity();
      }}catch(e){{
        clog('execute: '+e);
        solving=false;
        // Thử render lại widget
        setTimeout(function(){{renderWidget();setTimeout(doSolve,1000);}},500);
      }}
    }},300);
  }}catch(e){{solving=false;clog('doSolve: '+e);}}
}}

// ── Watch bframe + Audio Challenge Solver ────────────────
// KHÔNG dùng screenshot (không hoạt động trên mobile HTTP)
// Thay vào đó: click nút 🎧 Audio → fetch MP3 → Gemini transcribe → điền text
var bfReported=false,bfWatcher=null,bfLastH=0,bfStable=0;

function watchForBframe(){{
  if(bfWatcher)clearInterval(bfWatcher);
  bfReported=false;bfLastH=0;bfStable=0;
  bfWatcher=setInterval(function(){{
    if(!solving){{clearInterval(bfWatcher);bfWatcher=null;return;}}
    var bf=document.querySelector('iframe[src*="bframe"]');
    if(!bf){{bfLastH=0;bfStable=0;return;}}
    if(bfReported)return;
    markActivity();
    var h=Math.round(bf.getBoundingClientRect().height);
    // bframe height > 100 là đã có challenge (visual hoặc audio)
    if(h<100){{bfLastH=0;bfStable=0;return;}}
    if(h!==bfLastH){{bfLastH=h;bfStable=0;clog('bframe '+h+'px');return;}}
    if(++bfStable<2)return;  // Ổn định 800ms
    bfReported=true;clearInterval(bfWatcher);bfWatcher=null;
    clog('✓ bframe '+h+'px → chuyển sang Audio challenge');
    setSt('<span class="sp"></span>Đang chuyển sang giọng nói...');
    log('c','Challenge → Audio solver...');
    solveWithAudio(bf);
  }},400);
}}

// ── AUDIO CHALLENGE SOLVER ────────────────────────────────
// Hoạt động 100% trên mọi browser, không cần screenshot
async function solveWithAudio(bfEl){{
  try{{
    markActivity();
    var fr = bfEl.getBoundingClientRect();
    setSt('<span class="sp"></span>🎧 Click nút Audio...');

    // Xóa performance buffer cũ để bắt URL audio mới
    if(performance.clearResourceTimings) performance.clearResourceTimings();

    // Bước 1: Click nút audio (🎧) trong bframe
    // Nút nằm ở bottom-left của bframe, khoảng (left+45, bottom-28)
    var audioClickPositions = [
      {{x: fr.left+45,  y: fr.bottom-28}},   // Vị trí thường gặp nhất
      {{x: fr.left+50,  y: fr.bottom-25}},
      {{x: fr.left+38,  y: fr.bottom-30}},
    ];

    var clicked = false;
    for(var i=0;i<audioClickPositions.length;i++){{
      var pos = audioClickPositions[i];
      var el  = document.elementFromPoint(pos.x, pos.y);
      if(el){{
        clog('Click audio btn @ ('+Math.round(pos.x)+','+Math.round(pos.y)+') → '+el.tagName);
        ['mousedown','mouseup','click'].forEach(function(ev){{
          el.dispatchEvent(new MouseEvent(ev,{{bubbles:true,cancelable:true,clientX:pos.x,clientY:pos.y}}));
        }});
        clicked=true; break;
      }}
    }}

    if(!clicked){{
      clog('Không tìm thấy audio btn → thử tọa độ cố định');
      // Fallback: click thẳng vào tọa độ dự đoán
      var fx=fr.left+45, fy=fr.bottom-28;
      ['mousedown','mouseup','click'].forEach(function(ev){{
        document.dispatchEvent(new MouseEvent(ev,{{bubbles:true,clientX:fx,clientY:fy}}));
      }});
    }}

    // Bước 2: Đợi audio load (2-4s), bắt URL từ performance
    clog('Chờ audio load...');
    setSt('<span class="sp"></span>🎧 Đợi audio...');
    var audioUrl = null;

    for(var attempt=0; attempt<15; attempt++){{
      await sleep(800);
      markActivity();
      var entries = performance.getEntriesByType('resource');
      for(var j=0;j<entries.length;j++){{
        var u=entries[j].name;
        if(u.includes('recaptcha') && (u.includes('audio') || u.includes('mp3') || u.includes('payload')||u.includes('src='))
           && u.startsWith('https')){{
          audioUrl=u;
          clog('✓ Audio URL: ...'+u.slice(-50));
          break;
        }}
      }}
      if(audioUrl) break;

      // Nếu chưa có audio → click lại
      if(attempt===4 || attempt===8){{
        clog('Thử click audio btn lần '+(attempt===4?2:3));
        var el2=document.elementFromPoint(fr.left+45, fr.bottom-28);
        if(el2) el2.click();
      }}
    }}

    if(!audioUrl){{
      clog('⚠ Không bắt được audio URL → thử visual fallback');
      await solveVisualFallback(bfEl);
      return;
    }}

    // Bước 3: Fetch MP3 và gửi Gemini để nhận dạng
    setSt('<span class="sp"></span>🎧 Fetch audio → Gemini...');
    markActivity();
    clog('Fetch: '+audioUrl.slice(-60));

    var audioB64 = await fetchAsBase64(audioUrl);
    if(!audioB64){{
      clog('Fetch audio thất bại → visual fallback');
      await solveVisualFallback(bfEl);
      return;
    }}
    clog('Audio: '+Math.round(audioB64.length/1024)+'KB → Gemini...');

    // Bước 4: Gửi Python → Gemini
    var resp = await fetch('/solve_audio',{{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{audio_b64:audioB64, url:audioUrl}})
    }});
    var d = await resp.json();
    markActivity();

    if(d.error || !d.text){{
      clog('Gemini audio lỗi: '+(d.error||'no text'));
      await solveVisualFallback(bfEl);
      return;
    }}

    var audioText = d.text.trim().toLowerCase().replace(/[^a-z0-9\s]/g,'').trim();
    clog('✓ Gemini nhận dạng: "'+audioText+'"');
    setSt('🎧 Text: "'+audioText+'" → điền...');
    // Hiện text cho user thấy
    var atd=document.getElementById('audio-text-display');
    if(atd){{atd.style.display='block';atd.textContent='🎧 AI nghe: "'+audioText+'"';}}

    // Bước 5: Điền text vào input trong bframe
    // Input audio nằm trong bframe nhưng ta dùng elementFromPoint
    // Input thường ở giữa bframe, khoảng (center, top+280)
    var inputX = fr.left + fr.width/2;
    var inputY = fr.top  + fr.height * 0.55;  // ~55% chiều cao

    // Click vào input field
    var inputEl = document.elementFromPoint(inputX, inputY);
    clog('Input @ ('+Math.round(inputX)+','+Math.round(inputY)+') → '+(inputEl?inputEl.tagName:'?'));

    if(inputEl){{
      inputEl.focus();
      inputEl.click();
      await sleep(300);

      // Dùng execCommand để insert text (hoạt động trên nhiều browser hơn)
      document.execCommand('insertText', false, audioText);
      await sleep(200);

      // Fallback: value assignment + events
      if(inputEl.value!==audioText){{
        inputEl.value = audioText;
        ['input','change','keyup'].forEach(function(ev){{
          inputEl.dispatchEvent(new Event(ev,{{bubbles:true}}));
        }});
      }}
      clog('✓ Đã điền: "'+audioText+'"');
    }}

    await sleep(600);

    // Bước 6: Click Verify
    await clickVerify(bfEl);

  }}catch(e){{
    clog('solveWithAudio: '+e);
    bfReported=false;
    setTimeout(watchForBframe,1500);
  }}
}}

// ── Visual fallback: gửi screenshot nếu có thể ───────────
async function solveVisualFallback(bfEl){{
  clog('Visual fallback...');
  // Thử getDisplayMedia nếu browser hỗ trợ
  if(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia){{
    if(!screenGranted) await requestScreenCapture();
    if(screenGranted){{
      var b64=await captureScreen(bfEl);
      if(b64){{
        var resp=await fetch('/solve_imgs',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{imgs:[b64],screenshot:true}})}});
        var d=await resp.json();
        if(!d.error&&d.indices&&d.indices.length){{
          await clickTiles(d.indices,bfEl); return;
        }}
      }}
    }}
  }}
  // Nếu tất cả fail: reset và thử lại
  clog('Tất cả phương án fail → reset và thử lại sau 3s');
  bfReported=false;
  try{{if(wid!==null){{grecaptcha.reset(wid);setTimeout(function(){{grecaptcha.execute(wid);}},500);}}}}catch(e){{}}
  setTimeout(watchForBframe,3000);
}}

// ── Helpers ───────────────────────────────────────────────
async function fetchAsBase64(url){{
  try{{
    var r=await fetch(url,{{credentials:'omit',mode:'cors'}});
    if(!r.ok) r=await fetch('/img_proxy?url='+encodeURIComponent(url));
    if(!r.ok) return null;
    var ab=await r.arrayBuffer();
    if(ab.byteLength<100) return null;
    var bytes=new Uint8Array(ab),bin='';
    for(var i=0;i<bytes.byteLength;i+=8192)
      bin+=String.fromCharCode.apply(null,bytes.subarray(i,i+8192));
    return btoa(bin);
  }}catch(e){{clog('fetchAsBase64: '+e);return null;}}
}}

function sleep(ms){{return new Promise(function(r){{setTimeout(r,ms);}});}}

async function clickTiles(indices,bfEl){{
  if(!bfEl||!indices||!indices.length){{await clickVerify(bfEl);return;}}
  var fr=bfEl.getBoundingClientRect();
  var gT=fr.top+75,gL=fr.left+8,cW=(fr.width-16)/3,cH=(fr.height-75-50)/3;
  for(var i=0;i<indices.length;i++){{
    var idx2=indices[i];if(idx2<0||idx2>8)continue;
    var cx=gL+(idx2%3)*cW+cW/2,cy=gT+Math.floor(idx2/3)*cH+cH/2;
    var el=document.elementFromPoint(cx,cy);
    if(el)['mousedown','mouseup','click'].forEach(function(ev){{
      el.dispatchEvent(new MouseEvent(ev,{{bubbles:true,cancelable:true,clientX:cx,clientY:cy}}));
    }});
    markActivity();
    await sleep(300+Math.random()*120);
  }}
  await sleep(900);
  await clickVerify(bfEl);
}}

async function clickVerify(bfEl){{
  if(!bfEl)return;
  var fr=bfEl.getBoundingClientRect();
  // Verify button ở bottom-right
  var vx=fr.right-72,vy=fr.bottom-22;
  var vel=document.elementFromPoint(vx,vy);
  clog('Verify @ ('+Math.round(vx)+','+Math.round(vy)+')'+(vel?' '+vel.tagName:''));
  if(vel)['mousedown','mouseup','click'].forEach(function(ev){{
    vel.dispatchEvent(new MouseEvent(ev,{{bubbles:true,cancelable:true,clientX:vx,clientY:vy}}));
  }});
  markActivity();
  setSt('⏳ Verify...');
  await sleep(2500);
  // Kiểm tra challenge còn không
  var bf2=document.querySelector('iframe[src*="bframe"]');
  if(bf2&&bf2.getBoundingClientRect().height>100&&solving){{
    clog('Challenge mới → audio lại');
    bfReported=false;watchForBframe();
  }}
}}
// ── Token received ────────────────────────────────────────────
function tokenReceived(token){{
  solving=false;
  need_solving=false;
  if(bfWatcher){{clearInterval(bfWatcher);bfWatcher=null;}}
  document.getElementById('cap-sec').classList.remove('on');
  fetch('/token?t='+encodeURIComponent(token))
    .then(function(r){{return r.json();}})
    .then(function(d){{log(d.ok?'s':'e','Token '+(d.ok?'OK':'từ chối')+' ('+token.length+'c)');}}
    ).catch(function(e){{log('e','token: '+e);}});
}}

// ── Load Accounts tab ────────────────────────────────────────
function loadAccounts(){{
  fetch('/accounts').then(function(r){{return r.json();}}).then(function(d){{
    var tb=document.getElementById('acc-tbody');
    if(!tb)return;
    tb.innerHTML=d.accounts.map(function(a){{
      var plts=a.platforms.map(function(p){{
        var cls=p==='shopee'?'sp':p==='tiktok'?'tk':'lz';
        var lbl=p==='shopee'?'🛍️ Shopee':p==='tiktok'?'🎵 TikTok':'🟠 Lazada';
        return '<span class="plt-tag plt-'+cls+'">'+lbl+'</span>';
      }}).join('');
      var statusCls=a.running?'b-run':'b-wait';
      var statusTxt=a.running?'Đang chạy':'Chờ';
      return '<tr>'+
        '<td style="color:#3a3a5c">'+(a.idx+1)+'</td>'+
        '<td style="font-weight:700">'+a.acc_id+'</td>'+
        '<td>'+plts+'</td>'+
        '<td style="color:#00e5a0">'+a.ok+'</td>'+
        '<td style="color:#ee4d2d">'+a.xu+'</td>'+
        '<td><span class="badge '+statusCls+'">'+statusTxt+'</span></td>'+
        '</tr>';
    }}).join('');
  }}).catch(function(){{}});
}}

// ── Load History tab ─────────────────────────────────────────
function loadHistory(){{
  fetch('/history').then(function(r){{return r.json();}}).then(function(d){{
    var list=document.getElementById('hist-list');
    var cnt =document.getElementById('hist-count');
    if(!list)return;
    if(cnt) cnt.textContent=(d.jobs||[]).length+' jobs';
    list.innerHTML=(d.jobs||[]).slice(0,100).map(function(j){{
      var icon=j.platform==='lazada'?'🟠':j.platform==='tiktok'?'🎵':'🛍️';
      var cls=j.success?'hist-ok':'hist-sk';
      return '<div class="hist-item '+cls+'">'+
        '<div style="display:flex;justify-content:space-between">'+
          '<span>'+icon+' ['+j.type+'] #'+j.job_id+'</span>'+
          (j.success?'<span class="hist-xu">+'+j.coin+'xu</span>':'<span style="color:#3a3a5c">Skip</span>')+
        '</div>'+
        '<div style="display:flex;justify-content:space-between;margin-top:2px">'+
          '<span class="hist-time">'+j.account+'</span>'+
          '<span class="hist-time">'+j.time+'</span>'+
        '</div>'+
        '</div>';
    }}).join('');

    // Update total banner
    var t=d.total||{{}};
    var tok=document.getElementById('t-ok');
    var txu=document.getElementById('t-xu');
    var tsk=document.getElementById('t-sk');
    if(tok)tok.textContent=t.ok||0;
    if(txu)txu.textContent=t.xu||0;
    if(tsk)tsk.textContent=t.sk||0;
  }}).catch(function(){{}});
}}

// ── Poll Python ──────────────────────────────────────────────
function poll(){{
  fetch('/need_token').then(function(r){{return r.json();}}).then(function(d){{
    // Update all account stats
    if(d.acc_stats){{
      var rows=document.querySelectorAll('#acc-tbody tr');
      // rows updated via loadAccounts when tab is open
    }}
    // Total banner (session stats)
    var s=d.stats||{{}};
    // Update from history API separately
    if(d.received){{
      setStatus('✓ Token OK — đang xử lý...','ok');
      document.getElementById('job').style.display='none';
    }}else if(d.need){{
      setStatus('<span class="sp"></span><b>BOT CẦN TOKEN!</b>','err');
      var jel=document.getElementById('job');
      if(d.job){{jel.style.display='block';document.getElementById('jtxt').textContent=d.job;}}
      var acc_el=document.getElementById('jacc');
      if(acc_el&&d.acc)acc_el.textContent='['+d.acc+']';
      var sec=document.getElementById('cap-sec');
      if(!sec.classList.contains('on')){{
        sec.classList.add('on');
        document.getElementById('cap-log').innerHTML='';
        document.getElementById('cap-imgs').style.display='none';
        document.getElementById('img-grid').innerHTML='';
        sec.scrollIntoView({{behavior:'smooth',block:'start'}});
        doSolve();watchForBframe();
      }}
    }}else{{
      setStatus('⏳ Chờ bot...','warn');
      document.getElementById('job').style.display='none';
      need_solving=false;  // Python không cần token nữa
    }}
    // Refresh total from history periodically
    setTimeout(poll,900);
  }}).catch(function(){{setTimeout(poll,2000);}});
}}

// Refresh history total mỗi 10s
setInterval(loadHistory, 10000);

window.addEventListener('load',function(){{
  acquireWakeLock();
  renderWidget();
  loadHistory();
  startWatchdog();  // Watchdog tự reset captcha khi bị stuck
  poll();
}});
</script>
</body>
</html>'''

# ══ HTTP SERVER ═══════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def send_json(self, code, data):
        b = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Content-Length',str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Headers','*')
        self.end_headers()

    def do_GET(self):
        p  = urlparse(self.path)
        qs = parse_qs(p.query)

        if p.path in ('/','/cap'):
            b = make_html(actual_port).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        elif p.path == '/token':
            tok = qs.get('t',[''])[0]
            if tok and len(tok) > 100:
                tok_q.put(tok)
                need_tok.clear()
                self.send_json(200,{'ok':True})
            else:
                self.send_json(400,{'ok':False})

        elif p.path == '/need_token':
            need = need_tok.is_set()
            recv = not tok_q.empty()
            job  = ''
            acc  = ''
            if need and current_jobs:
                first = next(iter(current_jobs.values()),{})
                job   = f'{first.get("platform","?")} [{first.get("type","?")}] #{first.get("uid","?")} +{first.get("coin",0)}xu'
                acc   = first.get('label','')
            self.send_json(200,{
                'need'    : need and not recv,
                'received': recv,
                'job'     : job,
                'acc'     : acc,
                'stats'   : {a.label:a.stats for a in accounts},
            })

        elif p.path == '/accounts':
            self.send_json(200,{'accounts':[{
                'idx'      : a.idx,
                'acc_id'   : a.acc_id,
                'platforms': a.platforms,
                'running'  : a.running,
                'ok'       : a.stats['ok'],
                'xu'       : a.stats['xu'],
            } for a in accounts]})

        elif p.path == '/history':
            self.send_json(200, load_history())

        elif p.path == '/cap_fail':
            need_tok.clear()
            self.send_json(200,{'ok':True})

        elif p.path == '/pause':
            bot_paused.clear()
            log(Y,'⏸',f'Bot đã tạm dừng')
            self.send_json(200,{'ok':True,'paused':True})

        elif p.path == '/resume':
            bot_paused.set()
            log(G,'▶',f'Bot tiếp tục chạy')
            self.send_json(200,{'ok':True,'paused':False})

        elif p.path == '/status':
            self.send_json(200,{
                'paused' : not bot_paused.is_set(),
                'version': 'v9',
                'accounts': len(accounts),
                'running' : sum(1 for a in accounts if a.running),
                'stats'  : {a.label:a.stats for a in accounts},
            })

        elif p.path == '/img_proxy':
            url = qs.get('url',[''])[0]
            if not url.startswith('http'):
                self.send_response(400); self.end_headers(); return
            try:
                ir = requests.get(url,timeout=8,headers={'Referer':'https://www.google.com/'})
                self.send_response(ir.status_code)
                self.send_header('Content-Type',ir.headers.get('Content-Type','image/jpeg'))
                self.send_header('Access-Control-Allow-Origin','*')
                self.send_header('Content-Length',str(len(ir.content)))
                self.end_headers()
                self.wfile.write(ir.content)
            except:
                self.send_response(500); self.end_headers()

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        p      = urlparse(self.path)
        length = int(self.headers.get('Content-Length',0))
        body   = self.rfile.read(length) if length else b''

        if p.path == '/solve_audio':
            # Nhận audio MP3 base64 → Gemini transcribe → trả text
            try:
                payload   = json.loads(body)
                audio_b64 = payload.get('audio_b64','')
                audio_url = payload.get('url','')
                if not audio_b64:
                    self.send_json(400,{'error':'no audio'}); return

                log(C,'🎧',f'Audio {len(audio_b64)//1024}KB → Gemini transcribe...')

                # Gemini nhận audio và transcribe
                parts = [
                    {'text': (
                        'This is a Google reCAPTCHA audio challenge MP3 file.\n'
                        'The audio says a sequence of digits or words.\n'
                        'Transcribe ONLY the digits/words spoken, nothing else.\n'
                        'Example response: "47382" or "three five nine two"\n'
                        'Just the answer, no explanation.'
                    )},
                    {'inline_data': {
                        'mime_type': 'audio/mp3',
                        'data'     : audio_b64
                    }}
                ]
                gr = requests.post(
                    GEMINI_URL+'?key='+GEMINI_KEY,
                    json={
                        'contents'        : [{'parts':parts}],
                        'generationConfig': {'temperature':0,'maxOutputTokens':30}
                    },
                    timeout=20
                )
                gd = gr.json()
                if 'error' in gd:
                    msg = gd['error'].get('message','?')
                    log(R,'✗',f'Gemini audio: {msg}')
                    self.send_json(200,{'error':msg,'text':''}); return

                txt = (((gd.get('candidates',[{}])[0]).get('content',{}))
                       .get('parts',[{}])[0]).get('text','').strip()
                log(G,'🎧',f'Transcribed: "{txt}"')

                # Clean: chỉ giữ số và chữ
                clean = re.sub(r'[^a-z0-9 ]','', txt.lower()).strip()
                self.send_json(200,{'text':clean,'raw':txt})
            except Exception as e:
                log(R,'✗',f'solve_audio: {e}')
                self.send_json(500,{'error':str(e),'text':''})

        elif p.path == '/solve_imgs':
            try:
                payload  = json.loads(body)
                imgs     = payload.get('imgs',[])
                is_ss    = payload.get('screenshot',False)
                indices, challenge = gemini_solve(imgs, is_ss)
                log(G,'🤖',f'Gemini: "{challenge}" → {indices}')
                self.send_json(200,{'indices':indices,'challenge':challenge})
            except Exception as e:
                self.send_json(500,{'error':str(e),'indices':[]})

        elif p.path == '/input_tap':
            import subprocess as _sp
            try:
                payload = json.loads(body)
                coords  = payload.get('coords',[])
                vx,vy   = payload.get('verify_x',0),payload.get('verify_y',0)
                for c in coords:
                    _sp.run(['input','tap',str(c['x']),str(c['y'])],capture_output=True,timeout=3)
                    time.sleep(0.35)
                if vx and vy:
                    time.sleep(0.9)
                    _sp.run(['input','tap',str(vx),str(vy)],capture_output=True,timeout=3)
                self.send_json(200,{'ok':True})
            except Exception as e:
                self.send_json(200,{'ok':False,'error':str(e)})

        elif p.path == '/termux_solve':
            import subprocess as _sp
            try:
                payload  = json.loads(body)
                bf_top   = payload.get('bf_top',0)
                bf_left  = payload.get('bf_left',0)
                bf_w     = payload.get('bf_width',400)
                bf_h     = payload.get('bf_height',580)
                cap_path = '/sdcard/glbot_cap.png'
                r = _sp.run(['screencap','-p',cap_path],capture_output=True,timeout=5)
                if r.returncode!=0:
                    self.send_json(200,{'ok':False,'error':'screencap failed'}); return
                from PIL import Image; import io as _io
                img   = Image.open(cap_path)
                iw,_  = img.size
                density = iw/360
                crop  = img.crop((int(bf_left*density),int(bf_top*density),
                                  int((bf_left+bf_w)*density),int((bf_top+bf_h)*density)))
                buf   = _io.BytesIO(); crop.save(buf,format='JPEG',quality=90)
                b64   = base64.b64encode(buf.getvalue()).decode()
                indices, challenge = gemini_solve([b64], True)
                log(G,'🤖',f'Termux Gemini: "{challenge}" → {indices}')
                gT=(bf_top+75)*density; gL=(bf_left+8)*density
                cW=(bf_w-16)/3*density; cH=(bf_h-75-50)/3*density
                for idx in indices:
                    if idx<0 or idx>8: continue
                    cx=int(gL+(idx%3)*cW+cW/2); cy=int(gT+(idx//3)*cH+cH/2)
                    _sp.run(['input','tap',str(cx),str(cy)],capture_output=True,timeout=3)
                    time.sleep(0.35)
                if indices:
                    time.sleep(0.9)
                    vx=int((bf_left+bf_w-72)*density); vy=int((bf_top+bf_h-22)*density)
                    _sp.run(['input','tap',str(vx),str(vy)],capture_output=True,timeout=3)
                self.send_json(200,{'ok':True,'message':f'Tapped {len(indices)} tiles'})
            except Exception as e:
                self.send_json(200,{'ok':False,'error':str(e)})

        else:
            self.send_response(404); self.end_headers()


def start_server():
    global actual_port
    for port in [8080,9191,8181,7777,6666]:
        try:
            srv = HTTPServer(('0.0.0.0',port),Handler)
            srv.allow_reuse_address = True
            threading.Thread(target=srv.serve_forever,daemon=True).start()
            actual_port = port
            return port
        except OSError: continue
    return None

# ══ OPEN BROWSER ════════════════════════════════════════════
def open_browser(url):
    import subprocess as _sp, sys
    opened = False
    if not opened and os.path.exists('/data/data/com.termux'):
        for cmd in [
            ['am','start','-a','android.intent.action.VIEW','-d',url,
             '-n','com.android.chrome/com.google.android.apps.chrome.Main'],
            ['termux-open-url',url],
            ['am','start','-a','android.intent.action.VIEW','-d',url],
        ]:
            try:
                if _sp.run(cmd,capture_output=True,timeout=5).returncode==0:
                    opened=True; break
            except: pass
    if not opened and sys.platform.startswith('linux'):
        for cmd in [['google-chrome','--new-tab',url],['chromium-browser',url],
                    ['xdg-open',url],['firefox',url]]:
            try: _sp.Popen(cmd,stdout=_sp.DEVNULL,stderr=_sp.DEVNULL); opened=True; break
            except FileNotFoundError: continue
    if not opened and sys.platform=='win32':
        try: os.startfile(url); opened=True
        except: pass
    if not opened and sys.platform=='darwin':
        try: _sp.Popen(['open',url]); opened=True
        except: pass
    log(G if opened else Y,'→',f'Browser: {url}')
    return opened

# ══ BOT WORKER — chạy 1 account trên nhiều platform ══════════
def bot_worker(acc: Account, delay: int):
    acc.running = True
    log(P,'🛍️',f'[{acc.label}] Bắt đầu | Platforms: {acc.platforms}')
    platform_idx = 0

    while acc.running:
        try:
            # ── Kiểm tra tạm dừng ────────────────────────
            if not bot_paused.is_set():
                log(Y,'⏸',f'[{acc.label}] Đang tạm dừng...')
                bot_paused.wait()
                if not acc.running: break
                log(G,'▶',f'[{acc.label}] Tiếp tục chạy')

            platform = acc.platforms[platform_idx % len(acc.platforms)]
            platform_idx += 1
            icon = PLATFORMS[platform]['icon']

            # ── Lấy job ──────────────────────────────────
            data = acc.get_jobs(platform)
            jd   = data.get('data')

            if not data.get('success') or not isinstance(jd,dict) or not jd.get('id'):
                time.sleep(8); continue

            uid   = jd['id']
            jtype = (jd.get('package_name') or jd.get('type') or 'follow').lower()
            coin  = jd.get('price_per_after_cost') or jd.get('price_after_cost') or 0
            objId = str(jd.get('object_id',''))
            title = str(jd.get('link') or jd.get('title') or objId)
            lock  = int((data.get('lock') or {}).get('lock_time',300))

            current_jobs[acc.label] = {'uid':uid,'type':jtype,'coin':coin,'platform':platform,'label':acc.label}
            log(W,icon,f'[{acc.label}][{platform}] #{uid} "{title[:28]}" +{coin}xu')

            # ── Lấy captcha ──────────────────────────────
            cap = get_cap_token(acc.label, timeout=max(min(lock-delay-5, 90), 15))
            if not cap:
                acc.skip(platform, uid, objId, jtype)
                acc.stats['sk'] += 1
                record_job(acc.label, platform, jtype, uid, 0, False, False)
                current_jobs.pop(acc.label, None)
                continue

            acc.stats['cap'] += 1
            log(C,'⏳',f'[{acc.label}] Chờ {delay}s...'); time.sleep(delay)

            # ── Complete ──────────────────────────────────
            ok = False
            urls_try = [PLATFORMS[platform]['complete'],
                        PLATFORMS[platform]['complete'].replace('gateway','dev')]
            for url in urls_try:
                try:
                    res  = acc.complete(platform, uid, objId, cap, url)
                    rst  = int(res.get('status') or res.get('code') or 0)
                    rmsg = str(res.get('message') or '')
                    log(C,'>',f'[{acc.label}] {json.dumps(res,ensure_ascii=False)[:100]}')

                    if rst==200 or res.get('success') in (True,'1',1) \
                       or re.search(r'thanh.?cong|success|done|completed',rmsg,re.I):
                        earned = int((res.get('data') or {}).get('coin') or coin or 0)
                        acc.stats['ok'] += 1
                        acc.stats['xu'] += earned
                        ok = True
                        log(G,'✓',f'[{acc.label}] DONE #{acc.stats["ok"]} +{earned}xu | Tổng:{acc.stats["xu"]}xu')
                        record_job(acc.label, platform, jtype, uid, earned, True, True)
                        break
                    elif re.search(r'captcha|robot',rmsg,re.I):
                        log(Y,'!',f'[{acc.label}] Captcha từ chối → token mới')
                        cap2 = get_cap_token(acc.label, timeout=60)
                        if cap2:
                            time.sleep(2)
                            res2 = acc.complete(platform, uid, objId, cap2)
                            if res2.get('success') in (True,'1',1) or int(res2.get('status') or 0)==200:
                                e2 = int((res2.get('data') or {}).get('coin') or coin or 0)
                                acc.stats['ok']+=1; acc.stats['xu']+=e2; ok=True
                                log(G,'✓',f'[{acc.label}] Retry DONE +{e2}xu')
                                record_job(acc.label, platform, jtype, uid, e2, True, True)
                                break
                except Exception as e:
                    log(R,'✗',f'[{acc.label}]: {e}')
                    if '401' in str(e) or '403' in str(e):
                        log(R,'✗',f'[{acc.label}] Token hết hạn!'); acc.running=False; break

            if not ok:
                acc.skip(platform, uid, objId, jtype)
                acc.stats['sk'] += 1
                record_job(acc.label, platform, jtype, uid, 0, False, True)
                log(Y,'↷',f'[{acc.label}] Skip #{uid}')

            current_jobs.pop(acc.label, None)
            time.sleep(0.5)

        except requests.exceptions.ConnectionError:
            log(R,'✗',f'[{acc.label}] Mất kết nối...'); time.sleep(5)
        except Exception as e:
            if '401' in str(e) or '403' in str(e):
                log(R,'✗',f'[{acc.label}] Token hết hạn!'); acc.running=False; break
            log(R,'✗',f'[{acc.label}] Lỗi: {e}'); time.sleep(3)

    acc.running = False
    log(Y,'■',f'[{acc.label}] Dừng | Done:{acc.stats["ok"]} Xu:{acc.stats["xu"]}')

# ══ MAIN ════════════════════════════════════════════════════
def run():
    global actual_port

    print(f'\n{W}╔═══════════════════════════════════════════╗')
    print(f'║   GoLike Bot v9 — TikTok + Pause/Resume   ║')
    print(f'║   Shopee + Lazada | Gemini AI Captcha    ║')
    print(f'╚═══════════════════════════════════════════╝{N}\n')

    delay = 5
    d = input(f'{C}Delay giữa job [5s]: {N}').strip()
    if d.isdigit(): delay = int(d)

    # ── Nhập tài khoản ────────────────────────────────────
    print(f'\n{Y}═══ NHẬP TÀI KHOẢN (Enter để kết thúc) ═══{N}')
    acc_list = []
    idx = 0
    while True:
        print(f'\n{W}─── Tài khoản {idx+1} ───{N}')
        token = input(f'{C}Bearer token (Enter để dừng): {N}').strip()
        if not token: break
        if token.startswith('Bearer '): token = token[7:]
        acc_id = input(f'{C}Account ID: {N}').strip()
        if not acc_id: break

        print(f'{C}Platform (1=Shopee, 2=Lazada, 3=TikTok, 4=Tất cả) [1]: {N}',end='')
        plt_choice = input().strip() or '1'
        if plt_choice == '1':   plts = ['shopee']
        elif plt_choice == '2': plts = ['lazada']
        elif plt_choice == '3': plts = ['tiktok']
        else:                   plts = ['shopee','lazada','tiktok']

        acc = Account(idx, token, acc_id, plts, delay)
        acc_list.append(acc)
        accounts.append(acc)
        all_stats[acc.label] = acc.stats
        log(G,'✓',f'Thêm {acc.label} | Platforms: {plts}')
        idx += 1

    if not acc_list:
        log(R,'✗','Chưa nhập tài khoản nào!')
        return

    # ── Start server ──────────────────────────────────────
    port = start_server()
    if not port: log(R,'✗','Không start server!'); return

    url = f'http://localhost:{port}'
    log(G,'✓',f'Server: {url}')
    log(G,'✓',f'Lịch sử: {HISTORY_FILE}')

    print(f'\n{Y}══ HƯỚNG DẪN ══════════════════════════════{N}')
    print(f'{C}1. Bot tự mở Chrome → {url}{N}')
    print(f'{C}2. Bấm "📱 Cho phép chụp" (1 lần duy nhất){N}')
    print(f'{C}3. {len(acc_list)} tài khoản chạy song song tự động{N}')
    print(f'{C}4. Tab "📋 Lịch sử" xem kết quả chi tiết{N}')
    print(f'{Y}════════════════════════════════════════════{N}\n')

    time.sleep(1)
    open_browser(url)
    print(f'\n{W}Đường dẫn: {Y}{url}{N}')
    input(f'{W}Nhấn ENTER khi đã thấy trang sẵn sàng...{N}\n')

    # ── Khởi động các worker thread ───────────────────────
    threads = []
    for acc in acc_list:
        t = threading.Thread(target=bot_worker, args=(acc, delay), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.3)  # Lệch nhau để tránh tranh token

    log(P,'🚀',f'{len(acc_list)} tài khoản đang chạy song song!')

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(2)
    except KeyboardInterrupt:
        log(Y,'!','Dừng tất cả...')
        for acc in accounts: acc.running = False

    # ── Tổng kết ──────────────────────────────────────────
    print(f'\n{W}═══ KẾT QUẢ TỪNG TÀI KHOẢN ═══{N}')
    total_ok=total_xu=total_sk=0
    for acc in accounts:
        total_ok+=acc.stats['ok']; total_xu+=acc.stats['xu']; total_sk+=acc.stats['sk']
        log(P,'★',f'[{acc.label}] Done:{acc.stats["ok"]} Skip:{acc.stats["sk"]} Xu:{acc.stats["xu"]}')
    print(f'\n{G}TỔNG: Done:{total_ok} Skip:{total_sk} Xu:{total_xu}{N}')
    log(G,'📋',f'Lịch sử đã lưu: {HISTORY_FILE}')

if __name__ == '__main__':
    run()
