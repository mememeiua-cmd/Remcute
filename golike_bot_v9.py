#!/usr/bin/env python3
"""
GoLike Bot v9 - GoLike Helper Integration
- Đa tài khoản: chạy song song nhiều token cùng lúc
- Hỗ trợ: Shopee + Lazada
- Lịch sử: lưu vào history.json, xem qua web UI
- Gemini AI: tự giải captcha qua GoLike Helper App (APK)
  → Chụp ảnh thật bằng MediaProjection
  → Click thật bằng Accessibility Service
  → Không cần root, không cần HTTPS
- Fallback: browser reCAPTCHA nếu Helper không có
"""
import requests, time, json, re, base64, threading, queue, os, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from datetime import datetime

# ══ CONFIG ══════════════════════════════════════════════════
GEMINI_KEY    = "AIzaSyB04DoRbSJH7efErVsANUoBuLAa9-vzkJQ"
GEMINI_URL    = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
RCAP_SITEKEY  = "6Leo5PMrAAAAAArIr7KjV49Pz4zRgLq05wIZy33w"
GW            = "https://gateway.golike.net"
HISTORY_FILE  = "golike_history.json"

# ── GoLike Helper App (Android APK) ─────────────────────────
HELPER_HOST   = "http://127.0.0.1:7788"   # localhost:7788 qua ADB forward
# Để dùng qua ADB: adb forward tcp:7788 tcp:7788
# Hoặc nếu Termux: dùng trực tiếp http://localhost:7788

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
}

R='\033[0;31m';G='\033[0;32m';Y='\033[1;33m'
C='\033[0;36m';P='\033[0;35m';W='\033[1;37m';N='\033[0m'
def log(c,i,m): print(f"{c}[{time.strftime('%H:%M:%S')}] {i} {m}{N}",flush=True)

def genT():
    ts=str(int(time.time()))
    return base64.b64encode(base64.b64encode(base64.b64encode(
        ts.encode()).decode().encode()).decode().encode()).decode()

# ══ HELPER APP CLIENT ════════════════════════════════════════
helper_available = False

def helper_ping(timeout=3):
    """Kiểm tra GoLike Helper App có đang chạy không."""
    global helper_available
    try:
        r = requests.get(f"{HELPER_HOST}/ping", timeout=timeout)
        d = r.json()
        if d.get('status') == 'ok':
            helper_available = True
            return d
    except Exception:
        pass
    helper_available = False
    return None

def helper_screenshot(quality=80, scale_div=2):
    """Chụp màn hình thật bằng MediaProjection."""
    try:
        r = requests.post(
            f"{HELPER_HOST}/screenshot",
            json={'quality': quality, 'scale_div': scale_div},
            timeout=10
        )
        d = r.json()
        if 'image' in d:
            return d['image'], d.get('width', 0), d.get('height', 0)
    except Exception as e:
        log(R,'✗',f'helper_screenshot: {e}')
    return None, 0, 0

def helper_tap(x, y):
    """Click một điểm bằng Accessibility Service."""
    try:
        r = requests.post(
            f"{HELPER_HOST}/tap",
            json={'x': x, 'y': y},
            timeout=5
        )
        d = r.json()
        return d.get('status') == 'ok'
    except Exception as e:
        log(R,'✗',f'helper_tap: {e}')
    return False

def helper_click_list(points):
    """Click nhiều điểm với delay. points = [{x,y,delay}, ...]"""
    try:
        r = requests.post(
            f"{HELPER_HOST}/click",
            json=points,
            timeout=30
        )
        d = r.json()
        return d.get('status') == 'ok', d.get('clicked', 0)
    except Exception as e:
        log(R,'✗',f'helper_click: {e}')
    return False, 0

def helper_solve_captcha(grid_top, grid_left, grid_w, grid_h):
    """
    Giải captcha hoàn toàn tự động:
    1. Chụp ảnh màn hình thật
    2. Gửi Gemini nhận dạng
    3. Click các ô đúng
    4. Click Verify
    Trả về: (success, challenge, indices_clicked)
    """
    try:
        r = requests.post(
            f"{HELPER_HOST}/solve_captcha",
            json={
                'gemini_key'   : GEMINI_KEY,
                'click_results': True,
                'quality'      : 85,
                'grid_top'     : grid_top,
                'grid_left'    : grid_left,
                'grid_w'       : grid_w,
                'grid_h'       : grid_h,
            },
            timeout=40
        )
        d = r.json()
        if d.get('status') == 'ok':
            ch  = d.get('challenge', '')
            idx = d.get('indices', [])
            log(G,'🤖',f'Helper giải: "{ch}" → {idx} → click {len(d.get("clicked",[]))} ô')
            return True, ch, idx
        else:
            log(R,'✗',f'Helper solve_captcha: {d.get("error","?")}')
    except Exception as e:
        log(R,'✗',f'helper_solve_captcha: {e}')
    return False, '', []

