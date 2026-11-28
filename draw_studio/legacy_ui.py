"""HTML / CSS / JS for Colab Studio (single page, no external assets)."""

LOGIN_HTML = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>登录 · Colab Studio</title>
<script>(function(){try{var t=localStorage.getItem('colab-studio.theme')||'light';document.documentElement.dataset.theme=t;}catch(e){document.documentElement.dataset.theme='light';}})();</script>
<style>
  :root{color-scheme:dark;--bg:#07080d;--card:rgba(20,22,34,.78);--line:rgba(255,255,255,.1);--text:#eceef6;--muted:#8b91a7;--in:rgba(0,0,0,.35);--sh:0 30px 80px rgba(0,0,0,.45);--err:#fca5a5}
  :root[data-theme="light"]{color-scheme:light;--bg:#f4f6fb;--card:rgba(255,255,255,.92);--line:rgba(15,23,42,.1);--text:#0f172a;--muted:#64748b;--in:#f8fafc;--sh:0 24px 60px rgba(15,23,42,.1);--err:#dc2626}
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:grid;place-items:center;color:var(--text);
    font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    background:radial-gradient(900px 500px at 15%% -10%%,rgba(139,92,246,.16),transparent 60%%),
      radial-gradient(800px 500px at 110%% 110%%,rgba(34,211,238,.12),transparent 60%%),var(--bg)}
  form{width:min(360px,92vw);display:grid;gap:14px;padding:32px 28px;border-radius:20px;
    background:var(--card);border:1px solid var(--line);backdrop-filter:blur(18px);box-shadow:var(--sh)}
  .logo{width:46px;height:46px;border-radius:14px;background:linear-gradient(135deg,#8b5cf6,#6366f1 45%%,#22d3ee);
    display:grid;place-items:center;box-shadow:0 10px 30px rgba(99,102,241,.35)}
  h1{margin:4px 0 0;font-size:22px;letter-spacing:.2px}
  p{margin:0;color:var(--muted);font-size:13px}
  input{padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:var(--in);
    color:inherit;font-size:15px;outline:none;transition:border-color .15s,box-shadow .15s}
  input:focus{border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.2)}
  button{padding:12px;border:0;border-radius:12px;color:#fff;font-weight:650;font-size:15px;cursor:pointer;
    background:linear-gradient(135deg,#7c3aed,#6366f1 45%%,#06b6d4);box-shadow:0 10px 26px rgba(99,102,241,.3)}
  button:hover{filter:brightness(1.06)}
  .err{color:var(--err);min-height:1.2em;font-size:13px}
</style></head>
<body><form method="post" action="login">
  <div class="logo"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 3v4M17 5h4M5 17v4M3 19h4"/></svg></div>
  <div><h1>Colab Studio</h1><p>生图 · 改图 · 生视频 Playground</p></div>
  <input type="password" name="password" placeholder="访问密码" autofocus autocomplete="current-password">
  <button>进入工作台</button>
  <div class="err">%s</div>
</form></body></html>
"""

_CSS = r"""
:root{
  color-scheme:dark;
  --bg:#07080d;--bg-glow1:rgba(139,92,246,.16);--bg-glow2:rgba(34,211,238,.10);
  --topbar-bg:rgba(7,8,13,.84);
  --panel:rgba(17,19,30,.86);--card:rgba(255,255,255,.035);--card2:rgba(255,255,255,.065);
  --surface:rgba(0,0,0,.25);--surface2:rgba(0,0,0,.35);--input-bg:rgba(0,0,0,.32);--option-bg:#151826;
  --gobar-bg:rgba(12,13,21,.94);--modal-bg:#10121c;--drawer-bg:#0f111a;--toast-bg:#151826;
  --viewer-bg:#05060a;--viewer-check:rgba(255,255,255,.028);--thumb-bg:#0b0c12;
  --progress-bg:rgba(10,11,18,.86);--log-bg:rgba(6,7,11,.97);--log-text:#c9cede;--log-err:#fca5a5;--log-ok:#86efac;
  --line:rgba(255,255,255,.08);--line2:rgba(255,255,255,.16);--scroll:rgba(255,255,255,.14);
  --text:#eceef6;--muted:#9399b0;--dim:#646a82;--prompt-text:#d6d9e6;
  --a1:#8b5cf6;--a2:#22d3ee;--a3:#6366f1;--grad:linear-gradient(135deg,#8b5cf6,#6366f1 45%,#22d3ee);
  --ok:#34d399;--warn:#fbbf24;--bad:#f87171;--info:#60a5fa;--r:14px;
  --danger-fg:#fecaca;--danger-bg:rgba(248,113,113,.12);--danger-bd:rgba(248,113,113,.35);
  --pchip-on-fg:#fff;--pchip-on-bg:rgba(139,92,246,.22);--pchip-on-bd:rgba(139,92,246,.75);
  --eng-on-fg:#fff;--eng-on-bg:rgba(139,92,246,.24);--eng-on-bd:rgba(139,92,246,.55);
  --badge-run-fg:#6ee7b7;--badge-run-bg:rgba(16,185,129,.14);--badge-run-bd:rgba(16,185,129,.35);
  --badge-ok-fg:#93c5fd;--badge-ok-bg:rgba(59,130,246,.12);--badge-ok-bd:rgba(59,130,246,.28);
  --badge-warn-fg:#fcd34d;--badge-warn-bg:rgba(245,158,11,.14);--badge-warn-bd:rgba(245,158,11,.35);
  --badge-bad-fg:#fda4af;--badge-bad-bg:rgba(244,63,94,.14);--badge-bad-bd:rgba(244,63,94,.35);
  --fmt-fg:#67e8f9;--fmt-bg:rgba(34,211,238,.14);--fmt-bd:rgba(34,211,238,.28);
  --fmt-nv-fg:#ddd6fe;--fmt-nv-bg:rgba(139,92,246,.2);--fmt-nv-bd:rgba(139,92,246,.4);
  --range-track:rgba(255,255,255,.14);--tg-off:rgba(255,255,255,.16);
  --shadow:0 16px 48px rgba(0,0,0,.42);
}
:root[data-theme="light"]{
  color-scheme:light;
  --bg:#f2f5fa;--bg-glow1:rgba(124,58,237,.08);--bg-glow2:rgba(6,182,212,.07);
  --topbar-bg:rgba(255,255,255,.88);
  --panel:#ffffff;--card:#f8fafc;--card2:#f1f5f9;
  --surface:#f1f5f9;--surface2:#e8edf5;--input-bg:#ffffff;--option-bg:#ffffff;
  --gobar-bg:rgba(255,255,255,.96);--modal-bg:#ffffff;--drawer-bg:#ffffff;--toast-bg:#ffffff;
  --viewer-bg:#eef2f7;--viewer-check:rgba(15,23,42,.045);--thumb-bg:#e2e8f0;
  --progress-bg:rgba(255,255,255,.94);--log-bg:#0f172a;--log-text:#e2e8f0;--log-err:#fca5a5;--log-ok:#86efac;
  --line:rgba(15,23,42,.09);--line2:rgba(15,23,42,.18);--scroll:rgba(15,23,42,.18);
  --text:#0f172a;--muted:#475569;--dim:#64748b;--prompt-text:#1e293b;
  --a1:#7c3aed;--a2:#0891b2;--a3:#4f46e5;--grad:linear-gradient(135deg,#7c3aed,#4f46e5 50%,#06b6d4);
  --ok:#059669;--warn:#d97706;--bad:#dc2626;--info:#2563eb;--r:14px;
  --danger-fg:#dc2626;--danger-bg:rgba(220,38,38,.08);--danger-bd:rgba(220,38,38,.28);
  --pchip-on-fg:#5b21b6;--pchip-on-bg:rgba(124,58,237,.12);--pchip-on-bd:rgba(124,58,237,.55);
  --eng-on-fg:#5b21b6;--eng-on-bg:#ffffff;--eng-on-bd:rgba(124,58,237,.45);
  --badge-run-fg:#047857;--badge-run-bg:rgba(16,185,129,.12);--badge-run-bd:rgba(16,185,129,.35);
  --badge-ok-fg:#1d4ed8;--badge-ok-bg:rgba(37,99,235,.10);--badge-ok-bd:rgba(37,99,235,.28);
  --badge-warn-fg:#b45309;--badge-warn-bg:rgba(245,158,11,.14);--badge-warn-bd:rgba(245,158,11,.35);
  --badge-bad-fg:#be123c;--badge-bad-bg:rgba(225,29,72,.10);--badge-bad-bd:rgba(225,29,72,.3);
  --fmt-fg:#0e7490;--fmt-bg:rgba(6,182,212,.12);--fmt-bd:rgba(6,182,212,.3);
  --fmt-nv-fg:#6d28d9;--fmt-nv-bg:rgba(124,58,237,.12);--fmt-nv-bd:rgba(124,58,237,.32);
  --range-track:rgba(15,23,42,.14);--tg-off:rgba(15,23,42,.2);
  --shadow:0 8px 30px rgba(15,23,42,.08);
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{font:14px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--text);
  background:radial-gradient(1200px 640px at 8% -12%,var(--bg-glow1),transparent 60%),
    radial-gradient(900px 520px at 108% 0%,var(--bg-glow2),transparent 60%),var(--bg);background-attachment:fixed;
  display:flex;flex-direction:column;height:100dvh;overflow:hidden}
button,input,select,textarea{font:inherit;color:inherit}
a{color:var(--a2)}
.ic{width:16px;height:16px;flex:none;display:inline-block;vertical-align:middle}
.ic.lg{width:20px;height:20px}.ic.xl{width:40px;height:40px}
::-webkit-scrollbar{width:9px;height:9px}::-webkit-scrollbar-thumb{background:var(--scroll);border-radius:10px;border:2px solid transparent;background-clip:padding-box}
::selection{background:rgba(124,58,237,.28)}

/* ── top bar ── */
.topbar{flex:none;z-index:40;display:flex;align-items:center;gap:12px;padding:10px 18px;
  background:var(--topbar-bg);backdrop-filter:blur(16px) saturate(140%);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;letter-spacing:.2px;white-space:nowrap}
.brand .logo{width:32px;height:32px;border-radius:10px;background:var(--grad);color:#fff;display:grid;place-items:center;box-shadow:0 6px 18px rgba(99,102,241,.35)}
.brand small{color:var(--dim);font-weight:500;font-size:11px;margin-left:2px}
.grow{flex:1}
.chip{display:inline-flex;align-items:center;gap:7px;height:32px;padding:0 12px;border-radius:999px;border:1px solid var(--line);
  background:var(--card);color:var(--muted);font-size:12.5px;white-space:nowrap;cursor:default}
button.chip{cursor:pointer}button.chip:hover{border-color:var(--line2);color:var(--text)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--dim);flex:none}
.dot.ok{background:var(--ok);box-shadow:0 0 0 3px rgba(52,211,153,.2)}
.dot.warn{background:var(--warn);box-shadow:0 0 0 3px rgba(251,191,36,.2)}
.dot.bad{background:var(--bad);box-shadow:0 0 0 3px rgba(248,113,113,.2)}
.dot.busy{background:var(--a2);animation:pulse 1.2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,211,238,.55)}100%{box-shadow:0 0 0 9px rgba(34,211,238,0)}}
.iconbtn{width:34px;height:34px;flex:none;display:inline-grid;place-items:center;border-radius:10px;border:1px solid var(--line);background:var(--card);
  color:var(--muted);cursor:pointer;transition:.15s;position:relative;text-decoration:none}
.iconbtn:hover{color:var(--text);border-color:var(--line2);background:var(--card2)}
.iconbtn.on{color:var(--a1);border-color:rgba(124,58,237,.55);background:rgba(124,58,237,.12)}
.badge{position:absolute;top:-5px;right:-5px;min-width:17px;height:17px;padding:0 4px;border-radius:9px;background:var(--a1);color:#fff;font-size:10.5px;
  display:grid;place-items:center;font-weight:700}

/* ── buttons ── */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;height:36px;padding:0 14px;border-radius:11px;border:1px solid var(--line);
  background:var(--card2);color:var(--text);font-weight:600;font-size:13px;cursor:pointer;transition:.15s;white-space:nowrap}
