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
  <span class="chip" id="phaseChip"><span class="dot" id="phaseDot"></span><span id="phaseText">连接中…</span></span>
  <span class="chip hide hide-sm" id="idleChip" title="空闲后自动释放 Colab 运行时"><i data-i="clock"></i><span id="idleText"></span></span>
  <div class="grow"></div>
  <button class="chip" id="colabChip" title="Google Colab 账号与算力"><span class="dot" id="colabDot"></span><span id="colabText" class="hide-sm">Colab</span></button>
  <button class="btn sm danger hide" id="releaseBtn" title="立即释放所有 Colab 运行时，停止消耗 Compute Units"><i data-i="power"></i><span class="hide-sm">释放算力</span></button>
  <button class="iconbtn" id="themeBtn" title="切换亮色 / 暗色模式"><i data-i="moon"></i></button>
  <button class="iconbtn" id="logBtn" title="实时日志 (L)"><i data-i="terminal"></i><span class="badge hide" id="logBadge"></span></button>
  <button class="iconbtn" id="settingsBtn" title="设置"><i data-i="settings"></i></button>
  <a class="iconbtn" href="logout" title="退出登录"><i data-i="logout"></i></a>
</header>

<div class="layout">
  <aside class="panel">
    <div class="panel-scroll">
      <div class="seg">
        <button id="mImage" class="on"><i data-i="image"></i>生图 / 改图</button>
        <button id="mVideo"><i data-i="video"></i>生视频 + 音频</button>
      </div>

      <section class="block" id="modeBlock">
        <div class="bh"><i data-i="layers"></i><span id="modeBlockTitle">引擎与模型</span></div>
        <div id="imageModelWrap">
          <div class="eng-seg" role="tablist" aria-label="生图引擎">
            <button type="button" id="engDiffusers" class="on">Diffusers（整机）</button>
            <button type="button" id="engComfy">ComfyUI（三件套）</button>
          </div>
          <div id="diffusersBox">
            <label class="f">生图模型（支持任意 HF 仓库 ID）</label>
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
          <label class="f">MiniMax-H3 工作流（先选模式，下方自动匹配 3 段 / 6 段提示词）</label>
          <div class="chips" id="workflowChips"></div>
        </div>
        <div id="framesWrap" class="hide">
          <label class="f">时长（24 fps · 用于 H3 时间轴对齐）</label>
          <div class="chips" id="frameChips"></div>
        </div>
      </section>

      <section class="block" id="refBlock">
        <div class="bh"><i data-i="image"></i><span id="refTitle">参考图</span><span class="hint" id="refHint">点击 / 拖入 / 粘贴（可多选）</span></div>
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
          <label class="switch" title="自动以最新作品为参考图，适合连续修改"><input type="checkbox" id="chain" data-p><span class="tg"></span>接着改（自动用最新作品）</label>
        </div>
        <div class="help" id="refHelp"></div>
      </section>

      <section class="block" id="promptBlock">
        <div class="bh"><i data-i="sparkles"></i>创意与提示词<span class="hint" id="shortcutHint">Ctrl + Enter 生成</span></div>
        <div class="rw-badge" id="rewriteModeBadge">deepseek-flash · 自动适配当前模式</div>
        <label class="f">一句话想法（交给 deepseek-flash 看图 / 按 H3 规范改写）</label>
        <div class="row" style="align-items:stretch">
          <textarea id="idea" data-p rows="2" placeholder="例如：雨夜霓虹街头，撑透明雨伞的人回头微笑，电影感"></textarea>
        </div>
        <div class="row" style="margin-top:8px">
          <button class="btn sm" id="rewriteBtn"><i data-i="sparkles"></i>AI 改写为提示词</button>
          <span class="dim" style="font-size:12px" id="rewriteHint"></span>
        </div>
        <label class="f">提示词 Prompt</label>
        <textarea id="prompt" data-p placeholder="直接写英文 / 中文提示词，或点上方「AI 改写」生成标准分段提示词"></textarea>
        <div class="counter"><span id="promptCount">0</span> / <span id="promptMax">12000</span></div>
        <details id="negWrap">
          <summary class="dim" style="cursor:pointer;font-size:12px;margin-top:4px">负面提示词（可选）</summary>
          <textarea id="negative" data-p rows="2" style="margin-top:6px">blurry, lowres, jpeg artifacts, deformed, bad anatomy, watermark, text, logo, signature</textarea>
        </details>
      </section>

      <section class="block">
        <div class="bh"><i data-i="settings"></i>画幅与采样参数</div>
        <label class="f">画幅</label>
        <div class="chips" id="sizeChips"></div>
        <div class="g2" style="margin-top:8px">
          <div class="row"><span class="dim" style="font-size:12px;width:16px">W</span><input type="number" id="width" step="64" min="512" max="1536"></div>
          <div class="row"><span class="dim" style="font-size:12px;width:16px">H</span><input type="number" id="height" step="64" min="512" max="1536"></div>
        </div>

        <label class="f">采样步数 <span class="dim" id="stepsHint"></span></label>
        <div class="slider"><input type="range" id="stepsR" min="2" max="60"><input type="number" id="steps" min="2" max="60"></div>
        <label class="f">CFG / 引导强度</label>
        <div class="slider"><input type="range" id="cfgR" min="1" max="12" step="0.5"><input type="number" id="cfg" min="1" max="12" step="0.5"></div>
        <label class="f">种子（-1 = 每次随机）</label>
        <div class="row">
          <input type="number" id="seed" value="-1">
          <button class="iconbtn" id="seedRand" title="随机一个固定种子"><i data-i="dice"></i></button>
          <button class="iconbtn" id="seedAuto" title="改回 -1（每次随机）"><i data-i="reuse"></i></button>
        </div>
        <label class="switch hide" id="offloadWrap"><input type="checkbox" id="autoOffload" data-p checked><span class="tg"></span>自动 CPU Offload <small>显存不足时推荐</small></label>
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
        <div class="poll-bar">
          <div class="poll-row">
            <span>轮询次数</span>
            <input type="number" id="pollRounds" data-p min="1" max="10" value="2">
            <span>轮</span>
            <span class="poll-plan" id="pollSummary"></span>
          </div>
          <label class="switch" style="margin:0" title="开启后每轮依次切换全部已配置的代理（美国 / 新加坡 / 自定义，绝不直连）逐卡抢算力">
            <input type="checkbox" id="pollAllProxies" data-p>
            <span class="tg"></span>使用全部已配代理轮询
          </label>
        </div>
        <div class="help" id="gpuHelp"></div>
        <div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--line)">
          <div class="row" style="justify-content:space-between;margin-bottom:6px">
            <span class="mgroup-lbl" style="margin:0;color:var(--muted);font-weight:500">Colab 出口线路（不同地区机房库存不同）</span>
            <button type="button" class="btn sm" id="testProxyBtn" style="height:24px;padding:0 8px;font-size:11px">测出口</button>
          </div>
          <div class="chips" id="proxyChips"></div>
          <div id="customProxyWrap" class="hide" style="margin-top:8px">
            <div class="row">
              <input type="password" id="customProxyUrl" autocomplete="off" placeholder="http://user:pass@host:port 或 socks5://...">
              <button type="button" class="btn sm primary" id="saveCustomProxyBtn">启用</button>
            </div>
            <div class="help" id="customProxyHint">密码保存在服务器 0600 文件中，页面不会回显。</div>
          </div>
          <div class="help" id="proxyHelp"></div>
        </div>
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
          <button class="btn sm" id="selBtn"><i data-i="select"></i>多选</button>
          <button class="btn sm" id="cleanBtn"><i data-i="broom"></i>清理旧作品</button>
          <button class="btn sm" id="trashBtn" style="position:relative"><i data-i="trash"></i>回收站<span class="badge hide" id="trashBadge"></span></button>
        </div>
        <div class="selbar hide" id="selBar">
          <b id="selCount">已选 0</b>
          <button class="btn sm ghost" id="selAll">全选当前</button>
          <button class="btn sm ghost" id="selNone">清除选择</button>
          <div class="grow"></div>
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
  cfg:null, mode:'image', engine:'diffusers', status:null, logSeq:0, logCount:0, galleryRev:-1, gallery:[], stats:{},
  filter:{kind:'', starred:false, q:''}, page:60, viewing:null, followLatest:true,
  selecting:false, selected:new Set(), lastClicked:null, refs:{}, lastLatestId:null, form:{}, unseenLogs:0,
  comfyPresets:[], proxy:null, customProxyOpen:false, galleryOpen:false, galleryLoaded:false,
};
const LS_KEY = 'colab-studio.v2';
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
  f.common.count = +$('#count').textContent; f.common.gpu = S.gpu; f.common.gpu_pool = S.gpuPool; f.common.workflow = S.workflow; f.common.frames = S.frames;
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
function setNum(id, v){ $('#'+id).value = v; const r = $('#'+id+'R'); if (r) r.value = v; if (id==='width'||id==='height') renderSizeChips(); }