def solve_with_helper(acc_label, timeout=60):
    """
    Flow đầy đủ: chụp → Gemini → click → lấy token.
    Trả về captcha_token hoặc None.
    Ghi chú: flow này giải visual captcha trên màn hình điện thoại.
    Cần biết tọa độ của captcha grid trên màn hình.
    """
    if not helper_available:
        return None

    log(P,'📱',f'[{acc_label}] Dùng GoLike Helper App để giải captcha...')

    # Chụp ảnh để xác định vị trí captcha trên màn hình
    b64, w, h = helper_screenshot(quality=70, scale_div=1)
    if not b64:
        log(R,'✗',f'[{acc_label}] Không chụp được ảnh')
        return None

    log(C,'📷',f'[{acc_label}] Ảnh {w}×{h} | Gửi Gemini tìm captcha...')

    # Gửi Gemini để tìm vị trí captcha grid
    try:
        prompt_locate = (
            'This is a screenshot of an Android phone screen showing a Google reCAPTCHA challenge.\n'
            'Find the captcha image grid (3x3 grid of images).\n'
            'Also read the challenge title (what object to click).\n'
            'Reply ONLY in this format:\n'
            'GRID_TOP: <y pixel>\n'
            'GRID_LEFT: <x pixel>\n'
            'GRID_WIDTH: <width>\n'
            'GRID_HEIGHT: <height>\n'
            'CHALLENGE: <what to click>\n'
            'INDICES: [list of 0-8 indices]'
        )
        parts = [
            {'text': prompt_locate},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': b64}}
        ]
        gr = requests.post(
            GEMINI_URL + '?key=' + GEMINI_KEY,
            json={
                'contents': [{'parts': parts}],
                'generationConfig': {'temperature': 0, 'maxOutputTokens': 120}
            },
            timeout=20
        )
        gd  = gr.json()
        txt = (((gd.get('candidates',[{}])[0]).get('content',{}))
               .get('parts',[{}])[0]).get('text','')
        log(G,'🤖',f'[{acc_label}] Gemini locate: {txt.strip()[:80]}')

        # Parse tọa độ grid
        def gi(pattern, default):
            m = re.search(pattern, txt, re.I)
            return int(m.group(1)) if m else default

        grid_top  = gi(r'GRID_TOP[:\s]+(\d+)',    int(h * 0.25))
        grid_left = gi(r'GRID_LEFT[:\s]+(\d+)',   int(w * 0.03))
        grid_w    = gi(r'GRID_WIDTH[:\s]+(\d+)',  int(w * 0.94))
        grid_h    = gi(r'GRID_HEIGHT[:\s]+(\d+)', int(h * 0.55))

        # Parse indices từ response Gemini
        challenge = ''
        mc = re.search(r'CHALLENGE[:\s]+(.+)', txt, re.I)
        if mc: challenge = mc.group(1).strip()

        indices = []
        mi = re.search(r'INDICES[:\s]+(\[[\d,\s]*\])', txt, re.I)
        if mi:
            try: indices = json.loads(mi.group(1))
            except: pass

        log(C,'📐',f'[{acc_label}] Grid: top={grid_top} left={grid_left} w={grid_w} h={grid_h}')
        log(C,'🎯',f'[{acc_label}] Challenge: "{challenge}" | Indices: {indices}')

        if not indices:
            log(Y,'!',f'[{acc_label}] Gemini không tìm được ô → fallback')
            return None

        # Click các ô tìm được
        gT = grid_top + 75
        gL = grid_left + 8
        cW = (grid_w - 16) / 3
        cH = (grid_h - 75 - 50) / 3

        click_pts = []
        for idx in indices:
            if idx < 0 or idx > 8: continue
            cx = gL + (idx % 3) * cW + cW / 2
            cy = gT + (idx // 3) * cH + cH / 2
            click_pts.append({'x': round(cx), 'y': round(cy), 'delay': 400})

        if click_pts:
            ok, cnt = helper_click_list(click_pts)
            log(G if ok else Y, '✓' if ok else '!',
                f'[{acc_label}] Clicked {cnt} ô')
            time.sleep(1.0)
            # Click Verify button
            vx = grid_left + grid_w - 72
            vy = grid_top  + grid_h - 22
            helper_tap(round(vx), round(vy))
            log(G,'✓',f'[{acc_label}] Click Verify @ ({round(vx)},{round(vy)})')
            time.sleep(2.5)

        # Sau khi click, chụp lại để xem kết quả (optional)
        log(G,'✓',f'[{acc_label}] Helper đã xử lý captcha. Đợi token từ browser...')
        # Captcha visual → vẫn cần token từ browser sau khi solve
        # Trả về None để fallback sang get_cap_token (browser)
        # vì sau khi click visual captcha, reCAPTCHA sẽ emit token vào browser
        return None

    except Exception as e:
        log(R,'✗',f'[{acc_label}] solve_with_helper: {e}')
        return None

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
        h['jobs'] = h['jobs'][:500]
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
        self.platforms = platforms
        self.delay     = delay
        self.label     = f'Acc{idx+1}({acc_id})'
        self.stats     = {'ok':0,'sk':0,'xu':0,'cap':0}
        self.running   = False
        self.sess      = requests.Session()
        self.sess.headers.update({
            'User-Agent'     : 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                               '(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            'Accept-Language': 'vi-VN,vi;q=0.9',
            'Origin'         : 'https://app.golike.net',
            'Referer'        : 'https://app.golike.net/',
        })

    def api(self, method, url, body=None):
        auth = self.token if self.token.startswith('Bearer ') else 'Bearer ' + self.token
        h = {'Authorization': auth, 't': genT(), 'Accept': 'application/json'}
        if body: h['Content-Type'] = 'application/json;charset=UTF-8'
        r = self.sess.request(method, url, headers=h, json=body, timeout=20)
        return r.json()

    def get_jobs(self, platform):
        url = PLATFORMS[platform]['jobs']
        return self.api('GET', f'{url}?account_id={self.acc_id}')

    def complete(self, platform, ads_id, obj_id, cap_token):
        return self.api('POST', PLATFORMS[platform]['complete'], {
            'ads_id': ads_id, 'account_id': int(self.acc_id),
            'async': True, 'data': None, 'captcha_token': cap_token,
        })

    def skip(self, platform, ads_id, obj_id, jtype):
        try:
            self.api('POST', PLATFORMS[platform]['skip'], {
                'ads_id': ads_id, 'object_id': str(obj_id),
                'account_id': int(self.acc_id), 'type': jtype,
            })
        except: pass

# ══ SHARED STATE ════════════════════════════════════════════
accounts     = []
tok_q        = queue.Queue()
need_tok     = threading.Event()
current_jobs = {}
all_stats    = {}
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

# ══ GEMINI (Fallback) ═════════════════════════════════════════
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
        parts = [{'text': prompt}]
        for b64 in imgs_b64:
            parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': b64}})
        gr = requests.post(
            GEMINI_URL + '?key=' + GEMINI_KEY,
            json={'contents': [{'parts': parts}],
                  'generationConfig': {'temperature': 0, 'maxOutputTokens': 80}},
            timeout=15
        )
        gd = gr.json()
        if 'error' in gd:
            log(R,'✗',f'Gemini: {gd["error"].get("message","?")}')
            return [], ''
        txt = (((gd.get('candidates',[{}])[0]).get('content',{}))
               .get('parts',[{}])[0]).get('text','')
        log(G,'🤖',f'Gemini: {txt.strip()[:60]}')
        indices, challenge = '', ''
        mc = re.search(r'CHALLENGE[:\s]+(.+)', txt, re.I)
        if mc: challenge = mc.group(1).strip()
        mi = re.search(r'INDICES[:\s]+(\[[\d,\s]*\])', txt, re.I)
        if mi:
            try: indices = json.loads(mi.group(1))
            except: pass
        if not indices:
            m2 = re.search(r'\[[\d, ]+\]', txt)
            if m2:
                try: indices = json.loads(m2.group(0))
                except: pass
        return indices, challenge
    except Exception as e:
        log(R,'✗',f'gemini_solve: {e}')
        return [], ''

# ══ HTML (Web UI cho browser giải captcha) ═══════════════════
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
.helper-ok{{background:rgba(0,229,160,.07);border:2px solid rgba(0,229,160,.4);color:#00e5a0;border-radius:9px;padding:8px 12px;margin:6px 0;font-size:11px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.sp{{display:inline-block;width:9px;height:9px;border:2px solid rgba(255,255,255,.1);
     border-top-color:#ee4d2d;border-radius:50%;animation:spin .6s linear infinite;
     margin-right:4px;vertical-align:middle}}
hr{{border:none;border-top:1px solid #1a1a2e;margin:8px 0}}
.tabs{{display:flex;gap:0;border-bottom:1px solid #1a1a2e;margin-bottom:10px}}
.tab{{flex:1;padding:9px 4px;text-align:center;font-size:11px;color:#3a3a5c;
       cursor:pointer;border-bottom:2px solid transparent;transition:.2s}}
.tab.on{{color:#ee4d2d;border-color:#ee4d2d}}
.page{{display:none}}.page.on{{display:block}}
.acc-table{{width:100%;border-collapse:collapse;font-size:10px}}
.acc-table th{{background:#0f0f1a;color:#3a3a5c;padding:6px 4px;text-align:left;
               border-bottom:1px solid #1a1a2e;letter-spacing:.5px}}
.acc-table td{{padding:6px 4px;border-bottom:1px solid rgba(255,255,255,.03)}}
.badge{{display:inline-block;padding:1px 6px;border-radius:10px;font-size:9px}}
.b-run{{background:rgba(0,229,160,.12);color:#00e5a0;border:1px solid rgba(0,229,160,.2)}}
.b-wait{{background:rgba(255,179,0,.1);color:#ffb300;border:1px solid rgba(255,179,0,.2)}}
.plt-tag{{display:inline-block;padding:1px 5px;border-radius:4px;font-size:9px;margin:1px}}
.plt-sp{{background:rgba(238,77,45,.1);color:#ee4d2d}}
.plt-lz{{background:rgba(255,140,0,.1);color:#ff8c00}}
#cap-sec{{display:none;background:#0f0f1a;border:2px solid #ee4d2d;
          border-radius:12px;padding:12px;margin:8px 0}}
#cap-sec.on{{display:block}}
.cap-hdr{{color:#ee4d2d;font-size:11px;font-weight:700;letter-spacing:1px;
           margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;gap:4px}}
#rcap{{background:#fff;border-radius:8px;min-height:74px;
       display:flex;align-items:center;justify-content:center;padding:4px}}
#cap-log{{font-size:9px;color:#4a4a6a;background:#030308;border-radius:5px;
          padding:5px;max-height:60px;overflow-y:auto;margin-top:5px}}
.tb{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
     color:#777;border-radius:5px;padding:3px 7px;font-size:9px;cursor:pointer;white-space:nowrap}}
.total-banner{{background:linear-gradient(135deg,rgba(238,77,45,.1),rgba(255,179,0,.08));
               border:1px solid rgba(238,77,45,.2);border-radius:10px;
               padding:12px;margin:8px 0;display:grid;
               grid-template-columns:repeat(3,1fr);gap:6px;text-align:center}}
.tb-val{{font-size:24px;font-weight:800}}
.tb-lbl{{font-size:8px;color:#3a3a5c;margin-top:2px}}
.con{{background:#030308;border:1px solid #1a1a2e;border-radius:8px;
      padding:8px;height:150px;overflow-y:auto;font-size:10px;line-height:1.7}}
.con::-webkit-scrollbar{{width:2px}}
.con::-webkit-scrollbar-thumb{{background:#1a1a2e}}
.ll{{border-bottom:1px solid rgba(255,255,255,.02);padding:1px 0}}
.li{{color:#4fc3f7}}.ls{{color:#00e5a0}}.le{{color:#ff5252}}
.lw{{color:#ffb300}}.lp{{color:#ee4d2d}}.lc{{color:#b39ddb}}
.hist-item{{background:#0a0a14;border:1px solid #1a1a2e;border-radius:8px;
            padding:8px 10px;margin:5px 0;font-size:10px}}
.hist-ok{{border-left:3px solid #00e5a0}}
.hist-sk{{border-left:3px solid #3a3a5c}}
.hist-time{{color:#3a3a5c;font-size:9px}}
.hist-xu{{color:#ee4d2d;font-weight:700}}
#bg-b{{position:fixed;top:8px;right:8px;background:rgba(0,229,160,.12);
        border:1px solid rgba(0,229,160,.25);color:#00e5a0;border-radius:20px;
        padding:3px 9px;font-size:9px;display:none}}
#bg-b.on{{display:block}}
</style>
</head>
<body>
<div id="bg-b">🔋 Chạy ngầm</div>

<div class="wrap">
<h2>🛍️ GOLIKE BOT v9 — HELPER + AI AUTO</h2>

<!-- Helper Status -->
<div id="helper-status" class="box warn">📱 Đang kiểm tra GoLike Helper App...</div>

<!-- TABS -->
<div class="tabs">
  <div class="tab on" onclick="showTab('main',event)">📊 Chính</div>
  <div class="tab"    onclick="showTab('accs',event)">👥 Tài khoản</div>
  <div class="tab"    onclick="showTab('hist',event)">📋 Lịch sử</div>
</div>

<!-- TAB MAIN -->
<div id="tab-main" class="page on">
  <div id="st" class="box warn">⏳ Chờ bot...</div>
  <div id="job" class="box pu" style="display:none">
    Job: <b id="jtxt"></b> <span id="jacc" style="color:#3a3a5c"></span>
  </div>

  <!-- Captcha (fallback nếu không có Helper) -->
  <div id="cap-sec">
    <div class="cap-hdr">
      🤖 BROWSER CAPTCHA (Fallback)
      <button class="tb" onclick="doSolve();watchForBframe()">▶ Giải</button>
    </div>
    <div id="rcap"></div>
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
</div>

<script src="https://www.google.com/recaptcha/api.js?render=explicit" async defer></script>
<script>
'use strict';
var PORT    = {port};
var SITEKEY = '{RCAP_SITEKEY}';
var wid = null, solving = false, need_solving = false;
var bfReported=false, bfWatcher=null, bfLastH=0, bfStable=0;
var wakeLock=null;
var lastSolveActivity=0, watchdogTimer=null;

// ── Helper App Status ────────────────────────────────────────
var helperAvailable = false;
function checkHelper(){{
  fetch('/helper_status').then(function(r){{return r.json();}}).then(function(d){{
    helperAvailable = d.available;
    var el = document.getElementById('helper-status');
    if(d.available){{
      el.className='box ok';
      el.innerHTML='📱 GoLike Helper App: <b>Kết nối ✓</b> | Screen:'+d.screen_ready+' | Click:'+d.accessibility;
    }}else{{
      el.className='box warn';
      el.innerHTML='📱 GoLike Helper App: <b>Chưa kết nối</b> → Dùng browser fallback<br><small>Cài APK + ADB forward tcp:7788 tcp:7788</small>';
    }}
  }}).catch(function(){{
    document.getElementById('helper-status').className='box warn';
    document.getElementById('helper-status').innerHTML='📱 Helper: Không tìm thấy → Browser mode';
  }});
}}
setInterval(checkHelper, 5000);

// ── Tabs ─────────────────────────────────────────────────────
function showTab(name, evt){{
  document.querySelectorAll('.page').forEach(function(p){{p.classList.remove('on');}});
  document.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('on');}});
  document.getElementById('tab-'+name).classList.add('on');
  if(evt && evt.target) evt.target.classList.add('on');
  if(name==='hist') loadHistory();
  if(name==='accs') loadAccounts();
}}

// ── Wake Lock ────────────────────────────────────────────────
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
  if(document.visibilityState==='visible'){{if(!wakeLock)acquireWakeLock();}}
}});

// ── Watchdog ─────────────────────────────────────────────────
function markActivity(){{ lastSolveActivity=Date.now(); }}
function startWatchdog(){{
  if(watchdogTimer)clearInterval(watchdogTimer);
  watchdogTimer=setInterval(function(){{
    if(!solving) return;
    var idle=Date.now()-lastSolveActivity;
    if(idle>45000){{
      clog('⚠ Watchdog reset');
      solving=false; bfReported=false;
      if(bfWatcher){{clearInterval(bfWatcher);bfWatcher=null;}}
      try{{if(wid!==null)grecaptcha.reset(wid);}}catch(e){{}}
      setTimeout(function(){{
        fetch('/need_token').then(function(r){{return r.json();}}).then(function(d){{
          if(d.need&&!d.received){{doSolve();watchForBframe();}}
        }}).catch(function(){{}});
      }},1000);
    }}
  }},5000);
}}

// ── reCAPTCHA widget ─────────────────────────────────────────
function renderWidget(){{
  var box=document.getElementById('rcap');
  if(!box)return;
  if(wid!==null){{try{{grecaptcha.reset(wid);}}catch(e){{}}wid=null;}}
  function doRender(){{
    try{{
      wid=grecaptcha.render(box,{{
        sitekey:SITEKEY,size:'invisible',
        callback:function(token){{markActivity();clog('✓ Token '+token.length+'c');solving=false;tokenReceived(token);}},
        'error-callback':function(){{clog('error-cb → reset 2s');solving=false;markActivity();setTimeout(renderWidget,2000);}},
        'expired-callback':function(){{solving=false;if(need_solving){{setTimeout(function(){{doSolve();watchForBframe();}},500);}}}}
      }});
    }}catch(e){{setTimeout(renderWidget,1000);}}
  }}
  if(window.grecaptcha&&typeof grecaptcha.render==='function')doRender();
  else{{var iv=setInterval(function(){{if(window.grecaptcha&&typeof grecaptcha.render==='function'){{clearInterval(iv);doRender();}}}},200);}}
}}

function doSolve(){{
  if(solving)return;
  solving=true;need_solving=true;markActivity();
  setSt('<span class="sp"></span>Lấy token...');
  try{{
    if(wid===null){{renderWidget();setTimeout(doSolve,1500);return;}}
    grecaptcha.reset(wid);
    setTimeout(function(){{try{{grecaptcha.execute(wid);markActivity();}}catch(e){{solving=false;setTimeout(function(){{renderWidget();setTimeout(doSolve,1000);}},500);}}}},300);
  }}catch(e){{solving=false;clog('doSolve: '+e);}}
}}

// ── Watch bframe + Audio Challenge ───────────────────────────
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
    if(h<100){{bfLastH=0;bfStable=0;return;}}
    if(h!==bfLastH){{bfLastH=h;bfStable=0;return;}}
    if(++bfStable<2)return;
    bfReported=true;clearInterval(bfWatcher);bfWatcher=null;
    clog('✓ bframe '+h+'px → Audio solver');
    setSt('<span class="sp"></span>Audio challenge...');
    solveWithAudio(bf);
  }},400);
}}

async function solveWithAudio(bfEl){{
  try{{
    markActivity();
    var fr=bfEl.getBoundingClientRect();
    if(performance.clearResourceTimings)performance.clearResourceTimings();
    var audioClickPositions=[{{x:fr.left+45,y:fr.bottom-28}},{{x:fr.left+50,y:fr.bottom-25}},{{x:fr.left+38,y:fr.bottom-30}}];
    for(var i=0;i<audioClickPositions.length;i++){{
      var pos=audioClickPositions[i];
      var el=document.elementFromPoint(pos.x,pos.y);
      if(el){{['mousedown','mouseup','click'].forEach(function(ev){{el.dispatchEvent(new MouseEvent(ev,{{bubbles:true,cancelable:true,clientX:pos.x,clientY:pos.y}}));}});break;}}
    }}
    var audioUrl=null;
    for(var attempt=0;attempt<15;attempt++){{
      await sleep(800);markActivity();
      var entries=performance.getEntriesByType('resource');
      for(var j=0;j<entries.length;j++){{
        var u=entries[j].name;
        if(u.includes('recaptcha')&&(u.includes('audio')||u.includes('mp3')||u.includes('payload'))&&u.startsWith('https')){{audioUrl=u;break;}}
      }}
      if(audioUrl)break;
      if(attempt===4||attempt===8){{var el2=document.elementFromPoint(fr.left+45,fr.bottom-28);if(el2)el2.click();}}
    }}
    if(!audioUrl){{clog('⚠ Không bắt được audio URL → reset');bfReported=false;setTimeout(watchForBframe,3000);return;}}
    setSt('<span class="sp"></span>🎧 Fetch audio → Gemini...');markActivity();
    var audioB64=await fetchAsBase64(audioUrl);
    if(!audioB64){{bfReported=false;setTimeout(watchForBframe,3000);return;}}
    var resp=await fetch('/solve_audio',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{audio_b64:audioB64,url:audioUrl}})}});
    var d=await resp.json();markActivity();
    if(d.error||!d.text){{clog('Gemini audio lỗi');bfReported=false;setTimeout(watchForBframe,2000);return;}}
    var audioText=d.text.trim().toLowerCase().replace(/[^a-z0-9\s]/g,'').trim();
    clog('✓ Nghe được: "'+audioText+'"');
    setSt('🎧 "'+audioText+'" → điền...');
    var atd=document.getElementById('audio-text-display');
    if(atd){{atd.style.display='block';atd.textContent='🎧 AI nghe: "'+audioText+'"';}}
    var inputX=fr.left+fr.width/2,inputY=fr.top+fr.height*0.55;
    var inputEl=document.elementFromPoint(inputX,inputY);
    if(inputEl){{
      inputEl.focus();inputEl.click();await sleep(300);
      document.execCommand('insertText',false,audioText);await sleep(200);
      if(inputEl.value!==audioText){{inputEl.value=audioText;['input','change','keyup'].forEach(function(ev){{inputEl.dispatchEvent(new Event(ev,{{bubbles:true}}));}});}}
    }}
    await sleep(600);
    var vx=fr.right-72,vy=fr.bottom-22;
    var vel=document.elementFromPoint(vx,vy);
    if(vel)['mousedown','mouseup','click'].forEach(function(ev){{vel.dispatchEvent(new MouseEvent(ev,{{bubbles:true,cancelable:true,clientX:vx,clientY:vy}}));}});
    markActivity();setSt('⏳ Verify...');await sleep(2500);
    var bf2=document.querySelector('iframe[src*="bframe"]');
    if(bf2&&bf2.getBoundingClientRect().height>100&&solving){{bfReported=false;watchForBframe();}}
  }}catch(e){{clog('solveWithAudio: '+e);bfReported=false;setTimeout(watchForBframe,1500);}}
}}

async function fetchAsBase64(url){{
  try{{
    var r=await fetch(url,{{credentials:'omit',mode:'cors'}});
    if(!r.ok)r=await fetch('/img_proxy?url='+encodeURIComponent(url));
    if(!r.ok)return null;
    var ab=await r.arrayBuffer();
    if(ab.byteLength<100)return null;
    var bytes=new Uint8Array(ab),bin='';
    for(var i=0;i<bytes.byteLength;i+=8192)bin+=String.fromCharCode.apply(null,bytes.subarray(i,i+8192));
    return btoa(bin);
  }}catch(e){{clog('fetchAsBase64: '+e);return null;}}
}}

function sleep(ms){{return new Promise(function(r){{setTimeout(r,ms);}});}}

function tokenReceived(token){{
  solving=false;need_solving=false;
  if(bfWatcher){{clearInterval(bfWatcher);bfWatcher=null;}}
  document.getElementById('cap-sec').classList.remove('on');
  fetch('/token?t='+encodeURIComponent(token))
    .then(function(r){{return r.json();}})
    .then(function(d){{log(d.ok?'s':'e','Token '+(d.ok?'OK':'từ chối')+' ('+token.length+'c)');}}
    ).catch(function(e){{log('e','token: '+e);}});
}}

// ── Load tabs ────────────────────────────────────────────────
function loadAccounts(){{
  fetch('/accounts').then(function(r){{return r.json();}}).then(function(d){{
    var tb=document.getElementById('acc-tbody');if(!tb)return;
    tb.innerHTML=d.accounts.map(function(a){{
      var plts=a.platforms.map(function(p){{return '<span class="plt-tag plt-'+(p==='shopee'?'sp':'lz')+'">'+(p==='shopee'?'🛍️ Shopee':'🟠 Lazada')+'</span>';}}).join('');
      return '<tr><td style="color:#3a3a5c">'+(a.idx+1)+'</td><td style="font-weight:700">'+a.acc_id+'</td><td>'+plts+'</td><td style="color:#00e5a0">'+a.ok+'</td><td style="color:#ee4d2d">'+a.xu+'</td><td><span class="badge '+(a.running?'b-run':'b-wait')+'">'+(a.running?'Chạy':'Chờ')+'</span></td></tr>';
    }}).join('');
  }}).catch(function(){{}});
}}

function loadHistory(){{
  fetch('/history').then(function(r){{return r.json();}}).then(function(d){{
    var list=document.getElementById('hist-list'),cnt=document.getElementById('hist-count');
    if(!list)return;
    if(cnt)cnt.textContent=(d.jobs||[]).length+' jobs';
    list.innerHTML=(d.jobs||[]).slice(0,100).map(function(j){{
      var icon=j.platform==='lazada'?'🟠':'🛍️';
      return '<div class="hist-item '+(j.success?'hist-ok':'hist-sk')+'"><div style="display:flex;justify-content:space-between"><span>'+icon+' ['+j.type+'] #'+j.job_id+'</span>'+(j.success?'<span class="hist-xu">+'+j.coin+'xu</span>':'<span style="color:#3a3a5c">Skip</span>')+'</div><div style="display:flex;justify-content:space-between;margin-top:2px"><span class="hist-time">'+j.account+'</span><span class="hist-time">'+j.time+'</span></div></div>';
    }}).join('');
    var t=d.total||{{}};
    ['ok','xu','sk'].forEach(function(k){{var el=document.getElementById('t-'+k);if(el)el.textContent=t[k]||0;}});
  }}).catch(function(){{}});
}}

// ── Poll ─────────────────────────────────────────────────────
function poll(){{
  fetch('/need_token').then(function(r){{return r.json();}}).then(function(d){{
    if(d.received){{
      setStatus('✓ Token OK — đang xử lý...','ok');
      document.getElementById('job').style.display='none';
    }}else if(d.need){{
      setStatus('<span class="sp"></span><b>BOT CẦN TOKEN!</b>','err');
      var jel=document.getElementById('job');
      if(d.job){{jel.style.display='block';document.getElementById('jtxt').textContent=d.job;}}
      if(d.acc){{var ae=document.getElementById('jacc');if(ae)ae.textContent='['+d.acc+']';}}
      var sec=document.getElementById('cap-sec');
      if(!sec.classList.contains('on')){{
        sec.classList.add('on');
        document.getElementById('cap-log').innerHTML='';
        sec.scrollIntoView({{behavior:'smooth',block:'start'}});
        doSolve();watchForBframe();
      }}
    }}else{{
      setStatus('⏳ Chờ bot...','warn');
      document.getElementById('job').style.display='none';
      need_solving=false;
    }}
    setTimeout(poll,900);
  }}).catch(function(){{setTimeout(poll,2000);}});
}}
setInterval(loadHistory,10000);

// ── Helpers ──────────────────────────────────────────────────
function setSt(h){{var e=document.getElementById('cap-st');if(e)e.innerHTML=h;}}
function clog(m){{var e=document.getElementById('cap-log');if(e){{e.innerHTML='<div>'+m+'</div>'+e.innerHTML;if(e.childNodes.length>20)e.removeChild(e.lastChild);}};}}
function setStatus(h,c){{var e=document.getElementById('st');if(e){{e.innerHTML=h;e.className='box '+c;}}}}
function log(t,m){{
  var cls={{s:'ls',e:'le',w:'lw',c:'lc',i:'li'}}[t]||'li';
  var pre={{s:'✓',e:'✗',w:'!',c:'⏳',i:'›'}}[t]||'›';
  var con=document.getElementById('con');
  if(!con)return;
  var div=document.createElement('div');div.className='ll';
  div.innerHTML='<span class="'+cls+'">'+pre+' '+m+'</span>';
  con.insertBefore(div,con.firstChild);
  while(con.childNodes.length>100)con.removeChild(con.lastChild);
}}

window.addEventListener('load',function(){{
  acquireWakeLock();
  renderWidget();
  loadHistory();
  checkHelper();
  startWatchdog();
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
        self.send_header('Content-Length', str(len(b)))
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
            self.send_header('Content-Length', str(len(b)))
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

        elif p.path == '/helper_status':
            d = helper_ping(timeout=2)
            if d:
                self.send_json(200,{
                    'available'    : True,
                    'screen_ready' : d.get('screen_ready', False),
                    'accessibility': d.get('accessibility', False),
                    'requests'     : d.get('requests', 0),
                    'screenshots'  : d.get('screenshots', 0),
                    'clicks'       : d.get('clicks', 0),
                })
            else:
                self.send_json(200,{'available': False})

        elif p.path == '/img_proxy':
            url = qs.get('url',[''])[0]
            if not url.startswith('http'):
                self.send_response(400); self.end_headers(); return
            try:
                ir = requests.get(url, timeout=8, headers={'Referer':'https://www.google.com/'})
                self.send_response(ir.status_code)
                self.send_header('Content-Type', ir.headers.get('Content-Type','image/jpeg'))
                self.send_header('Access-Control-Allow-Origin','*')
                self.send_header('Content-Length', str(len(ir.content)))
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
            try:
                payload   = json.loads(body)
                audio_b64 = payload.get('audio_b64','')
                if not audio_b64:
                    self.send_json(400,{'error':'no audio'}); return
                log(C,'🎧',f'Audio {len(audio_b64)//1024}KB → Gemini transcribe...')
                parts = [
                    {'text': (
                        'This is a Google reCAPTCHA audio challenge MP3 file.\n'
                        'Transcribe ONLY the digits/words spoken, nothing else.\n'
                        'Example: "47382" or "three five nine two"\n'
                        'Just the answer, no explanation.'
                    )},
                    {'inline_data': {'mime_type': 'audio/mp3', 'data': audio_b64}}
                ]
                gr = requests.post(
                    GEMINI_URL+'?key='+GEMINI_KEY,
                    json={'contents': [{'parts': parts}],
                          'generationConfig': {'temperature':0,'maxOutputTokens':30}},
                    timeout=20
                )
                gd  = gr.json()
                if 'error' in gd:
                    msg = gd['error'].get('message','?')
                    log(R,'✗',f'Gemini audio: {msg}')
                    self.send_json(200,{'error':msg,'text':''}); return
                txt   = (((gd.get('candidates',[{}])[0]).get('content',{}))
                         .get('parts',[{}])[0]).get('text','').strip()
                clean = re.sub(r'[^a-z0-9 ]','', txt.lower()).strip()
                log(G,'🎧',f'Transcribed: "{clean}"')
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
                self.send_json(200,{'indices':indices,'challenge':challenge})
            except Exception as e:
                self.send_json(500,{'error':str(e),'indices':[]})

        else:
            self.send_response(404); self.end_headers()


def start_server():
    global actual_port
    for port in [8080,9191,8181,7777,6666]:
        try:
            srv = HTTPServer(('0.0.0.0',port), Handler)
            srv.allow_reuse_address = True
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            actual_port = port
            return port
        except OSError:
            continue
    return None

def open_browser(url):
    import subprocess as _sp
    opened = False
    if os.path.exists('/data/data/com.termux'):
        for cmd in [
            ['am','start','-a','android.intent.action.VIEW','-d',url,
             '-n','com.android.chrome/com.google.android.apps.chrome.Main'],
            ['termux-open-url',url],
            ['am','start','-a','android.intent.action.VIEW','-d',url],
        ]:
            try:
                if _sp.run(cmd, capture_output=True, timeout=5).returncode == 0:
                    opened=True; break
            except: pass
    if not opened and sys.platform.startswith('linux'):
        for cmd in [['google-chrome','--new-tab',url],['chromium-browser',url],
                    ['xdg-open',url],['firefox',url]]:
            try: _sp.Popen(cmd, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL); opened=True; break
            except FileNotFoundError: continue
    if not opened and sys.platform == 'win32':
        try: os.startfile(url); opened=True
        except: pass
    if not opened and sys.platform == 'darwin':
        try: _sp.Popen(['open',url]); opened=True
        except: pass
    log(G if opened else Y, '→', f'Browser: {url}')
    return opened

# ══ BOT WORKER ═══════════════════════════════════════════════
def bot_worker(acc: Account, delay: int):
    acc.running = True
    log(P,'🛍️',f'[{acc.label}] Bắt đầu | Platforms: {acc.platforms}')
    platform_idx = 0

    while acc.running:
        try:
            platform     = acc.platforms[platform_idx % len(acc.platforms)]
            platform_idx += 1
            icon         = PLATFORMS[platform]['icon']

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

            current_jobs[acc.label] = {
                'uid':uid,'type':jtype,'coin':coin,'platform':platform,'label':acc.label
            }
            log(W, icon, f'[{acc.label}][{platform}] #{uid} "{title[:28]}" +{coin}xu')

            # ── Lấy captcha token ──────────────────────────
            cap = get_cap_token(acc.label, timeout=min(lock-delay-5, 90))
            if not cap:
                acc.skip(platform, uid, objId, jtype)
                acc.stats['sk'] += 1
                record_job(acc.label, platform, jtype, uid, 0, False, False)
                current_jobs.pop(acc.label, None)
                continue

            acc.stats['cap'] += 1
            log(C,'⏳',f'[{acc.label}] Delay {delay}s...'); time.sleep(delay)

            # ── Complete ───────────────────────────────────
            ok = False
            for url in [PLATFORMS[platform]['complete'],
                        PLATFORMS[platform]['complete'].replace('gateway','dev')]:
                try:
                    res  = acc.complete(platform, uid, objId, cap)
                    rst  = int(res.get('status') or res.get('code') or 0)
                    rmsg = str(res.get('message') or '')
                    log(C,'>',f'[{acc.label}] {json.dumps(res,ensure_ascii=False)[:100]}')

                    if rst==200 or res.get('success') in (True,'1',1) \
                       or re.search(r'thanh.?cong|success|done|completed',rmsg,re.I):
                        earned = int((res.get('data') or {}).get('coin') or coin or 0)
                        acc.stats['ok'] += 1; acc.stats['xu'] += earned; ok = True
                        log(G,'✓',f'[{acc.label}] DONE #{acc.stats["ok"]} +{earned}xu')
                        record_job(acc.label, platform, jtype, uid, earned, True, True)
                        break

                    elif re.search(r'captcha|robot',rmsg,re.I):
                        log(Y,'!',f'[{acc.label}] Captcha từ chối → thử lại')
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

    print(f'\n{W}╔════════════════════════════════════════════╗')
    print(f'║   GoLike Bot v9 — Helper + AI Auto        ║')
    print(f'║   Shopee + Lazada | GoLike Helper APK      ║')
    print(f'╚════════════════════════════════════════════╝{N}\n')

    # ── Kiểm tra GoLike Helper App ──────────────────────────
    print(f'{C}Kiểm tra GoLike Helper App tại {HELPER_HOST}...{N}')
    d = helper_ping(timeout=3)
    if d:
        log(G,'📱',f'GoLike Helper App KẾT NỐI! Screen:{d.get("screen_ready")} Click:{d.get("accessibility")}')
        log(G,'✓','Bot sẽ dùng Helper để chụp màn hình và click thật')
    else:
        log(Y,'!',f'GoLike Helper App KHÔNG tìm thấy tại {HELPER_HOST}')
        log(Y,'!','→ Cài APK lên điện thoại rồi chạy: adb forward tcp:7788 tcp:7788')
        log(Y,'!','→ Hoặc nếu chạy trên Termux: bỏ qua, dùng localhost:7788')
        log(Y,'!','→ Bot sẽ dùng browser fallback để giải captcha')

    delay = 5
    d_in = input(f'\n{C}Delay giữa job [5s]: {N}').strip()
    if d_in.isdigit(): delay = int(d_in)

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

        print(f'{C}Platform (1=Shopee, 2=Lazada, 3=Cả hai) [1]: {N}', end='')
        plt_choice = input().strip() or '1'
        if plt_choice == '1':   plts = ['shopee']
        elif plt_choice == '2': plts = ['lazada']
        else:                   plts = ['shopee','lazada']

        acc = Account(idx, token, acc_id, plts, delay)
        acc_list.append(acc)
        accounts.append(acc)
        all_stats[acc.label] = acc.stats
        log(G,'✓',f'Thêm {acc.label} | Platforms: {plts}')
        idx += 1

    if not acc_list:
        log(R,'✗','Chưa nhập tài khoản nào!'); return

    port = start_server()
    if not port: log(R,'✗','Không start server!'); return

    url = f'http://localhost:{port}'
    log(G,'✓',f'Web UI: {url}')

    print(f'\n{Y}══ HƯỚNG DẪN ══════════════════════════════{N}')
    print(f'{C}1. Mở Chrome: {url}{N}')
    print(f'{C}2. {len(acc_list)} tài khoản chạy song song tự động{N}')
    if helper_available:
        print(f'{G}3. GoLike Helper App đang kết nối ✓{N}')
        print(f'{G}   → Captcha sẽ được chụp ảnh và click thật!{N}')
    else:
        print(f'{Y}3. Dùng browser để giải captcha (fallback){N}')
    print(f'{Y}════════════════════════════════════════════{N}\n')

    time.sleep(1)
    open_browser(url)
    print(f'\n{W}URL: {Y}{url}{N}')
    input(f'{W}Nhấn ENTER khi sẵn sàng...{N}\n')

    threads = []
    for acc in acc_list:
        t = threading.Thread(target=bot_worker, args=(acc, delay), daemon=True)
        t.start(); threads.append(t)
        time.sleep(0.3)

    log(P,'🚀',f'{len(acc_list)} tài khoản đang chạy!')

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(2)
    except KeyboardInterrupt:
        log(Y,'!','Dừng tất cả...')
        for acc in accounts: acc.running = False

    print(f'\n{W}═══ KẾT QUẢ ═══{N}')
    total_ok=total_xu=total_sk=0
    for acc in accounts:
        total_ok+=acc.stats['ok']; total_xu+=acc.stats['xu']; total_sk+=acc.stats['sk']
        log(P,'★',f'[{acc.label}] Done:{acc.stats["ok"]} Skip:{acc.stats["sk"]} Xu:{acc.stats["xu"]}')
    print(f'\n{G}TỔNG: Done:{total_ok} Skip:{total_sk} Xu:{total_xu}{N}')
    log(G,'📋',f'Lịch sử: {HISTORY_FILE}')

if __name__ == '__main__':
    run()