.btn:hover{border-color:var(--line2);background:var(--surface2)}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn.sm{height:30px;padding:0 10px;font-size:12.5px;border-radius:9px}
.btn.primary{border:0;background:var(--grad);color:#fff;box-shadow:0 8px 22px rgba(99,102,241,.28)}
.btn.primary:hover{filter:brightness(1.06)}
.btn.danger{border-color:var(--danger-bd);background:var(--danger-bg);color:var(--danger-fg)}
.btn.danger:hover{filter:brightness(1.04);background:rgba(239,68,68,.18)}
.btn.ghost{background:transparent}
.btn.solid-danger{border:0;background:#ef4444;color:#fff}
.btn.solid-danger:hover{background:#dc2626}

/* ── top workspace nav & serverless badge ── */
.ws-nav{display:inline-flex;gap:3px;padding:3px;border-radius:11px;background:var(--surface2);border:1px solid var(--line)}
.ws-nav button{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 12px;border:0;border-radius:8px;background:transparent;color:var(--muted);font-size:12.5px;font-weight:650;cursor:pointer;transition:.16s;white-space:nowrap}
.ws-nav button:hover{color:var(--text);background:var(--card)}
.ws-nav button.on{background:var(--grad);color:#fff;box-shadow:0 3px 12px rgba(99,102,241,.28)}
.sv-pill{font-size:10px;font-weight:750;letter-spacing:.4px;padding:1px 6px;border-radius:5px;text-transform:uppercase;border:1px solid transparent}
.sv-pill.warm{color:var(--badge-run-fg);background:var(--badge-run-bg);border-color:var(--badge-run-bd)}
.sv-pill.cold{color:var(--dim);background:var(--surface2);border-color:var(--line)}
.sv-pill.busy{color:var(--fmt-fg);background:var(--fmt-bg);border-color:var(--fmt-bd)}
.sv-pill.warn{color:var(--badge-warn-fg);background:var(--badge-warn-bg);border-color:var(--badge-warn-bd)}
.sv-pill.bad{color:var(--badge-bad-fg);background:var(--badge-bad-bg);border-color:var(--badge-bad-bd)}
.tip-q{display:inline-grid;place-items:center;width:15px;height:15px;border-radius:50%;border:1px solid var(--line2);color:var(--dim);font-size:10px;font-weight:700;cursor:help;margin-left:4px;vertical-align:middle}
.mp-badge{font-size:11px;color:var(--a2);font-weight:600;background:var(--fmt-bg);border:1px solid var(--fmt-bd);padding:1px 7px;border-radius:6px}
.preset-bar{display:flex;align-items:center;gap:6px;margin-bottom:10px}
.preset-bar select{height:32px;padding:4px 8px;font-size:12.5px;flex:1}
.hist-pop{margin-top:6px;padding:6px;border-radius:10px;border:1px solid var(--line2);background:var(--panel);box-shadow:var(--shadow);max-height:200px;overflow:auto;display:grid;gap:4px}
.hist-item{text-align:left;padding:6px 8px;border-radius:7px;border:1px solid transparent;background:var(--surface);color:var(--text);font-size:12px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hist-item:hover{border-color:var(--a1);background:var(--pchip-on-bg)}
.wc-pill{display:inline-flex;align-items:center;gap:4px;padding:1px 7px;border-radius:6px;font-size:11px;color:var(--muted);background:var(--surface);border:1px dashed var(--line2);cursor:pointer}
.wc-pill:hover{color:var(--text);border-color:var(--a1)}

/* ── A/B compare slider ── */
.ab-wrap{position:relative;width:100%;height:min(66vh,560px);background:var(--viewer-bg);border-radius:12px;overflow:hidden;border:1px solid var(--line);user-select:none}
.ab-wrap img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;pointer-events:none}
.ab-top{position:absolute;inset:0;overflow:hidden}
.ab-line{position:absolute;top:0;bottom:0;width:2px;background:#fff;box-shadow:0 0 10px rgba(0,0,0,.7);pointer-events:none;z-index:3}
.ab-handle{position:absolute;top:50%;transform:translate(-50%,-50%);width:34px;height:34px;border-radius:50%;background:var(--grad);color:#fff;border:2px solid #fff;display:grid;place-items:center;font-weight:700;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.45);pointer-events:none;z-index:4}
.ab-tag{position:absolute;top:10px;z-index:3;padding:3px 9px;border-radius:7px;background:rgba(0,0,0,.68);color:#fff;font-size:12px;font-weight:600}
.ab-tag.l{left:10px}.ab-tag.r{right:10px}
.ab-range{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:ew-resize;z-index:5;margin:0}

/* ── Tab 3: Long-Video Workflow Studio ── */
.wf-layout{flex:1;min-height:0;width:100%;display:grid;grid-template-columns:clamp(270px,22vw,330px) minmax(0,1fr);gap:16px;padding:14px 18px;overflow:hidden}
.wf-side{height:100%;min-height:0;display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);overflow:hidden}
.wf-side-scroll{flex:1;min-height:0;overflow:auto;padding:12px}
.wf-main{height:100%;min-height:0;display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);overflow:hidden}
.wf-head{flex:none;padding:14px 16px;border-bottom:1px solid var(--line);background:var(--card);display:grid;gap:10px}
.wf-canvas{flex:1;min-height:0;overflow:auto;padding:16px;display:flex;flex-direction:column;gap:0}
.wf-item{width:100%;min-width:0;overflow:hidden;text-align:left;padding:9px 11px;border-radius:11px;border:1px solid var(--line);background:var(--card);cursor:pointer;transition:.15s;margin-bottom:6px;display:grid;grid-template-columns:minmax(0,1fr);gap:3px}
.wf-item:hover{border-color:var(--line2);background:var(--card2)}
.wf-item.on{border-color:var(--pchip-on-bd);background:var(--pchip-on-bg)}
.wf-item .wt{font-weight:650;font-size:13px;display:flex;align-items:center;gap:6px;min-width:0;width:100%}
.wf-item .wt-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.wf-item .ws{font-size:11.5px;color:var(--dim);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.wf-x{flex:none;width:22px;height:22px;border-radius:6px;border:0;background:transparent;color:var(--dim);cursor:pointer;display:grid;place-items:center;font-size:15px;line-height:1;padding:0}
.wf-x:hover{background:var(--danger-bg);color:var(--bad)}
.wf-st{flex:none;white-space:nowrap;font-size:11px;padding:2px 8px;border-radius:99px;font-weight:600;border:1px solid transparent}
.wf-arrow{display:flex;align-items:center;justify-content:center;height:22px;color:var(--dim);font-size:13px;user-select:none}
.wf-node{border:1px solid var(--line);border-radius:15px;background:var(--card);overflow:hidden;transition:border-color .15s}
.wf-node.running{border-color:var(--a2);box-shadow:0 0 0 2px rgba(34,211,238,.2)}
.wf-node.done{border-color:rgba(16,185,129,.42)}
.wf-node.error{border-color:rgba(239,68,68,.5)}
.wf-node.disabled{opacity:.58}
.wf-nh{display:flex;align-items:center;gap:8px;padding:10px 14px;background:var(--surface);border-bottom:1px solid var(--line);flex-wrap:wrap}
.wf-nb{padding:12px 14px;display:grid;gap:10px}
.wf-type{font-size:11px;padding:2px 7px;border-radius:6px;background:var(--surface2);color:var(--muted);border:1px solid var(--line);font-weight:600}
.wf-st.pending{color:var(--dim);background:var(--surface2);border-color:var(--line)}
.wf-st.running{color:var(--fmt-fg);background:var(--fmt-bg);border-color:var(--fmt-bd)}
.wf-st.done{color:var(--badge-run-fg);background:var(--badge-run-bg);border-color:var(--badge-run-bd)}
.wf-st.paused{color:var(--badge-warn-fg);background:var(--badge-warn-bg);border-color:var(--badge-warn-bd)}
.wf-st.error,.wf-st.canceled{color:var(--badge-bad-fg);background:var(--badge-bad-bg);border-color:var(--badge-bad-bd)}
.wf-st.skipped{color:var(--dim);background:var(--surface);border-color:var(--line)}
.wf-out{border-top:1px dashed var(--line2);padding-top:10px;display:grid;gap:8px}
.wf-scenes{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}
.wf-scene{padding:10px;border-radius:11px;border:1px solid var(--line);background:var(--panel);display:grid;gap:6px;font-size:12px}
.wf-scene input,.wf-scene textarea{font-size:12px;padding:5px 7px;min-height:46px}
.wf-scene input{min-height:0}
.wf-thumbs{display:flex;flex-wrap:wrap;gap:8px}
.wf-thumb{position:relative;width:116px;border-radius:10px;border:1px solid var(--line);background:var(--viewer-bg);overflow:hidden}
.wf-thumb img,.wf-thumb video{width:100%;height:84px;object-fit:cover;display:block;cursor:pointer}
.wf-thumb .cap{padding:4px 6px;font-size:10.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;background:var(--panel)}
.wf-thumb .rm{position:absolute;top:4px;right:4px;width:20px;height:20px;border-radius:6px;border:0;background:rgba(0,0,0,.68);color:#fff;cursor:pointer;display:grid;place-items:center;font-size:12px}
.wf-thumb .rm:hover{background:#ef4444}
.wf-pause-banner{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:12px;background:var(--badge-warn-bg);border:1px solid var(--badge-warn-bd);color:var(--badge-warn-fg);font-size:13px;font-weight:550;margin-bottom:12px}
.wf-palette{margin-top:14px;padding:12px;border-radius:14px;border:1.5px dashed var(--line2);background:var(--card);display:grid;gap:8px}
.wf-final-video{width:100%;max-height:380px;border-radius:12px;background:#000;border:1px solid var(--line)}
.wf-logs{margin-top:12px;border:1px solid var(--line);border-radius:12px;padding:8px 12px;background:var(--surface)}
.wf-logs pre{margin:6px 0 0;max-height:160px;overflow:auto;font:11.5px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--muted);white-space:pre-wrap}
@media (max-width:1100px){.wf-layout{grid-template-columns:1fr;overflow:visible;height:auto}.wf-side,.wf-main{height:auto;overflow:visible}.wf-side-scroll,.wf-canvas{overflow:visible}}

/* ── desktop viewport shell layout (zoom-safe, no sticky fly-out) ── */
.layout{flex:1;min-height:0;width:100%;display:grid;grid-template-columns:clamp(350px,27vw,430px) minmax(0,1fr);gap:16px;padding:14px 18px;overflow:hidden}
.panel{height:100%;min-height:0;min-width:0;display:flex;flex-direction:column;
  background:var(--panel);border:1px solid var(--line);border-radius:18px;backdrop-filter:blur(14px);box-shadow:var(--shadow);overflow:hidden}
.panel-scroll{overflow-y:auto;overflow-x:hidden;padding:14px 14px 8px;flex:1;min-height:0}
.main{height:100%;min-height:0;min-width:0;overflow-y:auto;overflow-x:hidden;display:flex;flex-direction:column;gap:16px;padding-bottom:16px}

.seg{display:grid;grid-template-columns:1fr 1fr;gap:4px;padding:4px;border-radius:13px;background:var(--surface2);border:1px solid var(--line);margin-bottom:12px}
.seg button{display:flex;align-items:center;justify-content:center;gap:8px;height:36px;border:0;border-radius:10px;background:transparent;color:var(--muted);font-weight:650;cursor:pointer;transition:.18s}
.seg button.on{background:var(--grad);color:#fff;box-shadow:0 4px 14px rgba(99,102,241,.3)}
.seg button:not(.on):hover{color:var(--text);background:var(--card)}

.block{border:1px solid var(--line);background:var(--card);border-radius:var(--r);padding:12px;margin-bottom:12px;min-width:0}
.block>summary{list-style:none;cursor:pointer}
.block>summary::-webkit-details-marker{display:none}
.bh{display:flex;align-items:center;gap:8px;font-weight:650;font-size:13px;color:var(--text)}
.bh .ic{color:var(--a2)}
.bh .hint{margin-left:auto;font-weight:500;color:var(--dim);font-size:12px}
details.block[open]>summary{margin-bottom:10px}
details.block>summary .chev{margin-left:6px;transition:transform .2s;color:var(--dim)}
details.block[open]>summary .chev{transform:rotate(90deg)}

label.f{display:block;color:var(--muted);font-size:12px;margin:10px 0 5px;font-weight:500}
label.f:first-child{margin-top:0}
.row{display:flex;gap:8px;align-items:center;min-width:0}
.row.wrap{flex-wrap:wrap}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
input[type=text],input[type=number],input[type=password],input[type=search],select,textarea{
  width:100%;min-width:0;background:var(--input-bg);border:1px solid var(--line);border-radius:10px;padding:8px 10px;outline:none;transition:border-color .15s,box-shadow .15s}
input:focus,select:focus,textarea:focus{border-color:rgba(124,58,237,.7);box-shadow:0 0 0 3px rgba(124,58,237,.16)}
textarea{resize:vertical;min-height:64px;line-height:1.55}
textarea#prompt{min-height:140px}
.rw-badge{display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:550;color:var(--pchip-on-fg);background:var(--pchip-on-bg);border:1px solid var(--pchip-on-bd);margin-top:6px}
select{cursor:pointer}
select option{background:var(--option-bg);color:var(--text)}
.counter{font-size:11px;color:var(--dim);text-align:right;margin-top:3px}
.help{font-size:12px;color:var(--dim);margin-top:6px;word-break:break-word}

.chips{display:flex;flex-wrap:wrap;gap:6px}
.pchip{height:30px;padding:0 10px;border-radius:9px;border:1px solid var(--line);background:var(--surface);color:var(--muted);font-size:12px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:.15s;max-width:100%}
.pchip:hover{color:var(--text);border-color:var(--line2)}
.pchip.on{color:var(--pchip-on-fg);border-color:var(--pchip-on-bd);background:var(--pchip-on-bg);font-weight:600}
.ar{display:inline-block;border:1.5px solid currentColor;border-radius:2px;opacity:.8}

.slider{display:grid;grid-template-columns:1fr 64px;gap:10px;align-items:center}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:4px;border-radius:4px;background:var(--range-track);outline:none}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;border-radius:50%;background:#fff;border:3px solid var(--a1);cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,.25)}
input[type=range]::-moz-range-thumb{width:12px;height:12px;border-radius:50%;background:#fff;border:3px solid var(--a1);cursor:pointer}
.slider input[type=number]{text-align:center;padding:6px}

.switch{display:flex;align-items:center;gap:10px;cursor:pointer;font-size:13px;color:var(--text);user-select:none;margin:8px 0 2px}
.switch input{display:none}
.switch .tg{width:34px;height:20px;border-radius:20px;background:var(--tg-off);position:relative;transition:.2s;flex:none}
.switch .tg::after{content:"";position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:.2s}
.switch input:checked+.tg{background:var(--a1)}
.switch input:checked+.tg::after{left:17px}
.switch small{color:var(--dim);font-size:12px}

/* dropzones */
.drops{display:grid;grid-template-columns:1fr;gap:8px}
.drops.two{grid-template-columns:1fr 1fr}
.drop{position:relative;border:1.5px dashed var(--line2);border-radius:12px;min-height:112px;display:grid;place-items:center;text-align:center;cursor:pointer;
  background:var(--surface);transition:.15s;overflow:hidden;color:var(--muted);font-size:12px;padding:8px}
.drop:hover,.drop.over{border-color:var(--a1);background:rgba(124,58,237,.08);color:var(--text)}
.drop img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:var(--viewer-bg)}
.drop .tag{position:absolute;left:6px;bottom:6px;background:rgba(0,0,0,.7);color:#fff;font-size:11px;padding:2px 7px;border-radius:6px;z-index:2}
.drop .clear{position:absolute;right:6px;top:6px;z-index:2;width:26px;height:26px;border-radius:8px;border:0;background:rgba(0,0,0,.65);color:#fff;cursor:pointer;display:grid;place-items:center}
.drop .clear:hover{background:#ef4444}
.drop .ttl{position:absolute;left:8px;top:6px;z-index:2;font-size:11px;color:#fff;background:rgba(0,0,0,.55);padding:1px 7px;border-radius:6px}
.drop.set .empty{display:none}
.drop:not(.set) img,.drop:not(.set) .tag,.drop:not(.set) .clear{display:none}
.ref-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
.ref-card{position:relative;aspect-ratio:1/1;border-radius:11px;border:1px solid var(--line);background:var(--viewer-bg);overflow:hidden}
.ref-card img{width:100%;height:100%;object-fit:cover;display:block}
.ref-card .ref-idx{position:absolute;left:5px;top:5px;z-index:2;font-size:10px;font-weight:700;color:#fff;background:rgba(15,23,42,.72);padding:1px 6px;border-radius:5px}
.ref-card .tag{position:absolute;left:5px;bottom:5px;right:5px;z-index:2;background:rgba(0,0,0,.68);color:#fff;font-size:10px;padding:1px 5px;border-radius:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ref-card .clear{position:absolute;right:5px;top:5px;z-index:2;width:22px;height:22px;border-radius:7px;border:0;background:rgba(0,0,0,.68);color:#fff;cursor:pointer;display:grid;place-items:center}
.ref-card .clear:hover{background:#ef4444}
.ref-add{position:relative;aspect-ratio:1/1;border:1.5px dashed var(--line2);border-radius:11px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
  text-align:center;cursor:pointer;background:var(--surface);color:var(--muted);font-size:11.5px;padding:8px;transition:.15s}
.ref-add.wide{grid-column:1/-1;aspect-ratio:auto;min-height:108px}
.ref-add:hover,.ref-add.over{border-color:var(--a1);background:rgba(124,58,237,.08);color:var(--text)}
.ref-bar{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:6px;font-size:11.5px;color:var(--dim)}

.lora{display:grid;grid-template-columns:1fr auto;gap:6px;margin-bottom:8px;padding:10px;border-radius:12px;background:var(--surface);border:1px solid var(--line)}
.lora .full{grid-column:1/-1}
.mgroup{margin-top:8px}
.mgroup-lbl{font-size:11px;color:var(--dim);margin:0 0 4px}
.pchip .rm{margin-left:2px;opacity:.6;font-size:13px;line-height:1;padding:0 2px;border-radius:4px}
.pchip .rm:hover{opacity:1;background:rgba(244,63,94,.2);color:var(--bad)}
.subfold{margin-top:8px;border:1px solid var(--line);border-radius:10px;padding:8px 10px;background:var(--surface)}
.subfold summary{list-style:none;cursor:pointer;font-size:12px;color:var(--muted);display:flex;align-items:center;justify-content:space-between}
.subfold summary::-webkit-details-marker{display:none}
.eng-seg{display:grid;grid-template-columns:1fr 1fr;gap:4px;padding:3px;border-radius:10px;background:var(--surface2);border:1px solid var(--line);margin:8px 0 10px}
.eng-seg button{height:30px;border:0;border-radius:7px;background:transparent;color:var(--muted);font-size:12px;font-weight:600;cursor:pointer;transition:.15s}
.eng-seg button:hover{color:var(--text)}
.eng-seg button.on{background:var(--eng-on-bg);color:var(--eng-on-fg);box-shadow:inset 0 0 0 1px var(--eng-on-bd),0 1px 3px rgba(0,0,0,.08)}
.link-meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:4px;font-size:11px;color:var(--dim);min-height:16px;overflow-wrap:anywhere;word-break:break-word}
.link-meta.err{color:var(--bad)}
.fmt-pill{display:inline-flex;align-items:center;padding:1px 6px;border-radius:5px;font-size:10px;font-weight:600;background:var(--fmt-bg);color:var(--fmt-fg);border:1px solid var(--fmt-bd)}
.fmt-pill.nv{background:var(--fmt-nv-bg);color:var(--fmt-nv-fg);border-color:var(--fmt-nv-bd)}
.subfold[open] summary{margin-bottom:8px;color:var(--text)}
.gpu-list{display:grid;gap:6px;margin-top:6px}
.gpu-item{display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:8px 10px;border-radius:11px;border:1px solid var(--line);
  background:var(--input-bg);color:var(--text);cursor:pointer;transition:.15s;font:inherit}
.gpu-item:hover{border-color:var(--line2);background:var(--surface)}
.gpu-item.on{border-color:var(--pchip-on-bd);background:var(--pchip-on-bg);box-shadow:inset 0 0 0 1px rgba(124,58,237,.18)}
.gpu-item.dimmed{opacity:.52}
.gpu-item .g-radio{width:18px;height:18px;border-radius:6px;border:1.5px solid var(--line2);flex:none;display:grid;place-items:center;font-size:11px;font-weight:700;color:transparent;transition:.15s}
.gpu-item.on .g-radio{border-color:var(--a1);background:var(--a1);color:#fff}
.poll-bar{margin-top:10px;padding:9px 10px;border-radius:11px;border:1px solid var(--line);background:var(--surface);display:grid;gap:8px}
.poll-row{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--text)}
.poll-row input[type=number]{width:60px;text-align:center;padding:4px 6px;height:28px}
.poll-plan{font-size:11.5px;color:var(--dim);margin-left:auto;text-align:right}
.gpu-item .g-main{flex:1;min-width:0}
.gpu-item .g-top{display:flex;align-items:center;gap:6px;font-size:13px;font-weight:650}
.gpu-item .g-vram{font-size:11px;font-weight:500;color:var(--muted);padding:0 5px;border-radius:5px;background:var(--surface2)}
.gpu-item .g-sub{font-size:11.5px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px}
.gpu-badge{font-size:11px;padding:2px 7px;border-radius:99px;white-space:nowrap;flex:none;border:1px solid transparent;font-weight:500}
.gpu-badge.run{color:var(--badge-run-fg);background:var(--badge-run-bg);border-color:var(--badge-run-bd)}
.gpu-badge.ok{color:var(--badge-ok-fg);background:var(--badge-ok-bg);border-color:var(--badge-ok-bd)}
.gpu-badge.warn{color:var(--badge-warn-fg);background:var(--badge-warn-bg);border-color:var(--badge-warn-bd)}
.gpu-badge.bad{color:var(--badge-bad-fg);background:var(--badge-bad-bg);border-color:var(--badge-bad-bd)}
.gpu-badge.off{color:var(--dim);background:var(--surface);border-color:var(--line)}

.gobar{flex:none;padding:11px 14px;border-top:1px solid var(--line);background:var(--gobar-bg);display:flex;gap:8px;align-items:center}
.stepper{display:flex;align-items:center;border:1px solid var(--line);border-radius:11px;background:var(--surface);height:44px}
.stepper button{width:30px;height:100%;border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:16px}
.stepper button:hover{color:var(--text)}
.stepper span{min-width:26px;text-align:center;font-weight:700}
.go{flex:1;height:44px;font-size:14.5px;border-radius:12px}
.go .kbd{font-size:10.5px;opacity:.8;font-weight:500;border:1px solid rgba(255,255,255,.35);border-radius:5px;padding:0 5px;margin-left:4px}

/* ── stage ── */
.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;backdrop-filter:blur(14px);box-shadow:var(--shadow)}
.stage{overflow:hidden;flex:none}
.viewer{position:relative;height:clamp(320px,56vh,680px);display:grid;place-items:center;
  background:repeating-conic-gradient(var(--viewer-check) 0 25%,transparent 0 50%) 0 0/24px 24px,var(--viewer-bg);border-bottom:1px solid var(--line)}
.viewer img,.viewer video{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;display:block;cursor:zoom-in}
.viewer video{cursor:default}
.empty-stage{text-align:center;color:var(--muted);padding:30px}
.empty-stage .art{width:80px;height:80px;margin:0 auto 14px;border-radius:22px;background:var(--grad);color:#fff;display:grid;place-items:center;box-shadow:0 16px 40px rgba(99,102,241,.32)}
.empty-stage h3{margin:0 0 6px;color:var(--text);font-size:18px}
.vnav{position:absolute;top:50%;transform:translateY(-50%);width:40px;height:40px;border-radius:50%;border:1px solid var(--line2);background:rgba(15,23,42,.55);color:#fff;
  display:grid;place-items:center;cursor:pointer;opacity:0;transition:.15s}
.viewer:hover .vnav{opacity:1}
.vnav.l{left:14px}.vnav.r{right:14px}
.vexpand{position:absolute;right:14px;top:14px;opacity:0}
.viewer:hover .vexpand{opacity:1}

.progress{position:absolute;left:16px;right:16px;bottom:16px;padding:14px 16px;border-radius:16px;background:var(--progress-bg);backdrop-filter:blur(14px);
  border:1px solid var(--line2);box-shadow:var(--shadow)}
.progress .top{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.progress .stage-name{font-weight:650}
.progress .meta{color:var(--muted);font-size:12px}
.bar{height:6px;border-radius:6px;background:var(--range-track);overflow:hidden;position:relative}
.bar i{position:absolute;left:0;top:0;bottom:0;background:var(--grad);border-radius:6px;transition:width .4s}
.bar.indet i{width:35%!important;animation:indet 1.4s ease-in-out infinite}
@keyframes indet{0%{left:-35%}100%{left:100%}}
.steps-line{display:flex;gap:6px;margin-top:10px;font-size:11.5px;color:var(--dim);flex-wrap:wrap}
.steps-line span{display:inline-flex;align-items:center;gap:5px}
.steps-line span.done{color:var(--ok)}.steps-line span.cur{color:var(--a2);font-weight:650}

.toolbar{display:flex;align-items:center;gap:8px;padding:12px 16px;flex-wrap:wrap;border-bottom:1px solid var(--line)}
.toolbar .title{font-weight:700;font-size:15px}
.toolbar .sub{color:var(--dim);font-size:12px}
.toolbar .acts-row{display:flex;gap:6px;flex-wrap:wrap;margin-left:auto}
@media (max-width:1560px){.toolbar .lbl{display:none}.toolbar .acts-row .btn{width:34px;padding:0}}
.meta-area{padding:12px 16px 16px}
.prompt-view{position:relative;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:10px 40px 10px 12px;color:var(--prompt-text);font-size:13px;
  white-space:pre-wrap;word-break:break-word;max-height:120px;overflow:auto}
.prompt-view .copy{position:absolute;right:6px;top:6px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.tag{display:inline-flex;align-items:center;gap:5px;height:24px;padding:0 9px;border-radius:7px;background:var(--surface);border:1px solid var(--line);color:var(--muted);font-size:11.5px}
.tag b{color:var(--text);font-weight:600}
.star-on{color:#eab308!important}
.star-on svg{fill:#eab308}

/* queue */
.queue{padding:12px 16px;border-bottom:1px solid var(--line);background:rgba(124,58,237,.05)}
.qrow{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:10px;background:var(--surface);border:1px solid var(--line);margin-top:8px;font-size:12.5px}
.qrow .p{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted)}
.qrow .n{font-weight:700;color:var(--text);width:22px;text-align:center}

/* ── gallery ── */
.gallery{padding:14px 16px 16px}
.gallery-head{display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none}
.gallery-head h2{margin:0;font-size:16px}
.gallery-head .chev{color:var(--dim);transition:transform .2s;flex:none}
.gallery.open .gallery-head .chev{transform:rotate(90deg)}
.gallery-body{margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
.gbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.gbar h2{margin:0 8px 0 0;font-size:16px}
.gbar .search{position:relative;width:220px}
.gbar .search .ic{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--dim)}
.gbar .search input{padding-left:32px;height:32px}
.gstat{color:var(--dim);font-size:12px}
.selbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 10px;border-radius:12px;background:rgba(124,58,237,.1);border:1px solid rgba(124,58,237,.3);margin-bottom:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.tile{position:relative;aspect-ratio:3/4;border-radius:14px;overflow:hidden;background:var(--thumb-bg);border:1px solid var(--line);cursor:pointer;transition:transform .15s,border-color .15s,box-shadow .15s}
.tile:hover{transform:translateY(-2px);border-color:var(--line2);box-shadow:0 10px 26px rgba(15,23,42,.18)}
.tile.cur{border-color:var(--a1);box-shadow:0 0 0 2px rgba(124,58,237,.5)}
.tile.sel{border-color:var(--a2);box-shadow:0 0 0 2px rgba(6,182,212,.55)}
.tile img,.tile video{width:100%;height:100%;object-fit:cover;display:block;background:var(--thumb-bg)}
.tile .ov{position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,.72),transparent 45%);opacity:0;transition:.15s}
.tile:hover .ov{opacity:1}
.tile .id{position:absolute;left:7px;bottom:7px;font-size:11px;font-weight:700;color:#fff;background:rgba(0,0,0,.55);padding:1px 7px;border-radius:6px}
.tile .kind{position:absolute;left:7px;top:7px;font-size:10.5px;color:#fff;background:rgba(99,102,241,.85);padding:2px 7px;border-radius:6px;display:flex;gap:4px;align-items:center}
.tile .acts{position:absolute;right:6px;top:6px;display:flex;flex-direction:column;gap:5px;opacity:0;transition:.15s}
.tile:hover .acts{opacity:1}
.tile .acts button{width:28px;height:28px;border-radius:8px;border:0;background:rgba(0,0,0,.65);color:#fff;cursor:pointer;display:grid;place-items:center}
.tile .acts button:hover{background:rgba(139,92,246,.9)}
.tile .acts button.del:hover{background:#ef4444}
.tile .st{position:absolute;right:7px;bottom:7px;color:#facc15}
.tile .ck{position:absolute;left:7px;top:7px;width:22px;height:22px;border-radius:7px;border:2px solid #fff;background:rgba(0,0,0,.4);display:none;place-items:center;color:#fff}
.selecting .tile .ck{display:grid}
.selecting .tile .kind{display:none}
.tile.sel .ck{background:var(--a2);border-color:var(--a2);color:#fff}
.tile .when{position:absolute;right:7px;bottom:7px;font-size:10.5px;color:rgba(255,255,255,.88);opacity:0}
.tile:hover .when{opacity:1}
.tile:hover .st{opacity:0}
.gempty{padding:40px;text-align:center;color:var(--dim);border:1px dashed var(--line2);border-radius:14px}
.more{display:flex;justify-content:center;margin-top:14px}

/* ── overlays ── */
.scrim{position:fixed;inset:0;z-index:80;background:rgba(15,23,42,.5);backdrop-filter:blur(6px);display:grid;place-items:center;padding:20px;animation:fade .15s}
@keyframes fade{from{opacity:0}to{opacity:1}}
.modal{width:min(560px,96vw);max-height:90vh;overflow:auto;background:var(--modal-bg);border:1px solid var(--line2);border-radius:18px;box-shadow:var(--shadow);animation:pop .18s}
.modal.wide{width:min(980px,96vw)}
@keyframes pop{from{transform:translateY(8px) scale(.98);opacity:0}to{transform:none;opacity:1}}
.mh{display:flex;align-items:center;gap:10px;padding:16px 18px;border-bottom:1px solid var(--line)}
.mh h3{margin:0;font-size:16px}
.mb{padding:16px 18px}
.mf{display:flex;gap:8px;justify-content:flex-end;padding:14px 18px;border-top:1px solid var(--line)}
.opt{display:flex;gap:10px;align-items:flex-start;padding:12px;border-radius:12px;border:1px solid var(--line);background:var(--card);margin-bottom:8px}
.opt input[type=checkbox]{margin-top:3px;accent-color:var(--a1);width:16px;height:16px}
.opt .inl{display:inline-block;width:80px;margin:0 6px;padding:4px 8px}
.preview-box{margin-top:12px;padding:12px;border-radius:12px;background:var(--surface);border:1px solid var(--line)}
.mini{display:flex;gap:6px;overflow-x:auto;margin-top:10px}
.mini img,.mini .mv{width:52px;height:66px;border-radius:8px;object-fit:cover;flex:none;background:var(--thumb-bg);border:1px solid var(--line)}
.mini .mv{display:grid;place-items:center;color:var(--muted)}
.warnbox{display:flex;gap:10px;padding:10px 12px;border-radius:12px;background:var(--danger-bg);border:1px solid var(--danger-bd);color:var(--danger-fg);font-size:12.5px;margin-top:10px}

.drawer{position:fixed;top:0;right:0;bottom:0;z-index:85;width:min(440px,100vw);background:var(--drawer-bg);border-left:1px solid var(--line2);box-shadow:var(--shadow);
  display:flex;flex-direction:column;animation:slide .2s}
@keyframes slide{from{transform:translateX(30px);opacity:0}to{transform:none;opacity:1}}
.drawer .mb{overflow:auto;flex:1}
.sect{border:1px solid var(--line);border-radius:14px;padding:14px;margin-bottom:12px;background:var(--card)}
.sect h4{margin:0 0 10px;font-size:13.5px;display:flex;align-items:center;gap:8px}
.kv{display:grid;grid-template-columns:90px 1fr;gap:6px 10px;font-size:12.5px}
.kv span:nth-child(odd){color:var(--dim)}
.sess{font-size:12px;color:var(--muted);background:var(--surface);border-radius:10px;padding:8px 10px;margin-top:8px;word-break:break-all}

.lb{position:fixed;inset:0;z-index:90;background:rgba(2,3,6,.95);display:flex;flex-direction:column;animation:fade .15s}
.lb-top{display:flex;align-items:center;gap:8px;padding:12px 16px;color:#fff}
.lb-body{flex:1;position:relative;display:grid;place-items:center;min-height:0;padding:0 70px}
.lb-body img,.lb-body video{position:absolute;top:0;bottom:0;left:70px;width:calc(100% - 140px);height:100%;object-fit:contain}
.lb-bottom{padding:12px 20px 18px;color:#cfd3e2;font-size:13px;max-height:22vh;overflow:auto;text-align:center}
.lb .vnav{opacity:.85}

/* logdock participates in desktop flex shell so it NEVER covers the left panel or generate button */
.logdock{flex:none;z-index:50;height:min(34vh,300px);background:var(--log-bg);color:var(--log-text);border-top:1px solid var(--line2);display:flex;flex-direction:column;animation:up .16s}
@keyframes up{from{opacity:.6}to{opacity:1}}
.logdock .lh{display:flex;align-items:center;gap:8px;padding:8px 14px;border-bottom:1px solid rgba(255,255,255,.1);color:#e2e8f0}
.logdock .lh .btn,.logdock .lh .iconbtn{color:#cbd5e1;border-color:rgba(255,255,255,.15);background:rgba(255,255,255,.06)}
.logdock .lh .dim,.logdock .lh small{color:#94a3b8}
.logdock pre{flex:1;min-height:0;margin:0;overflow:auto;padding:10px 14px;font:12px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--log-text);white-space:pre-wrap;word-break:break-word}
.logdock pre .e{color:var(--log-err)}.logdock pre .s{color:var(--log-ok)}

.toasts{position:fixed;top:66px;right:18px;z-index:100;display:flex;flex-direction:column;gap:8px;pointer-events:none}
.toast{pointer-events:auto;min-width:220px;max-width:380px;padding:10px 14px;border-radius:12px;background:var(--toast-bg);border:1px solid var(--line2);box-shadow:var(--shadow);font-size:13px;
  display:flex;gap:9px;align-items:flex-start;animation:pop .18s}
.toast.ok{border-color:rgba(16,185,129,.45)}.toast.ok .ic{color:var(--ok)}
.toast.err{border-color:rgba(239,68,68,.5)}.toast.err .ic{color:var(--bad)}
.toast .act{margin-left:auto;color:var(--a2);cursor:pointer;font-weight:650;white-space:nowrap}

.hide{display:none!important}
.muted{color:var(--muted)}.dim{color:var(--dim)}
.sp{display:inline-block;width:14px;height:14px;border-radius:50%;border:2px solid var(--line2);border-top-color:var(--a1);animation:spin .8s linear infinite;vertical-align:middle}
.btn.primary .sp{border-color:rgba(255,255,255,.35);border-top-color:#fff}
@keyframes spin{to{transform:rotate(360deg)}}

@media (max-width:1100px){
  html,body{height:auto;overflow:auto}
  body{display:block;min-height:100vh}
  .topbar{position:sticky;top:0}
  .layout{grid-template-columns:1fr;overflow:visible;height:auto}
  .panel{height:auto;overflow:visible}
  .panel-scroll{overflow:visible}
  .main{height:auto;overflow:visible}
  .gobar{position:sticky;bottom:0}
  .viewer{height:56vh;min-height:300px}
  .logdock{position:fixed;left:0;right:0;bottom:0;height:min(42vh,340px)}
}
@media (max-width:640px){
  .topbar{padding:8px 12px;gap:6px}
  .brand small,.hide-sm{display:none!important}
  .brand{font-size:0;gap:0}
  #phaseText{max-width:110px;overflow:hidden;text-overflow:ellipsis}
  .chip{padding:0 9px}
  .layout{padding:12px 10px 30px;gap:12px}
  .grid{grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px}
  .gbar .search{width:100%}
  .lb-body{padding:0 8px}
  .lb-body img,.lb-body video{left:8px;width:calc(100% - 16px)}
  .lb .vnav{display:none}
}
"""

_BODY = r"""
<header class="topbar">
  <div class="brand"><div class="logo"><i data-i="sparkles"></i></div>Colab Studio<small id="ver"></small></div>
  <nav class="ws-nav" aria-label="工作台切换">
    <button type="button" id="wsImage" class="on"><i data-i="image"></i><span class="hide-sm">生图 / 改图</span></button>
    <button type="button" id="wsVideo"><i data-i="video"></i><span class="hide-sm">生视频</span></button>
    <button type="button" id="wsWorkflow"><i data-i="workflow"></i><span>长视频工作流</span><span class="badge hide" id="wfRunBadge" style="position:static;margin-left:2px"></span></button>
  </nav>
  <span class="chip" id="phaseChip"><span class="dot" id="phaseDot"></span><span class="sv-pill cold" id="svBadge">COLD</span><span id="phaseText">连接中…</span></span>
  <span class="chip hide hide-sm" id="idleChip" title="空闲到期自动释放 Colab 运行时"><i data-i="clock"></i><span id="idleText"></span></span>
  <div class="grow"></div>
  <button class="chip" id="colabChip" title="Google Colab 账号与算力"><span class="dot" id="colabDot"></span><span id="colabText" class="hide-sm">Colab</span></button>
  <button class="btn sm danger hide" id="releaseBtn" title="立即释放所有 Colab 运行时，停止消耗 Compute Units"><i data-i="power"></i><span class="hide-sm">释放算力</span></button>
  <button class="iconbtn" id="themeBtn" title="切换亮色 / 暗色模式"><i data-i="moon"></i></button>
  <button class="iconbtn" id="logBtn" title="实时日志 (L)"><i data-i="terminal"></i><span class="badge hide" id="logBadge"></span></button>
  <button class="iconbtn" id="settingsBtn" title="设置" disabled><i data-i="settings"></i></button>
  <a class="iconbtn" href="logout" title="退出登录"><i data-i="logout"></i></a>
</header>

<div class="layout" id="studioLayout">
  <aside class="panel">
    <div class="panel-scroll">
      <div class="seg">
        <button id="mImage" class="on"><i data-i="image"></i>生图 / 改图</button>
        <button id="mVideo"><i data-i="video"></i>生视频 + 音频</button>
      </div>

      <div class="preset-bar" title="一键保存或应用参数组合">
        <select id="studioPresetSel" aria-label="参数预设"><option value="">参数预设</option></select>
        <button type="button" class="btn sm" id="saveStudioPresetBtn" title="保存当前参数为预设">存预设</button>
        <button type="button" class="iconbtn hide" id="delStudioPresetBtn" title="删除自定义预设" style="width:30px;height:30px"><i data-i="trash"></i></button>
      </div>

      <section class="block" id="modeBlock">
        <div class="bh"><i data-i="layers"></i><span id="modeBlockTitle">引擎与模型</span></div>
        <div id="imageModelWrap">
          <div class="eng-seg" role="tablist" aria-label="生图引擎">
            <button type="button" id="engDiffusers" class="on">Diffusers</button>
            <button type="button" id="engComfy">ComfyUI</button>
          </div>
          <div id="diffusersBox">
            <label class="f">生图模型</label>
            <div class="row">
              <input type="text" id="imageModel" data-p list="modelSuggest" placeholder="填内置名或 owner/repo，如 black-forest-labs/FLUX.1-dev">
              <button class="btn sm" id="saveModelBtn" title="保存到最近使用">保存</button>
            </div>
            <datalist id="modelSuggest"></datalist>
            <div class="help" id="modelHint"></div>
            <div id="recentModelsWrap" class="mgroup hide">
              <div class="mgroup-lbl">最近使用</div>
              <div class="chips" id="recentModelChips"></div>
            </div>
            <details class="subfold">
              <summary><span>内置预设</span><i data-i="right" class="chev"></i></summary>
              <div class="chips" id="presetModelChips"></div>
            </details>
            <details id="ggufWrap" class="subfold hide">
              <summary><span>自定义 GGUF 权重（选填，留空默认 Q5_K_M）</span><i data-i="right" class="chev"></i></summary>
              <div class="g2">
                <input type="text" id="ggufRepo" data-p placeholder="仓库（默认 unsloth/Qwen-Image-2.1-GGUF）">
                <input type="text" id="ggufFile" data-p placeholder="文件名（默认 qwen-image-2.1-Q5_K_M.gguf）">
              </div>
            </details>
          </div>

          <div id="comfyBox" class="hide">
            <div class="row" style="justify-content:space-between;margin-bottom:6px">
              <span class="mgroup-lbl" style="margin:0">常用组合方案</span>
              <button type="button" class="btn sm" id="saveComfyPresetBtn">保存当前组合</button>
            </div>
            <div id="savedComfyWrap" class="mgroup hide" style="margin-top:0">
              <div class="chips" id="savedComfyChips"></div>
            </div>
            <details class="subfold" open>
              <summary><span>内置推荐组合（一键填充）</span><i data-i="right" class="chev"></i></summary>
              <div class="chips" id="builtinComfyChips" style="margin-top:8px"></div>
            </details>

            <label class="f">ComfyUI 架构模板</label>
            <select id="comfyTemplate" data-p></select>

            <label class="f">1. 扩散模型链接（Diffusion / UNET）</label>
            <div class="row">
              <input type="text" id="comfyDiff" data-p placeholder="粘贴 HF 文件链接，如 .../diffusion_pytorch_model.safetensors 或 NVFP4 / GGUF">
              <button type="button" class="iconbtn" data-clr="comfyDiff" title="清空"><i data-i="x"></i></button>
            </div>
            <div class="link-meta" id="comfyDiffMeta"></div>

            <label class="f">2. 文本编码器链接（Text Encoder / CLIP）</label>
            <div class="row">
              <input type="text" id="comfyTe" data-p placeholder="粘贴 HF 文件链接，如 Comfy-Org/.../qwen3vl_8b_bf16.safetensors">
              <button type="button" class="iconbtn" data-clr="comfyTe" title="清空"><i data-i="x"></i></button>
            </div>
            <div class="link-meta" id="comfyTeMeta"></div>

            <label class="f">3. VAE 链接</label>
            <div class="row">
              <input type="text" id="comfyVae" data-p placeholder="粘贴 HF 文件链接，如 Comfy-Org/.../qwen_image_2.1_vae_bf16.safetensors">
              <button type="button" class="iconbtn" data-clr="comfyVae" title="清空"><i data-i="x"></i></button>
            </div>
            <div class="link-meta" id="comfyVaeMeta"></div>

            <div class="g2" style="margin-top:8px">
              <div><label class="f" style="margin-top:0">采样器</label><select id="comfySampler" data-p></select></div>
              <div><label class="f" style="margin-top:0">调度器</label><select id="comfyScheduler" data-p></select></div>
            </div>
            <div class="chips" id="comfyQuickChips" style="margin-top:8px">
              <button type="button" class="pchip" data-qcfg="35,5,euler,simple">35步精细 · CFG 5</button>
              <button type="button" class="pchip" data-qcfg="8,1,euler,simple">8步 Turbo · CFG 1</button>
            </div>
          </div>
        </div>

        <div id="workflowWrap" class="hide">
          <label class="f">视频工作流</label>
          <div class="chips" id="workflowChips"></div>
          <div id="videoTaskWrap" class="hide">
            <label class="f" for="videoTask">参考用途</label>
            <select id="videoTask" data-p><option value="">参考图</option><option value="edit">翻修原片</option><option value="continue">续拍下一段</option><option value="motion">白模 + 人设</option></select>
          </div>
        </div>
        <div id="framesWrap" class="hide">
          <label class="f">时长</label>
          <div class="chips" id="frameChips"></div>
        </div>
      </section>

      <section class="block" id="refBlock">
        <div class="bh"><i data-i="image"></i><span id="refTitle">参考图</span><span class="hint" id="refHint">点击 / 拖入 / 粘贴</span></div>
        <div id="videoRefWrap" class="hide">
          <label class="f" for="videoRefInput">参考视频（MP4，2–15 秒，最大 64 MB）</label>
          <video id="videoRefPreview" class="hide" style="width:100%;max-height:180px" controls playsinline preload="metadata"></video>
          <div class="row"><input type="file" id="videoRefInput" accept="video/mp4,.mp4"><button id="videoRefClear" class="btn sm ghost hide">移除视频</button></div>
          <label class="switch hide" id="videoImagesToggle"><input type="checkbox" id="videoUseImages" data-p><span class="tg"></span>附加参考图</label>
        </div>
        <div id="multiRefWrap">
          <div class="ref-grid" id="refGrid"></div>
          <div class="ref-bar hide" id="refBar">
            <span id="refCountText"></span>
            <button type="button" class="btn sm ghost" id="refClearAll" style="height:24px;padding:0 8px;font-size:11px">清空全部</button>
          </div>
        </div>
        <div class="drops hide" id="drops" style="margin-top:10px">
          <div class="drop" id="dropFirst" data-slot="first">
            <span class="ttl" id="firstTtl">首帧</span>
            <div class="empty"><i data-i="upload" class="lg"></i><div style="margin-top:6px">上传首帧图</div><div class="dim">PNG / JPEG / WebP ≤ 12MB</div></div>
            <img alt=""><span class="tag"></span><button class="clear" title="移除"><i data-i="x"></i></button>
          </div>
          <div class="drop hide" id="dropLast" data-slot="last">
            <span class="ttl">尾帧</span>
            <div class="empty"><i data-i="upload" class="lg"></i><div style="margin-top:6px">尾帧（可选）</div></div>
            <img alt=""><span class="tag"></span><button class="clear" title="移除"><i data-i="x"></i></button>
          </div>
        </div>
        <input type="file" id="fileInput" accept="image/png,image/jpeg,image/webp" multiple hidden>
        <div id="imgRefOpts">
          <label class="switch"><input type="checkbox" id="useRef" data-p><span class="tg"></span>用参考图改图</label>
          <label class="switch" title="自动以最新作品为参考图"><input type="checkbox" id="chain" data-p><span class="tg"></span>接着改</label>
        </div>
        <div class="help" id="refHelp"></div>
      </section>

      <section class="block" id="promptBlock">
        <div class="bh"><i data-i="sparkles"></i>创意与提示词<span class="hint" id="shortcutHint">Ctrl + Enter 生成</span></div>
        <div class="rw-badge" id="rewriteModeBadge">自动适配当前模式</div>
        <label class="f">一句话想法</label>
        <div class="row" style="align-items:stretch">
          <textarea id="idea" data-p rows="2" placeholder="例如：雨夜霓虹街头，撑透明雨伞的人回头微笑，电影感"></textarea>
        </div>
        <div class="row" style="margin-top:8px">
          <button class="btn sm" id="rewriteBtn"><i data-i="sparkles"></i>AI 改写为提示词</button>
          <span class="dim" style="font-size:12px" id="rewriteHint"></span>
        </div>
        <div class="row" style="justify-content:space-between;margin-top:10px;margin-bottom:5px">
          <label class="f" style="margin:0">提示词 Prompt <span class="tip-q" title="支持 {A|B|C} 抽签语法，多张生成时按种子自动抽取不同变体">?</span></label>
          <div class="row" style="gap:5px">
            <button type="button" class="wc-pill" id="insertWildcardBtn" title="插入变体抽签语法">{a|b|c}</button>
            <button type="button" class="wc-pill" id="promptHistBtn" title="最近 15 条提示词">历史</button>
          </div>
        </div>
        <div class="hist-pop hide" id="promptHistPop"></div>
        <textarea id="prompt" data-p placeholder="写英文或中文提示词，支持 {日落|雨夜|清晨} 抽签变体"></textarea>
        <div class="counter"><span id="promptCount">0</span> / <span id="promptMax">12000</span></div>
        <details id="negWrap">
          <summary class="dim" style="cursor:pointer;font-size:12px;margin-top:4px">负面提示词</summary>
          <textarea id="negative" data-p rows="2" style="margin-top:6px">blurry, lowres, jpeg artifacts, deformed, bad anatomy, watermark, text, logo, signature</textarea>
        </details>
      </section>

      <section class="block">
        <div class="bh">
          <i data-i="settings"></i>画幅与采样参数
          <span class="mp-badge" id="mpBadge" style="margin-left:auto">0.88 MP</span>
        </div>
        <div class="row" style="justify-content:space-between;margin:10px 0 5px">
          <label class="f" style="margin:0">画幅比例</label>
          <div class="row" style="gap:4px">
            <button type="button" class="btn sm ghost" id="swapWH" style="height:24px;padding:0 7px;font-size:11px" title="交换宽和高">W ↔ H</button>
            <button type="button" class="btn sm ghost" id="optWH" style="height:24px;padding:0 7px;font-size:11px" title="按当前比例对齐推荐像素数">最佳像素</button>
          </div>
        </div>
        <div class="chips" id="sizeChips"></div>
        <div style="margin-top:8px;display:grid;gap:6px">
          <div class="row"><span class="dim" style="font-size:11.5px;width:18px">W</span><input type="range" id="widthR" min="512" max="1536" step="64" style="flex:1"><input type="number" id="width" step="64" min="512" max="1536" style="width:74px;text-align:center;padding:5px"></div>
          <div class="row"><span class="dim" style="font-size:11.5px;width:18px">H</span><input type="range" id="heightR" min="512" max="1536" step="64" style="flex:1"><input type="number" id="height" step="64" min="512" max="1536" style="width:74px;text-align:center;padding:5px"></div>
        </div>

        <label class="f">采样步数 <span class="tip-q" title="常规 28–40 步；Turbo LoRA 可设 4–8 步">?</span> <span class="dim" id="stepsHint"></span></label>
        <div class="slider"><input type="range" id="stepsR" min="2" max="60"><input type="number" id="steps" min="2" max="60"></div>
        <label class="f">CFG <span class="tip-q" title="提示词遵循强度；Turbo 通常 1.0，常规推荐 4.5–5.5">?</span></label>
        <div class="slider"><input type="range" id="cfgR" min="1" max="12" step="0.5"><input type="number" id="cfg" min="1" max="12" step="0.5"></div>
        <label class="f">种子</label>
        <div class="row">
          <input type="number" id="seed" value="-1" placeholder="-1 随机">
          <button class="iconbtn" id="seedLast" title="复用上次种子"><i data-i="lock"></i></button>
          <button class="iconbtn" id="seedRand" title="随机固定种子"><i data-i="dice"></i></button>
          <button class="iconbtn" id="seedAuto" title="重置为 -1 随机"><i data-i="reuse"></i></button>
        </div>
        <div id="offloadWrap" class="hide" style="margin-top:8px">
          <label class="f" style="margin-top:0">显存卸载 <span class="tip-q" title="自动：80G/96G 走组件级，40G/24G 自动切逐层 Group Offload">?</span></label>
          <select id="offloadMode" data-p>
            <option value="auto">自动</option>
            <option value="component">组件级 · H100 / G4</option>
            <option value="group">逐层 · A100 / L4 无损 BF16</option>
            <option value="none">关闭</option>
          </select>
        </div>
      </section>

      <details class="block" id="loraBlock">
        <summary class="bh"><i data-i="link"></i>LoRA 挂载<span class="hint" id="loraHint">未启用</span><i data-i="right" class="chev"></i></summary>
        <div id="loraRows"></div>
        <div class="help">填 Hugging Face 仓库 ID（owner/repo）或直接粘贴 .safetensors 文件链接；MiniMax-H3 支持自动无损转换 ComfyUI 格式 LoRA。</div>
      </details>

      <section class="block" id="gpuBlock">
        <div class="bh">
          <i data-i="cpu"></i>Colab 算力列表
          <span class="hint" id="gpuHint"></span>
          <button type="button" class="iconbtn" id="refreshGpuBtn" title="刷新 Colab 算力状态" style="width:26px;height:26px;margin-left:4px"><i data-i="reuse"></i></button>
        </div>
        <div class="gpu-list" id="gpuChips"></div>
        <div class="help" id="gpuHelp"></div>
      </section>
    </div>

    <div class="gobar">
      <div class="stepper" title="一次生成几张（种子依次 +1）">
        <button id="cntMinus">−</button><span id="count">1</span><button id="cntPlus">+</button>
      </div>
      <button class="btn primary go" id="goBtn"><i data-i="sparkles"></i><span id="goText">开始生成</span><span class="kbd hide-sm">⌘↵</span></button>
      <button class="btn danger hide" id="stopBtn" title="取消当前任务" style="height:44px;width:44px;padding:0"><i data-i="stop"></i></button>
    </div>
  </aside>

  <main class="main">
    <section class="card stage">
      <div class="viewer" id="viewer">
        <div class="empty-stage hide" id="emptyStage">
          <div class="art"><i data-i="sparkles" class="xl"></i></div>
          <h3 id="emptyTitle">开始你的第一张作品</h3>
          <div id="emptyDesc">在左侧写下想法，选好模型，点「开始生成」。<br>作品会保存在下方作品库，可以随时收藏、复用参数或删除。</div>
          <button type="button" class="btn sm hide" id="emptyOpenGallery" style="margin-top:14px"><i data-i="layers"></i>展开作品库查看历史</button>
        </div>
        <img id="vImg" class="hide" alt="">
        <video id="vVid" class="hide" controls playsinline loop></video>
        <button class="vnav l hide" id="vPrev" title="上一个 (←)"><i data-i="left" class="lg"></i></button>
        <button class="vnav r hide" id="vNext" title="下一个 (→)"><i data-i="right" class="lg"></i></button>
        <button class="iconbtn vexpand hide" id="vExpand" title="全屏查看"><i data-i="expand"></i></button>
        <div class="progress hide" id="progress">
          <div class="top">
            <span class="sp"></span>
            <span class="stage-name" id="pStage">准备中</span>
            <span class="meta" id="pMeta"></span>
            <div class="grow"></div>
            <span class="meta" id="pTime"></span>
            <button class="btn sm danger" id="pCancel"><i data-i="stop"></i>取消</button>
          </div>
          <div class="bar" id="pBar"><i style="width:0"></i></div>
          <div class="steps-line" id="pSteps"></div>
        </div>
      </div>
      <div class="queue hide" id="queueBox">
        <div class="row"><b>任务队列</b><span class="dim" id="queueCount"></span><div class="grow"></div><button class="btn sm ghost" id="queueClear">清空队列</button></div>
        <div id="queueList"></div>
      </div>
      <div id="viewInfo" class="hide">
        <div class="toolbar">
          <span class="title" id="vTitle"></span><span class="sub" id="vSub"></span>
          <div class="acts-row">
          <button class="btn sm" id="aStar" title="收藏 (S)"><i data-i="star"></i><span class="lbl">收藏</span></button>
          <button class="btn sm" id="aRef" title="设为参考图 / 首帧"><i data-i="image"></i><span class="lbl">设为参考</span></button>
          <button class="btn sm hide" id="aLast" title="设为尾帧"><i data-i="film"></i><span class="lbl">设为尾帧</span></button>
          <button class="btn sm" id="aToVideo" title="以此图为首帧生成视频"><i data-i="video"></i><span class="lbl">做成视频</span></button>
          <button class="btn sm hide" id="aEditVideo" title="以这段视频为参考继续创作"><i data-i="film"></i><span class="lbl">翻修视频</span></button>
          <button class="btn sm hide" id="aContinueVideo" title="从这段视频的结尾续拍"><i data-i="video"></i><span class="lbl">续拍下一段</span></button>
          <a class="btn sm" id="aMediaTool" title="在新版工作台打开素材编辑器"></a>
          <a class="btn sm hide" id="aCrop">裁图</a>
          <button class="btn sm" id="aCompare" title="与其他图片左右滑块对比"><i data-i="compare"></i><span class="lbl">A/B对比</span></button>
          <button class="btn sm" id="aReuse" title="把这次的参数填回左侧"><i data-i="reuse"></i><span class="lbl">复用参数</span></button>
          <a class="btn sm" id="aDown" title="下载 (D)"><i data-i="download"></i><span class="lbl">下载</span></a>
          <button class="btn sm danger" id="aDel" title="删除 (Delete)"><i data-i="trash"></i><span class="lbl">删除</span></button>
          <button class="btn sm ghost" id="aHide" title="收起当前预览"><i data-i="x"></i><span class="lbl">收起</span></button>
          </div>
        </div>
        <div class="meta-area">
          <div class="prompt-view" id="vPrompt"><button class="iconbtn copy" id="aCopy" title="复制提示词"><i data-i="copy"></i></button><span></span></div>
          <div class="tags" id="vTags"></div>
        </div>
      </div>
    </section>

    <section class="card gallery" id="galleryCard">
      <div class="gallery-head" id="galleryHead">
        <i data-i="right" class="chev"></i>
        <h2>作品库</h2>
        <span class="gstat" id="gCollapsedStat"></span>
        <div class="grow"></div>
        <button type="button" class="btn sm ghost" id="galleryToggleBtn">展开</button>
      </div>
      <div class="gallery-body hide" id="galleryBody">
        <div class="gbar">
          <div class="chips" id="filterChips"></div>
          <div class="grow"></div>
          <div class="search"><i data-i="search"></i><input type="search" id="gSearch" placeholder="搜索提示词 / 编号"></div>
          <button class="btn sm" id="importMediaBtn">导入素材</button>
          <input hidden type="file" id="importMedia" accept="image/png,image/jpeg,image/webp,video/mp4,.mp4">
          <button class="btn sm" id="selBtn"><i data-i="select"></i>多选</button>
          <button class="btn sm" id="cleanBtn"><i data-i="broom"></i>清理旧作品</button>
          <button class="btn sm" id="trashBtn" style="position:relative"><i data-i="trash"></i>回收站<span class="badge hide" id="trashBadge"></span></button>
        </div>
        <div class="selbar hide" id="selBar">
          <b id="selCount">已选 0</b>
          <button class="btn sm ghost" id="selAll">全选当前</button>
          <button class="btn sm ghost" id="selNone">清除选择</button>
          <div class="grow"></div>
          <button class="btn sm" id="selCompare"><i data-i="compare"></i>对比两图</button>
          <button class="btn sm" id="selStar"><i data-i="star"></i>收藏</button>
          <button class="btn sm" id="selUnstar">取消收藏</button>
          <button class="btn sm danger" id="selDel"><i data-i="trash"></i>删除所选</button>
          <button class="btn sm" id="selDone"><i data-i="check"></i>完成</button>
        </div>
        <div class="gstat" id="gStat" style="margin:-4px 0 10px"></div>
        <div class="grid" id="grid"></div>
        <div class="more hide" id="moreWrap"><button class="btn sm" id="moreBtn">加载更多</button></div>
      </div>
    </section>
  </main>
</div>

<div class="wf-layout hide" id="workflowWorkspace">
  <aside class="wf-side">
    <div class="wf-side-scroll">
      <div class="row" style="justify-content:space-between;margin-bottom:8px">
        <b style="font-size:14px">工作流模板</b>
        <button type="button" class="btn sm" id="wfNewBlankBtn">+ 空白流程</button>
      </div>
      <div id="wfTemplateList"></div>
      <div class="row" style="justify-content:space-between;margin:14px 0 8px">
        <b style="font-size:14px">运行实例</b>
        <button type="button" class="iconbtn" id="wfRefreshBtn" style="width:26px;height:26px" title="刷新列表"><i data-i="reuse"></i></button>
      </div>
      <div id="wfRunList"></div>
    </div>
  </aside>

  <section class="wf-main">
    <div class="wf-head">
      <div class="row wrap" style="gap:8px">
        <input type="text" id="wfName" placeholder="工作流名称" style="flex:1;min-width:200px;font-weight:650">
        <span class="wf-st pending" id="wfStatusPill">草稿</span>
        <span class="tag" id="wfFfmpegTag" title="用于将多段视频合成为成品长视频">FFmpeg</span>
        <button type="button" class="btn sm" id="wfSaveTplBtn">存为模板</button>
        <button type="button" class="btn sm primary" id="wfStartBtn"><i data-i="play"></i>开始运行</button>
        <button type="button" class="btn sm primary hide" id="wfResumeBtn"><i data-i="play"></i>继续下一步</button>
        <button type="button" class="btn sm danger hide" id="wfCancelBtn"><i data-i="stop"></i>终止</button>
      </div>
      <div class="row" style="align-items:stretch">
        <textarea id="wfTopic" rows="2" placeholder="输入长视频主题或创意需求" style="min-height:46px"></textarea>
      </div>
    </div>
    <div class="wf-canvas" id="wfCanvas">
      <div class="wf-pause-banner hide" id="wfPauseBanner">
        <i data-i="info"></i>
        <span id="wfPauseText" style="flex:1"></span>
        <button type="button" class="btn sm primary" id="wfPauseResumeBtn"><i data-i="play"></i>继续下一步</button>
      </div>
      <div id="wfNodes"></div>
      <div class="wf-palette" id="wfPalette">
        <div class="row" style="justify-content:space-between">
          <b style="font-size:12.5px">添加流水线步骤</b>
          <span class="dim" style="font-size:11.5px">可自由编排每一步让 AI / Agent / 生图 / 视频 / 剪辑做什么</span>
        </div>
        <div class="chips" id="wfAddChips"></div>
      </div>
      <details class="wf-logs" id="wfLogsBox">
        <summary style="cursor:pointer;font-size:12px;font-weight:600;color:var(--muted)">工作流执行日志</summary>
        <pre id="wfLogsPre"></pre>
      </details>
    </div>
    <input type="file" id="wfAssetInput" accept="image/png,image/jpeg,image/webp" multiple hidden>
  </section>
</div>

<div class="logdock hide" id="logDock">
  <div class="lh"><i data-i="terminal"></i><b>实时日志</b><span class="dim" id="logLines"></span><div class="grow"></div>
    <label class="switch" style="margin:0"><input type="checkbox" id="logFollow" checked><span class="tg"></span><small>自动滚动</small></label>
    <button class="btn sm ghost" id="logCopy"><i data-i="copy"></i>复制</button>
    <button class="btn sm ghost" id="logClear">清屏</button>
    <button class="iconbtn" id="logClose"><i data-i="x"></i></button></div>
  <pre id="logPre"></pre>
</div>

<div class="toasts" id="toasts"></div>
<div id="overlay"></div>
"""

_JS = r"""
const $ = (s, el=document) => el.querySelector(s);
const $$ = (s, el=document) => [...el.querySelectorAll(s)];
const P = {
  sparkles:'<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 3v4M17 5h4M5 17v4M3 19h4"/>',
  image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
  video:'<path d="m22 8-6 4 6 4V8z"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
  upload:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>',
  x:'<path d="M18 6 6 18M6 6l12 12"/>',
  star:'<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>',
  trash:'<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6M14 11v6"/>',
  download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  reuse:'<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  film:'<rect x="2" y="2" width="20" height="20" rx="2.5"/><path d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5"/>',
  play:'<path d="m6 3 14 9-14 9V3z"/>',
  stop:'<rect x="5" y="5" width="14" height="14" rx="2"/>',
  power:'<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/>',
  settings:'<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  terminal:'<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
  logout:'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
  search:'<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  check:'<path d="M20 6 9 17l-5-5"/>',
  left:'<path d="m15 18-6-6 6-6"/>', right:'<path d="m9 18 6-6-6-6"/>',
  expand:'<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
  copy:'<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  cpu:'<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
  clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  broom:'<path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/><path d="M22 21H7"/><path d="m5 11 9 9"/>',
  undo:'<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  dice:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.2" fill="currentColor"/><circle cx="15.5" cy="15.5" r="1.2" fill="currentColor"/><circle cx="15.5" cy="8.5" r="1.2" fill="currentColor"/><circle cx="8.5" cy="15.5" r="1.2" fill="currentColor"/>',
  layers:'<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
  select:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m9 12 2 2 4-4"/>',
  key:'<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
  link:'<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  info:'<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  alert:'<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
  moon:'<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>',
  workflow:'<rect x="3" y="3" width="6" height="6" rx="1.5"/><rect x="15" y="3" width="6" height="6" rx="1.5"/><rect x="9" y="15" width="6" height="6" rx="1.5"/><path d="M6 9v2a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V9M12 13v2"/>',
  compare:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 2v20M8 10l-2 2 2 2M16 10l2 2-2 2"/>',
  lock:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  up:'<path d="m18 15-6-6-6 6"/>',
  down:'<path d="m6 9 6 6 6-6"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
};
const I = (n, c='') => `<svg class="ic ${c}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${P[n]||''}</svg>`;
function hydrateIcons(root=document){ $$('i[data-i]', root).forEach(el => { el.outerHTML = I(el.dataset.i, el.className); }); }
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtBytes = (b) => b >= 1073741824 ? (b/1073741824).toFixed(2)+' GB' : b >= 1048576 ? (b/1048576).toFixed(1)+' MB' : Math.max(1, Math.round(b/1024))+' KB';
let clockSkew = 0;
const now = () => Date.now()/1000 + clockSkew;
function ago(t){ const d = Math.max(0, now()-t); if (d<60) return '刚刚'; if (d<3600) return Math.floor(d/60)+' 分钟前'; if (d<86400) return Math.floor(d/3600)+' 小时前'; if (d<86400*30) return Math.floor(d/86400)+' 天前'; return new Date(t*1000).toLocaleDateString(); }
const fmtTime = (t) => new Date(t*1000).toLocaleString('zh-CN', {hour12:false});
const dur = (s) => { s = Math.max(0, Math.round(s)); const m = Math.floor(s/60), r = s%60; return m ? `${m}:${String(r).padStart(2,'0')}` : `${r}s`; };

async function api(path, opts={}){
  const o = {...opts, headers:{...(opts.headers||{})}};
  if (o.json !== undefined){ o.body = JSON.stringify(o.json); o.headers['Content-Type'] = 'application/json'; delete o.json; }
  if (o.body && !o.method) o.method = 'POST';
  const res = await fetch(path, o);
  if (res.status === 401){ location.href = 'login'; throw new Error('需要登录'); }
  const ct = res.headers.get('content-type') || '';
  const body = ct.includes('json') ? await res.json().catch(()=>({})) : {};
  if (!res.ok) throw new Error(body.error || `${res.status} ${res.statusText}`);
  return body;
}
const post = (path, json) => api(path, {method:'POST', json: json ?? {}});

function toast(msg, type='', action){
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.innerHTML = I(type==='err' ? 'alert' : type==='ok' ? 'check' : 'info') + `<div>${esc(msg)}</div>`;
  if (action){ const a = document.createElement('span'); a.className='act'; a.textContent = action.label; a.onclick = () => { action.fn(); el.remove(); }; el.appendChild(a); }
  $('#toasts').appendChild(el);
  setTimeout(() => { el.style.transition='.3s'; el.style.opacity='0'; setTimeout(()=>el.remove(), 300); }, action ? 7000 : 3800);
}

function modal(html, {wide=false, onClose}={}){
  const scrim = document.createElement('div');
  scrim.className = 'scrim';
  scrim.innerHTML = `<div class="modal ${wide?'wide':''}">${html}</div>`;
  hydrateIcons(scrim);
  const close = () => { scrim.remove(); document.removeEventListener('keydown', onKey, true); onClose && onClose(); };
  const onKey = (e) => { if (e.key === 'Escape'){ e.stopPropagation(); close(); } };
  scrim.addEventListener('mousedown', e => { if (e.target === scrim) close(); });
  document.addEventListener('keydown', onKey, true);
  $('#overlay').appendChild(scrim);
  $$('[data-close]', scrim).forEach(b => b.onclick = close);
  return {el: scrim, close};
}
function confirmBox({title, body='', ok='确定', danger=false}){
  return new Promise(resolve => {
    let done = false;
    const m = modal(`<div class="mh"><h3>${esc(title)}</h3></div><div class="mb" style="color:var(--muted)">${body}</div>
      <div class="mf"><button class="btn" data-close>取消</button><button class="btn ${danger?'solid-danger':'primary'}" id="cOk">${esc(ok)}</button></div>`,
      {onClose: () => { if (!done) resolve(false); }});
    const b = $('#cOk', m.el); b.focus();
    b.onclick = () => { done = true; m.close(); resolve(true); };
  });
}

/* ── state ── */
const S = {
  cfg:null, mode:'image', tab:'image', engine:'diffusers', status:null, logSeq:0, logCount:0, galleryRev:-1, gallery:[], stats:{},
  filter:{kind:'', starred:false, q:''}, page:60, viewing:null, followLatest:true,
  selecting:false, selected:new Set(), lastClicked:null, refs:{}, lastLatestId:null, form:{}, unseenLogs:0,
  comfyPresets:[], studioPresets:[], promptHist:[], proxy:null, galleryOpen:false, galleryLoaded:false,
  grabPool:[], pollRounds:2, pollAllProxies:false,
  wfData:null, wfRun:null, wfAssetStep:'',
};
const LS_KEY = 'colab-studio.v2';
const LS_PHIST_KEY = 'colab-studio.prompt-hist.v1';
const IMAGE_SIZES = [['1:1',1024,1024],['2:3',768,1152],['3:2',1152,768],['3:4',896,1152],['4:3',1152,896],['9:16',768,1344],['16:9',1344,768],['2:3 HD',1024,1536],['3:2 HD',1536,1024]];
const VIDEO_SIZES = [['16:9 横',1280,768],['9:16 竖',768,1280],['1:1',768,768],['预览',512,768]];
const FRAMES = [[124,'5 秒'],[175,'7 秒'],[243,'10 秒'],[345,'14 秒']];
const STAGES = [['queued','排队'],['provisioning','申请 GPU'],['uploading','上传'],['generating','生成'],['downloading','拉回'],['done','完成']];
const PHASE = {idle:['空闲','ok'], starting:['正在启动 GPU','busy'], ready:['GPU 就绪','ok'], generating:['生成中','busy'], stopping:['正在释放','warn'], error:['出错','bad']};

/* ── form persistence ── */
function loadForm(){ try { S.form = JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch { S.form = {}; } }
function saveForm(){
  const f = S.form; f.mode = S.mode; f.common = f.common || {};
  $$('[data-p]').forEach(el => { f.common[el.id] = el.type === 'checkbox' ? el.checked : el.value; });
  f.common.count = +$('#count').textContent; f.common.gpu = S.gpu; f.common.gpu_pool = S.grabPool; f.common.grab_pool = S.grabPool;
  f.common.pollRounds = S.pollRounds; f.common.pollAllProxies = !!S.pollAllProxies;
  f.common.workflow = S.workflow; f.common.frames = S.frames;
  f.common.engine = S.engine;
  f.common.loras = collectLoras(true);
  f[S.mode] = {width:+$('#width').value, height:+$('#height').value, steps:+$('#steps').value, cfg:+$('#cfg').value, seed:$('#seed').value};
  localStorage.setItem(LS_KEY, JSON.stringify(f));
}
let saveT; const saveSoon = () => { clearTimeout(saveT); saveT = setTimeout(saveForm, 300); };
function applyPerMode(m){
  const d = (S.cfg && S.cfg.defaults[m]) || {};
  const v = {...d, seed:-1, ...(S.form[m] || {})};
  setNum('width', v.width); setNum('height', v.height); setNum('steps', v.steps); setNum('cfg', v.cfg);
  $('#seed').value = v.seed ?? -1;
}
function setNum(id, v){
  $('#'+id).value = v;
  const r = $('#'+id+'R'); if (r) r.value = v;
  if (id==='width'||id==='height'){ renderSizeChips(); updateResInfo(); }
}
function gcd(a,b){ return b ? gcd(b, a % b) : a; }
function updateResInfo(){
  const w = +$('#width').value || 768, h = +$('#height').value || 1152;
  const mp = (w * h / 1e6).toFixed(2);
  const g = gcd(w, h) || 1;
  const rw = Math.round(w / g), rh = Math.round(h / g);
  const ratio = (rw <= 24 && rh <= 24) ? `${rw}:${rh}` : (w / h).toFixed(2);
  const el = $('#mpBadge');
  if (el) el.textContent = `${mp} MP · ${ratio}`;
}
function loadPromptHistory(){ try { S.promptHist = JSON.parse(localStorage.getItem(LS_PHIST_KEY) || '[]'); } catch { S.promptHist = []; } }
function pushPromptHistory(p){
  const t = String(p || '').trim(); if (!t) return;
  S.promptHist = [t, ...S.promptHist.filter(x => x !== t)].slice(0, 15);
  try { localStorage.setItem(LS_PHIST_KEY, JSON.stringify(S.promptHist)); } catch {}
}
function renderPromptHistory(){
  const pop = $('#promptHistPop'); if (!pop) return;
  if (!S.promptHist.length){ pop.innerHTML = '<div class="dim" style="padding:6px;font-size:12px">暂无历史提示词（提交生成后自动记录）</div>'; return; }
  pop.innerHTML = S.promptHist.map((p, i) => `<button type="button" class="hist-item" data-ph="${i}" title="${esc(p)}">${esc(p.slice(0, 120))}</button>`).join('');
}
function renderStudioPresets(){
  const sel = $('#studioPresetSel'); if (!sel || !S.cfg) return;
  const sp = S.cfg.studio_presets || {};
  const builtins = (sp.builtin || []).filter(p => p.mode === S.mode);
  const customs = (S.studioPresets || []).filter(p => p.mode === S.mode);
  const prev = sel.value;
  let html = '<option value="">参数预设</option>';
  if (customs.length){
    html += '<optgroup label="我的自定义预设">' + customs.map(p => `<option value="${esc(p.id)}">★ ${esc(p.name)} (${p.width}×${p.height} · ${p.steps}步)</option>`).join('') + '</optgroup>';
  }
  if (builtins.length){
    html += '<optgroup label="推荐预设">' + builtins.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('') + '</optgroup>';
  }
  sel.innerHTML = html;
  if (prev && [...sel.options].some(o => o.value === prev)) sel.value = prev;
  const isCustom = customs.some(p => p.id === sel.value);
  $('#delStudioPresetBtn').classList.toggle('hide', !isCustom);
}
function applyStudioPreset(pid){
  const sp = (S.cfg && S.cfg.studio_presets) || {};
  const all = [...(S.studioPresets || []), ...(sp.builtin || [])];
  const p = all.find(x => x.id === pid);
  if (!p) return;
  if (p.mode && p.mode !== S.mode) setMode(p.mode);
  if (p.mode === 'video'){
    $('#videoTask').value = p.video_task || '';
    if (p.workflow){ S.workflow = p.workflow; renderWorkflowChips(); }
    if (p.num_frames){ S.frames = p.num_frames; renderFrameChips(); }
    const om = p.offload_mode || (p.auto_offload === false ? 'none' : 'auto');
    if ($('#offloadMode')) $('#offloadMode').value = om;
  } else {
    if (p.engine === 'comfyui' && p.comfy){
      setEngine('comfyui');
      applyComfyPreset(p.comfy);
    } else if (p.model){
      setEngine('diffusers');
      $('#imageModel').value = p.model;
      renderModelOptions();
    }
  }
  if (p.width) setNum('width', p.width);
  if (p.height) setNum('height', p.height);
  if (p.steps) setNum('steps', p.steps);
  if (p.cfg) setNum('cfg', p.cfg);
  if (p.gpu){
    S.grabPool = [p.gpu];
    if (ownedSessions().some(s => String(s.gpu).toUpperCase() === p.gpu)){ S.gpu = p.gpu; S.gpuPool = [p.gpu]; }
    renderGpuChips();
  }
  if (p.negative !== undefined && p.negative !== '') $('#negative').value = p.negative;
  if (Array.isArray(p.loras) && p.loras.length){ renderLoraRows(p.loras); $('#loraBlock').open = true; }
  updateModeUI(); saveForm();
  toast('已应用预设：' + p.name, 'ok');
}

/* ── option rendering ── */
function renderStaticOptions(){
  const c = S.cfg;
  $('#ver').textContent = 'v' + c.version;
  S.recentModels = Array.isArray(c.recent_models) ? c.recent_models.slice() : [];
  const cc = c.comfy || {};
  S.comfyPresets = Array.isArray(cc.presets) ? cc.presets.slice() : [];
  S.studioPresets = Array.isArray(c.studio_presets && c.studio_presets.custom) ? c.studio_presets.custom.slice() : [];
  S.proxy = c.proxy || null;
  $('#comfyTemplate').innerHTML = (cc.templates || []).map(t => `<option value="${esc(t.id)}">${esc(t.label)}</option>`).join('');
  $('#comfySampler').innerHTML = (cc.samplers || ['euler']).map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  $('#comfyScheduler').innerHTML = (cc.schedulers || ['simple']).map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  renderComfyPresets();
  renderStudioPresets();
  renderProxyChips();
  renderModelOptions();
  renderGpuChips(); renderWorkflowChips(); renderFrameChips();
  const lim = c.limits;
  ['width','height','widthR','heightR'].forEach(id => { const el = $('#'+id); if (el){ el.min = lim.size_min; el.max = lim.size_max; el.step = lim.size_step; } });
  ['steps','stepsR'].forEach(id => { $('#'+id).min = lim.steps_min; $('#'+id).max = lim.steps_max; });
  ['cfg','cfgR'].forEach(id => { $('#'+id).min = lim.cfg_min; $('#'+id).max = lim.cfg_max; });
}
function parseComfyLinkClient(raw){
  const s = (raw || '').trim();
  if (!s) return null;
  const fmtOf = (p) => {
    const l = p.toLowerCase();
    for (const [k,v] of [['nvfp4','NVFP4'],['fp8','FP8'],['int8','INT8'],['nf4','NF4'],['bf16','BF16'],['fp16','FP16'],['fp32','FP32'],['q8_0','Q8_0'],['q6_k','Q6_K'],['q5_k_m','Q5_K_M'],['q4_k_m','Q4_K_M']]){
      if (l.includes(k)) return v;
    }
    return l.endsWith('.gguf') ? 'GGUF' : l.endsWith('.safetensors') ? 'SAFETENSORS' : '';
  };
  let m = s.match(/^https?:\/\/(?:www\.)?(?:huggingface\.co|hf\.co|hf-mirror\.com)\/([^/?#]+\/[^/?#]+)\/(?:blob|resolve|raw)\/[^/?#]+\/([^?#]+)/i);
  if (m){
    const file = decodeURIComponent(m[2]);
    return {ok: /\.(safetensors|gguf|ckpt|pt|pth|bin)$/i.test(file), repo:m[1], file, base:file.split('/').pop(), fmt:fmtOf(file)};
  }
  if (s.includes('::')){
    const [r, f] = s.split('::');
    const repo = r.trim(), file = (f||'').trim();
    if (/^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(repo) && /\.(safetensors|gguf|ckpt|pt|pth|bin)$/i.test(file)){
      return {ok:true, repo, file, base:file.split('/').pop(), fmt:fmtOf(file)};
    }
  }
  if (/^https?:\/\/.+\.(safetensors|gguf|ckpt|pt|pth|bin)(\?.*)?$/i.test(s)){
    const base = decodeURIComponent(s.split('?')[0].split('/').pop() || '');
    return {ok:true, repo:'直链', file:base, base, fmt:fmtOf(base)};
  }
  return {ok:false, msg:'请粘贴具体模型文件页链接（含 /blob/main/... 或 owner/repo :: 文件路径）'};
}
function updateComfyLinkPreviews(){
  for (const [inId, metaId] of [['comfyDiff','comfyDiffMeta'],['comfyTe','comfyTeMeta'],['comfyVae','comfyVaeMeta']]){
    const el = $('#'+metaId), val = ($('#'+inId).value || '').trim();
    const p = parseComfyLinkClient(val);
    if (!p){ el.className = 'link-meta'; el.innerHTML = ''; continue; }
    if (!p.ok){ el.className = 'link-meta err'; el.textContent = p.msg || '需指向 .safetensors / .gguf 具体文件'; continue; }
    el.className = 'link-meta';
    const nv = p.fmt === 'NVFP4' || p.fmt === 'FP8' ? ' nv' : '';
    el.innerHTML = (p.fmt ? `<span class="fmt-pill${nv}">${esc(p.fmt)}</span>` : '') + `<span>${esc(p.repo)} · ${esc(p.base)}</span>`;
  }
}
function renderComfyPresets(){
  const cc = (S.cfg && S.cfg.comfy) || {};
  const builtins = cc.builtin_presets || [];
  $('#builtinComfyChips').innerHTML = builtins.map(p =>
    `<button type="button" class="pchip" data-cp="${esc(p.id)}" title="${esc(p.name)}">${esc(p.name)}</button>`
  ).join('');
  const saved = S.comfyPresets || [];
  $('#savedComfyWrap').classList.toggle('hide', !saved.length);
  $('#savedComfyChips').innerHTML = saved.map(p =>
    `<button type="button" class="pchip" data-cp="${esc(p.id)}" title="${esc(p.name)}"><span>${esc(p.name)}</span><span class="rm" data-rm-cp="${esc(p.id)}" title="删除组合">×</span></button>`
  ).join('');
}
function applyComfyPreset(p){
  if (!p) return;
  if (p.template) $('#comfyTemplate').value = p.template;
  if (p.diffusion !== undefined) $('#comfyDiff').value = p.diffusion;
  if (p.text_encoder !== undefined) $('#comfyTe').value = p.text_encoder;
  if (p.vae !== undefined) $('#comfyVae').value = p.vae;
  if (p.sampler) $('#comfySampler').value = p.sampler;
  if (p.scheduler) $('#comfyScheduler').value = p.scheduler;
  if (p.width) setNum('width', p.width);
  if (p.height) setNum('height', p.height);
  if (p.steps) setNum('steps', p.steps);
  if (p.cfg) setNum('cfg', p.cfg);
  renderLoraRows(Array.isArray(p.loras) ? p.loras : []);
  if (Array.isArray(p.loras) && p.loras.length) $('#loraBlock').open = true;
  updateComfyLinkPreviews();
  $('#stepsHint').textContent = S.mode === 'video' ? '（Turbo LoRA 可设 4–8）' : (S.engine === 'comfyui' ? '（精细 28–35 步 / Turbo LoRA 8 步）' : '');
  saveSoon();
  toast('已载入组合：' + p.name, 'ok');
}
function setEngine(eng){
  S.engine = eng === 'comfyui' ? 'comfyui' : 'diffusers';
  $('#engDiffusers').classList.toggle('on', S.engine === 'diffusers');
  $('#engComfy').classList.toggle('on', S.engine === 'comfyui');
  $('#diffusersBox').classList.toggle('hide', S.engine !== 'diffusers');
  $('#comfyBox').classList.toggle('hide', S.engine !== 'comfyui');
  if (S.engine === 'comfyui' && !$('#comfyDiff').value.trim()){
    const cc = (S.cfg && S.cfg.comfy) || {};
    const tpl = (cc.templates || []).find(t => t.id === $('#comfyTemplate').value) || (cc.templates || [])[0];
    if (tpl && tpl.defaults){
      $('#comfyDiff').value = tpl.defaults.diffusion || '';
      $('#comfyTe').value = tpl.defaults.text_encoder || '';
      $('#comfyVae').value = tpl.defaults.vae || '';
      $('#comfySampler').value = tpl.defaults.sampler || 'euler';
      $('#comfyScheduler').value = tpl.defaults.scheduler || 'simple';
    }
  }
  updateComfyLinkPreviews();
  $('#stepsHint').textContent = S.mode === 'video' ? '（Turbo LoRA 可设 4–8）' : (S.engine === 'comfyui' ? '（精细 28–35 步 / Turbo LoRA 8 步）' : '');
  saveSoon();
}
function modelShortLabel(id){
  const preset = S.cfg && S.cfg.image_models.find(x => x.id === id);
  if (preset) return preset.label.split(' · ')[0] + (preset.id.endsWith('q5') ? ' Q5' : preset.id.endsWith('bf16') ? ' BF16' : '');
  return id.includes('/') ? id.split('/').pop() : id;
}
function renderModelOptions(){
  if (!S.cfg) return;
  const cur = ($('#imageModel').value || '').trim();
  const presets = S.cfg.image_models || [];
  const recents = S.recentModels || [];
  const allIds = [...new Set([...recents, ...presets.map(m => m.id)])];
  $('#modelSuggest').innerHTML = allIds.map(id => {
    const p = presets.find(x => x.id === id);
    return `<option value="${esc(id)}">${p ? esc(p.label) : esc(id)}</option>`;
  }).join('');
  $('#presetModelChips').innerHTML = presets.map(m =>
    `<button type="button" class="pchip ${cur===m.id?'on':''}" data-model="${esc(m.id)}" title="${esc(m.id + ' — ' + m.hint)}">${esc(modelShortLabel(m.id))}</button>`
  ).join('');
  const rWrap = $('#recentModelsWrap');
  rWrap.classList.toggle('hide', !recents.length);
  $('#recentModelChips').innerHTML = recents.map(id =>
    `<button type="button" class="pchip ${cur===id?'on':''}" data-model="${esc(id)}" title="${esc(id)}"><span>${esc(modelShortLabel(id))}</span><span class="rm" data-rm-model="${esc(id)}" title="从最近使用移除">×</span></button>`
  ).join('');
  const preset = presets.find(x => x.id === cur);
  if (preset) $('#modelHint').textContent = preset.hint;
  else if (/^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(cur)) $('#modelHint').textContent = '自定义 HF 模型：将通过 Diffusers 自动加载（受限模型需在设置里配 HF Token）';
  else if (!cur) $('#modelHint').textContent = '留空默认使用 Qwen-Image-2.1 · BF16';
  else $('#modelHint').textContent = '格式应为内置名或 Hugging Face 仓库 ID（owner/repo）';
  $('#ggufWrap').classList.toggle('hide', S.mode === 'video' || cur !== 'qwen-2.1-q5');
}
function ownedSessions(){
  const co = (S.status && S.status.colab) || {};
  const known = new Set(((S.cfg && S.cfg.gpus) || []).map(g => g.id));
  return (co.sessions || []).filter(s => known.has(String(s.gpu || '').toUpperCase()));
}
function renderGpuChips(){
  const box = $('#gpuChips');
  if (!box || !S.cfg) { renderGrabCatalog(); return; }
  const co = (S.status && S.status.colab) || {};
  if (!co.authed){
    box.innerHTML = '<div class="help" style="margin:2px 0 0">还没连接 Google Colab。去设置里连接并抢卡。</div>';
    $('#gpuHint').textContent = '';
    $('#gpuHelp').textContent = '';
    renderGrabCatalog();
    return;
  }
  const owned = ownedSessions();
  if (!owned.length){
    box.innerHTML = `<div class="help" style="margin:2px 0 0">还没有持有的算力。去设置里抢卡。</div>
      <button type="button" class="btn sm" data-open-settings style="margin-top:8px">打开设置</button>`;
    $('#gpuHint').textContent = '未持有';
    $('#gpuHelp').textContent = '';
    renderGrabCatalog();
    return;
  }
  const ids = owned.map(s => String(s.gpu).toUpperCase());
  if (!ids.includes(S.gpu)) S.gpu = ids[0];
  S.gpuPool = [S.gpu];
  box.innerHTML = owned.map(s => {
    const id = String(s.gpu).toUpperCase();
    const meta = (S.cfg.gpus || []).find(g => g.id === id) || {label: id};
    const on = id === S.gpu;
    const sub = [s.shape, s.endpoint].filter(Boolean).join(' · ');
    return `<button type="button" class="gpu-item ${on?'on':''}" data-gpu="${esc(id)}" title="使用这台已持有的卡">
      <span class="g-radio">${on ? '✓' : ''}</span>
      <span class="g-main">
        <span class="g-top"><span>${esc(meta.label || id)}</span></span>
        <span class="g-sub">${esc(sub)}</span>
      </span>
      <span class="gpu-badge run">持有中</span>
    </button>`;
  }).join('');
  $('#gpuHint').textContent = `${owned.length} 台持有中`;
  $('#gpuHelp').textContent = owned.length > 1
    ? '点选本次生成使用的卡。要申请新卡，去设置里抢卡。'
    : '生成会直接复用这台卡。要换卡或再抢一张，去设置里抢卡。';
  renderGrabCatalog();
}
function renderGrabCatalog(){
  const box = document.getElementById('sGrabGpus');
  if (!box || !S.cfg) return;
  const co = (S.status && S.status.colab) || {};
  const elig = Array.isArray(co.eligible_gpus) ? co.eligible_gpus : [];
  const health = co.gpu_health || {};
  const running = new Set((co.sessions || []).map(s => String(s.gpu || '').toUpperCase()));
  const curTs = now();
  const statusFor = (id) => {
    if (running.has(id)) return ['持有中', 'run', true];
    const h = health[id];
    if (h && h.at){
      const ago = Math.max(0, Math.round((curTs - h.at) / 60));
      const agoTxt = ago < 1 ? '刚刚' : `${ago}m前`;
      if (h.status === 'unavailable') return [`近期缺货 · ${agoTxt}`, 'warn', true];
      if (h.status === 'error') return [`异常 ${h.code || ''} · ${agoTxt}`.trim(), 'bad', true];
      if (h.status === 'ok') return [`近期可用 · ${agoTxt}`, 'ok', true];
    }
    if (elig.length) return elig.includes(id) ? ['账号可用', 'ok', true] : ['无权限', 'off', false];
    return [co.authed ? '待查询' : '未连接', 'off', true];
  };
  const pool = Array.isArray(S.grabPool) ? S.grabPool : [];
  box.innerHTML = S.cfg.gpus.map(g => {
    const [badgeTxt, badgeCls, ok] = statusFor(g.id);
    const idx = pool.indexOf(g.id);
    const on = idx >= 0;
    return `<button type="button" class="gpu-item ${on?'on':''} ${ok?'':'dimmed'}" data-grab="${g.id}" title="${esc(g.hint + '（点击勾选，按序号轮询抢卡）')}">
      <span class="g-radio">${on ? (idx + 1) : ''}</span>
      <span class="g-main">
        <span class="g-top"><span>${esc(g.label || g.id)}</span></span>
        <span class="g-sub">${esc(g.hint)}</span>
      </span>
      <span class="gpu-badge ${badgeCls}">${esc(badgeTxt)}</span>
    </button>`;
  }).join('');
  updatePollSummary();
  renderGrabState();
}
function updatePollSummary(){
  const el = $('#pollSummary'); if (!el) return;
  const pool = Array.isArray(S.grabPool) ? S.grabPool : [];
  const typed = $('#pollRounds');
  const rounds = Math.max(1, Math.min(10, +(typed && typed.value) || S.pollRounds || 1));
  const pxCnt = S.pollAllProxies && S.proxy && Array.isArray(S.proxy.profiles)
    ? Math.max(1, S.proxy.profiles.filter(p => p.configured).length)
    : 1;
  el.textContent = pool.length ? `${pool.length} 卡 × ${pxCnt} 代理 × ${rounds} 轮` : '还没选卡';
}
function renderGrabState(){
  const el = document.getElementById('sGrabState');
  if (!el || !S.status) return;
  const st = S.status;
  if (st.phase === 'starting' && !st.current) el.textContent = '正在抢卡…';
  else if (st.phase === 'error' && st.error) el.textContent = st.error;
  else if (st.idle_minutes === 0 && (st.active_gpu || (st.colab && st.colab.any_running))) el.textContent = '当前保持持有，不会自动释放。';
  else el.textContent = '';
}
function renderProxyChips(){
  if (!$('#proxyChips')) return;
  const px = S.proxy;
  if (!px || !Array.isArray(px.profiles)) return;
  const active = px.active || '';
  const entries = [{id:'', label:'系统网络', masked:''}, ...px.profiles];
  $('#proxyChips').innerHTML = entries.map(p =>
    `<button type="button" class="pchip ${active===p.id?'on':''}" data-proxy="${esc(p.id)}" title="${esc(p.masked||'')}">${esc(p.label)}</button>`).join('');
  const editor = $('#proxyEditTarget');
  const selected = editor.value;
  const choices = '<option value="">新增线路</option>' + px.profiles.map(p =>
    `<option value="${esc(p.id)}">${esc(p.label)}</option>`).join('');
  if (editor.dataset.choices !== choices){
    editor.innerHTML = choices;
    editor.dataset.choices = choices;
    editor.value = px.profiles.some(p => p.id === selected) ? selected : '';
    if (selected && !editor.value) editor.onchange?.();
  }
  $('#removeProxyBtn').disabled = !editor.value;
  $('#testProxyBtn').disabled = !active;
  const curP = px.profiles.find(p => p.id === active);
  const lt = px.last_test;
  let txt = curP ? `当前出口：${curP.label}` : '当前使用系统网络';
  if (lt && lt.profile === active){
    txt += lt.ok ? ` · 连通 ${lt.loc}/${lt.colo} (${lt.ms}ms)` : ` · 测速失败：${lt.error}`;
  } else if (curP && curP.hint){
    txt += ' · ' + curP.hint;
  }
  $('#proxyHelp').textContent = txt;
  updatePollSummary();
}
function renderWorkflowChips(){
  $('#workflowChips').innerHTML = S.cfg.video_workflows.map(w => `<button class="pchip ${S.workflow===w.id?'on':''}" data-wf="${w.id}">${w.id} · ${esc(w.label)}</button>`).join('');
}
function renderFrameChips(){
  $('#frameChips').innerHTML = FRAMES.map(([n,l]) => `<button class="pchip ${S.frames===n?'on':''}" data-fr="${n}">${l} <span class="dim">${n}f</span></button>`).join('');
}
function renderSizeChips(){
  const w = +$('#width').value, h = +$('#height').value;
  const list = S.mode === 'video' ? VIDEO_SIZES : IMAGE_SIZES;
  $('#sizeChips').innerHTML = list.map(([l,W,H]) => {
    const k = 14/Math.max(W,H);
    return `<button class="pchip ${W===w&&H===h?'on':''}" data-w="${W}" data-h="${H}"><span class="ar" style="width:${Math.round(W*k)}px;height:${Math.round(H*k)}px"></span>${l}</button>`;
  }).join('');
}
function renderLoraRows(saved){
  const rows = saved && saved.length ? saved : [{},{}];
  while (rows.length < 2) rows.push({});
  $('#loraRows').innerHTML = rows.slice(0,2).map((r,i) => `
    <div class="lora" data-i="${i}">
      <input type="text" class="lr" placeholder="LoRA ${i+1} · owner/repo 或粘贴 HF 文件链接" value="${esc(r.repo_id||'')}">
      <button class="btn sm ls">扫描</button>
      <input type="text" class="lf full" list="ll${i}" placeholder="权重文件 .safetensors（粘贴链接会自动填充）" value="${esc(r.weight_name||'')}">
      <datalist id="ll${i}"></datalist>
      <div class="slider full"><input type="range" class="lsr" min="0" max="2.5" step="0.05" value="${r.scale ?? 1}"><input type="number" class="lsc" min="0" max="2.5" step="0.05" value="${r.scale ?? 1}"></div>
    </div>`).join('');
  updateLoraHint();
}
function collectLoras(includeEmpty=false){
  return $$('#loraRows .lora').map(el => ({repo_id: $('.lr',el).value.trim(), weight_name: $('.lf',el).value.trim(), scale: +$('.lsc',el).value || 1}))
    .filter(l => includeEmpty || l.repo_id);
}
function updateLoraHint(){ const n = collectLoras().length; $('#loraHint').textContent = n ? `已启用 ${n} 个` : '未启用'; }

/* ── mode & 3-tab workspace ── */
function setWorkspace(tab, {keep=false}={}){
  const t = (tab === 'workflow' || tab === 'video') ? tab : 'image';
  S.tab = t;
  $('#wsImage').classList.toggle('on', t === 'image');
  $('#wsVideo').classList.toggle('on', t === 'video');
  $('#wsWorkflow').classList.toggle('on', t === 'workflow');
  $('#studioLayout').classList.toggle('hide', t === 'workflow');
  $('#workflowWorkspace').classList.toggle('hide', t !== 'workflow');
  if (t === 'workflow'){
    loadWorkflowData();
  } else {
    setMode(t, {keep});
  }
}
function setMode(m, {keep=false}={}){
  if (!keep && S.mode !== m) saveForm();
  S.mode = m;
  if (S.tab !== 'workflow'){
    S.tab = m;
    $('#wsImage').classList.toggle('on', m === 'image');
    $('#wsVideo').classList.toggle('on', m === 'video');
    $('#wsWorkflow').classList.remove('on');
  }
  $('#mImage').classList.toggle('on', m === 'image');
  $('#mVideo').classList.toggle('on', m === 'video');
  if (!keep) applyPerMode(m);
  renderStudioPresets();
  updateModeUI();
  saveSoon();
}
function isMultiRefMode(){
  return S.mode === 'image' || (S.mode === 'video' && S.workflow === 'ref2va');
}
function updateRewriteBadge(){
  const el = $('#rewriteModeBadge'); if (!el) return;
  const items = Array.isArray(S.refs.items) ? S.refs.items : [];
  const hasLast = !!(S.refs.last && S.refs.last.set);
  if (S.mode === 'video'){
    const sec = (S.frames / 24).toFixed(1);
    if (S.workflow === 'ref2va'){
      const useImages = !['edit', 'continue'].includes(currentVideoTask()) || $('#videoUseImages').checked;
      el.textContent = `H3 六段式 (Ref2VA · ${sec}s` + (items.length && useImages ? ` · 看 ${items.length} 张参考图)` : ')');
    } else if (S.workflow === 'fl2va'){
      const sub = items.length && hasLast ? 'FL2VA · 看首尾帧' : (items.length ? 'I2VA · 看首帧' : hasLast ? 'L2VA · 看尾帧' : 'FL2VA');
      el.textContent = `H3 三段式 (${sub} · ${sec}s)`;
    } else {
      el.textContent = `H3 三段式 (T2VA · ${sec}s)`;
    }
  } else {
    if ($('#chain').checked) el.textContent = '多模态连续改图（看最新作品）';
    else if ($('#useRef').checked && items.length) el.textContent = `多模态看图改写（看 ${items.length} 张参考图）`;
    else el.textContent = '文生图提示词改写';
  }
}
function currentVideoTask(){
  return S.mode === 'video' && S.workflow === 'ref2va' ? $('#videoTask').value : '';
}
function updateModeUI(){
  const v = S.mode === 'video';
  $('#modeBlockTitle').textContent = v ? '视频模式与时长' : '生图引擎与模型';
  $('#imageModelWrap').classList.toggle('hide', v);
  $('#workflowWrap').classList.toggle('hide', !v);
  $('#framesWrap').classList.toggle('hide', !v);
  $('#offloadWrap').classList.toggle('hide', !v);
  $('#imgRefOpts').classList.toggle('hide', v);
  $('#negWrap').classList.toggle('hide', v);
  const wf = S.workflow;
  const task = currentVideoTask();
  const optionalImages = task === 'edit' || task === 'continue';
  $('#videoTaskWrap').classList.toggle('hide', !v || wf !== 'ref2va');
  $('#videoRefWrap').classList.toggle('hide', !task);
  $('#videoImagesToggle').classList.toggle('hide', !optionalImages);
  const multi = isMultiRefMode();
  $('#refBlock').classList.toggle('hide', v && wf === 't2va');
  $('#multiRefWrap').classList.toggle('hide', !multi || (optionalImages && !$('#videoUseImages').checked));
  $('#drops').classList.toggle('hide', multi);
  $('#dropLast').classList.toggle('hide', !(v && wf === 'fl2va'));
  $('#drops').classList.toggle('two', v && wf === 'fl2va');
  $('#refTitle').textContent = task === 'motion' ? '白模视频与人设图' : task ? '参考视频' : v && wf === 'fl2va' ? '首帧 / 尾帧' : '参考图';
  $('#refHint').textContent = task ? '' : '点击 / 拖入 / 粘贴';
  $('#firstTtl').textContent = v ? (wf === 'fl2va' ? '首帧' : '参考图') : '参考图';
  $('#firstTtl').classList.toggle('hide', !(v && wf === 'fl2va'));
  const maxR = (S.refs && S.refs.max) || (S.cfg && S.cfg.limits && S.cfg.limits.refs_max) || 6;
  $('#refHelp').textContent = v
    ? (wf === 'fl2va' ? '可只用首帧、只用尾帧，或同时设置两帧。' : `最多可传 ${maxR} 张参考图，AI 改写会自动看图生成 6 段式 Ref2VA 提示词。`)
    : `最多可传 ${maxR} 张参考图；勾选「用参考图改图」后 AI 改写会自动看图。`;
  if (task) $('#refHelp').textContent = task === 'motion' ? '白模视频提供动作和运镜，第一张人设图提供角色外观。' :
    (task === 'continue' ? '从原片结尾续拍，新片段单独保存。可添加参考图。' : '请在提示词里写明要改动的内容。可添加参考图。');
  renderModelOptions();
  $('#goText').textContent = v ? '生成视频' : '开始生成';
  $('#stepsHint').textContent = v ? '（Turbo LoRA 可设 4–8；写实 LoRA 建议 18 步）' : (S.engine === 'comfyui' ? '（精细 28–35 步 / Turbo LoRA 8 步）' : '');
  renderSizeChips();
  updateRewriteBadge();
  updateGoState();
}

/* ── references ── */
function renderRefs(refs){
  S.refs = refs || {};
  const clip = S.refs.video;
  const preview = $('#videoRefPreview');
  const src = clip ? 'api/video-reference?id=' + encodeURIComponent(clip.id) : '';
  if (src !== (preview.getAttribute('src') || '')){
    if (src) preview.src = src;
    else { preview.removeAttribute('src'); preview.load(); }
  }
  preview.classList.toggle('hide', !clip);
  $('#videoRefClear').classList.toggle('hide', !clip);
  for (const slot of ['first','last']){
    const r = S.refs[slot] || {}; const el = $(slot==='first' ? '#dropFirst' : '#dropLast');
    el.classList.toggle('set', !!r.set);
    if (r.set){
      const src = `api/reference?slot=${slot}&t=${r.updated_at}`;
      const img = $('img', el); if (img.dataset.src !== src){ img.src = src; img.dataset.src = src; }
      $('.tag', el).textContent = r.source && r.source.startsWith('round:') ? '作品 #' + r.source.slice(6) : r.source === 'upload' ? '上传' : '已设置';
    }
  }
  const items = Array.isArray(S.refs.items) ? S.refs.items : [];
  const maxR = S.refs.max || (S.cfg && S.cfg.limits && S.cfg.limits.refs_max) || 6;
  const cards = items.map((it, idx) => {
    const src = `api/reference?id=${encodeURIComponent(it.id)}&t=${it.updated_at}`;
    const tag = it.source && it.source.startsWith('round:') ? '#' + it.source.slice(6) : it.source === 'upload' ? '上传' : '已设置';
    return `<div class="ref-card" data-rid="${esc(it.id)}">
      <span class="ref-idx">图${idx + 1}</span>
      <img src="${src}" alt="参考图 ${idx + 1}">
      <span class="tag">${esc(tag)}</span>
      <button type="button" class="clear" data-rmref="${esc(it.id)}" title="移除图${idx + 1}">${I('x')}</button>
    </div>`;
  });
  if (items.length < maxR){
    const wide = items.length === 0 ? ' wide' : '';
    cards.push(`<div class="ref-add${wide}" id="refAddZone" title="点击选择或拖入图片（可多选）">
      ${I('upload', items.length === 0 ? 'lg' : '')}
      <div>${items.length === 0 ? '上传参考图（可多选）' : '添加'}</div>
      ${items.length === 0 ? `<div class="dim">PNG / JPEG / WebP ≤ 12MB · 最多 ${maxR} 张</div>` : `<div class="dim">${items.length}/${maxR}</div>`}
    </div>`);
  }
  $('#refGrid').innerHTML = cards.join('');
  $('#refBar').classList.toggle('hide', items.length === 0);
  $('#refCountText').textContent = `已选 ${items.length} / ${maxR} 张参考图`;
  updateRewriteBadge();
}
async function uploadRef(slot, file, {append=false, silent=false}={}){
  if (!file) return false;
  if (!/^image\/(png|jpeg|webp)$/.test(file.type)){ toast('只支持 PNG / JPEG / WebP', 'err'); return false; }
  if (file.size > 12*1048576){ toast('图片超过 12MB', 'err'); return false; }
  try {
    const qs = slot === 'last' ? 'slot=last' : (append ? 'slot=first&append=1' : 'slot=first');
    const r = await api('api/reference?' + qs, {method:'POST', body:file});
    if (r && r.references) renderRefs(r.references);
    if (!silent) toast(slot === 'last' ? '尾帧已上传' : (append ? '已添加参考图' : '参考图已上传'), 'ok');
    if (slot === 'first' && S.mode === 'image'){ $('#useRef').checked = true; $('#chain').checked = false; saveSoon(); }
    if (!silent) refresh();
    return true;
  } catch(e){ toast('上传失败：' + e.message, 'err'); return false; }
}
async function uploadMultipleRefs(files){
  const list = [...(files || [])].filter(Boolean);
  if (!list.length) return;
  let ok = 0;
  for (const f of list){
    const res = await uploadRef('first', f, {append: true, silent: true});
    if (!res) break;
    ok++;
  }
  if (ok){
    toast(ok > 1 ? `已添加 ${ok} 张参考图` : '已添加参考图', 'ok');
    refresh();
  }
}
async function useAsRef(id, slot='first', append=null){
  const shouldAppend = append !== null ? append : (slot === 'first' && isMultiRefMode());
  try {
    const r = await post(`api/rounds/${id}/use`, {slot, append: shouldAppend});
    if (r && r.references) renderRefs(r.references);
    if (slot === 'first' && S.mode === 'image'){ $('#useRef').checked = true; $('#chain').checked = false; saveSoon(); }
    toast(slot === 'last' ? `已将 #${id} 设为尾帧` : (shouldAppend ? `已将 #${id} 加入参考图` : `已将 #${id} 设为首帧`), 'ok');
    refresh();
  } catch(e){ toast(e.message, 'err'); }
}
function bindDrop(el){
  const slot = el.dataset.slot;
  el.addEventListener('click', e => { if (e.target.closest('.clear')) return; S.pickSlot = slot; S.pickAppend = false; $('#fileInput').multiple = false; $('#fileInput').click(); });
  $('.clear', el).addEventListener('click', async e => { e.stopPropagation(); await api('api/reference?slot='+slot, {method:'DELETE'}); if (slot==='first') $('#useRef').checked = false; saveSoon(); refresh(); });
  el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('over'); });
  el.addEventListener('dragleave', () => el.classList.remove('over'));
  el.addEventListener('drop', e => {
    e.preventDefault(); el.classList.remove('over');
    const rid = e.dataTransfer.getData('text/x-round');
    if (rid) return useAsRef(rid, slot, false);
    const f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) uploadRef(slot, f);
  });
}

/* ── prompt ── */
async function rewrite(){
  const idea = $('#idea').value.trim();
  if (!idea) { toast('先写一句想法', 'err'); $('#idea').focus(); return; }
  const b = $('#rewriteBtn'); b.disabled = true; b.innerHTML = '<span class="sp"></span>改写中…';
  $('#rewriteHint').textContent = '正在改写…';
  try {
    const items = Array.isArray(S.refs.items) ? S.refs.items : [];
    const chain = S.mode === 'image' && $('#chain').checked;
    const editing = S.mode === 'image' && ($('#useRef').checked || chain);
    const has_last_image = S.mode === 'video' && S.workflow === 'fl2va' && !!(S.refs.last && S.refs.last.set);
    const ref_count = S.mode === 'image' ? (editing ? (chain ? 1 : items.length) : 0) : (S.workflow === 't2va' ? 0 : items.length);
    const r = await post('api/prompt', {
      text: idea,
      mode: S.mode,
      workflow: S.workflow,
      num_frames: S.frames,
      editing,
      chain,
      has_last_image,
      video_task: currentVideoTask() || undefined,
      ref_count: ['edit', 'continue'].includes(currentVideoTask()) && !$('#videoUseImages').checked ? 0 : ref_count,
    });
    $('#prompt').value = r.prompt; updateCount(); saveSoon();
    $('#rewriteHint').textContent = `✓ ${r.format || '已写入下方提示词'}`;
    setTimeout(() => $('#rewriteHint').textContent = '', 5000);
  } catch(e){ $('#rewriteHint').textContent = ''; toast('改写失败：' + e.message, 'err'); }
  b.disabled = false; b.innerHTML = I('sparkles') + 'AI 改写为提示词';
}
function updateCount(){ $('#promptCount').textContent = $('#prompt').value.length; }

/* ── generate ── */
function buildPayload(){
  const v = S.mode === 'video';
  const held = ownedSessions();
  const gpu = held.some(s => String(s.gpu).toUpperCase() === S.gpu) ? S.gpu : (held[0] ? String(held[0].gpu).toUpperCase() : (S.gpu || 'A100'));
  const p = {
    mode:S.mode, gpu, gpu_pool:[gpu],
    poll_rounds: 1,
    poll_all_proxies: false,
    prompt:$('#prompt').value.trim(), negative:$('#negative').value, idea:$('#idea').value.trim(),
    width:+$('#width').value, height:+$('#height').value, steps:+$('#steps').value, cfg:+$('#cfg').value,
    seed: $('#seed').value === '' ? -1 : +$('#seed').value, count:+$('#count').textContent, loras:collectLoras(),
  };
  if (v){
    const om = ($('#offloadMode') && $('#offloadMode').value) || 'auto';
    p.workflow = S.workflow; p.num_frames = S.frames; p.offload_mode = om; p.auto_offload = om !== 'none';
    p.has_last_image = S.workflow === 'fl2va' && !!S.refs.last?.set;
    p.has_image = S.workflow !== 't2va' && (!p.has_last_image || !!S.refs.first?.set);
    if (currentVideoTask()){
      p.video_task = currentVideoTask(); p.video_reference_id = S.refs.video?.id;
      p.has_image = p.video_task === 'motion' || ($('#videoUseImages').checked && !!S.refs.first?.set);
    }
  } else {
    p.engine = S.engine;
    p.chain = $('#chain').checked; p.has_image = $('#useRef').checked && !p.chain;
    if (S.engine === 'comfyui'){
      p.comfy = {
        template: $('#comfyTemplate').value || 'qwen-image-2.1',
        diffusion: $('#comfyDiff').value.trim(),
        text_encoder: $('#comfyTe').value.trim(),
        vae: $('#comfyVae').value.trim(),
        sampler: $('#comfySampler').value || 'euler',
        scheduler: $('#comfyScheduler').value || 'simple',
      };
    } else {
      p.model = $('#imageModel').value.trim();
      p.custom_transformer_repo = $('#ggufRepo').value.trim(); p.custom_transformer_file = $('#ggufFile').value.trim();
    }
  }
  return p;
}
async function generate(){
  const authed = S.status && S.status.colab && S.status.colab.authed;
  if (S.status && S.status.phase === 'starting' && !S.status.current){
    toast('正在抢卡，请等算力就绪后再生成', 'err');
    return;
  }
  if (authed && !ownedSessions().length){
    toast('还没有持有的算力，请到设置里抢卡', 'err');
    openSettings();
    return;
  }
  const p = buildPayload();
  if (p.video_task && (S.videoRefBusy || !p.video_reference_id)){ toast('请先选好参考视频', 'err'); return; }
  if (!p.prompt){ toast('请先填写提示词', 'err'); $('#prompt').focus(); return; }
  if (p.mode === 'image' && p.engine === 'comfyui'){
    if (!p.comfy.diffusion){ toast('请填写扩散模型链接（或先点选上方内置推荐组合）', 'err'); $('#comfyDiff').focus(); return; }
    if (!p.comfy.text_encoder){ toast('请填写文本编码器链接', 'err'); $('#comfyTe').focus(); return; }
    if (!p.comfy.vae){ toast('请填写 VAE 链接', 'err'); $('#comfyVae').focus(); return; }
  }
  if (p.has_image && !(S.refs.first && S.refs.first.set)){ toast('当前设置需要参考图 / 首帧，请先上传或从作品库选择', 'err'); return; }
  const b = $('#goBtn'); b.disabled = true;
  try {
    const r = await post('api/generate', p);
    pushPromptHistory(p.prompt);
    S.followLatest = true;
    toast(r.jobs.length > 1 ? `已加入队列：${r.jobs.length} 个任务` : '任务已提交', 'ok');
    saveForm();
  } catch(e){ toast(e.message, 'err'); }
  b.disabled = false; refresh();
}
function updateGoState(){
  const st = S.status; const authed = st && st.colab && st.colab.authed;
  const busy = st && (st.current || (st.queue||[]).length);
  const grabbing = st && st.phase === 'starting' && !st.current;
  $('#goText').textContent = !authed && st ? '先在设置里连接 Colab'
    : (authed && !ownedSessions().length) ? '去设置里抢卡'
    : grabbing ? '正在抢卡…'
    : busy ? '加入队列'
    : (S.mode === 'video' ? '生成视频' : '开始生成');
  $('#stopBtn').classList.toggle('hide', !(st && st.current));
}

/* ── status polling ── */
let pollT = null, polling = false;
async function refresh(){
  if (polling) return; polling = true;
  try {
    const st = await api('api/status?log_since=' + S.logSeq);
    clockSkew = st.server_time - Date.now()/1000;
    S.status = st;
    renderStatus(st);
    if (st.gallery_rev !== S.galleryRev) await loadGallery(st.gallery_rev);
  } catch(e){ $('#phaseText').textContent = '连接断开'; $('#phaseDot').className = 'dot bad'; }
  polling = false;
  clearTimeout(pollT);
  const st = S.status;
  const wfBusy = !!(st && st.workflow_active && st.workflow_active.status === 'running');
  const busy = (st && (st.current || (st.queue||[]).length || st.phase === 'stopping')) || wfBusy;
  if (S.tab === 'workflow' && S.wfRun && (wfBusy || S.wfRun.status === 'running')){
    pollActiveWorkflowRun();
  }
  pollT = setTimeout(refresh, document.hidden ? 10000 : busy || !$('#logDock').classList.contains('hide') ? 1200 : 5000);
}
const SV_STATE = {
  idle:['COLD','cold','按需冷启动 · 0 CU/h'],
  starting:['BOOTING','busy','正在拉起 Colab GPU 容器'],
  ready:['WARM','warm','模型常驻显存 · 0s 冷启'],
  generating:['RUNNING','busy','正在 GPU 推理'],
  stopping:['SCALING 0','warn','正在释放实例缩容至 0'],
  error:['ERROR','bad','最近一次执行异常'],
};
function renderIdleChip(st){
  const chip = $('#idleChip');
  if (!chip || !st) return;
  const holding = st.idle_minutes === 0 && (st.active_gpu || (st.colab && st.colab.any_running)) && !st.current;
  if (holding){
    chip.classList.remove('hide');
    chip.title = '已设为永不超期，不会自动释放';
    $('#idleText').textContent = '保持持有';
    return;
  }
  chip.title = '空闲到期自动释放 Colab 运行时';
  if (st.idle_deadline && !st.current){
    chip.classList.remove('hide');
    $('#idleText').textContent = dur(st.idle_deadline - now()) + ' 后缩容';
  } else chip.classList.add('hide');
}
function renderStatus(st){
  const [label, cls] = PHASE[st.phase] || [st.phase, ''];
  const [svTxt, svCls, svTip] = SV_STATE[st.phase] || ['COLD', 'cold', ''];
  const sv = $('#svBadge');
  if (sv){ sv.textContent = svTxt; sv.className = 'sv-pill ' + svCls; }
  $('#phaseText').textContent = label + (st.active_gpu ? ' · ' + st.active_gpu : '');
  $('#phaseDot').className = 'dot ' + cls;
  $('#phaseChip').title = st.error || svTip;
  renderIdleChip(st);
  renderGrabState();
  const wfB = $('#wfRunBadge');
  if (wfB){
    const wa = st.workflow_active;
    if (wa && wa.status === 'running'){
      wfB.textContent = `${wa.done_steps}/${wa.total_steps}`;
      wfB.classList.remove('hide');
    } else {
      wfB.classList.add('hide');
    }
  }
  renderColabChip(st.colab);
  renderGpuChips();
  renderRefs(st.references);
  if (Array.isArray(st.recent_models) && JSON.stringify(st.recent_models) !== JSON.stringify(S.recentModels || [])){
    S.recentModels = st.recent_models.slice();
    renderModelOptions();
  }
  if (Array.isArray(st.comfy_presets) && JSON.stringify(st.comfy_presets) !== JSON.stringify(S.comfyPresets || [])){
    S.comfyPresets = st.comfy_presets.slice();
    renderComfyPresets();
  }
  if (Array.isArray(st.studio_presets) && JSON.stringify(st.studio_presets) !== JSON.stringify(S.studioPresets || [])){
    S.studioPresets = st.studio_presets.slice();
    renderStudioPresets();
  }
  if (st.proxy && JSON.stringify(st.proxy) !== JSON.stringify(S.proxy || null)){
    S.proxy = st.proxy;
    renderProxyChips();
  }
  renderProgress(st);
  renderQueue(st);
  appendLogs(st.logs, st.log_seq);
  updateGoState();
  if (st.phase === 'error' && st.error && S.lastErr !== st.error){ S.lastErr = st.error; toast(st.error, 'err'); }
  if (st.phase !== 'error') S.lastErr = '';
}
function renderColabChip(c){
  const dot = $('#colabDot'), t = $('#colabText');
  const rel = $('#releaseBtn');
  if (!c || !c.authed){ dot.className='dot warn'; t.textContent='连接 Colab'; rel.classList.add('hide'); return; }
  if (!c.ok){ dot.className='dot bad'; t.textContent='Colab 查询异常'; rel.classList.remove('hide'); return; }
  const bal = c.balance == null ? '?' : Number(c.balance).toFixed(1);
  dot.className = 'dot ' + (c.any_running ? 'busy' : 'ok');
  t.textContent = c.any_running ? `${c.sessions.length} 台运行 · ${Number(c.rate_per_hour||0).toFixed(2)} CU/h · 余 ${bal}` : `余额 ${bal} CU`;
  rel.classList.toggle('hide', !c.any_running);
  rel.disabled = S.status && S.status.phase === 'stopping';
}
function renderProgress(st){
  const job = st.current; const box = $('#progress');
  if (!job){ box.classList.add('hide'); return; }
  box.classList.remove('hide');
  const stageName = (STAGES.find(s => s[0] === job.stage) || [0, job.stage])[1];
  const pr = job.progress;
  $('#pStage').textContent = stageName + (pr && pr.label ? ' · ' + pr.label : '') + (pr && pr.detail ? ' ' + pr.detail : '');
  $('#pMeta').textContent = `${job.mode==='video' ? 'MiniMax-H3 ' + (job.workflow||'') : job.model} · ${job.width}×${job.height} · seed ${job.seed}`;
  $('#pTime').textContent = job.started_at ? '已用 ' + dur(now() - job.started_at) + (pr && pr.rate ? ' · ' + pr.rate : '') : '';
  const bar = $('#pBar');
  if (pr && pr.pct != null){ bar.classList.remove('indet'); $('i', bar).style.width = pr.pct + '%'; }
  else { bar.classList.add('indet'); }
  const idx = STAGES.findIndex(s => s[0] === job.stage);
  $('#pSteps').innerHTML = STAGES.slice(1, 5).map((s, i) => `<span class="${i+1 < idx ? 'done' : i+1 === idx ? 'cur' : ''}">${i+1 < idx ? I('check') : '•'} ${s[1]}</span>`).join('');
  if (!S.viewing || S.followLatest) $('#emptyStage').classList.add('hide');
}
function renderQueue(st){
  const q = st.queue || [];
  const failed = (st.history || []).filter(j => j.retryable);
  $('#queueBox').classList.toggle('hide', !q.length && !failed.length);
  $('#queueClear').classList.toggle('hide', !q.length);
  $('#queueCount').textContent = q.length ? ` · ${q.length} 个等待中` : '';
  $('#queueList').innerHTML = q.map((j, i) => `<div class="qrow"><span class="n">${i+1}</span>${I(j.mode==='video'?'video':'image')}
    <span class="p">${esc(j.prompt)}</span><span class="dim">${j.width}×${j.height} · seed ${j.seed}</span>
    <button class="iconbtn" data-unq="${j.id}" title="移出队列">${I('x')}</button></div>`).join('')
    + failed.map(j => `<div class="qrow"><span class="p">${esc(j.prompt)}</span><span class="dim">${esc(j.error)}</span><button class="btn sm" data-retry="${esc(j.id)}">重试</button></div>`).join('');
}

/* ── logs ── */
function appendLogs(lines, seq){
  if (!lines || !lines.length){ S.logSeq = seq || S.logSeq; return; }
  S.logSeq = seq;
  const pre = $('#logPre');
  const frag = document.createDocumentFragment();
  for (const ln of lines){
    const span = document.createElement('span');
    if (/失败|ERR|Error|错误|异常/.test(ln)) span.className = 'e'; else if (/完成|已保存|成功|就绪/.test(ln)) span.className = 's';
    span.textContent = ln + '\n'; frag.appendChild(span);
  }
  pre.appendChild(frag);
  while (pre.childNodes.length > 1500) pre.removeChild(pre.firstChild);
  S.logCount = pre.childNodes.length;
  $('#logLines').textContent = S.logCount + ' 行';
  if ($('#logDock').classList.contains('hide')){ S.unseenLogs += lines.length; $('#logBadge').textContent = S.unseenLogs > 99 ? '99+' : S.unseenLogs; $('#logBadge').classList.remove('hide'); }
  else if ($('#logFollow').checked) pre.scrollTop = pre.scrollHeight;
}
function toggleLogs(force){
  const dock = $('#logDock'); const show = force ?? dock.classList.contains('hide');
  dock.classList.toggle('hide', !show); $('#logBtn').classList.toggle('on', show);
  if (show){ S.unseenLogs = 0; $('#logBadge').classList.add('hide'); const pre = $('#logPre'); pre.scrollTop = pre.scrollHeight; refresh(); }
}

/* ── gallery ── */
function setGalleryOpen(open){
  S.galleryOpen = !!open;
  $('#galleryCard').classList.toggle('open', S.galleryOpen);
  $('#galleryBody').classList.toggle('hide', !S.galleryOpen);
  $('#galleryToggleBtn').textContent = S.galleryOpen ? '收起' : '展开';
  renderGallery();
}
async function loadGallery(rev){
  try {
    const r = await api('api/rounds');
    const firstLoad = !S.galleryLoaded;
    S.galleryLoaded = true;
    const prevLatest = S.gallery.length ? S.gallery[0].id : null;
    S.gallery = r.rounds; S.stats = r.stats; S.galleryRev = rev ?? r.rev;
    const latest = S.gallery[0];
    if (!firstLoad && latest && latest.id !== prevLatest && (prevLatest === null || +latest.id > +prevLatest) && S.followLatest){
      S.viewing = latest.id;
      toast(`新作品 #${latest.id} 已生成`, 'ok');
    }
    if (S.viewing && !S.gallery.find(x => x.id === S.viewing)) S.viewing = null;
    for (const id of [...S.selected]) if (!S.gallery.find(x => x.id === id)) S.selected.delete(id);
    renderGallery(); renderStage(); loadTrashCount();
  } catch(e){ toast('作品库加载失败：' + e.message, 'err'); }
}
function filtered(){
  const f = S.filter; const q = f.q.trim().toLowerCase();
  return S.gallery.filter(it => (!f.kind || it.kind === f.kind) && (!f.starred || it.starred)
    && (!q || it.prompt.toLowerCase().includes(q) || String(+it.id) === q.replace(/^#/, '') || (it.model||'').toLowerCase().includes(q)));
}
const mediaUrl = (it) => `api/rounds/${it.id}?v=${it.mtime}`;
const thumbUrl = (it) => it.has_thumb ? `api/rounds/${it.id}/thumb?v=${it.mtime}` : it.kind === 'image' ? mediaUrl(it) : null;
function renderGallery(){
  const st = S.stats || {};
  $('#gCollapsedStat').textContent = st.count ? `共 ${st.count} 个作品 · ${fmtBytes(st.bytes || 0)}` : '暂无作品';
  if (!S.galleryOpen){
    $('#grid').innerHTML = '';
    $('#moreWrap').classList.add('hide');
    return;
  }
  $('#filterChips').innerHTML = [['', '全部', st.count], ['image', '图片', st.images], ['video', '视频', st.videos], ['star', '★ 收藏', st.starred]].map(([k, l, n]) => {
    const on = k === 'star' ? S.filter.starred : (!S.filter.starred && S.filter.kind === k);
    return `<button class="pchip ${on?'on':''}" data-filter="${k}">${l} <span class="dim">${n ?? 0}</span></button>`;
  }).join('');
  const items = filtered();
  const fil = S.filter.kind || S.filter.starred || S.filter.q.trim();
  $('#gStat').textContent = st.count ? (fil ? `筛选出 ${items.length} 个 · ` : '') + `共 ${st.count} 个作品 · 占用 ${fmtBytes(st.bytes || 0)}` : '';
  const grid = $('#grid');
  grid.classList.toggle('selecting', S.selecting);
  if (!items.length){
    grid.innerHTML = `<div class="gempty" style="grid-column:1/-1">${S.gallery.length ? '没有符合条件的作品' : '作品库还是空的，生成的图片和视频会出现在这里'}</div>`;
    $('#moreWrap').classList.add('hide'); return;
  }
  grid.innerHTML = items.slice(0, S.page).map(it => {
    const t = thumbUrl(it);
    const media = t ? `<img loading="lazy" src="${t}" alt="">` : `<video preload="metadata" muted playsinline src="${mediaUrl(it)}#t=0.1"></video>`;
    return `<div class="tile ${S.viewing===it.id?'cur':''} ${S.selected.has(it.id)?'sel':''}" data-id="${it.id}" draggable="true" title="${esc(it.prompt.slice(0,200))}">
      ${media}<div class="ov"></div>
      ${it.kind==='video' ? `<span class="kind">${I('play')}视频</span>` : ''}
      <span class="ck">${I('check')}</span>
      <span class="id">#${+it.id}</span>
      ${it.starred ? `<span class="st">${I('star','star-on')}</span>` : ''}
      <span class="when">${ago(it.created_at)}</span>
      <div class="acts">
        <button data-act="star" title="${it.starred?'取消收藏':'收藏'}" class="${it.starred?'star-on':''}">${I('star')}</button>
        ${it.kind==='image' ? `<button data-act="ref" title="设为参考图">${I('image')}</button>` : ''}
        <button data-act="lb" title="全屏查看">${I('expand')}</button>
        <button data-act="del" class="del" title="删除">${I('trash')}</button>
      </div></div>`;
  }).join('');
  $('#moreWrap').classList.toggle('hide', items.length <= S.page);
  updateSelBar();
}
function updateSelBar(){
  $('#selBar').classList.toggle('hide', !S.selecting);
  $('#selCount').textContent = `已选 ${S.selected.size}`;
  ['#selStar','#selUnstar','#selDel'].forEach(s => $(s).disabled = !S.selected.size);
  const selImgs = [...S.selected].filter(id => { const it = S.gallery.find(x => x.id === id); return it && it.kind === 'image'; });
  const sc = $('#selCompare');
  if (sc) sc.disabled = selImgs.length < 2;
  $('#selBtn').classList.toggle('hide', S.selecting);
}
function onTileClick(e){
  const tile = e.target.closest('.tile'); if (!tile) return;
  const id = tile.dataset.id; const act = e.target.closest('[data-act]');
  if (act){
    e.stopPropagation();
    const it = S.gallery.find(x => x.id === id);
    if (act.dataset.act === 'star') return setStar([id], !it.starred);
    if (act.dataset.act === 'del') return deleteRounds([id]);
    if (act.dataset.act === 'ref') return useAsRef(id);
    if (act.dataset.act === 'lb') return openLightbox(id);
  }
  if (S.selecting){
    const items = filtered().map(x => x.id);
    if (e.shiftKey && S.lastClicked){
      const a = items.indexOf(S.lastClicked), b = items.indexOf(id);
      if (a >= 0 && b >= 0) items.slice(Math.min(a,b), Math.max(a,b)+1).forEach(x => S.selected.add(x));
    } else if (S.selected.has(id)) S.selected.delete(id); else S.selected.add(id);
    S.lastClicked = id; renderGallery(); return;
  }
  view(id, false);
}
function view(id, follow){
  S.viewing = id; if (follow !== undefined) S.followLatest = follow;
  else S.followLatest = S.gallery.length && S.gallery[0].id === id;
  renderStage();
  $$('#grid .tile').forEach(t => t.classList.toggle('cur', t.dataset.id === id));
}
function current(){ return S.gallery.find(x => x.id === S.viewing); }
function renderStage(){
  const it = current();
  const img = $('#vImg'), vid = $('#vVid');
  $('#emptyStage').classList.toggle('hide', !!it || !!(S.status && S.status.current));
  $('#viewInfo').classList.toggle('hide', !it);
  ['#vPrev','#vNext','#vExpand'].forEach(s => $(s).classList.toggle('hide', !it));
  if (!it){
    img.classList.add('hide'); img.removeAttribute('src'); img.dataset.src = '';
    vid.pause(); vid.classList.add('hide'); vid.removeAttribute('src'); vid.dataset.src = '';
    const hasHistory = S.gallery.length > 0;
    $('#emptyTitle').textContent = hasHistory ? '历史作品已隐藏' : '开始你的第一张作品';
    $('#emptyDesc').innerHTML = hasHistory
      ? '进入页面默认不展示上次生成的作品。<br>新作品生成完成后会自动显示，也可点击下方按钮展开作品库。'
      : '在左侧写下想法，选好模型，点「开始生成」。<br>作品会保存在下方作品库，可以随时收藏、复用参数或删除。';
    $('#emptyOpenGallery').classList.toggle('hide', !hasHistory);
    return;
  }
  const url = mediaUrl(it);
  if (it.kind === 'video'){
    img.classList.add('hide'); vid.classList.remove('hide');
    if (vid.dataset.src !== url){ vid.src = url; vid.dataset.src = url; }
  } else {
    vid.pause(); vid.classList.add('hide'); img.classList.remove('hide');
    if (img.dataset.src !== url){ img.src = url; img.dataset.src = url; }
  }
  $('#vTitle').textContent = `#${+it.id}`;
  $('#vSub').textContent = `${it.kind==='video'?'视频':'图片'} · ${fmtTime(it.created_at)} · ${fmtBytes(it.bytes)}`;
  const star = $('#aStar'); star.classList.toggle('star-on', it.starred); $('span', star).textContent = it.starred ? '已收藏' : '收藏';
  $('#aRef').classList.toggle('hide', it.kind !== 'image');
  $('#aLast').classList.toggle('hide', !(it.kind === 'image' && S.mode === 'video' && S.workflow === 'fl2va'));
  $('#aToVideo').classList.toggle('hide', it.kind !== 'image');
  $('#aEditVideo').classList.toggle('hide', it.kind !== 'video');
  $('#aContinueVideo').classList.toggle('hide', it.kind !== 'video');
  $('#aMediaTool').textContent = it.kind === 'video' ? '取帧与裁段' : '局部改图';
  $('#aMediaTool').href = `./?tool=${it.kind === 'video' ? 'clip' : 'mask'}&round=${it.id}`;
  $('#aCrop').classList.toggle('hide', it.kind !== 'image');
  $('#aCrop').href = `./?tool=crop&round=${it.id}`;
  $('#aReuse').classList.toggle('hide', ['import', 'frame', 'clip', 'crop', 'masked_edit'].includes(it.media_operation) || it.workflow === 'stitch');
  const aCmp = $('#aCompare');
  if (aCmp) aCmp.classList.toggle('hide', it.kind !== 'image' || S.gallery.filter(x => x.kind === 'image').length < 2);
  $('#aDown').href = `api/rounds/${it.id}?download=1`;
  $('span', $('#vPrompt')).textContent = it.prompt || '（没有记录提示词）';
  const tags = [];
  const add = (k, v) => { if (v !== undefined && v !== null && v !== '') tags.push(`<span class="tag">${k} <b>${esc(v)}</b></span>`); };
  add('引擎', it.engine === 'comfyui' ? 'ComfyUI' : '');
  if (it.engine === 'comfyui' && it.comfy){
    add('模板', it.comfy.template);
    add('扩散模型', it.comfy.diffusion && it.comfy.diffusion.basename);
    add('采样', `${it.comfy.sampler || 'euler'} / ${it.comfy.scheduler || 'simple'}`);
  } else {
    add('模型', it.model);
  }
  add('工作流', it.workflow); add('尺寸', it.width && `${it.width}×${it.height}`); add('步数', it.steps); add('CFG', it.cfg);
  add('种子', it.seed); add('帧数', it.num_frames); add('GPU', it.gpu);
  if (it.media_duration_s != null) add('片长', Number(it.media_duration_s.toFixed(2)) + ' 秒');
  if (it.boot_s != null && it.infer_s != null){
    add('冷启 / 推理', `${dur(it.boot_s)} / ${dur(it.infer_s)}`);
  } else {
    if (it.workflow !== 'stitch' && it.duration_s != null) add('生成用时', dur(it.duration_s));
  }
  if (it.workflow_run_id) add('流水线', it.workflow_run_id);
  if (it.chain_from) add('接着改自', '#' + +it.chain_from);
  if (it.has_image) add('参考图', it.ref_count > 1 ? `${it.ref_count} 张` : '是');
  (it.loras || []).forEach(l => add('LoRA', `${l.repo_id}${l.weight_name ? ' / ' + l.weight_name.split('/').pop() : ''} ×${l.scale}`));
  $('#vTags').innerHTML = tags.join('');
}
function step(d){
  const items = filtered(); if (!items.length) return;
  let i = items.findIndex(x => x.id === S.viewing);
  i = i < 0 ? 0 : (i + d + items.length) % items.length;
  view(items[i].id);
  return items[i].id;
}

/* ── gallery actions ── */
async function setStar(ids, starred){
  try { await post('api/rounds/star', {ids, starred}); await loadGallery(); } catch(e){ toast(e.message, 'err'); }
}
async function deleteRounds(ids, {skipConfirm=false}={}){
  if (!ids.length) return false;
  const starred = ids.filter(id => (S.gallery.find(x => x.id === id) || {}).starred).length;
  if (!skipConfirm){
    const ok = await confirmBox({title: ids.length > 1 ? `删除 ${ids.length} 个作品？` : `删除作品 #${+ids[0]}？`,
      body: `作品会移入回收站，${S.cfg.trash_retention_days} 天内可以恢复。` + (starred ? `<br><b style="color:#facc15">其中 ${starred} 个是收藏的作品。</b>` : ''),
      ok: '删除', danger: true});
    if (!ok) return false;
  }
  try {
    const items = filtered(); const idx = items.findIndex(x => x.id === S.viewing);
    const r = await post('api/rounds/delete', {ids});
    if (ids.includes(S.viewing)){
      const rest = items.filter(x => !ids.includes(x.id));
      S.viewing = rest.length ? rest[Math.min(Math.max(idx, 0), rest.length - 1)].id : null;
    }
    ids.forEach(id => S.selected.delete(id));
    toast(`已删除 ${r.deleted.length} 个作品`, 'ok', {label:'撤销', fn: () => restoreRounds(r.deleted)});
    await loadGallery();
    return true;
  } catch(e){ toast(e.message, 'err'); return false; }
}
async function restoreRounds(ids){
  try { const r = await post('api/trash/restore', {ids}); toast(`已恢复 ${r.restored.length} 个作品`, 'ok'); await loadGallery(); } catch(e){ toast(e.message, 'err'); }
}
function reuse(it){
  const m = it.meta || it;
  setMode(it.kind === 'video' ? 'video' : 'image');
  if (m.prompt) $('#prompt').value = m.prompt;
  if (m.negative !== undefined) $('#negative').value = m.negative;
  if (it.kind === 'image'){
    if (m.engine === 'comfyui' && m.comfy){
      setEngine('comfyui');
      const cm = m.comfy;
      if (cm.template) $('#comfyTemplate').value = cm.template;
      if (cm.diffusion) $('#comfyDiff').value = cm.diffusion.raw || cm.diffusion.url || '';
      if (cm.text_encoder) $('#comfyTe').value = cm.text_encoder.raw || cm.text_encoder.url || '';
      if (cm.vae) $('#comfyVae').value = cm.vae.raw || cm.vae.url || '';
      if (cm.sampler) $('#comfySampler').value = cm.sampler;
      if (cm.scheduler) $('#comfyScheduler').value = cm.scheduler;
      updateComfyLinkPreviews();
    } else if (m.model){
      setEngine('diffusers');
      $('#imageModel').value = m.model;
    }
  }
  if (it.kind === 'video'){
    $('#videoTask').value = m.video_task || '';
    $('#videoUseImages').checked = !!m.has_image;
    if (m.workflow){ S.workflow = m.workflow; renderWorkflowChips(); }
    if (m.num_frames){ S.frames = m.num_frames; renderFrameChips(); }
    if ($('#offloadMode')) $('#offloadMode').value = m.offload_mode || (m.auto_offload === false ? 'none' : 'auto');
  }
  if (m.width) setNum('width', m.width); if (m.height) setNum('height', m.height);
  if (m.steps) setNum('steps', m.steps); if (m.cfg) setNum('cfg', m.cfg);
  if (m.seed !== undefined) $('#seed').value = m.seed;
  if (m.gpu){
    const gid = String(m.gpu).toUpperCase();
    S.grabPool = [gid];
    if (ownedSessions().some(s => String(s.gpu).toUpperCase() === gid)) S.gpu = gid;
    renderGpuChips();
  }
  if (Array.isArray(m.loras)) renderLoraRows(m.loras);
  updateCount(); updateModeUI(); saveForm();
  toast(`已把 #${+it.id} 的参数填回左侧（含种子 ${m.seed ?? '-'}）`, 'ok');
}
async function toVideo(id){
  await useAsRef(id, 'first', false);
  setMode('video'); S.workflow = 'fl2va'; renderWorkflowChips(); updateModeUI(); saveSoon();
  window.scrollTo({top:0, behavior:'smooth'});
}

/* ── cleanup ── */
function openCleanup(){
  const m = modal(`
    <div class="mh">${I('broom','lg')}<h3>清理旧作品</h3><div class="grow"></div><button class="iconbtn" data-close>${I('x')}</button></div>
    <div class="mb">
      <label class="opt"><input type="checkbox" id="cDaysOn" checked><div>删除 <input type="number" class="inl" id="cDays" min="0" step="1" value="30"> 天之前生成的作品</div></label>
      <label class="opt"><input type="checkbox" id="cKeepOn"><div>无论时间，只保留最近的 <input type="number" class="inl" id="cKeep" min="0" step="1" value="50"> 个作品</div></label>
      <div class="g2" style="margin-top:4px">
        <div><label class="f">范围</label><select id="cKind"><option value="">图片和视频</option><option value="image">只清理图片</option><option value="video">只清理视频</option></select></div>
        <div><label class="f">其他</label>
          <label class="switch" style="margin:4px 0"><input type="checkbox" id="cStar"><span class="tg"></span>也删除收藏的作品</label>
          <label class="switch" style="margin:4px 0"><input type="checkbox" id="cPerm"><span class="tg"></span>直接永久删除</label></div>
      </div>
      <div class="preview-box" id="cPrev"><span class="sp"></span> 计算中…</div>
      <div class="warnbox hide" id="cWarn">${I('alert')}<div>永久删除不经过回收站，无法恢复。</div></div>
    </div>
    <div class="mf"><button class="btn" data-close>取消</button><button class="btn solid-danger" id="cGo" disabled>${I('trash')}删除</button></div>`);
  const el = m.el; let plan = null; let t; let request = 0; let busy = false;
  const body = () => ({
    older_than_days: $('#cDaysOn', el).checked ? +$('#cDays', el).value : null,
    keep_latest: $('#cKeepOn', el).checked ? +$('#cKeep', el).value : null,
    kind: $('#cKind', el).value, include_starred: $('#cStar', el).checked, permanent: $('#cPerm', el).checked,
  });
  const preview = async (seq, b) => {
    if (seq !== request || !el.isConnected) return;
    $('#cWarn', el).classList.toggle('hide', !b.permanent);
    if (b.older_than_days === null && b.keep_latest === null){ $('#cPrev', el).textContent = '请至少勾选一个条件'; $('#cGo', el).disabled = true; return; }
    try {
      const result = await post('api/rounds/cleanup', {...b, dry_run:true});
      if (seq !== request || !el.isConnected) return;
      plan = {body:b, result};
      const thumbs = result.matched.slice(0, 14).map(id => { const it = S.gallery.find(x => x.id === id); const u = it && thumbUrl(it);
        return u ? `<img src="${u}" title="#${+id}">` : `<div class="mv">${I('play')}</div>`; }).join('');
      $('#cPrev', el).innerHTML = result.count
        ? `将${b.permanent ? '<b style="color:#fca5a5">永久</b>' : '移入回收站并'}删除 <b>${result.count}</b> 个作品，释放 <b>${fmtBytes(result.bytes)}</b>${b.include_starred ? '' : '（收藏的作品不受影响）'}<div class="mini">${thumbs}${result.count > 14 ? `<div class="mv">+${result.count-14}</div>` : ''}</div>`
        : '没有符合条件的作品 🎉';
      $('#cGo', el).disabled = busy || !result.count;
      $('#cGo', el).innerHTML = I('trash') + (result.count ? `删除 ${result.count} 个` : '删除');
    } catch(e){ if (seq !== request || !el.isConnected) return; $('#cPrev', el).textContent = e.message; $('#cGo', el).disabled = true; }
  };
  const schedulePreview = (delay = 250) => {
    const seq = ++request; const b = body();
    clearTimeout(t);
    plan = null;
    $('#cGo', el).disabled = true;
    $('#cGo', el).innerHTML = I('trash') + '删除';
    $('#cPrev', el).textContent = '计算中…';
    t = setTimeout(() => preview(seq, b), delay);
  };
  $$('input,select', el).forEach(i => i.addEventListener(i.type === 'number' ? 'input' : 'change', () => schedulePreview()));
  $('#cGo', el).onclick = async () => {
    if (busy || !plan?.result.count) return;
    const {body:b, result} = plan;
    if (JSON.stringify(b) !== JSON.stringify(body())) { schedulePreview(0); return; }
    const expected_ids = [...result.matched];
    busy = true;
    $('#cGo', el).disabled = true;
    try {
      if (b.permanent && !(await confirmBox({title:`永久删除 ${expected_ids.length} 个作品？`, body:'这些文件会被立即删除，无法恢复。', ok:'永久删除', danger:true}))) return;
      const r = await post('api/rounds/cleanup', {...b, expected_ids, dry_run:false});
      m.close();
      toast(`已清理 ${(r.deleted||[]).length} 个作品，释放 ${fmtBytes(r.bytes)}`, 'ok', b.permanent ? null : {label:'撤销', fn: () => restoreRounds(r.deleted)});
      await loadGallery();
    } catch(e){ toast(e.message, 'err'); schedulePreview(0); }
    finally { busy = false; $('#cGo', el).disabled = !plan?.result.count; }
  };
  schedulePreview(0);
}

/* ── trash ── */
async function loadTrashCount(){
  try { const r = await api('api/trash'); const b = $('#trashBadge'); b.textContent = r.count; b.classList.toggle('hide', !r.count); return r; } catch { return null; }
}
async function openTrash(){
  const m = modal(`
    <div class="mh">${I('trash','lg')}<h3>回收站</h3><span class="dim" id="tSum"></span><div class="grow"></div><button class="iconbtn" data-close>${I('x')}</button></div>
    <div class="mb"><div class="row" style="margin-bottom:10px">
        <button class="btn sm ghost" id="tAll">全选</button><div class="grow"></div>
        <button class="btn sm" id="tRestore" disabled>${I('undo')}恢复所选</button>
        <button class="btn sm danger" id="tPurge" disabled>${I('trash')}彻底删除所选</button>
        <button class="btn sm solid-danger" id="tEmpty">清空回收站</button></div>
      <div class="grid" id="tGrid" style="grid-template-columns:repeat(auto-fill,minmax(120px,1fr))"></div></div>`, {wide:true});
  const el = m.el; const sel = new Set(); let data = null;
  const render = () => {
    $('#tSum', el).textContent = data.count ? `· ${data.count} 个 · ${fmtBytes(data.bytes)} · 删除 ${data.retention_days} 天后自动清除` : '';
    $('#tGrid', el).classList.add('selecting');
    $('#tGrid', el).innerHTML = data.count ? data.items.map(it => {
      const u = it.has_thumb ? `api/trash/${it.id}/thumb` : it.kind === 'image' ? `api/trash/${it.id}` : null;
      const left = Math.max(0, Math.ceil((it.purge_at - now()) / 86400));
      return `<div class="tile ${sel.has(it.id)?'sel':''}" data-id="${it.id}">${u ? `<img loading="lazy" src="${u}">` : `<video preload="metadata" muted src="api/trash/${it.id}#t=0.1"></video>`}
        <div class="ov" style="opacity:1"></div><span class="ck">${I('check')}</span><span class="id">#${+it.id}</span>
        <span class="when" style="opacity:1">${left} 天后清除</span></div>`;
    }).join('') : `<div class="gempty" style="grid-column:1/-1">回收站是空的</div>`;
    $('#tRestore', el).disabled = $('#tPurge', el).disabled = !sel.size;
    $('#tEmpty', el).disabled = !data.count;
    $('#tAll', el).textContent = sel.size && sel.size === data.count ? '取消全选' : '全选';
  };
  const reload = async () => { data = await api('api/trash'); [...sel].forEach(id => { if (!data.items.find(x => x.id === id)) sel.delete(id); }); render(); loadTrashCount(); };
  $('#tGrid', el).onclick = e => { const t = e.target.closest('.tile'); if (!t) return; const id = t.dataset.id; sel.has(id) ? sel.delete(id) : sel.add(id); render(); };
  $('#tAll', el).onclick = () => { if (sel.size === data.count) sel.clear(); else data.items.forEach(x => sel.add(x.id)); render(); };
  $('#tRestore', el).onclick = async () => { await restoreRounds([...sel]); sel.clear(); reload(); };
  $('#tPurge', el).onclick = async () => {
    if (!(await confirmBox({title:`彻底删除 ${sel.size} 个作品？`, body:'删除后无法恢复。', ok:'彻底删除', danger:true}))) return;
    const r = await post('api/trash/purge', {ids:[...sel]}); toast(`已彻底删除 ${r.purged.length} 个，释放 ${fmtBytes(r.bytes)}`, 'ok'); sel.clear(); reload();
  };
  $('#tEmpty', el).onclick = async () => {
    if (!(await confirmBox({title:'清空回收站？', body:`将彻底删除回收站里全部 ${data.count} 个作品，无法恢复。`, ok:'清空', danger:true}))) return;
    const r = await post('api/trash/purge', {all:true}); toast(`回收站已清空，释放 ${fmtBytes(r.bytes)}`, 'ok'); sel.clear(); reload();
  };
  reload();
}

/* ── lightbox ── */
let LB = null;
function openLightbox(id){
  if (LB) LB.remove();
  LB = document.createElement('div'); LB.className = 'lb';
  LB.innerHTML = `<div class="lb-top"><b id="lbT"></b><span class="dim" id="lbS"></span><div class="grow"></div>
      <button class="btn sm" id="lbStar">${I('star')}收藏</button><button class="btn sm" id="lbRef">${I('image')}设为参考</button>
      <a class="btn sm" id="lbDown">${I('download')}下载</a><button class="btn sm danger" id="lbDel">${I('trash')}删除</button>
      <button class="iconbtn" id="lbX" title="关闭 (Esc)">${I('x')}</button></div>
    <div class="lb-body" id="lbB"></div><div class="lb-bottom" id="lbP"></div>
    <button class="vnav l" id="lbL">${I('left','lg')}</button><button class="vnav r" id="lbR">${I('right','lg')}</button>`;
  document.body.appendChild(LB);
  $('#lbX', LB).onclick = closeLightbox;
  $('#lbL', LB).onclick = () => lbShow(step(-1));
  $('#lbR', LB).onclick = () => lbShow(step(1));
  $('#lbStar', LB).onclick = async () => { const it = current(); await setStar([it.id], !it.starred); lbShow(it.id); };
  $('#lbRef', LB).onclick = () => useAsRef(S.viewing);
  $('#lbDel', LB).onclick = async () => { if (await deleteRounds([S.viewing])) { S.viewing ? lbShow(S.viewing) : closeLightbox(); } };
  $('#lbB', LB).addEventListener('click', e => { if (e.target.id === 'lbB') closeLightbox(); });
  view(id); lbShow(id);
}
function lbShow(id){
  const it = S.gallery.find(x => x.id === id); if (!it || !LB) return;
  $('#lbT', LB).textContent = '#' + +it.id; $('#lbS', LB).textContent = ` · ${it.width ? it.width+'×'+it.height+' · ' : ''}${fmtTime(it.created_at)}`;
  const url = mediaUrl(it);
  $('#lbB', LB).innerHTML = it.kind === 'video' ? `<video src="${url}" controls autoplay loop playsinline></video>` : `<img src="${url}" alt="">`;
  $('#lbP', LB).textContent = it.prompt;
  $('#lbDown', LB).href = `api/rounds/${it.id}?download=1`;
  const s = $('#lbStar', LB); s.classList.toggle('star-on', it.starred); s.lastChild.textContent = it.starred ? '已收藏' : '收藏';
  $('#lbRef', LB).classList.toggle('hide', it.kind !== 'image');
}
function closeLightbox(){ if (LB){ LB.remove(); LB = null; } }

/* ── SwarmUI / InvokeAI A/B Split Compare ── */
function openCompareModal(idA, idB){
  const imgs = S.gallery.filter(x => x.kind === 'image');
  if (imgs.length < 2){ toast('作品库里至少需要 2 张图片才能对比', 'err'); return; }
  let a = imgs.find(x => x.id === idA) || imgs[0];
  let b = imgs.find(x => x.id === idB && x.id !== a.id) || imgs.find(x => x.id !== a.id) || imgs[0];
  const opts = (sel) => imgs.map(it => `<option value="${it.id}" ${it.id===sel?'selected':''}>#${+it.id} · ${esc((it.prompt||'').slice(0,32))}</option>`).join('');
  const m = modal(`
    <div class="mh">${I('compare','lg')}<h3>A / B 细节对比</h3><div class="grow"></div><button class="iconbtn" data-close>${I('x')}</button></div>
    <div class="mb">
      <div class="g2" style="margin-bottom:10px">
        <div><label class="f" style="margin-top:0">左侧图 A</label><select id="abSelA">${opts(a.id)}</select></div>
        <div><label class="f" style="margin-top:0">右侧图 B</label><select id="abSelB">${opts(b.id)}</select></div>
      </div>
      <div class="ab-wrap" id="abWrap">
        <img id="abImgB" src="${mediaUrl(b)}" alt="">
        <div class="ab-top" id="abTop" style="clip-path:inset(0 50% 0 0)"><img id="abImgA" src="${mediaUrl(a)}" alt=""></div>
        <div class="ab-line" id="abLine" style="left:50%"></div>
        <div class="ab-handle" id="abHandle" style="left:50%">⇄</div>
        <span class="ab-tag l" id="abTagA">A #${+a.id}</span>
        <span class="ab-tag r" id="abTagB">B #${+b.id}</span>
        <input type="range" class="ab-range" id="abRange" min="0" max="100" value="50">
      </div>
      <div class="g2" style="margin-top:10px;font-size:12px;color:var(--muted)" id="abMeta"></div>
    </div>`, {wide:true});
  const el = m.el;
  const sync = () => {
    const itA = imgs.find(x => x.id === $('#abSelA', el).value) || a;
    const itB = imgs.find(x => x.id === $('#abSelB', el).value) || b;
    $('#abImgA', el).src = mediaUrl(itA); $('#abImgB', el).src = mediaUrl(itB);
    $('#abTagA', el).textContent = `A #${+itA.id}`; $('#abTagB', el).textContent = `B #${+itB.id}`;
    $('#abMeta', el).innerHTML =
      `<div><b>A #${+itA.id}</b> · ${esc(itA.model||'')} · ${itA.width||'?'}×${itA.height||'?'} · steps ${itA.steps||'?'} · seed ${itA.seed??'-'}</div>` +
      `<div><b>B #${+itB.id}</b> · ${esc(itB.model||'')} · ${itB.width||'?'}×${itB.height||'?'} · steps ${itB.steps||'?'} · seed ${itB.seed??'-'}</div>`;
  };
  const setPos = (v) => {
    const pct = Math.max(0, Math.min(100, +v));
    $('#abTop', el).style.clipPath = `inset(0 ${100 - pct}% 0 0)`;
    $('#abLine', el).style.left = pct + '%';
    $('#abHandle', el).style.left = pct + '%';
  };
  $('#abRange', el).addEventListener('input', e => setPos(e.target.value));
  $('#abSelA', el).addEventListener('change', sync);
  $('#abSelB', el).addEventListener('change', sync);
  sync();
}

/* ── Tab 3: Composable Long-Video Workflow Studio ── */
const WF_STATUS_ZH = {
  draft:'草稿', pending:'待执行', running:'运行中', paused:'等待审核', done:'已完成', error:'失败', canceled:'已终止', skipped:'已跳过'
};
let wfSaveTimer = null;

async function loadWorkflowData({keepRun=true, autoCreate=true}={}){
  try {
    const data = await api('api/workflows');
    S.wfData = data;
    renderWorkflowSidebar();
    renderWorkflowAddChips();
    const ff = $('#wfFfmpegTag');
    if (ff){
      ff.innerHTML = data.ffmpeg_available ? 'FFmpeg <b style="color:var(--ok)">就绪</b>' : 'FFmpeg <b style="color:var(--warn)">未安装</b>';
    }
    if (keepRun && S.wfRun){
      const fresh = await api('api/workflows/runs/' + encodeURIComponent(S.wfRun.id)).catch(() => null);
      if (fresh && fresh.run){ S.wfRun = fresh.run; renderWorkflowCanvas(); return; }
    }
    if (data.runs && data.runs.length){
      await selectWorkflowRun(data.runs[0].id);
    } else if (autoCreate){
      await createRunFromTemplate('builtin:agent-long-video');
    } else {
      S.wfRun = null;
      renderWorkflowSidebar();
      renderWorkflowCanvas();
    }
  } catch(e){ toast('加载工作流失败：' + e.message, 'err'); }
}
async function pollActiveWorkflowRun(){
  if (!S.wfRun) return;
  try {
    const r = await api('api/workflows/runs/' + encodeURIComponent(S.wfRun.id));
    if (r && r.run){
      const prevStatus = S.wfRun.status;
      S.wfRun = r.run;
      renderWorkflowCanvas({preserveInputs: true});
      if (prevStatus === 'running' && r.run.status !== 'running'){
        const d = await api('api/workflows');
        S.wfData = d;
        renderWorkflowSidebar();
        if (r.run.status === 'done') toast('工作流执行完成！成片已存入作品库', 'ok');
        else if (r.run.status === 'paused') toast(r.run.pause_reason || '工作流已暂停，请审核后继续', '');
        else if (r.run.status === 'error') toast(r.run.error || '工作流执行失败', 'err');
      }
    }
  } catch {}
}
async function selectWorkflowRun(runId){
  try {
    const r = await api('api/workflows/runs/' + encodeURIComponent(runId));
    S.wfRun = r.run;
    renderWorkflowSidebar();
    renderWorkflowCanvas();
  } catch(e){ toast(e.message, 'err'); }
}
async function createRunFromTemplate(wfId){
  try {
    const r = await post('api/workflows/runs', {workflow_id: wfId});
    S.wfRun = r.run;
    S.wfData = await api('api/workflows');
    renderWorkflowSidebar();
    renderWorkflowCanvas();
    toast('已创建工作流实例：' + r.run.workflow.name, 'ok');
  } catch(e){ toast(e.message, 'err'); }
}
async function createBlankWorkflowRun(){
  try {
    const r = await post('api/workflows/runs', {
      topic: '',
      workflow: {
        name: '我的自定义长视频流水线',
        description: '自由组合 AI 策划、网页找图、生图、H3 视频与 FFmpeg 剪辑',
        steps: [
          {id:'script', type:'llm_script', name:'1. AI 分镜脚本', enabled:true, pause_after:true, config:{scene_count:3, output_format:'storyboard'}},
          {id:'keyframes', type:'image_gen', name:'2. 关键帧生图', enabled:true, pause_after:true, config:{scenes_from:'script', ref_sources:[]}},
        ],
      },
    });
    S.wfRun = r.run;
    S.wfData = await api('api/workflows');
    renderWorkflowSidebar();
    renderWorkflowCanvas();
    toast('已创建空白工作流，可自由添加或删除步骤', 'ok');
  } catch(e){ toast(e.message, 'err'); }
}
function renderWorkflowSidebar(){
  const d = S.wfData; if (!d) return;
  const allTpls = [...(d.builtin || []), ...(d.custom || [])];
  $('#wfTemplateList').innerHTML = allTpls.map(t => `
    <div class="wf-item" data-wftpl="${esc(t.id)}">
      <div class="wt">
        <span class="wt-name" title="${esc(t.name)}">${esc(t.name)}</span>
        ${t.builtin ? '<span class="fmt-pill" style="flex:none">内置</span>' : `<button type="button" class="wf-x" data-del-wftpl="${esc(t.id)}" title="删除模板">×</button>`}
      </div>
      <div class="ws">${esc(t.description || '')}</div>
      <div class="dim" style="font-size:11px">${(t.steps||[]).length} 个步骤 · 点击新建实例</div>
    </div>`).join('');
  const runs = d.runs || [];
  $('#wfRunList').innerHTML = runs.length ? runs.map(r => `
    <div class="wf-item ${S.wfRun && S.wfRun.id === r.id ? 'on' : ''}" data-wfrun="${esc(r.id)}">
      <div class="wt">
        <span class="wt-name" title="${esc(r.workflow_name || r.id)}">${esc(r.workflow_name || r.id)}</span>
        <span class="wf-st ${esc(r.status)}">${esc(WF_STATUS_ZH[r.status] || r.status)}</span>
        <button type="button" class="wf-x" data-del-wfrun="${esc(r.id)}" title="删除此运行实例">×</button>
      </div>
      <div class="ws">${esc(r.topic || '（未填主题）')}</div>
      <div class="dim" style="font-size:11px">${r.done_steps}/${r.total_steps} 步${r.final_round_id ? ' · 成片 #' + +r.final_round_id : ''} · ${ago(r.updated_at || r.created_at)}</div>
    </div>`).join('') : '<div class="dim" style="font-size:12px;padding:8px">暂无运行记录</div>';
}
function renderWorkflowAddChips(){
  const cat = (S.wfData && S.wfData.step_catalog) || (S.cfg && S.cfg.workflow_step_catalog) || [];
  $('#wfAddChips').innerHTML = cat.map(s =>
    `<button type="button" class="pchip" data-wfadd="${esc(s.type)}" title="${esc(s.hint)}">${esc(s.icon)} + ${esc(s.label)}</button>`
  ).join('');
}
function saveWorkflowRunSoon(){
  clearTimeout(wfSaveTimer);
  wfSaveTimer = setTimeout(saveWorkflowRunNow, 450);
}
async function saveWorkflowRunNow(){
  if (!S.wfRun || S.wfRun.status === 'running') return;
  try {
    const r = await api('api/workflows/runs/' + encodeURIComponent(S.wfRun.id), {
      method:'PATCH',
      json:{topic: S.wfRun.topic, workflow: S.wfRun.workflow},
    });
    if (r && r.run){ S.wfRun = r.run; }
  } catch(e){ toast('保存配置失败：' + e.message, 'err'); }
}
function stepCatalogFor(type){
  const cat = (S.wfData && S.wfData.step_catalog) || (S.cfg && S.cfg.workflow_step_catalog) || [];
  return cat.find(x => x.type === type) || {label:type, icon:'⚙', hint:''};
}
function upstreamOptions(steps, curIdx, types, selectedVal){
  const prev = steps.slice(0, curIdx).filter(s => !types || types.includes(s.type));
  return '<option value="">（无 / 手动）</option>' + prev.map(s =>
    `<option value="${esc(s.id)}" ${s.id === selectedVal ? 'selected' : ''}>${esc(s.name)} (${esc(s.id)})</option>`
  ).join('');
}
function renderStepConfigHTML(step, idx, steps, run){
  const cfg = step.config || {};
  const dis = run.status === 'running' ? 'disabled' : '';
  const sid = esc(step.id);
  const videoInputs = () => {
    const gallerySelect = (kind, key, label) => {
      const items = S.gallery.filter(r => r.kind === kind);
      const selected = cfg[key] || '';
      return `<label class="f">${label}<select data-wfc="${sid}:${key}" ${dis}>
        <option value="">（无 / 沿用上游）</option>
        ${selected && !items.some(r => r.id === selected) ? `<option selected value="${esc(selected)}">#${esc(selected)} · 已移除</option>` : ''}
        ${items.map(r => `<option value="${esc(r.id)}" ${r.id === selected ? 'selected' : ''}>#${+r.id} · ${esc(r.prompt.slice(0, 40))}</option>`).join('')}</select></label>`;
    };
    if (cfg.workflow === 'fl2va') return gallerySelect('image', 'last_frame_round_id', '尾帧');
    if (cfg.workflow !== 'ref2va') return '';
    const refs = new Set(cfg.extra_ref_sources || []);
    const sources = steps.slice(0, idx).filter(s => ['asset_input','web_asset_fetch','image_gen'].includes(s.type));
    const upstream = steps.slice(0, idx).some(s => ['video_gen', 'video_stitch'].includes(s.type)) || cfg.video_from;
    return `<div class="g2">${upstream ? `<label class="f">上游参考视频<select data-wfc="${sid}:video_from" ${dis}>
      ${upstreamOptions(steps, idx, ['video_gen', 'video_stitch'], cfg.video_from)}</select></label>` : ''}
      ${cfg.video_from ? '' : gallerySelect('video', 'video_round_id', '参考视频')}
      ${cfg.video_round_id || cfg.video_from ? `<label class="f">参考视频用途<select data-wfc="${sid}:video_task" ${dis}>
        ${[['edit','翻修原片'],['continue','续拍下一段'],['motion','白模 + 人设']].map(([k,l]) => `<option value="${k}" ${k === (cfg.video_task || 'edit') ? 'selected' : ''}>${l}</option>`).join('')}</select></label>` : ''}
      </div>${sources.length ? '<label class="f">上游参考图（按选择顺序）</label>' : ''}
      <div class="chips">${sources.map(s => `<label class="pchip ${refs.has(s.id)?'on':''}"><input type="checkbox" data-wfref="${sid}:${esc(s.id)}" ${refs.has(s.id)?'checked':''} ${dis}>${esc(s.name)}</label>`).join('')}</div>`;
  };
  if (step.type === 'asset_input'){
    const files = cfg.asset_files || [];
    const rids = cfg.round_ids || [];
    const thumbs = [
      ...files.map(fn => `<div class="wf-thumb"><img src="api/workflows/runs/${esc(run.id)}/assets/${encodeURIComponent(fn)}" alt=""><button type="button" class="rm" data-wf-rmasset="${esc(fn)}" title="删除" ${dis}>×</button><div class="cap">${esc(fn)}</div></div>`),
      ...rids.map(rid => `<div class="wf-thumb"><img src="api/rounds/${esc(rid)}" alt=""><button type="button" class="rm" data-wf-rmround="${sid}:${esc(rid)}" title="移除" ${dis}>×</button><div class="cap">作品 #${+rid}</div></div>`),
    ].join('');
    return `
      <div class="row wrap" style="gap:8px">
        <button type="button" class="btn sm" data-wf-upload="${sid}" ${dis}>${I('upload')}上传本地图片</button>
        <button type="button" class="btn sm" data-wf-pickgal="${sid}" ${dis}>${I('image')}从作品库挑选</button>
        <span class="dim" style="font-size:11.5px">${esc(cfg.note || '供后续步骤引用的参考图')}</span>
      </div>
      <div class="wf-thumbs">${thumbs || '<span class="dim" style="font-size:12px">暂未绑定图片</span>'}</div>`;
  }
  if (step.type === 'llm_script'){
    return `
      <div class="g2">
        <div><label class="f" style="margin-top:0">分镜数量</label><input type="number" min="1" max="8" data-wfc="${sid}:scene_count:int" value="${cfg.scene_count ?? 3}" ${dis}></div>
        <div><label class="f" style="margin-top:0">输出格式</label><select data-wfc="${sid}:output_format" ${dis}>
          <option value="storyboard" ${cfg.output_format!=='text'?'selected':''}>结构化分镜 JSON</option>
          <option value="text" ${cfg.output_format==='text'?'selected':''}>自由文本</option>
        </select></div>
      </div>
      <label class="f">AI 导演指令</label>
      <textarea rows="3" data-wfc="${sid}:instruction" ${dis}>${esc(cfg.instruction || '')}</textarea>`;
  }
  if (step.type === 'web_asset_fetch'){
    return `
      <div class="g2">
        <div><label class="f" style="margin-top:0">目标网页 URL</label><input type="text" data-wfc="${sid}:url" value="${esc(cfg.url || '')}" placeholder="https://... 留空则自动检索图库" ${dis}></div>
        <div><label class="f" style="margin-top:0">检索关键词</label><input type="text" data-wfc="${sid}:search_query" value="${esc(cfg.search_query || '')}" placeholder="例如：white clay 3d pose model" ${dis}></div>
      </div>
      <div class="g2">
        <div><label class="f" style="margin-top:0">分镜词来源</label><select data-wfc="${sid}:scenes_from" ${dis}>${upstreamOptions(steps, idx, ['llm_script'], cfg.scenes_from || '')}</select></div>
        <div><label class="f" style="margin-top:0">最多下载数</label><input type="number" min="1" max="6" data-wfc="${sid}:max_images:int" value="${cfg.max_images ?? 2}" ${dis}></div>
      </div>
      <div class="row" style="justify-content:space-between;align-items:flex-end;gap:8px">
        <div style="flex:1"><label class="f">选图要求</label>
        <input type="text" data-wfc="${sid}:instruction" value="${esc(cfg.instruction || '')}" ${dis}></div>
        <button type="button" class="btn sm" data-wf-upload="${sid}" title="手动上传参考图" ${dis}>${I('upload')}手动上传白模</button>
      </div>`;
  }
  if (step.type === 'image_gen'){
    const prevImgSteps = steps.slice(0, idx).filter(s => ['asset_input','web_asset_fetch','image_gen'].includes(s.type));
    const chosenRefs = new Set(cfg.ref_sources || []);
    const refChecks = prevImgSteps.length
      ? prevImgSteps.map(s => `<label class="pchip ${chosenRefs.has(s.id)?'on':''}" style="cursor:pointer"><input type="checkbox" style="display:none" data-wfref="${sid}:${esc(s.id)}" ${chosenRefs.has(s.id)?'checked':''} ${dis}>${chosenRefs.has(s.id)?'✓ ':''}${esc(s.name)}</label>`).join('')
      : '<span class="dim" style="font-size:12px">上游暂无图片步骤</span>';
    return `
      <div class="g2">
        <div><label class="f" style="margin-top:0">分镜来源</label><select data-wfc="${sid}:scenes_from" ${dis}>${upstreamOptions(steps, idx, ['llm_script'], cfg.scenes_from || '')}</select></div>
        <div><label class="f" style="margin-top:0">生图模型</label><input type="text" data-wfc="${sid}:model" value="${esc(cfg.model || 'qwen-2.1-bf16')}" ${dis}></div>
      </div>
      <label class="f">引用上游参考图</label>
      <div class="chips">${refChecks}</div>
      <div class="g3" style="margin-top:6px">
        <div><label class="f" style="margin-top:0">宽 × 高</label><div class="row"><input type="number" step="64" min="512" max="1536" data-wfc="${sid}:width:int" value="${cfg.width ?? 1280}" ${dis}><input type="number" step="64" min="512" max="1536" data-wfc="${sid}:height:int" value="${cfg.height ?? 768}" ${dis}></div></div>
        <div><label class="f" style="margin-top:0">步数 / CFG</label><div class="row"><input type="number" min="2" max="60" data-wfc="${sid}:steps:int" value="${cfg.steps ?? 35}" ${dis}><input type="number" step="0.5" min="1" max="12" data-wfc="${sid}:cfg:float" value="${cfg.cfg ?? 5.0}" ${dis}></div></div>
        <div><label class="f" style="margin-top:0">首选 GPU</label><select data-wfc="${sid}:gpu" ${dis}>${(S.cfg.gpus||[]).map(g=>`<option value="${g.id}" ${(cfg.gpu||'A100')===g.id?'selected':''}>${esc(g.label || g.id)}</option>`).join('')}</select></div>
      </div>
      <label class="f">提示词模板</label>
      <input type="text" data-wfc="${sid}:prompt_template" value="${esc(cfg.prompt_template || '{{scene.keyframe_prompt}}')}" ${dis}>`;
  }
  if (step.type === 'h3_prompt'){
    return `
      <div class="g3">
        <div><label class="f" style="margin-top:0">分镜来源</label><select data-wfc="${sid}:scenes_from" ${dis}>${upstreamOptions(steps, idx, ['llm_script'], cfg.scenes_from || '')}</select></div>
        <div><label class="f" style="margin-top:0">关键帧来源</label><select data-wfc="${sid}:keyframe_from" ${dis}>${upstreamOptions(steps, idx, ['image_gen'], cfg.keyframe_from || '')}</select></div>
        <div><label class="f" style="margin-top:0">H3 模式</label><select data-wfc="${sid}:workflow" ${dis}>
          <option value="fl2va" ${cfg.workflow==='fl2va'?'selected':''}>fl2va · 首帧 / 尾帧</option>
          <option value="ref2va" ${cfg.workflow==='ref2va'?'selected':''}>ref2va · 图片 / 视频参考</option>
          <option value="t2va" ${cfg.workflow==='t2va'?'selected':''}>t2va · 文生</option>
        </select></div>
      </div>
      ${videoInputs()}<div class="g2">
        <div><label class="f" style="margin-top:0">单镜帧数</label><input type="number" min="120" max="${S.cfg?.limits?.frames_max || 345}" data-wfc="${sid}:num_frames:int" value="${cfg.num_frames ?? 124}" ${dis}></div>
        <div><label class="f" style="margin-top:0">补充要求</label><input type="text" data-wfc="${sid}:instruction" value="${esc(cfg.instruction || '')}" ${dis}></div>
      </div>`;
  }
  if (step.type === 'video_gen'){
    return `
      <div class="g3">
        <div><label class="f" style="margin-top:0">关键帧来源</label><select data-wfc="${sid}:keyframe_from" ${dis}>${upstreamOptions(steps, idx, ['image_gen'], cfg.keyframe_from || '')}</select></div>
        <div><label class="f" style="margin-top:0">提示词来源</label><select data-wfc="${sid}:prompts_from" ${dis}>${upstreamOptions(steps, idx, ['h3_prompt','llm_script'], cfg.prompts_from || '')}</select></div>
        <div><label class="f" style="margin-top:0">H3 模式</label><select data-wfc="${sid}:workflow" ${dis}>
          <option value="fl2va" ${cfg.workflow==='fl2va'?'selected':''}>fl2va · 首帧 / 尾帧</option>
          <option value="ref2va" ${cfg.workflow==='ref2va'?'selected':''}>ref2va · 图片 / 视频参考</option>
          <option value="t2va" ${cfg.workflow==='t2va'?'selected':''}>t2va · 文生</option>
        </select></div>
      </div>
      <div class="g3" style="margin-top:6px">
        <div><label class="f" style="margin-top:0">宽 × 高</label><div class="row"><input type="number" step="64" min="512" max="1536" data-wfc="${sid}:width:int" value="${cfg.width ?? 1280}" ${dis}><input type="number" step="64" min="512" max="1536" data-wfc="${sid}:height:int" value="${cfg.height ?? 768}" ${dis}></div></div>
        <div><label class="f" style="margin-top:0">帧数 / 步数</label><div class="row"><input type="number" min="120" max="${S.cfg?.limits?.frames_max || 345}" data-wfc="${sid}:num_frames:int" value="${cfg.num_frames ?? 124}" ${dis}><input type="number" min="2" max="60" data-wfc="${sid}:steps:int" value="${cfg.steps ?? 30}" ${dis}></div></div>
        <div><label class="f" style="margin-top:0">首选 GPU</label><select data-wfc="${sid}:gpu" ${dis}>${(S.cfg.gpus||[]).map(g=>`<option value="${g.id}" ${(cfg.gpu||'H100')===g.id?'selected':''}>${esc(g.label || g.id)}</option>`).join('')}</select></div>
      </div>
      ${videoInputs()}<div style="margin-top:6px"><label class="f" style="margin-top:0">显存卸载</label>
        <select data-wfc="${sid}:offload_mode" ${dis}>
          <option value="auto" ${(cfg.offload_mode||'auto')==='auto'?'selected':''}>自动</option>
          <option value="component" ${cfg.offload_mode==='component'?'selected':''}>组件级 · H100 / G4</option>
          <option value="group" ${cfg.offload_mode==='group'?'selected':''}>逐层 · A100 / L4 无损 BF16</option>
          <option value="none" ${cfg.offload_mode==='none'?'selected':''}>关闭</option>
        </select>
      </div>`;
  }
  if (step.type === 'video_stitch'){
    return `
      <div class="g3">
        <div><label class="f" style="margin-top:0">片段来源</label><select data-wfc="${sid}:clips_from" ${dis}>${upstreamOptions(steps, idx, ['video_gen'], cfg.clips_from || '')}</select></div>
        <div><label class="f" style="margin-top:0">转场</label><select data-wfc="${sid}:transition" ${dis}>
          <option value="fade" ${cfg.transition!=='cut'?'selected':''}>交叉淡入淡出</option>
          <option value="cut" ${cfg.transition==='cut'?'selected':''}>硬切</option>
        </select></div>
        <div><label class="f" style="margin-top:0">转场秒数</label><input type="number" step="0.05" min="0.1" max="1.5" data-wfc="${sid}:fade_s:float" value="${cfg.fade_s ?? 0.35}" ${dis}></div>
      </div>
      <div class="g3" style="margin-top:6px">
        <div><label class="f" style="margin-top:0">目标宽</label><input type="number" step="16" min="256" max="1920" data-wfc="${sid}:target_width:int" value="${cfg.target_width ?? 1280}" ${dis}></div>
        <div><label class="f" style="margin-top:0">目标高</label><input type="number" step="16" min="256" max="1920" data-wfc="${sid}:target_height:int" value="${cfg.target_height ?? 768}" ${dis}></div>
        <div><label class="f" style="margin-top:0">手动作品 ID</label><input type="text" data-wfc="${sid}:clip_round_ids:csv" value="${esc((cfg.clip_round_ids||[]).join(','))}" placeholder="012,013,014" ${dis}></div>
      </div>`;
  }
  return '';
}
function renderStepOutputHTML(step, ss, run){
  const out = (ss && ss.output) || {};
  const dis = run.status === 'running' ? 'disabled' : '';
  const sid = esc(step.id);
  if (ss && ss.error){
    return `<div class="wf-out"><div class="warnbox" style="margin-top:0">${I('alert')}<div>${esc(ss.error)}</div></div></div>`;
  }
  if (!out || !Object.keys(out).length) return '';
  if (step.type === 'llm_script' && Array.isArray(out.scenes) && out.scenes.length){
    return `<div class="wf-out">
      <div class="row" style="justify-content:space-between">
        <b style="font-size:12.5px">分镜产出 · ${esc(out.title || '')} · ${out.scenes.length} 镜</b>
        <button type="button" class="btn sm" data-wf-save-scenes="${sid}" ${dis}>保存分镜修改</button>
      </div>
      ${out.style_bible ? `<div class="dim" style="font-size:11.5px">视觉基调：${esc(out.style_bible)}</div>` : ''}
      <div class="wf-scenes" data-scenes-box="${sid}">
        ${out.scenes.map((sc, i) => `<div class="wf-scene" data-sc-idx="${i}">
          <b>镜头 #${sc.index || i + 1}</b>
          <input type="text" data-sf="title" value="${esc(sc.title || '')}" placeholder="镜头标题" ${dis}>
          <input type="text" data-sf="search_query" value="${esc(sc.search_query || '')}" placeholder="网页找图关键词" ${dis}>
          <textarea data-sf="keyframe_prompt" placeholder="关键帧生图提示词" ${dis}>${esc(sc.keyframe_prompt || '')}</textarea>
          <textarea data-sf="video_prompt" placeholder="视频动作与运镜" ${dis}>${esc(sc.video_prompt || '')}</textarea>
          <input type="text" data-sf="audio_notes" value="${esc(sc.audio_notes || '')}" placeholder="声音与环境音" ${dis}>
        </div>`).join('')}
      </div></div>`;
  }
  if (step.type === 'web_asset_fetch' && Array.isArray(out.images)){
    return `<div class="wf-out">
      <div class="row" style="justify-content:space-between">
        <b style="font-size:12.5px">已下载参考图 · ${out.images.length} 张</b>
        <button type="button" class="btn sm" data-wf-upload="${sid}" ${dis}>${I('upload')}补充上传</button>
      </div>
      <div class="wf-thumbs">
        ${out.images.map(im => `<div class="wf-thumb">
          <img src="api/workflows/runs/${esc(run.id)}/assets/${encodeURIComponent(im.filename)}" alt="" title="${esc(im.title || '')}">
          <button type="button" class="rm" data-wf-rmasset="${esc(im.filename)}" title="删除此图" ${dis}>×</button>
          <div class="cap" title="${esc(im.title || im.source_url || '')}">${esc(im.title || im.filename)}</div>
        </div>`).join('')}
      </div></div>`;
  }
  if (step.type === 'image_gen' && Array.isArray(out.items) && out.items.length){
    return `<div class="wf-out">
      <b style="font-size:12.5px">已生成关键帧（${out.items.length} 张）</b>
      <div class="wf-thumbs">
        ${out.items.map(it => `<div class="wf-thumb" data-wf-viewround="${esc(it.round_id)}">
          <img src="api/rounds/${esc(it.round_id)}" alt="">
          <div class="cap">#${+it.round_id} · ${esc(it.title || '')}</div>
        </div>`).join('')}
      </div></div>`;
  }
  if (step.type === 'h3_prompt' && Array.isArray(out.items) && out.items.length){
    return `<div class="wf-out">
      <div class="row" style="justify-content:space-between">
        <b style="font-size:12.5px">H3 视频提示词 · ${out.items.length} 镜</b>
        <button type="button" class="btn sm" data-wf-save-h3="${sid}" ${dis}>保存提示词修改</button>
      </div>
      <div class="wf-scenes" data-h3-box="${sid}">
        ${out.items.map((it, i) => `<div class="wf-scene" data-h3-idx="${i}">
          <b>镜头 #${it.scene_index || i + 1} · ${esc(it.title || '')} ${it.keyframe_round_id ? `(首帧 #${+it.keyframe_round_id})` : ''}</b>
          <textarea style="min-height:110px" data-h3f="video_prompt" ${dis}>${esc(it.video_prompt || '')}</textarea>
        </div>`).join('')}
      </div></div>`;
  }
  if (step.type === 'video_gen' && Array.isArray(out.items) && out.items.length){
    return `<div class="wf-out">
      <b style="font-size:12.5px">已生成视频片段（${out.items.length} 段）</b>
      <div class="wf-thumbs">
        ${out.items.map(it => `<div class="wf-thumb" style="width:180px">
          <video src="api/rounds/${esc(it.round_id)}" controls muted playsinline style="height:105px"></video>
          <div class="cap">#${+it.round_id} · ${esc(it.title || '')}</div>
        </div>`).join('')}
      </div></div>`;
  }
  if (step.type === 'video_stitch' && out.final_round_id){
    return `<div class="wf-out">
      <div class="row" style="justify-content:space-between">
        <b style="font-size:13px;color:var(--ok)">🎉 长视频成品已合成（作品 #${+out.final_round_id} · ${out.clip_count} 段 · ${out.duration_s}s）</b>
        <div class="row" style="gap:6px">
          <a class="btn sm primary" href="api/rounds/${esc(out.final_round_id)}?download=1">${I('download')}下载 MP4</a>
          <button type="button" class="btn sm" data-wf-viewround="${esc(out.final_round_id)}">在主舞台查看</button>
        </div>
      </div>
      <video class="wf-final-video" src="api/rounds/${esc(out.final_round_id)}" controls playsinline></video>
    </div>`;
  }
  return '';
}
function renderWorkflowCanvas({preserveInputs=false}={}){
  const run = S.wfRun;
  if (!run){
    $('#wfName').value = ''; $('#wfName').disabled = true;
    $('#wfTopic').value = ''; $('#wfTopic').disabled = true;
    $('#wfStatusPill').textContent = '未选择'; $('#wfStatusPill').className = 'wf-st pending';
    $('#wfStartBtn').classList.add('hide'); $('#wfResumeBtn').classList.add('hide'); $('#wfCancelBtn').classList.add('hide');
    $('#wfPauseBanner').classList.add('hide');
    $('#wfPalette').classList.add('hide');
    $('#wfLogsBox').classList.add('hide');
    $('#wfNodes').innerHTML = '<div class="gempty" style="margin:30px 0">当前没有打开的运行实例。<br>点击左侧任意「工作流模板」或「+ 空白流程」即可新建一个实例。</div>';
    return;
  }
  $('#wfPalette').classList.remove('hide');
  $('#wfLogsBox').classList.remove('hide');
  const running = run.status === 'running';
  const paused = run.status === 'paused';
  if (!preserveInputs || document.activeElement !== $('#wfName')) $('#wfName').value = run.workflow.name || '';
  if (!preserveInputs || document.activeElement !== $('#wfTopic')) $('#wfTopic').value = run.topic || '';
  $('#wfName').disabled = running;
  $('#wfTopic').disabled = running;
  const pill = $('#wfStatusPill');
  pill.textContent = WF_STATUS_ZH[run.status] || run.status;
  pill.className = 'wf-st ' + (run.status || 'pending');
  $('#wfStartBtn').classList.toggle('hide', running || paused);
  $('#wfResumeBtn').classList.toggle('hide', !paused);
  $('#wfCancelBtn').classList.toggle('hide', !running);
  $('#wfPauseBanner').classList.toggle('hide', !paused);
  $('#wfPauseText').textContent = run.pause_reason || '工作流已暂停，你可以检查或修改上方产出，确认无误后点击「继续下一步」。';

  const steps = run.workflow.steps || [];
  const states = run.step_states || {};
  $('#wfNodes').innerHTML = steps.map((st, idx) => {
    const ss = states[st.id] || {status:'pending', output:{}};
    const cat = stepCatalogFor(st.type);
    const arrow = idx > 0 ? '<div class="wf-arrow">↓</div>' : '';
    const durTxt = ss.started_at && ss.finished_at ? ` · ${dur(ss.finished_at - ss.started_at)}` : '';
    return `${arrow}<div class="wf-node ${esc(ss.status)} ${st.enabled === false ? 'disabled' : ''}" data-step="${esc(st.id)}">
      <div class="wf-nh">
        <span style="font-size:15px">${esc(cat.icon)}</span>
        <span class="wf-type">${esc(cat.label)}</span>
        <input type="text" data-wfst-name="${esc(st.id)}" value="${esc(st.name)}" style="flex:1;min-width:140px;height:28px;padding:3px 8px;font-weight:650" ${running?'disabled':''}>
        <span class="wf-st ${esc(ss.status)}">${esc(WF_STATUS_ZH[ss.status] || ss.status)}${esc(durTxt)}</span>
        ${ss.progress && ss.status === 'running' ? `<span class="dim" style="font-size:11.5px"><span class="sp"></span> ${esc(ss.progress)}</span>` : ''}
        <label class="switch" style="margin:0;font-size:11.5px" title="该步骤完成后暂停，让你检查或编辑结果再继续">
          <input type="checkbox" data-wfst-pause="${esc(st.id)}" ${st.pause_after ? 'checked' : ''} ${running?'disabled':''}><span class="tg"></span>暂停审核
        </label>
        <label class="switch" style="margin:0;font-size:11.5px" title="关闭则跳过该步骤">
          <input type="checkbox" data-wfst-en="${esc(st.id)}" ${st.enabled !== false ? 'checked' : ''} ${running?'disabled':''}><span class="tg"></span>启用
        </label>
        <button type="button" class="iconbtn" style="width:26px;height:26px" data-wfst-up="${esc(st.id)}" title="上移" ${running||idx===0?'disabled':''}>${I('up')}</button>
        <button type="button" class="iconbtn" style="width:26px;height:26px" data-wfst-dn="${esc(st.id)}" title="下移" ${running||idx===steps.length-1?'disabled':''}>${I('down')}</button>
        <button type="button" class="btn sm" style="height:26px;padding:0 8px;font-size:11.5px" data-wfst-retry="${esc(st.id)}" title="仅重跑这一步（不影响前面已完成的结果）" ${running?'disabled':''}>重跑此步</button>
        <button type="button" class="iconbtn" style="width:26px;height:26px" data-wfst-del="${esc(st.id)}" title="删除步骤" ${running||steps.length<=1?'disabled':''}>${I('x')}</button>
      </div>
      <div class="wf-nb">
        ${renderStepConfigHTML(st, idx, steps, run)}
        ${renderStepOutputHTML(st, ss, run)}
      </div>
    </div>`;
  }).join('');
  $('#wfLogsPre').textContent = (run.logs || []).join('\n');
}
function openGalleryPickerForWorkflow(stepId){
  const imgs = S.gallery.filter(x => x.kind === 'image');
  if (!imgs.length){ toast('作品库暂无图片，请先上传本地图片或去生图页生成', 'err'); return; }
  const m = modal(`
    <div class="mh">${I('image','lg')}<h3>从作品库挑选参考图</h3><div class="grow"></div><button class="iconbtn" data-close>${I('x')}</button></div>
    <div class="mb"><div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(110px,1fr))">
      ${imgs.slice(0, 60).map(it => `<div class="tile" data-pick="${it.id}"><img loading="lazy" src="${thumbUrl(it) || mediaUrl(it)}"><span class="id">#${+it.id}</span></div>`).join('')}
    </div></div>`, {wide:true});
  m.el.addEventListener('click', async e => {
    const t = e.target.closest('[data-pick]'); if (!t || !S.wfRun) return;
    const rid = t.dataset.pick;
    const st = S.wfRun.workflow.steps.find(s => s.id === stepId);
    if (st){
      st.config.round_ids = [...new Set([...(st.config.round_ids || []), rid])];
      await saveWorkflowRunNow();
      renderWorkflowCanvas();
      toast(`已绑定作品 #${+rid} 到「${st.name}」`, 'ok');
    }
    m.close();
  });
}

/* ── settings ── */
function openSettings(){
  const c = (S.status && S.status.colab) || {};
  const scrim = document.createElement('div'); scrim.className = 'scrim'; scrim.style.placeItems = 'stretch end'; scrim.style.padding = '0';
  scrim.innerHTML = `<div class="drawer">
    <div class="mh">${I('settings','lg')}<h3>设置</h3><div class="grow"></div><button class="iconbtn" data-close>${I('x')}</button></div>
    <div class="mb">
      <div class="sect"><h4>${I('cpu')}Google Colab 账号</h4><div id="sColab"></div>
        <div style="margin-top:12px" class="row wrap"><button class="btn sm primary" id="sAuth">${I('link')}${c.authed ? '切换账号' : '连接 Google Colab'}</button>
          ${c.authed ? `<button class="btn sm ghost" id="sLogout">清除授权</button>` : ''}<button class="btn sm ghost" id="sRefresh">${I('reuse')}刷新</button></div>
        <div id="sAuthFlow" class="hide" style="margin-top:12px">
          <div class="help" style="margin:0 0 8px">① 打开授权链接并登录 Google 账号 → ② 复制页面上的授权码粘贴到下面。</div>
          <a id="sLink" class="btn sm" target="_blank" rel="noopener">${I('link')}打开 Google 授权页 ↗</a>
          <div class="row" style="margin-top:8px"><input type="text" id="sCode" placeholder="4/0A…"><button class="btn sm primary" id="sDone">完成授权</button></div>
        </div></div>
      <div class="sect"><h4>${I('key')}Hugging Face Token <span class="dim" style="font-weight:500">${c.hf_token_set ? '· 已配置' : '· 未配置'}</span></h4>
        <div class="help" style="margin:0 0 8px">访问受限仓库（FLUX.2 / MiniMax-H3）或加速下载时需要。只保存在服务器 0600 文件里，不会回显。</div>
        <div class="row"><input type="password" id="sHf" placeholder="hf_…" autocomplete="off"><button class="btn sm" id="sHfSave">保存</button>${c.hf_token_set ? `<button class="btn sm ghost" id="sHfClear">清除</button>` : ''}</div></div>
      <div class="sect" id="sGrabSect"><h4>${I('cpu')}抢卡</h4>
        <div class="help" style="margin:0 0 8px">在这里申请 Colab GPU 并持有。Draw 页的算力列表只显示已经抢到的卡。</div>
        <div class="gpu-list" id="sGrabGpus"></div>
        <div class="poll-bar">
          <div class="poll-row">
            <span>轮询次数</span>
            <input type="number" id="pollRounds" min="1" max="10" value="${S.pollRounds || 2}">
            <span>轮</span>
            <span class="poll-plan" id="pollSummary"></span>
          </div>
          <label class="switch" style="margin:0" title="开启后每轮使用全部已保存的代理线路申请算力">
            <input type="checkbox" id="pollAllProxies" ${S.pollAllProxies ? 'checked' : ''}>
            <span class="tg"></span>使用全部已配代理轮询
          </label>
        </div>
        <div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--line)">
          <div class="row" style="justify-content:space-between;margin-bottom:6px">
            <span class="mgroup-lbl" style="margin:0;color:var(--muted);font-weight:500">Colab 出口线路（不同地区机房库存不同）</span>
            <button type="button" class="btn sm" id="testProxyBtn" style="height:24px;padding:0 8px;font-size:11px">测出口</button>
          </div>
          <div class="chips" id="proxyChips"></div>
          <div class="row" style="margin-top:8px">
            <select id="proxyEditTarget" aria-label="管理线路"><option value="">新增线路</option></select>
            <button type="button" class="btn sm danger" id="removeProxyBtn" disabled>删除线路</button>
          </div>
          <div class="row" style="margin-top:8px">
            <input type="text" id="proxyLabel" aria-label="线路名称" placeholder="线路名称" maxlength="80">
            <input type="password" id="customProxyUrl" autocomplete="new-password" aria-label="代理地址" placeholder="http://host:port 或 socks5://host:port">
            <button type="button" class="btn sm" id="saveCustomProxyBtn">保存线路</button>
          </div>
          <div class="help" id="proxyHelp"></div>
        </div>
        <div class="row" style="margin-top:10px"><button class="btn sm primary" id="sGrab">${I('sparkles')}抢卡</button></div>
        <div class="help" id="sGrabState" style="margin:8px 0 0"></div>
        <h4 style="margin-top:16px">${I('clock')}空闲自动释放</h4>
        <div class="help" style="margin:0 0 8px">最后一个任务结束后，空闲多久自动释放 Colab 运行时（停止消耗 CU）。选「永不超期」则一直持有，直到手动释放。</div>
        <div class="chips" id="sIdle">${[[5,'5 分钟'],[10,'10 分钟'],[20,'20 分钟'],[30,'30 分钟'],[60,'60 分钟'],[0,'永不超期']].map(([n, label]) => `<button class="pchip ${S.status && S.status.idle_minutes===n?'on':''}" data-idle="${n}">${label}</button>`).join('')}</div></div>
      <div class="sect"><h4>${I('info')}关于</h4><div class="kv"><span>版本</span><span>Colab Studio v${S.cfg.version}</span>
        <span>快捷键</span><span>Ctrl/⌘+Enter 生成 · ←/→ 切换作品 · S 收藏 · D 下载 · Delete 删除 · F 全屏 · L 日志</span>
        <span>回收站</span><span>删除的作品保留 ${S.cfg.trash_retention_days} 天</span></div></div>
    </div></div>`;
  hydrateIcons(scrim);
  const close = () => { scrim.remove(); document.removeEventListener('keydown', onKey, true); };
  const onKey = e => { if (e.key === 'Escape'){ e.stopPropagation(); close(); } };
  document.addEventListener('keydown', onKey, true);
  scrim.addEventListener('mousedown', e => { if (e.target === scrim) close(); });
  $('#overlay').appendChild(scrim);
  $$('[data-close]', scrim).forEach(b => b.onclick = close);
  const renderC = (c) => {
    const eg = (c.eligible_gpus || []).join(' / ');
    const et = (c.eligible_tpus || []).join(' / ');
    $('#sColab', scrim).innerHTML = !c.authed ? '<div class="muted">还没有连接。连接后才能申请 Colab GPU。</div>' : !c.ok ? `<div style="color:#fca5a5">${esc(c.error)}</div>`
      : `<div class="kv"><span>账号</span><span>${esc(c.email || '已授权')}</span><span>CU 余额</span><span>${c.balance ?? '?'}</span>
        <span>消耗速率</span><span>${c.rate_per_hour ?? 0} CU / 小时</span><span>运行实例</span><span>${c.sessions.length} 台</span>`
        + (eg ? `<span>可用 GPU</span><span>${esc(eg)}</span>` : '')
        + (et ? `<span>可用 TPU</span><span>${esc(et)}</span>` : '')
        + `</div>`
        + (c.sessions || []).map(s => `<div class="sess">${esc(s.gpu)} (${esc(s.shape)}) · ${esc(s.name)}<br><span class="dim">${esc(s.endpoint)}</span></div>`).join('');
  };
  renderC(c);
  $('#sRefresh', scrim).onclick = async () => { try { renderC(await api('api/colab/status')); } catch(e){ toast(e.message, 'err'); } };
  $('#sAuth', scrim).onclick = async () => {
    try { const r = await post('api/colab/auth/start'); $('#sLink', scrim).href = r.auth_url; $('#sAuthFlow', scrim).classList.remove('hide'); }
    catch(e){ toast(e.message, 'err'); }
  };
  $('#sDone', scrim).onclick = async () => {
    const code = $('#sCode', scrim).value.trim(); if (!code) return toast('请粘贴授权码', 'err');
    try { const r = await post('api/colab/auth/complete', {code}); toast('已连接 ' + (r.email || 'Google Colab'), 'ok'); close(); refresh(); }
    catch(e){ toast('授权失败：' + e.message, 'err'); }
  };
  const lo = $('#sLogout', scrim);
  if (lo) lo.onclick = async () => { if (await confirmBox({title:'清除 Colab 授权？', body:'服务器上保存的 Google 凭据会被删除，之后需要重新授权。', ok:'清除', danger:true})){ await post('api/colab/auth/logout'); close(); refresh(); } };
  $('#sHfSave', scrim).onclick = async () => { try { await post('api/colab/hf-token', {token: $('#sHf', scrim).value.trim()}); toast('HF Token 已保存', 'ok'); close(); refresh(); } catch(e){ toast(e.message, 'err'); } };
  const hc = $('#sHfClear', scrim);
  if (hc) hc.onclick = async () => { await post('api/colab/hf-token', {token:''}); toast('已清除 HF Token', 'ok'); close(); refresh(); };
  renderGrabCatalog();
  renderProxyChips();
  $('#sGrabGpus', scrim).onclick = e => {
    const b = e.target.closest('[data-grab]'); if (!b) return;
    const id = b.dataset.grab;
    const pool = Array.isArray(S.grabPool) ? S.grabPool.slice() : [];
    const idx = pool.indexOf(id);
    if (idx >= 0){
      if (pool.length <= 1){ toast('至少保留 1 张候选 GPU', 'err'); return; }
      pool.splice(idx, 1);
    } else pool.push(id);
    S.grabPool = pool;
    renderGrabCatalog();
    saveSoon();
  };
  const roundsEl = $('#pollRounds', scrim);
  const syncRounds = () => {
    const lim = (S.cfg && S.cfg.limits) || {};
    S.pollRounds = Math.max(lim.poll_rounds_min || 1, Math.min(lim.poll_rounds_max || 10, +roundsEl.value || 1));
    roundsEl.value = S.pollRounds;
    updatePollSummary();
    saveSoon();
  };
  roundsEl.addEventListener('input', () => {
    const n = +roundsEl.value;
    if (n >= 1 && n <= 10) S.pollRounds = n;
    updatePollSummary();
  });
  roundsEl.addEventListener('change', syncRounds);
  $('#pollAllProxies', scrim).addEventListener('change', e => {
    S.pollAllProxies = !!e.target.checked;
    updatePollSummary();
    saveSoon();
  });
  $('#sGrab', scrim).onclick = async () => {
    if (!S.grabPool.length) return toast('请先勾选要抢的卡', 'err');
    const b = $('#sGrab', scrim); b.disabled = true;
    try {
      await post('api/colab/grab', {
        gpu_pool: S.grabPool,
        poll_rounds: S.pollRounds || 1,
        poll_all_proxies: !!S.pollAllProxies,
      });
      toast('开始抢卡', 'ok');
      refresh();
    } catch(err){ toast(err.message, 'err'); }
    b.disabled = false;
  };
  $('#proxyChips', scrim).onclick = async e => {
    const b = e.target.closest('[data-proxy]'); if (!b || b.disabled) return;
    const pid = b.dataset.proxy;
    try {
      const r = await post('api/proxy', {active: pid});
      S.proxy = r;
      renderProxyChips();
      const lbl = (r.profiles.find(p => p.id === pid) || {}).label || '系统网络';
      toast('已切换出口为 ' + lbl, 'ok');
      refresh();
    } catch(err){ toast(err.message, 'err'); }
  };
  const editor = $('#proxyEditTarget', scrim);
  editor.onchange = () => {
    const selected = S.proxy?.profiles.find(p => p.id === editor.value);
    $('#proxyLabel', scrim).value = selected?.label || '';
    $('#customProxyUrl', scrim).value = '';
    $('#customProxyUrl', scrim).placeholder = selected ? '留空保留地址与凭据' : 'http://host:port 或 socks5://host:port';
    $('#removeProxyBtn', scrim).disabled = !selected;
  };
  $('#removeProxyBtn', scrim).onclick = async () => {
    const pid = editor.value;
    const profile = S.proxy?.profiles.find(p => p.id === pid);
    if (!profile || !await confirmBox({title:`删除「${profile.label}」？`,ok:'删除',danger:true})) return;
    try {
      S.proxy = await api('api/proxy/profiles/' + encodeURIComponent(pid), {method:'DELETE'});
      renderProxyChips(); refresh();
    } catch(err){ toast(err.message, 'err'); }
  };
  $('#saveCustomProxyBtn', scrim).onclick = async () => {
    const url = $('#customProxyUrl', scrim).value.trim();
    const label = $('#proxyLabel', scrim).value.trim();
    const id = editor.value || undefined;
    if (!label || (!url && !id)) return toast('请填写线路名称与代理地址', 'err');
    const b = $('#saveCustomProxyBtn', scrim); b.disabled = true;
    try {
      const r = await post('api/proxy/profiles', {id, label, url: url || undefined});
      S.proxy = r;
      editor.value = '';
      editor.onchange();
      renderProxyChips();
      toast('线路已保存', 'ok');
      refresh();
    } catch(err){ toast(err.message, 'err'); }
    b.disabled = false;
  };
  $('#testProxyBtn', scrim).onclick = async () => {
    const b = $('#testProxyBtn', scrim); b.disabled = true; b.textContent = '测试中…';
    try {
      const r = await post('api/proxy/test', {});
      if (S.proxy) S.proxy.last_test = r;
      renderProxyChips();
      if (r.ok) toast(`出口正常：${r.loc} / ${r.colo}（${r.ms}ms）`, 'ok');
      else toast('出口测试失败：' + r.error, 'err');
    } catch(err){ toast(err.message, 'err'); }
    b.disabled = false; b.textContent = '测出口';
  };
  $('#sIdle', scrim).onclick = async e => {
    const b = e.target.closest('[data-idle]'); if (!b) return;
    const minutes = +b.dataset.idle;
    try {
      const r = await post('api/settings', {idle_minutes: minutes});
      if (S.status) S.status.idle_minutes = r.idle_minutes;
      $$('[data-idle]', scrim).forEach(x => x.classList.toggle('on', +x.dataset.idle === r.idle_minutes));
      toast(r.idle_minutes === 0 ? '已设为永不超期，会一直持有直到手动释放' : `空闲 ${r.idle_minutes} 分钟后自动释放`, 'ok');
      refresh();
    }
    catch(err){ toast(err.message, 'err'); }
  };
}

/* ── wiring ── */
function bind(){
  $('#videoTask').onchange = () => { updateModeUI(); saveSoon(); };
  $('#videoUseImages').onchange = () => { updateModeUI(); saveSoon(); };
  const changeVideo = async (request, task) => {
    if (S.videoRefBusy) return;
    S.videoRefBusy = true;
    try {
      const r = await request();
      if (task) {
        setMode('video'); S.workflow = 'ref2va'; $('#videoTask').value = task; $('#videoUseImages').checked = false;
        renderWorkflowChips(); updateModeUI(); saveSoon();
      }
      renderRefs(r.references);
    } catch(e){ toast(e.message, 'err'); }
    finally { S.videoRefBusy = false; }
  };
  $('#videoRefInput').onchange = e => {
    const file = e.target.files[0]; e.target.value = '';
    if (file) changeVideo(() => api('api/video-reference', {method:'POST', body:file}));
  };
  $('#videoRefClear').onclick = () => S.refs.video && changeVideo(() => api('api/video-reference?id=' + encodeURIComponent(S.refs.video.id), {method:'DELETE'}));
  const useGalleryVideo = task => S.viewing && changeVideo(() => post('api/rounds/' + S.viewing + '/use', {slot:'video'}), task);
  $('#aEditVideo').onclick = () => useGalleryVideo('edit');
  $('#aContinueVideo').onclick = () => useGalleryVideo('continue');
  $('#wsImage').onclick = () => setWorkspace('image');
  $('#wsVideo').onclick = () => setWorkspace('video');
  $('#wsWorkflow').onclick = () => setWorkspace('workflow');
  $('#mImage').onclick = () => setMode('image');
  $('#mVideo').onclick = () => setMode('video');
  $('#studioPresetSel').addEventListener('change', e => {
    const pid = e.target.value;
    const isCustom = (S.studioPresets || []).some(p => p.id === pid);
    $('#delStudioPresetBtn').classList.toggle('hide', !isCustom);
    if (pid) applyStudioPreset(pid);
  });
  $('#saveStudioPresetBtn').onclick = () => {
    const m = modal(`
      <div class="mh">${I('sparkles','lg')}<h3>保存当前参数预设</h3><div class="grow"></div><button class="iconbtn" data-close>${I('x')}</button></div>
      <div class="mb">
        <label class="f" style="margin-top:0">预设名称</label>
        <input type="text" id="spName" placeholder="例如：写实人像 2:3 · 35步" maxlength="60">
        <div class="help">将保存当前模式（${S.mode==='video'?'生视频':'生图'}）的模型/引擎、画幅、步数、CFG、GPU 与 LoRA。</div>
      </div>
      <div class="mf"><button class="btn" data-close>取消</button><button class="btn primary" id="spOk">保存预设</button></div>`);
    const inp = $('#spName', m.el); inp.focus();
    const go = async () => {
      const name = inp.value.trim(); if (!name) return toast('请填写预设名称', 'err');
      try {
        const p = buildPayload();
        const r = await post('api/presets', {...p, name});
        S.studioPresets = r.custom || [];
        renderStudioPresets();
        if (r.preset) $('#studioPresetSel').value = r.preset.id;
        $('#delStudioPresetBtn').classList.remove('hide');
        toast('已保存参数预设：' + name, 'ok');
        m.close();
      } catch(err){ toast(err.message, 'err'); }
    };
    $('#spOk', m.el).onclick = go;
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
  };
  $('#delStudioPresetBtn').onclick = async () => {
    const pid = $('#studioPresetSel').value;
    if (!pid || pid.startsWith('builtin:')) return;
    try {
      const r = await api('api/presets/' + encodeURIComponent(pid), {method:'DELETE'});
      S.studioPresets = r.custom || [];
      $('#studioPresetSel').value = '';
      renderStudioPresets();
      toast('已删除自定义预设', 'ok');
    } catch(err){ toast(err.message, 'err'); }
  };
  $('#insertWildcardBtn').onclick = () => {
    const ta = $('#prompt');
    const snip = '{晨光柔和|赛博霓虹雨夜|黄昏逆光}';
    const s = ta.selectionStart ?? ta.value.length, e = ta.selectionEnd ?? ta.value.length;
    ta.value = ta.value.slice(0, s) + snip + ta.value.slice(e);
    ta.focus(); ta.setSelectionRange(s + 1, s + snip.length - 1);
    updateCount(); saveSoon();
    toast('已插入抽签变体语法：把数量调为 2–4 张可一次抽多套变体', 'ok');
  };
  $('#promptHistBtn').onclick = () => {
    const pop = $('#promptHistPop');
    const show = pop.classList.contains('hide');
    if (show) renderPromptHistory();
    pop.classList.toggle('hide', !show);
  };
  $('#promptHistPop').onclick = e => {
    const b = e.target.closest('[data-ph]'); if (!b) return;
    const p = S.promptHist[+b.dataset.ph];
    if (p){ $('#prompt').value = p; updateCount(); saveSoon(); }
    $('#promptHistPop').classList.add('hide');
  };
  $('#swapWH').onclick = () => {
    const w = +$('#width').value, h = +$('#height').value;
    setNum('width', h); setNum('height', w); saveSoon();
  };
  $('#optWH').onclick = () => {
    const w = +$('#width').value || 768, h = +$('#height').value || 1152;
    const ratio = w / h;
    const targetArea = S.mode === 'video' ? (1280 * 768) : (1024 * 1024);
    const lim = S.cfg.limits;
    const snap = v => Math.min(lim.size_max, Math.max(lim.size_min, Math.round(v / lim.size_step) * lim.size_step));
    const nw = snap(Math.sqrt(targetArea * ratio));
    const nh = snap(Math.sqrt(targetArea / ratio));
    setNum('width', nw); setNum('height', nh); saveSoon();
    toast(`已按当前比例优化为 ${nw}×${nh}`, 'ok');
  };
  $('#seedLast').onclick = () => {
    const it = current() || S.gallery[0];
    if (!it || it.seed === undefined || it.seed === null){ toast('暂无可锁定的历史种子', 'err'); return; }
    $('#seed').value = it.seed; saveSoon();
    toast(`已锁定作品 #${+it.id} 的种子：${it.seed}`, 'ok');
  };
  $('#aCompare').onclick = () => {
    const imgs = S.gallery.filter(x => x.kind === 'image');
    const cur = current();
    const other = imgs.find(x => !cur || x.id !== cur.id);
    openCompareModal(cur && cur.id, other && other.id);
  };
  $('#selCompare').onclick = () => {
    const imgs = [...S.selected].filter(id => { const it = S.gallery.find(x => x.id === id); return it && it.kind === 'image'; });
    openCompareModal(imgs[0], imgs[1]);
  };

  // Tab 3 Workflow Studio bindings
  $('#wfNewBlankBtn').onclick = createBlankWorkflowRun;
  $('#wfRefreshBtn').onclick = () => loadWorkflowData({keepRun:true});
  $('#wfTemplateList').onclick = async e => {
    const del = e.target.closest('[data-del-wftpl]');
    if (del){
      e.stopPropagation();
      try {
        await api('api/workflows/' + encodeURIComponent(del.dataset.delWftpl), {method:'DELETE'});
        S.wfData = await api('api/workflows');
        renderWorkflowSidebar();
        toast('已删除模板', 'ok');
      } catch(err){ toast(err.message, 'err'); }
      return;
    }
    const item = e.target.closest('[data-wftpl]');
    if (item) createRunFromTemplate(item.dataset.wftpl);
  };
  $('#wfRunList').onclick = async e => {
    const del = e.target.closest('[data-del-wfrun]');
    if (del){
      e.stopPropagation();
      const rid = del.dataset.delWfrun;
      try {
        await api('api/workflows/runs/' + encodeURIComponent(rid), {method:'DELETE'});
        const wasCurrent = S.wfRun && S.wfRun.id === rid;
        if (wasCurrent) S.wfRun = null;
        await loadWorkflowData({keepRun: !wasCurrent, autoCreate: false});
        toast('已删除运行实例', 'ok');
      } catch(err){ toast(err.message, 'err'); }
      return;
    }
    const item = e.target.closest('[data-wfrun]');
    if (item) selectWorkflowRun(item.dataset.wfrun);
  };
  $('#wfName').addEventListener('input', () => { if (!S.wfRun) return; S.wfRun.workflow.name = $('#wfName').value; saveWorkflowRunSoon(); });
  $('#wfTopic').addEventListener('input', () => { if (!S.wfRun) return; S.wfRun.topic = $('#wfTopic').value; saveWorkflowRunSoon(); });
  $('#wfSaveTplBtn').onclick = async () => {
    if (!S.wfRun) return;
    const name = ($('#wfName').value || '').trim();
    if (!name) return toast('请先填写工作流名称', 'err');
    try {
      await saveWorkflowRunNow();
      await post('api/workflows', {
        name,
        description: S.wfRun.workflow.description || S.wfRun.topic.slice(0, 120),
        default_topic: S.wfRun.topic,
        steps: S.wfRun.workflow.steps,
        ...(S.wfRun.workflow.variables ? {variables: S.wfRun.workflow.variables} : {}),
      });
      S.wfData = await api('api/workflows');
      renderWorkflowSidebar();
      toast('已保存为自定义模板：' + name, 'ok');
    } catch(err){ toast(err.message, 'err'); }
  };
  const startOrResume = async (ep) => {
    if (!S.wfRun) return;
    try {
      await saveWorkflowRunNow();
      const r = await post(`api/workflows/runs/${encodeURIComponent(S.wfRun.id)}/${ep}`, {});
      S.wfRun = r.run;
      renderWorkflowCanvas();
      refresh();
      toast(ep === 'resume' ? '继续执行后续步骤…' : '工作流已启动', 'ok');
    } catch(err){ toast(err.message, 'err'); }
  };
  $('#wfStartBtn').onclick = () => startOrResume('start');
  $('#wfResumeBtn').onclick = $('#wfPauseResumeBtn').onclick = () => startOrResume('resume');
  $('#wfCancelBtn').onclick = async () => {
    if (!S.wfRun) return;
    try {
      const r = await post(`api/workflows/runs/${encodeURIComponent(S.wfRun.id)}/cancel`, {});
      S.wfRun = r.run;
      renderWorkflowCanvas();
      toast('已发送终止信号');
    } catch(err){ toast(err.message, 'err'); }
  };
  $('#wfAddChips').onclick = async e => {
    const b = e.target.closest('[data-wfadd]'); if (!b || !S.wfRun || S.wfRun.status === 'running') return;
    const cat = stepCatalogFor(b.dataset.wfadd);
    const steps = S.wfRun.workflow.steps;
    const base = b.dataset.wfadd;
    let id = base, n = 2;
    while (steps.some(s => s.id === id)) id = `${base}_${n++}`;
    steps.push({
      id,
      type: b.dataset.wfadd,
      name: `${steps.length + 1}. ${cat.label}`,
      enabled: true,
      pause_after: false,
      config: JSON.parse(JSON.stringify(cat.default_config || {})),
    });
    await saveWorkflowRunNow();
    renderWorkflowCanvas();
  };
  $('#wfNodes').addEventListener('input', e => {
    if (!S.wfRun || S.wfRun.status === 'running') return;
    const nm = e.target.dataset.wfstName;
    if (nm){
      const st = S.wfRun.workflow.steps.find(s => s.id === nm);
      if (st){ st.name = e.target.value; saveWorkflowRunSoon(); }
      return;
    }
    const spec = e.target.dataset.wfc;
    if (spec){
      const [sid, key, kind] = spec.split(':');
      const st = S.wfRun.workflow.steps.find(s => s.id === sid);
      if (!st) return;
      let val = e.target.value;
      if (kind === 'int') val = parseInt(val, 10) || 0;
      else if (kind === 'float') val = parseFloat(val) || 0;
      else if (kind === 'csv') val = val.split(',').map(x => x.trim()).filter(Boolean);
      st.config[key] = val;
      if (key === 'gpu') st.config.gpu_pool = [val];
      saveWorkflowRunSoon();
    }
  });
  $('#wfNodes').addEventListener('change', e => {
    if (!S.wfRun || S.wfRun.status === 'running') return;
    const pId = e.target.dataset.wfstPause;
    if (pId){ const st = S.wfRun.workflow.steps.find(s => s.id === pId); if (st){ st.pause_after = e.target.checked; saveWorkflowRunSoon(); } return; }
    const eId = e.target.dataset.wfstEn;
    if (eId){ const st = S.wfRun.workflow.steps.find(s => s.id === eId); if (st){ st.enabled = e.target.checked; saveWorkflowRunSoon(); renderWorkflowCanvas(); } return; }
    const refSpec = e.target.dataset.wfref;
    if (refSpec){
      const [sid, srcId] = refSpec.split(':');
      const st = S.wfRun.workflow.steps.find(s => s.id === sid);
      if (st){
        const key = st.type === 'image_gen' ? 'ref_sources' : 'extra_ref_sources';
        const list = new Set(st.config[key] || []);
        if (e.target.checked) list.add(srcId); else list.delete(srcId);
        st.config[key] = [...list];
        saveWorkflowRunSoon(); renderWorkflowCanvas();
      }
      return;
    }
    if (e.target.dataset.wfc){
      const [sid, key, kind] = e.target.dataset.wfc.split(':');
      const st = S.wfRun.workflow.steps.find(s => s.id === sid);
      if (st){
        let val = e.target.value;
        if (kind === 'int') val = parseInt(val, 10) || 0;
        else if (kind === 'float') val = parseFloat(val) || 0;
        else if (kind === 'csv') val = val.split(',').map(x => x.trim()).filter(Boolean);
        st.config[key] = val;
        if (key === 'gpu') st.config.gpu_pool = [val];
        saveWorkflowRunSoon();
        if (key === 'video_from') st.config.video_round_id = '';
        if (key === 'workflow' || key === 'video_round_id' || key === 'video_from') renderWorkflowCanvas();
      }
    }
  });
  $('#wfNodes').addEventListener('click', async e => {
    if (!S.wfRun) return;
    const steps = S.wfRun.workflow.steps;
    const viewR = e.target.closest('[data-wf-viewround]');
    if (viewR){
      const rid = viewR.dataset.wfViewround;
      setWorkspace('image', {keep:true});
      await loadGallery();
      view(rid, false);
      return;
    }
    const upBtn = e.target.closest('[data-wf-upload]');
    if (upBtn){ S.wfAssetStep = upBtn.dataset.wfUpload; $('#wfAssetInput').click(); return; }
    const pickBtn = e.target.closest('[data-wf-pickgal]');
    if (pickBtn){ openGalleryPickerForWorkflow(pickBtn.dataset.wfPickgal); return; }
    const rmAsset = e.target.closest('[data-wf-rmasset]');
    if (rmAsset){
      try {
        await api(`api/workflows/runs/${encodeURIComponent(S.wfRun.id)}/assets/${encodeURIComponent(rmAsset.dataset.wfRmasset)}`, {method:'DELETE'});
        await selectWorkflowRun(S.wfRun.id);
        toast('已移除图片', 'ok');
      } catch(err){ toast(err.message, 'err'); }
      return;
    }
    const rmRound = e.target.closest('[data-wf-rmround]');
    if (rmRound){
      const [sid, rid] = rmRound.dataset.wfRmround.split(':');
      const st = steps.find(s => s.id === sid);
      if (st){ st.config.round_ids = (st.config.round_ids || []).filter(x => x !== rid); await saveWorkflowRunNow(); renderWorkflowCanvas(); }
      return;
    }
    const saveSc = e.target.closest('[data-wf-save-scenes]');
    if (saveSc){
      const sid = saveSc.dataset.wfSaveScenes;
      const box = $(`[data-scenes-box="${sid}"]`, $('#wfNodes'));
      const curOut = (S.wfRun.step_states[sid] && S.wfRun.step_states[sid].output) || {};
      const orig = curOut.scenes || [];
      const updated = $$('.wf-scene', box).map((card, i) => ({
        ...(orig[i] || {index: i + 1, duration_s: 5}),
        index: i + 1,
        title: $('[data-sf="title"]', card).value.trim(),
        search_query: $('[data-sf="search_query"]', card).value.trim(),
        keyframe_prompt: $('[data-sf="keyframe_prompt"]', card).value.trim(),
        video_prompt: $('[data-sf="video_prompt"]', card).value.trim(),
        audio_notes: $('[data-sf="audio_notes"]', card).value.trim(),
      }));
      try {
        const r = await post(`api/workflows/runs/${encodeURIComponent(S.wfRun.id)}/steps/${encodeURIComponent(sid)}/output`, {output: {scenes: updated}});
        S.wfRun = r.run; renderWorkflowCanvas(); toast('分镜修改已保存', 'ok');
      } catch(err){ toast(err.message, 'err'); }
      return;
    }
    const saveH3 = e.target.closest('[data-wf-save-h3]');
    if (saveH3){
      const sid = saveH3.dataset.wfSaveH3;
      const box = $(`[data-h3-box="${sid}"]`, $('#wfNodes'));
      const curOut = (S.wfRun.step_states[sid] && S.wfRun.step_states[sid].output) || {};
      const orig = curOut.items || [];
      const updated = $$('.wf-scene', box).map((card, i) => ({
        ...(orig[i] || {scene_index: i + 1}),
        video_prompt: $('[data-h3f="video_prompt"]', card).value.trim(),
      }));
      try {
        const r = await post(`api/workflows/runs/${encodeURIComponent(S.wfRun.id)}/steps/${encodeURIComponent(sid)}/output`, {output: {items: updated}});
        S.wfRun = r.run; renderWorkflowCanvas(); toast('H3 视频提示词已保存', 'ok');
      } catch(err){ toast(err.message, 'err'); }
      return;
    }
    const mvUp = e.target.closest('[data-wfst-up]');
    if (mvUp){
      const i = steps.findIndex(s => s.id === mvUp.dataset.wfstUp);
      if (i > 0){ [steps[i-1], steps[i]] = [steps[i], steps[i-1]]; await saveWorkflowRunNow(); renderWorkflowCanvas(); }
      return;
    }
    const mvDn = e.target.closest('[data-wfst-dn]');
    if (mvDn){
      const i = steps.findIndex(s => s.id === mvDn.dataset.wfstDn);
      if (i >= 0 && i < steps.length - 1){ [steps[i], steps[i+1]] = [steps[i+1], steps[i]]; await saveWorkflowRunNow(); renderWorkflowCanvas(); }
      return;
    }
    const delSt = e.target.closest('[data-wfst-del]');
    if (delSt && steps.length > 1){
      const i = steps.findIndex(s => s.id === delSt.dataset.wfstDel);
      if (i >= 0){ steps.splice(i, 1); await saveWorkflowRunNow(); renderWorkflowCanvas(); }
      return;
    }
    const retrySt = e.target.closest('[data-wfst-retry]');
    if (retrySt){
      try {
        await saveWorkflowRunNow();
        const r = await post(`api/workflows/runs/${encodeURIComponent(S.wfRun.id)}/steps/${encodeURIComponent(retrySt.dataset.wfstRetry)}/retry`, {single_step: true});
        S.wfRun = r.run; renderWorkflowCanvas(); refresh();
        toast('正在单步重跑该节点…', 'ok');
      } catch(err){ toast(err.message, 'err'); }
      return;
    }
  });
  $('#wfAssetInput').onchange = async e => {
    const files = [...(e.target.files || [])];
    e.target.value = '';
    if (!files.length || !S.wfRun) return;
    let ok = 0;
    for (const f of files){
      try {
        await api(`api/workflows/runs/${encodeURIComponent(S.wfRun.id)}/assets?step_id=${encodeURIComponent(S.wfAssetStep || '')}`, {method:'POST', body:f});
        ok++;
      } catch(err){ toast('上传失败：' + err.message, 'err'); }
    }
    if (ok){ await selectWorkflowRun(S.wfRun.id); toast(`已上传 ${ok} 张资产图`, 'ok'); }
  };
  $('#rewriteBtn').onclick = rewrite;
  $('#goBtn').onclick = generate;
  $('#stopBtn').onclick = $('#pCancel').onclick = async () => { await post('api/stop'); toast('已发送取消信号'); refresh(); };
  $('#releaseBtn').onclick = async () => {
    if (!(await confirmBox({title:'释放全部 Colab 算力？', body:'会立即销毁所有运行中的 Colab 实例并清空队列，模型缓存随之丢失，下次生成需要重新加载。', ok:'立即释放', danger:true}))) return;
    await post('api/release'); toast('正在释放…'); refresh();
  };
  $('#settingsBtn').onclick = $('#colabChip').onclick = openSettings;
  $('#settingsBtn').disabled = false;
  $('#logBtn').onclick = () => toggleLogs();
  const THEME_KEY = 'colab-studio.theme';
  const applyTheme = (t) => {
    const mode = t === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = mode;
    try { localStorage.setItem(THEME_KEY, mode); } catch {}
    const b = $('#themeBtn');
    if (b){
      b.innerHTML = I(mode === 'light' ? 'moon' : 'sun');
      b.title = mode === 'light' ? '切换到暗色模式' : '切换到亮色模式';
    }
  };
  applyTheme(localStorage.getItem(THEME_KEY) || 'light');
  $('#themeBtn').onclick = () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'); $('#logClose').onclick = () => toggleLogs(false);
  $('#logClear').onclick = () => { $('#logPre').innerHTML = ''; $('#logLines').textContent = ''; };
  $('#logCopy').onclick = () => navigator.clipboard.writeText($('#logPre').textContent).then(() => toast('日志已复制', 'ok'));
  $('#prompt').addEventListener('input', updateCount);
  $('#imageModel').addEventListener('input', renderModelOptions);
  $('#imageModel').addEventListener('change', renderModelOptions);
  $('#saveModelBtn').onclick = async () => {
    const m = $('#imageModel').value.trim();
    if (!m) return toast('请先输入模型名称或 owner/repo', 'err');
    try {
      const r = await post('api/models/recent', {model: m});
      S.recentModels = r.recent_models || [];
      renderModelOptions();
      toast('已保存到最近使用', 'ok');
    } catch(e){ toast(e.message, 'err'); }
  };
  const onModelChipClick = async e => {
    const rm = e.target.closest('[data-rm-model]');
    if (rm){
      e.stopPropagation();
      try {
        const r = await api('api/models/recent', {method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({model: rm.dataset.rmModel})});
        S.recentModels = r.recent_models || [];
        renderModelOptions();
      } catch(err){ toast(err.message, 'err'); }
      return;
    }
    const b = e.target.closest('[data-model]');
    if (!b) return;
    $('#imageModel').value = b.dataset.model;
    renderModelOptions();
    saveSoon();
  };
  $('#recentModelChips').onclick = onModelChipClick;
  $('#presetModelChips').onclick = onModelChipClick;
  $('#engDiffusers').onclick = () => setEngine('diffusers');
  $('#engComfy').onclick = () => setEngine('comfyui');
  ['comfyDiff','comfyTe','comfyVae'].forEach(id => $('#'+id).addEventListener('input', updateComfyLinkPreviews));
  $('#comfyBox').addEventListener('click', e => {
    const clr = e.target.closest('[data-clr]');
    if (clr){ const inp = $('#' + clr.dataset.clr); if (inp){ inp.value = ''; updateComfyLinkPreviews(); saveSoon(); inp.focus(); } return; }
    const q = e.target.closest('[data-qcfg]');
    if (q){
      const [st, cf, sm, sc] = q.dataset.qcfg.split(',');
      setNum('steps', +st); setNum('cfg', +cf);
      $('#comfySampler').value = sm; $('#comfyScheduler').value = sc;
      saveSoon(); toast(`已设为 ${st} 步 · CFG ${cf}`, 'ok');
    }
  });
  $('#comfyTemplate').addEventListener('change', () => {
    const cc = (S.cfg && S.cfg.comfy) || {};
    const tpl = (cc.templates || []).find(t => t.id === $('#comfyTemplate').value);
    if (tpl && tpl.defaults){
      if (tpl.defaults.text_encoder && !$('#comfyTe').value.trim()) $('#comfyTe').value = tpl.defaults.text_encoder;
      if (tpl.defaults.vae && !$('#comfyVae').value.trim()) $('#comfyVae').value = tpl.defaults.vae;
      if (tpl.defaults.sampler) $('#comfySampler').value = tpl.defaults.sampler;
      if (tpl.defaults.scheduler) $('#comfyScheduler').value = tpl.defaults.scheduler;
      updateComfyLinkPreviews();
    }
  });
  const onComfyPresetClick = async e => {
    const rm = e.target.closest('[data-rm-cp]');
    if (rm){
      e.stopPropagation();
      try {
        const r = await api('api/comfy/presets/' + encodeURIComponent(rm.dataset.rmCp), {method:'DELETE'});
        S.comfyPresets = r.presets || [];
        renderComfyPresets();
        toast('已删除该组合', 'ok');
      } catch(err){ toast(err.message, 'err'); }
      return;
    }
    const b = e.target.closest('[data-cp]'); if (!b) return;
    const all = [...((S.cfg && S.cfg.comfy && S.cfg.comfy.builtin_presets) || []), ...(S.comfyPresets || [])];
    const found = all.find(x => x.id === b.dataset.cp);
    if (found) applyComfyPreset(found);
  };
  $('#builtinComfyChips').onclick = onComfyPresetClick;
  $('#savedComfyChips').onclick = onComfyPresetClick;
  $('#saveComfyPresetBtn').onclick = () => {
    const m = modal(`
      <div class="mh">${I('layers','lg')}<h3>保存 ComfyUI 组合方案</h3><div class="grow"></div><button class="iconbtn" data-close>${I('x')}</button></div>
      <div class="mb">
        <label class="f" style="margin-top:0">方案名称</label>
        <input type="text" id="cpName" placeholder="例如：Omni BF16 + Turbo 8步" maxlength="60">
        <div class="help">将保存当前模板、三件套链接、采样器、步数、CFG、画幅与 LoRA。</div>
      </div>
      <div class="mf"><button class="btn" data-close>取消</button><button class="btn primary" id="cpSaveOk">保存</button></div>`);
    const inp = $('#cpName', m.el); inp.focus();
    const doSave = async () => {
      const name = inp.value.trim();
      if (!name) return toast('请填写方案名称', 'err');
      try {
        const r = await post('api/comfy/presets', {
          name,
          template: $('#comfyTemplate').value,
          diffusion: $('#comfyDiff').value.trim(),
          text_encoder: $('#comfyTe').value.trim(),
          vae: $('#comfyVae').value.trim(),
          sampler: $('#comfySampler').value,
          scheduler: $('#comfyScheduler').value,
          width: +$('#width').value,
          height: +$('#height').value,
          steps: +$('#steps').value,
          cfg: +$('#cfg').value,
          loras: collectLoras(),
        });
        S.comfyPresets = r.presets || [];
        renderComfyPresets();
        toast('已保存组合：' + name, 'ok');
        m.close();
      } catch(err){ toast(err.message, 'err'); }
    };
    $('#cpSaveOk', m.el).onclick = doSave;
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') doSave(); });
  };
  document.addEventListener('input', e => { if (e.target.closest('.panel')) saveSoon(); });
  document.addEventListener('change', e => { if (e.target.closest('.panel')) saveSoon(); });
  $('#useRef').addEventListener('change', () => { if ($('#useRef').checked) $('#chain').checked = false; updateRewriteBadge(); });
  $('#chain').addEventListener('change', () => { if ($('#chain').checked) $('#useRef').checked = false; updateRewriteBadge(); });
  [['steps','stepsR'],['cfg','cfgR'],['width','widthR'],['height','heightR']].forEach(([n, r]) => {
    $('#'+r).addEventListener('input', () => { $('#'+n).value = $('#'+r).value; if (n==='width'||n==='height'){ renderSizeChips(); updateResInfo(); } });
    $('#'+n).addEventListener('input', () => { $('#'+r).value = $('#'+n).value; if (n==='width'||n==='height'){ renderSizeChips(); updateResInfo(); } });
  });
  ['width','height'].forEach(id => $('#'+id).addEventListener('change', () => {
    const lim = S.cfg.limits; let v = Math.round((+$('#'+id).value || lim.size_min) / lim.size_step) * lim.size_step;
    v = Math.min(lim.size_max, Math.max(lim.size_min, v));
    $('#'+id).value = v; $('#'+id+'R').value = v; renderSizeChips(); updateResInfo();
  }));
  $('#sizeChips').onclick = e => { const b = e.target.closest('[data-w]'); if (!b) return; setNum('width', +b.dataset.w); setNum('height', +b.dataset.h); saveSoon(); };
  $('#gpuChips').onclick = e => {
    if (e.target.closest('[data-open-settings]')){ openSettings(); return; }
    const b = e.target.closest('[data-gpu]'); if (!b) return;
    const id = b.dataset.gpu;
    if (!ownedSessions().some(s => String(s.gpu).toUpperCase() === id)) return;
    S.gpu = id;
    S.gpuPool = [id];
    renderGpuChips();
    saveSoon();
  };
  $('#refreshGpuBtn').onclick = async () => {
    const b = $('#refreshGpuBtn'); b.disabled = true;
    try {
      const c = await api('api/colab/status');
      if (S.status) S.status.colab = c;
      renderColabChip(c); renderGpuChips();
      toast('已刷新 Colab 算力状态', 'ok');
    } catch(e){ toast(e.message, 'err'); }
    b.disabled = false;
  };
  $('#workflowChips').onclick = e => { const b = e.target.closest('[data-wf]'); if (!b) return; S.workflow = b.dataset.wf; renderWorkflowChips(); updateModeUI(); renderStage(); saveSoon(); };
  $('#frameChips').onclick = e => { const b = e.target.closest('[data-fr]'); if (!b) return; S.frames = +b.dataset.fr; renderFrameChips(); updateRewriteBadge(); saveSoon(); };
  $('#seedRand').onclick = () => { $('#seed').value = Math.floor(Math.random() * 2147483646); saveSoon(); };
  $('#seedAuto').onclick = () => { $('#seed').value = -1; saveSoon(); };
  $('#cntMinus').onclick = () => { $('#count').textContent = Math.max(1, +$('#count').textContent - 1); saveSoon(); };
  $('#cntPlus').onclick = () => { $('#count').textContent = Math.min(S.cfg.limits.count_max, +$('#count').textContent + 1); saveSoon(); };
  $('#loraRows').addEventListener('input', e => {
    const row = e.target.closest('.lora'); if (!row) return;
    if (e.target.classList.contains('lr')){
      const val = e.target.value.trim();
      if (/^https?:\/\//i.test(val) || val.includes('::')){
        const parsed = parseComfyLinkClient(val);
        if (parsed && parsed.ok && parsed.repo && parsed.repo !== '直链'){
          e.target.value = parsed.repo;
          $('.lf', row).value = parsed.file;
          toast('已自动拆分 LoRA 仓库与文件名', 'ok');
        }
      }
    }
    if (e.target.classList.contains('lsr')) $('.lsc', row).value = e.target.value;
    if (e.target.classList.contains('lsc')) $('.lsr', row).value = e.target.value;
    updateLoraHint();
  });
  $('#loraRows').addEventListener('click', async e => {
    const b = e.target.closest('.ls'); if (!b) return;
    const row = b.closest('.lora'); const repo = $('.lr', row).value.trim();
    if (!repo) return toast('先填写仓库 ID（owner/repo）', 'err');
    b.disabled = true; b.innerHTML = '<span class="sp"></span>';
    try {
      const r = await post('api/hf/list-loras', {repo_id: repo});
      $('datalist', row).innerHTML = r.files.map(f => `<option value="${esc(f)}">`).join('');
      if (r.files.length && !$('.lf', row).value) $('.lf', row).value = r.files[0];
      toast(`${repo}：找到 ${r.files.length} 个 .safetensors`, r.files.length ? 'ok' : '');
      saveSoon();
    } catch(err){ toast('扫描失败：' + err.message, 'err'); }
    b.disabled = false; b.textContent = '扫描';
  });
  bindDrop($('#dropFirst')); bindDrop($('#dropLast'));
  $('#refGrid').addEventListener('click', async e => {
    const rm = e.target.closest('[data-rmref]');
    if (rm){
      e.stopPropagation();
      const rid = rm.dataset.rmref;
      try {
        const r = await api('api/reference?id=' + encodeURIComponent(rid), {method:'DELETE'});
        if (r && r.references){
          renderRefs(r.references);
          if (!(r.references.items && r.references.items.length)) $('#useRef').checked = false;
        }
        saveSoon(); refresh();
      } catch(err){ toast(err.message, 'err'); }
      return;
    }
    if (e.target.closest('#refAddZone')){
      S.pickSlot = 'first'; S.pickAppend = true; $('#fileInput').multiple = true; $('#fileInput').click();
    }
  });
  $('#refGrid').addEventListener('dragover', e => { e.preventDefault(); const z = $('#refAddZone'); if (z) z.classList.add('over'); });
  $('#refGrid').addEventListener('dragleave', () => { const z = $('#refAddZone'); if (z) z.classList.remove('over'); });
  $('#refGrid').addEventListener('drop', e => {
    e.preventDefault(); const z = $('#refAddZone'); if (z) z.classList.remove('over');
    const rid = e.dataTransfer.getData('text/x-round');
    if (rid) return useAsRef(rid, 'first', true);
    if (e.dataTransfer.files && e.dataTransfer.files.length) uploadMultipleRefs(e.dataTransfer.files);
  });
  $('#refClearAll').onclick = async () => {
    const r = await api('api/reference?slot=first', {method:'DELETE'});
    if (r && r.references) renderRefs(r.references);
    $('#useRef').checked = false; saveSoon(); refresh();
  };
  $('#fileInput').onchange = e => {
    const files = [...(e.target.files || [])];
    e.target.value = '';
    if (!files.length) return;
    if (S.pickAppend && S.pickSlot !== 'last') uploadMultipleRefs(files);
    else uploadRef(S.pickSlot || 'first', files[0]);
  };
  document.addEventListener('paste', e => {
    const imgs = [...(e.clipboardData?.files || [])].filter(x => x.type.startsWith('image/'));
    if (!imgs.length) return;
    e.preventDefault();
    if (isMultiRefMode()) uploadMultipleRefs(imgs);
    else uploadRef('first', imgs[0]);
  });

  // stage
  $('#vImg').onclick = () => S.viewing && openLightbox(S.viewing);
  $('#vExpand').onclick = () => S.viewing && openLightbox(S.viewing);
  $('#vPrev').onclick = () => step(-1); $('#vNext').onclick = () => step(1);
  $('#aStar').onclick = () => { const it = current(); it && setStar([it.id], !it.starred); };
  $('#aRef').onclick = () => S.viewing && useAsRef(S.viewing, 'first');
  $('#aLast').onclick = () => S.viewing && useAsRef(S.viewing, 'last');
  $('#aToVideo').onclick = () => S.viewing && toVideo(S.viewing);
  $('#aReuse').onclick = async () => { const it = current(); if (!it) return; try { reuse(await api(`api/rounds/${it.id}/meta`)); } catch(e){ toast(e.message, 'err'); } };
  $('#aDel').onclick = () => S.viewing && deleteRounds([S.viewing]);
  $('#aHide').onclick = () => { S.viewing = null; renderStage(); renderGallery(); };
  $('#aCopy').onclick = () => { const it = current(); it && navigator.clipboard.writeText(it.prompt).then(() => toast('提示词已复制', 'ok')); };
  $('#galleryHead').onclick = () => setGalleryOpen(!S.galleryOpen);
  $('#emptyOpenGallery').onclick = () => { setGalleryOpen(true); $('#galleryCard').scrollIntoView({behavior:'smooth', block:'start'}); };
  $('#queueList').onclick = async e => {
    const b = e.target.closest('[data-unq],[data-retry]'); if (!b) return; b.disabled = true;
    try {
      if (b.dataset.retry) await post('api/queue/' + b.dataset.retry + '/retry');
      else await api('api/queue/' + b.dataset.unq, {method:'DELETE'});
      await refresh();
    } catch(err){ b.disabled = false; toast(err.message, 'err'); }
  };
  $('#queueClear').onclick = async () => { await post('api/queue/clear'); refresh(); };

  // gallery
  $('#importMediaBtn').onclick = () => $('#importMedia').click();
  $('#importMedia').onchange = async e => {
    const file = e.target.files[0]; e.target.value = ''; if (!file) return;
    const kind = file.type === 'video/mp4' || file.name.toLowerCase().endsWith('.mp4') ? 'video' : 'image';
    $('#importMediaBtn').disabled = true;
    try {
      const r = await api(`api/rounds/import?kind=${kind}&name=${encodeURIComponent(file.name)}`, {body:file});
      await loadGallery(); view(r.id, false);
    } catch(err){ toast(err.message, 'err'); }
    finally { $('#importMediaBtn').disabled = false; }
  };
  $('#grid').addEventListener('click', onTileClick);
  $('#grid').addEventListener('dblclick', e => { const t = e.target.closest('.tile'); if (t && !S.selecting) openLightbox(t.dataset.id); });
  $('#grid').addEventListener('dragstart', e => { const t = e.target.closest('.tile'); if (t) e.dataTransfer.setData('text/x-round', t.dataset.id); });
  $('#grid').addEventListener('mouseover', e => { const v = e.target.closest('.tile video'); if (v) v.play().catch(()=>{}); });
  $('#grid').addEventListener('mouseout', e => { const v = e.target.closest('.tile video'); if (v) v.pause(); });
  $('#filterChips').onclick = e => {
    const b = e.target.closest('[data-filter]'); if (!b) return; const k = b.dataset.filter;
    if (k === 'star'){ S.filter.starred = !S.filter.starred; S.filter.kind = ''; } else { S.filter.starred = false; S.filter.kind = k; }
    S.page = 60; renderGallery();
  };
  let qt; $('#gSearch').addEventListener('input', e => { clearTimeout(qt); qt = setTimeout(() => { S.filter.q = e.target.value; S.page = 60; renderGallery(); }, 150); });
  $('#moreBtn').onclick = () => { S.page += 60; renderGallery(); };
  $('#selBtn').onclick = () => { S.selecting = true; S.selected.clear(); renderGallery(); };
  $('#selDone').onclick = () => { S.selecting = false; S.selected.clear(); renderGallery(); };
  $('#selAll').onclick = () => { filtered().forEach(x => S.selected.add(x.id)); renderGallery(); };
  $('#selNone').onclick = () => { S.selected.clear(); renderGallery(); };
  $('#selStar').onclick = () => setStar([...S.selected], true);
  $('#selUnstar').onclick = () => setStar([...S.selected], false);
  $('#selDel').onclick = () => deleteRounds([...S.selected]);
  $('#cleanBtn').onclick = openCleanup;
  $('#trashBtn').onclick = openTrash;

  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter'){
      if (S.tab === 'workflow') return;
      e.preventDefault(); generate(); return;
    }
    if (e.target.matches('input,textarea,select') || $('#overlay').children.length) return;
    if (e.key === 'Escape'){ if (LB) closeLightbox(); else if (S.selecting) $('#selDone').click(); return; }
    if (e.key === 'ArrowLeft'){ const id = step(-1); if (LB) lbShow(id); }
    else if (e.key === 'ArrowRight'){ const id = step(1); if (LB) lbShow(id); }
    else if (e.key === 'Delete' || e.key === 'Backspace'){ if (S.selecting && S.selected.size) deleteRounds([...S.selected]); else if (S.viewing) deleteRounds([S.viewing]).then(ok => { if (ok && LB) S.viewing ? lbShow(S.viewing) : closeLightbox(); }); }
    else if (e.key.toLowerCase() === 's' && S.viewing){ const it = current(); setStar([it.id], !it.starred).then(() => LB && lbShow(it.id)); }
    else if (e.key.toLowerCase() === 'd' && S.viewing){ location.href = `api/rounds/${S.viewing}?download=1`; }
    else if (e.key.toLowerCase() === 'f' && S.viewing && !LB){ openLightbox(S.viewing); }
    else if (e.key.toLowerCase() === 'l'){ toggleLogs(); }
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  setInterval(() => { if (S.status) { renderProgress(S.status); renderIdleChip(S.status); } }, 1000);
}

async function init(){
  hydrateIcons();
  const mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  $('.go .kbd').textContent = mac ? '⌘↵' : 'Ctrl↵';
  const sh = $('#shortcutHint'); if (sh) sh.textContent = (mac ? '⌘' : 'Ctrl') + ' + Enter 生成';
  loadForm();
  loadPromptHistory();
  try { S.cfg = await api('api/config'); } catch(e){ toast('加载配置失败：' + e.message, 'err'); return; }
  if (S.cfg && S.cfg.limits && S.cfg.limits.prompt_max) $('#promptMax').textContent = S.cfg.limits.prompt_max;
  const c = S.form.common || {};
  const validGpus = new Set((S.cfg.gpus || []).map(g => g.id));
  const savedGrab = Array.isArray(c.grab_pool) ? c.grab_pool : (Array.isArray(c.gpu_pool) ? c.gpu_pool : []);
  S.grabPool = savedGrab.map(x => String(x || '').toUpperCase()).filter(x => validGpus.has(x));
  if (!S.grabPool.length) S.grabPool = [c.gpu && validGpus.has(c.gpu) ? c.gpu : S.cfg.defaults.gpu];
  S.gpu = S.grabPool[0];
  S.gpuPool = [S.gpu];
  const lim = S.cfg.limits || {};
  S.pollRounds = Math.max(lim.poll_rounds_min || 1, Math.min(lim.poll_rounds_max || 10, +c.pollRounds || S.cfg.defaults.poll_rounds || 2));
  S.pollAllProxies = !!c.pollAllProxies;
  S.workflow = c.workflow || S.cfg.defaults.video.workflow; S.frames = Math.max(S.cfg.limits.frames_min || 120, c.frames || S.cfg.defaults.video.num_frames);
  renderStaticOptions();
  $('#imageModel').value = S.cfg.defaults.image.model;
  $$('[data-p]').forEach(el => { if (c[el.id] !== undefined){ if (el.type === 'checkbox') el.checked = c[el.id]; else el.value = c[el.id]; } });
  if (!$('#imageModel').value.trim()) $('#imageModel').value = S.cfg.defaults.image.model;
  setEngine(c.engine === 'comfyui' ? 'comfyui' : 'diffusers');
  $('#count').textContent = c.count || 1;
  renderLoraRows(c.loras);
  S.mode = S.form.mode === 'video' ? 'video' : 'image';
  S.tab = S.mode;
  $('#mImage').classList.toggle('on', S.mode === 'image'); $('#mVideo').classList.toggle('on', S.mode === 'video');
  $('#wsImage').classList.toggle('on', S.mode === 'image'); $('#wsVideo').classList.toggle('on', S.mode === 'video');
  applyPerMode(S.mode);
  updateResInfo();
  renderStudioPresets();
  updateCount(); updateModeUI(); bind();
  if (collectLoras().length) $('#loraBlock').open = true;
  await refresh();
}
init();
"""

PAGE_HTML = (
    "<!doctype html>\n<html lang=\"zh\" data-theme=\"light\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
    "<title>Colab Studio · 生图 · 生视频 · 长视频工作流</title>\n"
    "<script>(function(){try{var t=localStorage.getItem('colab-studio.theme')||'light';document.documentElement.dataset.theme=t;}catch(e){}})();</script>\n"
    "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%238b5cf6'/%3E%3Cstop offset='1' stop-color='%2322d3ee'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='24' height='24' rx='6' fill='url(%23g)'/%3E%3Cpath d='M12 5l1.5 4 4 1.5-4 1.5L12 16l-1.5-4-4-1.5 4-1.5z' fill='white'/%3E%3C/svg%3E\">\n"
    "<style>" + _CSS + "</style>\n</head>\n<body>\n" + _BODY + "\n<script>" + _JS + "</script>\n</body>\n</html>\n"
)
