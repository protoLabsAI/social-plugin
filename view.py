"""The Social Studio console view — the content queue as a board.

A four-rules-compliant page (see the plugin-views guide): served PUBLIC at
``/plugins/social/view``, pulling GATED data from ``/api/plugins/social/*`` through
the design-system kit's slug-aware authed fetch, themed entirely from ``--pl-*``
tokens so it follows the console's light/dark.

The board earns its place by doing the one thing the chat transcript can't: showing
the whole pipeline at once, and putting a copy button on every approved post so
publishing by hand is a click per post rather than a hunt through scrollback.
"""

from __future__ import annotations

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Social Studio</title>
<style>
  html,body{margin:0;background:var(--pl-color-bg,#111);color:var(--pl-color-fg,#eee);
    font-family:var(--pl-font-sans,system-ui);font-size:13px}
  .wrap{padding:var(--pl-space-4,12px) var(--pl-space-5,16px);max-width:100%}
  header{display:flex;align-items:baseline;gap:var(--pl-space-3,8px);flex-wrap:wrap;
    margin-bottom:var(--pl-space-4,12px)}
  h1{font-size:15px;font-weight:600;margin:0}
  .brand{color:var(--pl-color-fg-muted,#999)}
  .spacer{flex:1}
  .pillars{display:flex;gap:var(--pl-space-3,8px);flex-wrap:wrap;
    color:var(--pl-color-fg-muted,#999);font-size:12px}
  .pillars b{color:var(--pl-color-fg,#eee);font-weight:600}
  .board{display:flex;gap:var(--pl-space-3,10px);align-items:flex-start;
    overflow-x:auto;padding-bottom:var(--pl-space-3,8px)}
  .col{flex:0 0 260px;min-width:260px;background:var(--pl-color-bg-subtle,#181818);
    border:1px solid var(--pl-color-border,#2a2a2a);border-radius:var(--pl-radius-md,8px);
    padding:var(--pl-space-3,8px)}
  .col h2{font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin:0 0 8px;
    color:var(--pl-color-fg-muted,#999);display:flex;justify-content:space-between}
  .card{background:var(--pl-color-bg,#111);border:1px solid var(--pl-color-border,#2a2a2a);
    border-radius:var(--pl-radius-sm,6px);padding:8px;margin-bottom:6px;cursor:pointer}
  .card:hover{border-color:var(--pl-color-border-strong,#3d3d3d)}
  .card .meta{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:5px;
    font-size:11px;color:var(--pl-color-fg-muted,#999)}
  .tag{border:1px solid var(--pl-color-border,#2a2a2a);border-radius:999px;padding:1px 7px;
    font-size:10px;letter-spacing:.03em}
  .tag.plat{color:var(--pl-color-accent,#9b87f2);border-color:var(--pl-color-accent,#9b87f2)}
  .body{white-space:pre-wrap;word-break:break-word;line-height:1.45;max-height:5.8em;overflow:hidden}
  .card.open .body{max-height:none}
  .score{margin-left:auto;font-variant-numeric:tabular-nums}
  .score.low{color:var(--pl-color-danger,#e5484d)}
  .score.mid{color:var(--pl-color-warning,#f5a524)}
  .score.high{color:var(--pl-color-success,#30a46c)}
  .actions{display:none;gap:6px;margin-top:8px}
  .card.open .actions{display:flex}
  button{font:inherit;font-size:11px;padding:3px 9px;cursor:pointer;
    background:var(--pl-color-bg-subtle,#181818);color:var(--pl-color-fg,#eee);
    border:1px solid var(--pl-color-border,#2a2a2a);border-radius:var(--pl-radius-sm,6px)}
  button:hover{border-color:var(--pl-color-accent,#9b87f2)}
  .empty{color:var(--pl-color-fg-muted,#999);font-size:12px;padding:6px 2px}
  .note{color:var(--pl-color-fg-muted,#999);font-size:12px;margin-top:10px}
  #err{display:block;margin-bottom:10px}
  #hold{display:block;margin-bottom:10px;border:1px solid var(--pl-color-danger,#e5484d);
    border-radius:var(--pl-radius-md,8px);padding:8px 10px;
    background:color-mix(in srgb, var(--pl-color-danger,#e5484d) 12%, transparent)}
  #hold b{color:var(--pl-color-danger,#e5484d)}
  [hidden]{display:none !important}
</style>
<script>
  var BASE = location.pathname.split("/plugins/")[0];
  (function(){ var l=document.createElement("link"); l.rel="stylesheet";
    l.href=BASE+"/_ds/plugin-kit.css"; document.head.appendChild(l); })();
</script>
</head><body><div class="wrap">
  <header>
    <h1>Social Studio</h1>
    <span class="brand" id="brand"></span>
    <span class="spacer"></span>
    <div class="pillars" id="pillars"></div>
  </header>
  <div id="err" class="pl-callout pl-callout--error" hidden></div>
  <div id="hold" hidden></div>
  <div class="board" id="board"></div>
  <div class="note" id="note"></div>
</div>
<script type="module">
  let kit;
  try { kit = await import(BASE + "/_ds/plugin-kit.js"); }
  catch (e) { kit = { initPluginView(){}, apiFetch: (p, i) => fetch(BASE + p, i) }; }

  const COLUMNS = ["idea", "drafted", "needs_edit", "approved", "scheduled", "posted"];
  const LABELS = { idea: "Ideas", drafted: "Drafted", needs_edit: "Needs edit",
                   approved: "Approved", scheduled: "Scheduled", posted: "Posted" };

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
    (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));

  function scoreClass(n){ return n >= 85 ? "high" : n >= 60 ? "mid" : "low"; }

  function card(p){
    const el = document.createElement("div");
    el.className = "card";
    const when = (p.scheduled_for || "").replace("T", " ").slice(0, 16);
    const bits = [`<span class="tag plat">${esc(p.platform)}</span>`];
    if (p.pillar) bits.push(`<span class="tag">${esc(p.pillar)}</span>`);
    if (when) bits.push(`<span>${esc(when)}</span>`);
    if (p.score) bits.push(`<span class="score ${scoreClass(p.score)}">${p.score}</span>`);
    const text = p.body || p.title || "(no copy yet)";
    el.innerHTML =
      `<div class="meta">${bits.join("")}</div>` +
      `<div class="body">${esc(text)}</div>` +
      `<div class="actions"><button data-copy="1">Copy</button>` +
      (p.hashtags ? `<button data-copy="2">Copy + hashtags</button>` : "") +
      `<span class="tag">#${p.id}</span></div>`;
    el.addEventListener("click", (ev) => {
      const btn = ev.target.closest("button");
      if (!btn) { el.classList.toggle("open"); return; }
      ev.stopPropagation();
      const payload = btn.dataset.copy === "2" ? `${p.body}\n\n${p.hashtags}` : (p.body || "");
      navigator.clipboard.writeText(payload).then(() => {
        const was = btn.textContent; btn.textContent = "Copied";
        setTimeout(() => { btn.textContent = was; }, 1200);
      }, () => {});
    });
    return el;
  }

  async function load(){
    const err = document.getElementById("err");
    try {
      const data = await kit.apiFetch("/api/plugins/social/queue").then(r => r.json());
      err.hidden = true;

      document.getElementById("brand").textContent = data.brand ? `· ${data.brand}` : "";

      // A hold is the most important thing on this page when it's on — nothing
      // queued should go out, and the board is where someone would look first.
      const holdEl = document.getElementById("hold");
      if (data.hold) {
        holdEl.hidden = false;
        holdEl.innerHTML = `<b>Queue held</b> since ${esc(data.hold.since)} — ${esc(data.hold.reason)}` +
          `<br>Nothing below should be published until the hold is lifted.`;
      } else {
        holdEl.hidden = true;
      }

      const pillars = Object.entries(data.pillars || {});
      document.getElementById("pillars").innerHTML = pillars.length
        ? pillars.map(([k, v]) => `<span><b>${v}</b> ${esc(k)}</span>`).join("")
        : "";

      const byStatus = {};
      for (const p of (data.posts || [])) (byStatus[p.status] ||= []).push(p);

      const board = document.getElementById("board");
      board.textContent = "";
      for (const status of COLUMNS){
        const posts = byStatus[status] || [];
        const col = document.createElement("div");
        col.className = "col";
        col.innerHTML = `<h2><span>${LABELS[status]}</span><span>${posts.length}</span></h2>`;
        if (!posts.length) col.insertAdjacentHTML("beforeend", `<div class="empty">—</div>`);
        for (const p of posts) col.appendChild(card(p));
        board.appendChild(col);
      }

      const total = (data.posts || []).length;
      document.getElementById("note").textContent = total
        ? "Click a card to expand it, then Copy to publish it by hand."
        : "Nothing queued yet. Ask the agent to plan a calendar or draft a post.";
    } catch (e) {
      err.hidden = false; err.textContent = "Could not load the queue: " + e;
    }
  }

  let booted = false;
  function boot(){ if (booted) return; booted = true; load(); setInterval(load, 20000); }
  kit.initPluginView(boot);
  setTimeout(boot, 800);
</script>
</body></html>
"""