/* ── option rendering ── */
function renderStaticOptions(){
  const c = S.cfg;
  $('#ver').textContent = 'v' + c.version;
  S.recentModels = Array.isArray(c.recent_models) ? c.recent_models.slice() : [];
  const cc = c.comfy || {};
  S.comfyPresets = Array.isArray(cc.presets) ? cc.presets.slice() : [];
  S.proxy = c.proxy || null;
  $('#comfyTemplate').innerHTML = (cc.templates || []).map(t => `<option value="${esc(t.id)}">${esc(t.label)}</option>`).join('');
  $('#comfySampler').innerHTML = (cc.samplers || ['euler']).map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  $('#comfyScheduler').innerHTML = (cc.schedulers || ['simple']).map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  renderComfyPresets();
  renderProxyChips();
  renderModelOptions();
  renderGpuChips(); renderWorkflowChips(); renderFrameChips();
  const lim = c.limits;
  ['width','height'].forEach(id => { $('#'+id).min = lim.size_min; $('#'+id).max = lim.size_max; $('#'+id).step = lim.size_step; });
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
function renderGpuChips(){
  const co = (S.status && S.status.colab) || {};
  const elig = Array.isArray(co.eligible_gpus) ? co.eligible_gpus : [];
  const health = co.gpu_health || {};
  const running = new Set((co.sessions || []).map(s => String(s.gpu || '').toUpperCase()));
  const curTs = now();

  const statusFor = (id) => {
    if (running.has(id)) return ['运行中 · 可复用', 'run', true];
    const h = health[id];
    if (h && h.at){
      const ago = Math.max(0, Math.round((curTs - h.at) / 60));
      const agoTxt = ago < 1 ? '刚刚' : `${ago}m前`;
      if (h.status === 'unavailable') return [`近期缺货 · ${agoTxt}`, 'warn', true];
      if (h.status === 'error') return [`异常 ${h.code || ''} · ${agoTxt}`.trim(), 'bad', true];
      if (h.status === 'ok') return [`近期可用 · ${agoTxt}`, 'run', true];
    }
    if (elig.length){
      return elig.includes(id) ? ['账号可用', 'ok', true] : ['无权限', 'off', false];
    }
    return [co.authed ? '待查询' : '未连接', 'off', true];
  };

  const pool = Array.isArray(S.gpuPool) && S.gpuPool.length ? S.gpuPool : [S.gpu];
  $('#gpuChips').innerHTML = S.cfg.gpus.map(g => {
    const [badgeTxt, badgeCls, ok] = statusFor(g.id);
    const idx = pool.indexOf(g.id);
    const on = idx >= 0;
    return `<button type="button" class="gpu-item ${on?'on':''} ${ok?'':'dimmed'}" data-gpu="${g.id}" title="${esc(g.hint + '（点击勾选/取消，按序号轮询）')}">
      <span class="g-radio">${on ? (idx + 1) : ''}</span>
      <span class="g-main">
        <span class="g-top"><span>${esc(g.id)}</span><span class="g-vram">${g.vram}GB</span></span>
        <span class="g-sub">${esc(g.hint)}</span>
      </span>
      <span class="gpu-badge ${badgeCls}">${esc(badgeTxt)}</span>
    </button>`;
  }).join('');

  const cur = S.cfg.gpus.find(x => x.id === pool[0]) || S.cfg.gpus[0];
  const unavailCnt = S.cfg.gpus.filter(g => (health[g.id] || {}).status === 'unavailable').length;
  $('#gpuHint').textContent = running.size ? `${running.size} 台运行中` : pool.join(' → ');
  $('#gpuHelp').textContent = elig.length
    ? `点击勾选多张卡按序号轮询。账号支持 ${elig.join(' / ')}${unavailCnt ? `（近期 ${unavailCnt} 档报 503）` : ''}。`
    : cur.hint;
  updatePollSummary();
}
function updatePollSummary(){
  const el = $('#pollSummary'); if (!el) return;
  const pool = Array.isArray(S.gpuPool) && S.gpuPool.length ? S.gpuPool : [S.gpu];
  const rounds = Math.max(1, Math.min(10, +($('#pollRounds') && $('#pollRounds').value) || 1));
  const allPx = !!($('#pollAllProxies') && $('#pollAllProxies').checked);
  const pxCnt = allPx && S.proxy && Array.isArray(S.proxy.profiles)
    ? Math.max(1, S.proxy.profiles.filter(p => p.configured).length)
    : 1;
  el.textContent = `${pool.length} 卡 × ${pxCnt} 代理 × ${rounds} 轮`;
}
function renderProxyChips(){
  const px = S.proxy;
  if (!px || !Array.isArray(px.profiles)) return;
  const active = px.active || '';
  $('#proxyChips').innerHTML = px.profiles.map(p => {
    const on = active === p.id;
    const disabled = !p.configured && p.id !== 'custom';
    return `<button type="button" class="pchip ${on?'on':''}" data-proxy="${esc(p.id)}" ${disabled?'disabled style="opacity:.45;cursor:not-allowed"':''} title="${esc(p.hint + (p.masked ? ' · ' + p.masked : ''))}">${esc(p.label)}</button>`;
  }).join('');
  const cust = px.profiles.find(p => p.id === 'custom') || {};
  const showCust = S.customProxyOpen || active === 'custom';
  $('#customProxyWrap').classList.toggle('hide', !showCust);
  if (cust.configured) $('#customProxyHint').textContent = `当前已配置：${cust.masked}（输入新地址可覆盖）`;
  else $('#customProxyHint').textContent = '填入 http:// 或 socks5:// 代理，密码仅存服务器 0600 文件，不回显。';

  const curP = px.profiles.find(p => p.id === active);
  const lt = px.last_test;
  let txt = curP ? `当前出口：${curP.label}` : '尚未配置出口代理';
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

/* ── mode ── */
function setMode(m, {keep=false}={}){
  if (!keep && S.mode !== m) saveForm();
  S.mode = m;
  $('#mImage').classList.toggle('on', m === 'image');
  $('#mVideo').classList.toggle('on', m === 'video');
  if (!keep) applyPerMode(m);
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
      el.textContent = `deepseek-flash · H3 六段式 (Ref2VA · ${sec}s` + (items.length ? ` · 看 ${items.length} 张参考图)` : ')');
    } else if (S.workflow === 'fl2va'){
      const sub = items.length && hasLast ? 'FL2VA · 看首尾帧' : (items.length ? 'I2VA · 看首帧' : 'FL2VA');
      el.textContent = `deepseek-flash · H3 三段式 (${sub} · ${sec}s)`;
    } else {
      el.textContent = `deepseek-flash · H3 三段式 (T2VA · ${sec}s)`;
    }
  } else {
    if ($('#chain').checked) el.textContent = 'deepseek-flash · 多模态连续改图（看最新作品）';
    else if ($('#useRef').checked && items.length) el.textContent = `deepseek-flash · 多模态看图改写（看 ${items.length} 张参考图）`;
    else el.textContent = 'deepseek-flash · 文生图提示词改写';
  }
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
  const multi = isMultiRefMode();
  $('#refBlock').classList.toggle('hide', v && wf === 't2va');
  $('#multiRefWrap').classList.toggle('hide', !multi);
  $('#drops').classList.toggle('hide', multi);
  $('#dropLast').classList.toggle('hide', !(v && wf === 'fl2va'));
  $('#drops').classList.toggle('two', v && wf === 'fl2va');
  $('#refTitle').textContent = v ? (wf === 'fl2va' ? '首帧 / 尾帧' : '参考图（多图）') : '参考图（多图）';
  $('#refHint').textContent = multi ? '点击 / 拖入 / 粘贴（可多选）' : '点击 / 拖入 / 粘贴';
  $('#firstTtl').textContent = v ? (wf === 'fl2va' ? '首帧' : '参考图') : '参考图';
  $('#firstTtl').classList.toggle('hide', !(v && wf === 'fl2va'));
  const maxR = (S.refs && S.refs.max) || (S.cfg && S.cfg.limits && S.cfg.limits.refs_max) || 6;
  $('#refHelp').textContent = v
    ? (wf === 'fl2va' ? '首帧必填，尾帧可选；AI 改写会自动查看首尾帧。' : `最多可传 ${maxR} 张参考图，AI 改写会自动看图生成 6 段式 Ref2VA 提示词。`)
    : `最多可传 ${maxR} 张参考图；勾选「用参考图改图」后 AI 改写会自动看图。`;
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
  $('#rewriteHint').textContent = 'deepseek-flash 正在生成…';
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
      ref_count,
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
  const pool = Array.isArray(S.gpuPool) && S.gpuPool.length ? S.gpuPool.slice() : [S.gpu];
  const p = {
    mode:S.mode, gpu:pool[0], gpu_pool:pool,
    poll_rounds: Math.max(1, Math.min(10, +($('#pollRounds') && $('#pollRounds').value) || 1)),
    poll_all_proxies: !!($('#pollAllProxies') && $('#pollAllProxies').checked),
    prompt:$('#prompt').value.trim(), negative:$('#negative').value, idea:$('#idea').value.trim(),
    width:+$('#width').value, height:+$('#height').value, steps:+$('#steps').value, cfg:+$('#cfg').value,
    seed: $('#seed').value === '' ? -1 : +$('#seed').value, count:+$('#count').textContent, loras:collectLoras(),
  };
  if (v){
    p.workflow = S.workflow; p.num_frames = S.frames; p.auto_offload = $('#autoOffload').checked;
    p.has_image = S.workflow !== 't2va'; p.has_last_image = S.workflow === 'fl2va' && !!(S.refs.last && S.refs.last.set);
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
  const p = buildPayload();
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
    S.followLatest = true;
    toast(r.jobs.length > 1 ? `已加入队列：${r.jobs.length} 个任务` : '任务已提交', 'ok');
    saveForm();
  } catch(e){ toast(e.message, 'err'); }
  b.disabled = false; refresh();
}
function updateGoState(){
  const st = S.status; const authed = st && st.colab && st.colab.authed;
  const busy = st && (st.current || (st.queue||[]).length);
  $('#goText').textContent = !authed && st ? '先在设置里连接 Colab' : busy ? '加入队列' : (S.mode === 'video' ? '生成视频' : '开始生成');
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
  const st = S.status; const busy = st && (st.current || (st.queue||[]).length || st.phase === 'stopping');
  pollT = setTimeout(refresh, document.hidden ? 10000 : busy || !$('#logDock').classList.contains('hide') ? 1200 : 3500);
}
function renderStatus(st){
  const [label, cls] = PHASE[st.phase] || [st.phase, ''];
  $('#phaseText').textContent = label + (st.active_gpu ? ' · ' + st.active_gpu : '');
  $('#phaseDot').className = 'dot ' + cls;
  $('#phaseChip').title = st.error || '';
  if (st.idle_deadline && !st.current){ $('#idleChip').classList.remove('hide'); $('#idleText').textContent = dur(st.idle_deadline - now()) + ' 后释放'; }
  else $('#idleChip').classList.add('hide');
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
  $('#queueBox').classList.toggle('hide', !q.length);
  $('#queueCount').textContent = q.length ? ` · ${q.length} 个等待中` : '';
  $('#queueList').innerHTML = q.map((j, i) => `<div class="qrow"><span class="n">${i+1}</span>${I(j.mode==='video'?'video':'image')}
    <span class="p">${esc(j.prompt)}</span><span class="dim">${j.width}×${j.height} · seed ${j.seed}</span>
    <button class="iconbtn" data-unq="${j.id}" title="移出队列">${I('x')}</button></div>`).join('');
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
  add('种子', it.seed); add('帧数', it.num_frames); add('GPU', it.gpu); add('用时', it.duration_s && dur(it.duration_s));
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
  if (it.kind === 'video'){ if (m.workflow){ S.workflow = m.workflow; renderWorkflowChips(); } if (m.num_frames){ S.frames = m.num_frames; renderFrameChips(); } }
  if (m.width) setNum('width', m.width); if (m.height) setNum('height', m.height);
  if (m.steps) setNum('steps', m.steps); if (m.cfg) setNum('cfg', m.cfg);
  if (m.seed !== undefined) $('#seed').value = m.seed;
  if (m.gpu){ S.gpu = m.gpu; S.gpuPool = [m.gpu]; renderGpuChips(); }
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
  const el = m.el; let plan = null; let t;
  const body = () => ({
    older_than_days: $('#cDaysOn', el).checked ? +$('#cDays', el).value : null,
    keep_latest: $('#cKeepOn', el).checked ? +$('#cKeep', el).value : null,
    kind: $('#cKind', el).value, include_starred: $('#cStar', el).checked, permanent: $('#cPerm', el).checked,
  });
  const preview = async () => {
    const b = body();
    $('#cWarn', el).classList.toggle('hide', !b.permanent);
    if (b.older_than_days === null && b.keep_latest === null){ $('#cPrev', el).textContent = '请至少勾选一个条件'; $('#cGo', el).disabled = true; return; }
    try {
      plan = await post('api/rounds/cleanup', {...b, dry_run:true});
      const thumbs = plan.matched.slice(0, 14).map(id => { const it = S.gallery.find(x => x.id === id); const u = it && thumbUrl(it);
        return u ? `<img src="${u}" title="#${+id}">` : `<div class="mv">${I('play')}</div>`; }).join('');
      $('#cPrev', el).innerHTML = plan.count
        ? `将${b.permanent ? '<b style="color:#fca5a5">永久</b>' : '移入回收站并'}删除 <b>${plan.count}</b> 个作品，释放 <b>${fmtBytes(plan.bytes)}</b>${b.include_starred ? '' : '（收藏的作品不受影响）'}<div class="mini">${thumbs}${plan.count > 14 ? `<div class="mv">+${plan.count-14}</div>` : ''}</div>`
        : '没有符合条件的作品 🎉';
      $('#cGo', el).disabled = !plan.count;
      $('#cGo', el).innerHTML = I('trash') + (plan.count ? `删除 ${plan.count} 个` : '删除');
    } catch(e){ $('#cPrev', el).textContent = e.message; $('#cGo', el).disabled = true; }
  };
  $$('input,select', el).forEach(i => i.addEventListener('input', () => { clearTimeout(t); t = setTimeout(preview, 250); }));
  $('#cGo', el).onclick = async () => {
    const b = body();
    if (b.permanent && !(await confirmBox({title:`永久删除 ${plan.count} 个作品？`, body:'这些文件会被立即删除，无法恢复。', ok:'永久删除', danger:true}))) return;
    try {
      const r = await post('api/rounds/cleanup', {...b, dry_run:false});
      m.close();
      toast(`已清理 ${(r.deleted||[]).length} 个作品，释放 ${fmtBytes(r.bytes)}`, 'ok', b.permanent ? null : {label:'撤销', fn: () => restoreRounds(r.deleted)});
      await loadGallery();
    } catch(e){ toast(e.message, 'err'); }
  };
  preview();
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
      <div class="sect"><h4>${I('clock')}空闲自动释放</h4>
        <div class="help" style="margin:0 0 8px">最后一个任务结束后，空闲多久自动释放 Colab 运行时（停止消耗 CU）。</div>
        <div class="chips" id="sIdle">${[5,10,20,30,60].map(n => `<button class="pchip ${S.status && S.status.idle_minutes===n?'on':''}" data-idle="${n}">${n} 分钟</button>`).join('')}</div></div>
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
  $('#sIdle', scrim).onclick = async e => {
    const b = e.target.closest('[data-idle]'); if (!b) return;
    try { const r = await post('api/settings', {idle_minutes: +b.dataset.idle}); $$('[data-idle]', scrim).forEach(x => x.classList.toggle('on', x === b)); toast(`空闲 ${r.idle_minutes} 分钟后自动释放`, 'ok'); refresh(); }
    catch(e){ toast(e.message, 'err'); }
  };
}

/* ── wiring ── */
function bind(){
  $('#mImage').onclick = () => setMode('image');
  $('#mVideo').onclick = () => setMode('video');
  $('#rewriteBtn').onclick = rewrite;
  $('#goBtn').onclick = generate;
  $('#stopBtn').onclick = $('#pCancel').onclick = async () => { await post('api/stop'); toast('已发送取消信号'); refresh(); };
  $('#releaseBtn').onclick = async () => {
    if (!(await confirmBox({title:'释放全部 Colab 算力？', body:'会立即销毁所有运行中的 Colab 实例并清空队列，模型缓存随之丢失，下次生成需要重新加载。', ok:'立即释放', danger:true}))) return;
    await post('api/release'); toast('正在释放…'); refresh();
  };
  $('#settingsBtn').onclick = $('#colabChip').onclick = openSettings;
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
  [['steps','stepsR'],['cfg','cfgR']].forEach(([n, r]) => {
    $('#'+r).addEventListener('input', () => $('#'+n).value = $('#'+r).value);
    $('#'+n).addEventListener('input', () => $('#'+r).value = $('#'+n).value);
  });
  ['width','height'].forEach(id => $('#'+id).addEventListener('change', () => {
    const lim = S.cfg.limits; let v = Math.round((+$('#'+id).value || lim.size_min) / lim.size_step) * lim.size_step;
    $('#'+id).value = Math.min(lim.size_max, Math.max(lim.size_min, v)); renderSizeChips();
  }));
  $('#sizeChips').onclick = e => { const b = e.target.closest('[data-w]'); if (!b) return; setNum('width', +b.dataset.w); setNum('height', +b.dataset.h); saveSoon(); };
  $('#gpuChips').onclick = e => {
    const b = e.target.closest('[data-gpu]'); if (!b) return;
    const id = b.dataset.gpu;
    const pool = Array.isArray(S.gpuPool) && S.gpuPool.length ? S.gpuPool.slice() : [S.gpu];
    const idx = pool.indexOf(id);
    if (idx >= 0){
      if (pool.length <= 1){ toast('至少保留 1 张候选 GPU', 'err'); return; }
      pool.splice(idx, 1);
    } else {
      pool.push(id);
    }
    S.gpuPool = pool; S.gpu = pool[0];
    renderGpuChips(); saveSoon();
  };
  $('#pollRounds').addEventListener('input', updatePollSummary);
  $('#pollRounds').addEventListener('change', () => {
    const lim = S.cfg.limits;
    $('#pollRounds').value = Math.max(lim.poll_rounds_min || 1, Math.min(lim.poll_rounds_max || 10, +$('#pollRounds').value || 1));
    updatePollSummary(); saveSoon();
  });
  $('#pollAllProxies').addEventListener('change', () => { updatePollSummary(); saveSoon(); });
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
  $('#proxyChips').onclick = async e => {
    const b = e.target.closest('[data-proxy]'); if (!b || b.disabled) return;
    const pid = b.dataset.proxy;
    if (pid === 'custom'){
      const cust = (S.proxy && S.proxy.profiles || []).find(p => p.id === 'custom');
      S.customProxyOpen = true;
      renderProxyChips();
      if (!cust || !cust.configured){ $('#customProxyUrl').focus(); return; }
    } else {
      S.customProxyOpen = false;
    }
    try {
      const r = await post('api/proxy', {active: pid});
      S.proxy = r;
      renderProxyChips();
      const lbl = (r.profiles.find(p => p.id === pid) || {}).label || pid;
      toast('已切换出口为 ' + lbl, 'ok');
      refresh();
    } catch(err){ toast(err.message, 'err'); }
  };
  $('#saveCustomProxyBtn').onclick = async () => {
    const url = $('#customProxyUrl').value.trim();
    if (!url) return toast('请先输入代理地址', 'err');
    const b = $('#saveCustomProxyBtn'); b.disabled = true;
    try {
      const r = await post('api/proxy', {active: 'custom', custom_url: url});
      S.proxy = r;
      $('#customProxyUrl').value = '';
      renderProxyChips();
      toast('自定义代理已保存并启用', 'ok');
      refresh();
    } catch(err){ toast(err.message, 'err'); }
    b.disabled = false;
  };
  $('#testProxyBtn').onclick = async () => {
    const b = $('#testProxyBtn'); b.disabled = true; b.textContent = '测试中…';
    try {
      const r = await post('api/proxy/test', {});
      if (S.proxy) S.proxy.last_test = r;
      renderProxyChips();
      if (r.ok) toast(`出口正常：${r.loc} / ${r.colo}（${r.ms}ms）`, 'ok');
      else toast('出口测试失败：' + r.error, 'err');
    } catch(err){ toast(err.message, 'err'); }
    b.disabled = false; b.textContent = '测出口';
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
  $('#queueList').onclick = async e => { const b = e.target.closest('[data-unq]'); if (!b) return; try { await api('api/queue/' + b.dataset.unq, {method:'DELETE'}); refresh(); } catch(err){ toast(err.message, 'err'); } };
  $('#queueClear').onclick = async () => { await post('api/queue/clear'); refresh(); };

  // gallery
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
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter'){ e.preventDefault(); generate(); return; }
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
  setInterval(() => { if (S.status) { renderProgress(S.status); if (S.status.idle_deadline && !S.status.current) $('#idleText').textContent = dur(S.status.idle_deadline - now()) + ' 后释放'; } }, 1000);
}

async function init(){
  hydrateIcons();
  const mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  $('.go .kbd').textContent = mac ? '⌘↵' : 'Ctrl↵';
  const sh = $('#shortcutHint'); if (sh) sh.textContent = (mac ? '⌘' : 'Ctrl') + ' + Enter 生成';
  loadForm();
  try { S.cfg = await api('api/config'); } catch(e){ toast('加载配置失败：' + e.message, 'err'); return; }
  if (S.cfg && S.cfg.limits && S.cfg.limits.prompt_max) $('#promptMax').textContent = S.cfg.limits.prompt_max;
  const c = S.form.common || {};
  const validGpus = new Set((S.cfg.gpus || []).map(g => g.id));
  const savedPool = Array.isArray(c.gpu_pool) ? c.gpu_pool.filter(x => validGpus.has(x)) : [];
  S.gpuPool = savedPool.length ? savedPool : [c.gpu && validGpus.has(c.gpu) ? c.gpu : S.cfg.defaults.gpu];
  S.gpu = S.gpuPool[0]; S.workflow = c.workflow || S.cfg.defaults.video.workflow; S.frames = Math.max(S.cfg.limits.frames_min || 120, c.frames || S.cfg.defaults.video.num_frames);
  renderStaticOptions();
  $('#imageModel').value = S.cfg.defaults.image.model;
  $$('[data-p]').forEach(el => { if (c[el.id] !== undefined){ if (el.type === 'checkbox') el.checked = c[el.id]; else el.value = c[el.id]; } });
  if (!$('#imageModel').value.trim()) $('#imageModel').value = S.cfg.defaults.image.model;
  setEngine(c.engine === 'comfyui' ? 'comfyui' : 'diffusers');
  $('#count').textContent = c.count || 1;
  renderLoraRows(c.loras);
  S.mode = S.form.mode === 'video' ? 'video' : 'image';
  $('#mImage').classList.toggle('on', S.mode === 'image'); $('#mVideo').classList.toggle('on', S.mode === 'video');
  applyPerMode(S.mode);
  updateCount(); updateModeUI(); bind();
  if (collectLoras().length) $('#loraBlock').open = true;
  await refresh();
}
init();
"""

PAGE_HTML = (
    "<!doctype html>\n<html lang=\"zh\" data-theme=\"light\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
    "<title>Colab Studio · 生图 · 改图 · 生视频</title>\n"
    "<script>(function(){try{var t=localStorage.getItem('colab-studio.theme')||'light';document.documentElement.dataset.theme=t;}catch(e){}})();</script>\n"
    "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%238b5cf6'/%3E%3Cstop offset='1' stop-color='%2322d3ee'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='24' height='24' rx='6' fill='url(%23g)'/%3E%3Cpath d='M12 5l1.5 4 4 1.5-4 1.5L12 16l-1.5-4-4-1.5 4-1.5z' fill='white'/%3E%3C/svg%3E\">\n"
    "<style>" + _CSS + "</style>\n</head>\n<body>\n" + _BODY + "\n<script>" + _JS + "</script>\n</body>\n</html>\n"
)
