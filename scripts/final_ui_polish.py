from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

html = path.read_text(encoding="utf-8")

# Rebuild the desktop header from one authoritative block. This removes all
# previous layered header CSS/JS revisions without touching the rest of UI.
for pattern in (
    r'\s*<style id="dport-header-final-v[0-9]+">.*?</style>\s*',
    r'\s*<style id="dport-top-header-final-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-top-header-final-v[0-9]+-script">.*?</script>\s*',
    r'\s*<style id="dport-top-header-layout-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-top-header-layout-script-v[0-9]+">.*?</script>\s*',
    r'\s*<style id="dport-ultra-header-layout-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-ultra-header-layout-v[0-9]+-script">.*?</script>\s*',
    r'\s*<style id="dport-ultra-header-notification-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-ultra-header-notification-v[0-9]+-script">.*?</script>\s*',
):
    html = re.sub(pattern, "\n", html, flags=re.S)

# Remove any persistent notification card from old header experiments.
html = re.sub(
    r'\s*<div[^>]*id=["\']dport-persistent-notification["\'][\s\S]*?</div>\s*',
    "\n", html, flags=re.I
)

# Update-check wording only. The updater still decides when the result is shown.
html = html.replace("（GitHub 最新正式版）", "（最新）")
html = html.replace("DPort：檢查 GitHub 最新正式版…", "DPort：檢查更新中…")
html = re.sub(r'DPort：v\d+\.\d+\.\d+（最新）', '', html)

css = "\n<style id=\"dport-final-ui-polish-v8\">\n:root{\n    --dport-panel:#2a3240;\n    --dport-panel-hover:#323c4e;\n    --dport-border:#5d6c88;\n    --dport-border-hover:#8295bd;\n    --dport-text:#f7f9fc;\n    --dport-muted:#aeb8ca;\n    --dport-blue:#5669e7;\n    --dport-blue-hover:#697bf4;\n    --dport-action-bg:rgba(67,78,98,.66);\n    --dport-action-hover:rgba(87,101,126,.84);\n    --dport-action-border:rgba(127,143,171,.72);\n    --dport-action-text:#edf2fa;\n}\n\n/* DPort application buttons. Map controls are intentionally excluded. */\nbody button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a){\n    box-sizing:border-box !important;\n    font-family:inherit !important;\n    font-weight:700 !important;\n    border-radius:10px !important;\n    transition:\n        background .16s ease,\n        border-color .16s ease,\n        color .16s ease,\n        box-shadow .16s ease,\n        transform .16s ease !important;\n}\nbody button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a):hover{\n    transform:translateY(-1px) !important;\n}\nbody button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a):active{\n    transform:translateY(0) !important;\n}\nbody button:disabled{\n    opacity:.48 !important;\n    cursor:not-allowed !important;\n    transform:none !important;\n}\n\n/* Dark blue-gray utility / clear family. */\n#geoport-copy-coordinates,\n#geoport-load-last,\n#geoport-clear-coordinates,\n.geoport-recent-delete-selected,\n.geoport-recent-clear,\n.geoport-fav-clear-all{\n    background:var(--dport-action-bg) !important;\n    border:1px solid var(--dport-action-border) !important;\n    color:var(--dport-action-text) !important;\n    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;\n}\n#geoport-copy-coordinates:hover,\n#geoport-load-last:hover,\n#geoport-clear-coordinates:hover,\n.geoport-recent-delete-selected:hover,\n.geoport-recent-clear:hover,\n.geoport-fav-clear-all:hover{\n    background:var(--dport-action-hover) !important;\n    border-color:var(--dport-border-hover) !important;\n    color:#fff !important;\n    box-shadow:0 6px 15px rgba(0,0,0,.18) !important;\n}\n\n/* Favorite section. */\n.geoport-favorites-title{\n    display:flex !important;\n    align-items:center !important;\n    justify-content:space-between !important;\n    gap:10px !important;\n    margin:14px 0 8px !important;\n}\n.geoport-favorites-actions{\n    display:flex !important;\n    align-items:center !important;\n}\n.geoport-fav-count{\n    color:var(--dport-muted) !important;\n    font-size:13px !important;\n    font-weight:700 !important;\n}\n.geoport-fav-list{\n    display:grid !important;\n    grid-template-columns:repeat(2,minmax(0,1fr)) !important;\n    grid-template-rows:repeat(3,68px) !important;\n    grid-auto-rows:68px !important;\n    gap:8px !important;\n    padding:9px !important;\n    margin:0 !important;\n    height:236px !important;\n    max-height:236px !important;\n    overflow-y:auto !important;\n    overflow-x:hidden !important;\n    border:1px solid #46536b !important;\n    border-radius:14px !important;\n    background:rgba(29,35,47,.74) !important;\n    scrollbar-width:thin !important;\n    scrollbar-color:#68758d transparent !important;\n}\n.geoport-fav-list::-webkit-scrollbar{width:7px}\n.geoport-fav-list::-webkit-scrollbar-track{background:transparent}\n.geoport-fav-list::-webkit-scrollbar-thumb{background:#68758d;border-radius:999px}\n\n.geoport-fav-card{\n    position:relative !important;\n    width:100% !important;\n    height:68px !important;\n    min-width:0 !important;\n    min-height:68px !important;\n    overflow:hidden !important;\n    border-radius:11px !important;\n}\n.geoport-fav-open{\n    position:absolute !important;\n    inset:0 !important;\n    width:100% !important;\n    height:100% !important;\n    min-height:0 !important;\n    box-sizing:border-box !important;\n    display:flex !important;\n    align-items:center !important;\n    justify-content:flex-start !important;\n    text-align:left !important;\n    padding:8px 28px 8px 13px !important;\n    border:1px solid #5d6c88 !important;\n    border-radius:11px !important;\n    background:var(--dport-panel) !important;\n    color:var(--dport-text) !important;\n    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;\n    overflow:hidden !important;\n    z-index:1 !important;\n}\n.geoport-fav-open:hover{\n    background:var(--dport-panel-hover) !important;\n    border-color:var(--dport-border-hover) !important;\n    box-shadow:0 7px 16px rgba(0,0,0,.20) !important;\n}\n.geoport-fav-name{\n    display:-webkit-box !important;\n    width:100% !important;\n    max-width:100% !important;\n    margin:0 !important;\n    padding:0 !important;\n    color:var(--dport-text) !important;\n    font-size:15px !important;\n    font-weight:700 !important;\n    line-height:1.17 !important;\n    white-space:normal !important;\n    overflow:hidden !important;\n    text-overflow:clip !important;\n    -webkit-box-orient:vertical !important;\n    -webkit-line-clamp:2 !important;\n    overflow-wrap:anywhere !important;\n}\n.geoport-fav-name.long{font-size:14px !important}\n.geoport-fav-name.xlong{font-size:12.5px !important;line-height:1.08 !important}\n.geoport-fav-detail{display:none !important}\n\n/* Keep a comfortable click target, but show the X as a small chip in the\n   bottom-right INSIDE the card. */\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete{\n    position:absolute !important;\n    top:auto !important;\n    left:auto !important;\n    right:2px !important;\n    bottom:2px !important;\n    width:30px !important;\n    min-width:30px !important;\n    max-width:30px !important;\n    height:30px !important;\n    min-height:30px !important;\n    max-height:30px !important;\n    margin:0 !important;\n    padding:0 !important;\n    border:0 !important;\n    border-radius:8px !important;\n    background:transparent !important;\n    color:transparent !important;\n    font-size:0 !important;\n    line-height:0 !important;\n    box-shadow:none !important;\n    overflow:visible !important;\n    transform:none !important;\n    z-index:20 !important;\n    cursor:pointer !important;\n}\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::before{\n    content:'' !important;\n    position:absolute !important;\n    right:6px !important;\n    bottom:6px !important;\n    width:18px !important;\n    height:18px !important;\n    border-radius:5px !important;\n    background:rgba(67,78,98,.70) !important;\n    border:1px solid rgba(127,143,171,.72) !important;\n    box-sizing:border-box !important;\n    box-shadow:0 2px 6px rgba(0,0,0,.15) !important;\n}\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::after{\n    content:'×' !important;\n    position:absolute !important;\n    right:6px !important;\n    bottom:6px !important;\n    width:18px !important;\n    height:18px !important;\n    display:flex !important;\n    align-items:center !important;\n    justify-content:center !important;\n    color:#edf2fa !important;\n    font-size:12px !important;\n    line-height:18px !important;\n    font-weight:800 !important;\n}\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::before{\n    background:rgba(87,101,126,.88) !important;\n    border-color:#8fa1c1 !important;\n}\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::after{\n    color:#ffffff !important;\n}\n\n/* Favorite clear-all button stays compact and in the same blue-gray family. */\n.geoport-fav-clear-all{\n    min-width:56px !important;\n    min-height:38px !important;\n    height:38px !important;\n    padding:5px 13px !important;\n    border-radius:9px !important;\n}\n\n/* Top-right status notification, always clipped inside the map frame. */\n#dport-map-status-overlay{\n    position:absolute !important;\n    top:8px !important;\n    right:8px !important;\n    left:auto !important;\n    bottom:auto !important;\n    z-index:900 !important;\n    width:min(320px,34%) !important;\n    max-width:calc(100% - 16px) !important;\n    min-width:0 !important;\n    margin:0 !important;\n    padding:0 !important;\n    box-sizing:border-box !important;\n    pointer-events:none !important;\n    overflow:hidden !important;\n}\n#dport-map-status-overlay > *{\n    width:100% !important;\n    max-width:100% !important;\n    min-width:0 !important;\n    box-sizing:border-box !important;\n    padding:7px 10px !important;\n    margin:0 !important;\n    background:rgba(31,38,50,.93) !important;\n    border:1px solid rgba(92,108,137,.84) !important;\n    border-radius:9px !important;\n    color:#f5f7fb !important;\n    box-shadow:0 7px 18px rgba(0,0,0,.22) !important;\n    backdrop-filter:blur(7px) !important;\n    overflow:hidden !important;\n    font-size:13px !important;\n    line-height:1.3 !important;\n}\n#dport-map-status-overlay > * *{\n    max-width:100% !important;\n    font-size:13px !important;\n    line-height:1.3 !important;\n    overflow:hidden !important;\n    text-overflow:ellipsis !important;\n}\n@media (max-width:1100px){\n    #dport-map-status-overlay{\n        width:min(280px,42%) !important;\n    }\n    #dport-map-status-overlay > *,\n    #dport-map-status-overlay > * *{\n        font-size:12px !important;\n    }\n}\n@media (max-width:700px){\n    #dport-map-status-overlay{\n        top:6px !important;\n        right:6px !important;\n        width:min(245px,56%) !important;\n        max-width:calc(100% - 12px) !important;\n    }\n}\n</style>\n"
favorites_js = "\n<script id=\"dport-final-favorites-render-v8\">\n(function(){\n    function renderFavorites(){\n        var box=document.getElementById('geoport-favorites');\n        if(!box || typeof geoportGetFavorites!=='function') return;\n        var items=geoportGetFavorites() || [];\n        box.innerHTML='';\n\n        var count=document.getElementById('geoport-fav-count');\n        if(count) count.textContent=items.length + '/20';\n\n        if(!items.length){\n            box.innerHTML='<div class=\"geoport-fav-empty\">還沒有儲存的位置</div>';\n            return;\n        }\n\n        items.forEach(function(item,index){\n            var card=document.createElement('div');\n            card.className='geoport-fav-card';\n\n            var open=document.createElement('button');\n            open.type='button';\n            open.className='geoport-fav-open';\n            open.title='前往 ' + String(item.name || '未命名位置');\n\n            var name=document.createElement('span');\n            name.className='geoport-fav-name';\n            var text=String(item.name || '未命名位置');\n            if(text.length > 16) name.classList.add('long');\n            if(text.length > 28) name.classList.add('xlong');\n            name.textContent=text;\n\n            open.appendChild(name);\n            open.onclick=function(){\n                geoportSetMapOnlyCoordinates(item.lat,item.lng);\n                geoportMoveActiveMarker(item.lat,item.lng,15);\n                if(typeof geoportStatus==='function'){\n                    geoportStatus('已載入最愛位置',false);\n                }\n            };\n\n            var del=document.createElement('button');\n            del.type='button';\n            del.className='geoport-fav-delete';\n            del.textContent='×';\n            del.title='刪除 ' + text;\n            del.setAttribute('aria-label','刪除 ' + text);\n            del.onclick=function(event){\n                event.preventDefault();\n                event.stopPropagation();\n                var next=geoportGetFavorites() || [];\n                next.splice(index,1);\n                geoportSetFavorites(next);\n                renderFavorites();\n            };\n\n            card.appendChild(open);\n            card.appendChild(del);\n            box.appendChild(card);\n        });\n    }\n\n    window.geoportRenderFavorites=renderFavorites;\n\n    function init(){\n        renderFavorites();\n    }\n\n    if(document.readyState==='loading'){\n        document.addEventListener('DOMContentLoaded',init,{once:true});\n    }else{\n        init();\n    }\n})();\n</script>\n"
status_js = "\n<script id=\"dport-map-status-overlay-script\">\n(function(){\n    function findStatusCard(){\n        var found=[];\n        document.querySelectorAll('body *').forEach(function(el){\n            if(!el || el.id==='dport-map-status-overlay') return;\n            var t=(el.innerText||'').replace(/\\\\s+/g,' ').trim();\n            if(\n                (t.indexOf('準備就緒')>=0 || t.indexOf('定位套用失敗')>=0 ||\n                 t.indexOf('定位成功')>=0 || t.indexOf('目前尚未偵測')>=0) &&\n                (t.indexOf('USB')>=0 || t.indexOf('裝置')>=0 || t.indexOf('座標')>=0)\n            ){\n                var r=el.getBoundingClientRect();\n                if(r.width>=140 && r.height>=28 && r.width<=700 && r.height<=280){\n                    found.push(el);\n                }\n            }\n        });\n        found.sort(function(a,b){\n            var ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();\n            return (ra.width*ra.height)-(rb.width*rb.height);\n        });\n        return found[0] || null;\n    }\n\n    function getMapFrame(){\n        var selectors=['.leaflet-container','#map','.map-container'];\n        for(var i=0;i<selectors.length;i++){\n            var map=document.querySelector(selectors[i]);\n            if(!map) continue;\n            var r=map.getBoundingClientRect();\n            if(r.width>=250 && r.height>=180) return map;\n        }\n        return null;\n    }\n\n    function mount(){\n        if(document.getElementById('dport-map-status-overlay')) return true;\n        var map=getMapFrame();\n        var source=findStatusCard();\n        if(!map || !source) return false;\n\n        var holder=document.createElement('div');\n        holder.id='dport-map-status-overlay';\n        map.appendChild(holder);\n        holder.appendChild(source);\n        return true;\n    }\n\n    function ensure(){\n        if(mount()) return;\n        [200,500,1000,1800,3000].forEach(function(ms){\n            setTimeout(mount,ms);\n        });\n    }\n\n    if(document.readyState==='loading'){\n        document.addEventListener('DOMContentLoaded',ensure,{once:true});\n    }else{\n        ensure();\n    }\n    window.addEventListener('load',ensure);\n})();\n</script>\n"
header_css = r"""
<style id="dport-header-final-v2">
/*
  DPort Header final visual reference:
  Brand -> GPX -> Device -> Refresh -> Connect -> Exit.
  No notification column.
*/
@media (min-width:1600px){
  .dport-hero{
    display:grid!important;
    grid-template-columns:clamp(300px,19vw,340px) minmax(600px,1fr) clamp(560px,31vw,680px) 82px!important;
    column-gap:14px!important;
    row-gap:0!important;
    align-items:center!important;
    justify-content:start!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    height:100px!important;
    min-height:100px!important;
    max-height:100px!important;
    padding:8px 14px!important;
    box-sizing:border-box!important;
    overflow:hidden!important;
  }

  /* No header notifications. All reminders remain in the left green status area. */
  .dport-hero-notifications{
    display:none!important;
    width:0!important;height:0!important;min-width:0!important;min-height:0!important;
    max-width:0!important;max-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important;
  }

  .dport-brand{
    grid-column:1!important;grid-row:1!important;
    display:flex!important;align-items:center!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:86px!important;min-height:86px!important;max-height:86px!important;
    margin:0!important;padding:0!important;overflow:hidden!important;box-sizing:border-box!important;
  }
  .dport-brand-icon{
    flex:0 0 84px!important;
    width:84px!important;height:84px!important;
    min-width:84px!important;min-height:84px!important;
    max-width:84px!important;max-height:84px!important;
    border-radius:16px!important;
  }
  .dport-brand-text{
    min-width:0!important;
    max-width:calc(100% - 100px)!important;
    margin-left:14px!important;
    overflow:hidden!important;
  }
  .dport-title{
    font-size:30px!important;line-height:1.05!important;font-weight:850!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-subtitle{
    margin-top:5px!important;font-size:12px!important;line-height:1.2!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-caption,
  #dport-pm3-status{
    margin-top:3px!important;font-size:10.5px!important;line-height:1.15!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }

  .dport-header-center{display:contents!important;min-width:0!important}
  .dport-standard-device-slot{display:none!important}

  /* GPX: visual priority second only to brand. */
  .dport-ultra-gpx-slot{
    grid-column:2!important;grid-row:1!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:86px!important;min-height:86px!important;max-height:86px!important;
    margin:0!important;padding:0!important;overflow:hidden!important;box-sizing:border-box!important;
    justify-self:stretch!important;align-self:center!important;
  }
  .dport-ultra-gpx-slot > *{
    width:100%!important;min-width:0!important;max-width:none!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-card{
    display:block!important;width:100%!important;height:86px!important;min-height:86px!important;max-height:86px!important;
    min-width:0!important;max-width:none!important;margin:0!important;padding:6px 9px!important;
    box-sizing:border-box!important;overflow:hidden!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-head{
    display:grid!important;grid-template-columns:minmax(0,1fr) auto auto!important;
    align-items:center!important;gap:9px!important;width:100%!important;min-width:0!important;max-width:none!important;
    height:28px!important;min-height:28px!important;max-height:28px!important;margin:0!important;padding:0!important;overflow:hidden!important;
    box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-head > *{
    min-width:0!important;max-width:100%!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-section-kicker{
    font-size:9px!important;line-height:1!important;
  }
  .dport-ultra-gpx-slot .dport-section-title{
    font-size:18px!important;line-height:19px!important;font-weight:850!important;
    min-width:0!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-status-pill{
    max-width:135px!important;min-width:0!important;padding:3px 8px!important;
    font-size:9px!important;line-height:14px!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-wrap{
    display:flex!important;align-items:center!important;justify-content:flex-end!important;gap:5px!important;min-width:0!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-label{
    font-size:9px!important;white-space:nowrap!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-select{
    width:118px!important;min-width:118px!important;max-width:118px!important;height:30px!important;min-height:30px!important;
    padding:3px 22px 3px 8px!important;font-size:10.5px!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-grid{
    display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:7px!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:45px!important;min-height:45px!important;max-height:45px!important;
    margin:5px 0 0!important;padding:0!important;overflow:hidden!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item{
    width:100%!important;min-width:0!important;height:45px!important;min-height:45px!important;max-height:45px!important;
    margin:0!important;padding:6px 8px!important;border-radius:9px!important;box-sizing:border-box!important;overflow:hidden!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item span{
    display:block!important;max-width:100%!important;font-size:9px!important;line-height:10px!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item strong{
    display:block!important;max-width:100%!important;margin-top:2px!important;font-size:13px!important;line-height:16px!important;
    font-weight:800!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }

  /* Device block: complete phone selector first, then Refresh + Connect. */
  .dport-ultra-device-slot{
    grid-column:3!important;grid-row:1!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:86px!important;min-height:86px!important;max-height:86px!important;
    display:block!important;margin:0!important;padding:0!important;overflow:hidden!important;box-sizing:border-box!important;
  }
  .dport-ultra-device-slot .dport-connection-panel{
    width:100%!important;height:86px!important;min-height:86px!important;max-height:86px!important;min-width:0!important;max-width:none!important;
    margin:0!important;padding:8px 9px!important;box-sizing:border-box!important;overflow:hidden!important;
  }
  .dport-ultra-device-slot .dport-connection-title{margin:0 0 5px!important}
  .dport-ultra-device-slot .dport-section-kicker{font-size:9px!important;line-height:1!important}
  .dport-ultra-device-slot .dport-mini-title{font-size:15px!important;line-height:1.05!important;font-weight:850!important}
  .dport-ultra-device-slot .dport-connection-body{
    display:flex!important;flex-direction:row!important;align-items:center!important;flex-wrap:nowrap!important;gap:8px!important;
    width:100%!important;min-width:0!important;max-width:100%!important;margin:0!important;padding:0!important;overflow:hidden!important;
  }
  .dport-ultra-device-slot .dport-connection-body>form{
    flex:1 1 auto!important;width:auto!important;min-width:0!important;max-width:none!important;margin:0!important;padding:0!important;overflow:hidden!important;
  }
  .dport-ultra-device-slot .dport-connection-body form>.mb-3,
  .dport-ultra-device-slot .dport-connection-body form>.mb-3>.row{
    width:100%!important;min-width:0!important;margin:0!important;padding:0!important;
  }
  .dport-ultra-device-slot .dport-connection-body form>.mb-3>.row{
    display:flex!important;align-items:center!important;flex-wrap:nowrap!important;gap:8px!important;
  }
  .dport-ultra-device-slot .dport-connection-body form>.mb-3>.row>.col{
    flex:1 1 auto!important;width:auto!important;min-width:0!important;max-width:none!important;margin:0!important;padding:0!important;
  }
  .dport-ultra-device-slot #device{
    display:block!important;width:100%!important;min-width:0!important;max-width:100%!important;height:46px!important;min-height:46px!important;
    margin:0!important;padding:6px 30px 6px 12px!important;box-sizing:border-box!important;font-size:14px!important;font-weight:800!important;
    line-height:1.15!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-ultra-device-slot #refresh-device{
    flex:0 0 90px!important;width:90px!important;min-width:90px!important;max-width:90px!important;height:46px!important;min-height:46px!important;
    margin:0!important;padding:5px 4px!important;font-size:12.5px!important;line-height:1!important;white-space:nowrap!important;box-sizing:border-box!important;
  }
  .dport-ultra-device-slot #connect,
  .dport-ultra-device-slot #disconnect{
    flex:0 0 100px!important;width:100px!important;min-width:100px!important;max-width:100px!important;height:46px!important;min-height:46px!important;
    margin:0!important;padding:5px 6px!important;font-size:12.5px!important;line-height:1!important;white-space:nowrap!important;box-sizing:border-box!important;
  }

  /* Exit is aligned to the exact same 46px control height as Connect. */
  .dport-hero-actions{
    grid-column:4!important;grid-row:1!important;
    display:flex!important;align-items:center!important;justify-content:flex-end!important;align-self:center!important;
    width:82px!important;min-width:82px!important;max-width:82px!important;height:86px!important;
    margin:0!important;padding:0!important;box-sizing:border-box!important;
  }
  .dport-hero-actions #exit-btn{
    align-self:center!important;
    width:82px!important;min-width:82px!important;max-width:82px!important;height:46px!important;min-height:46px!important;
    margin:0!important;padding:5px 8px!important;font-size:12.5px!important;line-height:1!important;white-space:nowrap!important;box-sizing:border-box!important;
  }
}

@media (min-width:1400px) and (max-width:1599px){
  .dport-hero{
    grid-template-columns:240px minmax(430px,1fr) 510px 70px!important;
    column-gap:10px!important;height:88px!important;min-height:88px!important;max-height:88px!important;padding:7px 10px!important;
  }
  .dport-brand{height:72px!important;min-height:72px!important;max-height:72px!important}
  .dport-brand-icon{
    flex-basis:72px!important;width:72px!important;height:72px!important;min-width:72px!important;min-height:72px!important;
    max-width:72px!important;max-height:72px!important;
  }
  .dport-title{font-size:22px!important}
  .dport-ultra-device-slot{height:74px!important;min-height:74px!important;max-height:74px!important}
  .dport-ultra-device-slot .dport-connection-panel{height:74px!important;min-height:74px!important;max-height:74px!important}
  .dport-ultra-gpx-slot{height:74px!important;min-height:74px!important;max-height:74px!important}
  .dport-ultra-gpx-slot .dport-gpx-card{height:74px!important;min-height:74px!important;max-height:74px!important}
  .dport-ultra-gpx-slot .dport-gpx-grid{height:40px!important;min-height:40px!important;max-height:40px!important;margin-top:4px!important}
  .dport-ultra-gpx-slot .dport-gpx-item{height:40px!important;min-height:40px!important;max-height:40px!important}
  .dport-hero-actions{height:74px!important;min-height:74px!important;max-height:74px!important;width:70px!important;min-width:70px!important;max-width:70px!important}
  .dport-hero-actions #exit-btn{width:70px!important;min-width:70px!important;max-width:70px!important;height:42px!important;min-height:42px!important}
}

@media (min-width:2200px){
  .dport-hero{
    grid-template-columns:330px minmax(760px,1fr) 640px 84px!important;
    column-gap:16px!important;height:104px!important;min-height:104px!important;max-height:104px!important;padding:8px 16px!important;
  }
  .dport-brand{height:90px!important;min-height:90px!important;max-height:90px!important}
  .dport-brand-icon{
    flex-basis:88px!important;width:88px!important;height:88px!important;min-width:88px!important;min-height:88px!important;
    max-width:88px!important;max-height:88px!important;
  }
  .dport-title{font-size:29px!important}
  .dport-ultra-gpx-slot,
  .dport-ultra-gpx-slot .dport-gpx-card{height:92px!important;min-height:92px!important;max-height:92px!important}
  .dport-ultra-gpx-slot .dport-gpx-grid{height:53px!important;min-height:53px!important;max-height:53px!important}
  .dport-ultra-gpx-slot .dport-gpx-item{height:53px!important;min-height:53px!important;max-height:53px!important}
  .dport-ultra-device-slot{height:92px!important;min-height:92px!important;max-height:92px!important}
  .dport-ultra-device-slot .dport-connection-panel{height:92px!important;min-height:92px!important;max-height:92px!important}
  .dport-hero-actions{height:92px!important;min-height:92px!important;max-height:92px!important;width:84px!important;min-width:84px!important;max-width:84px!important}
  .dport-hero-actions #exit-btn{width:84px!important;min-width:84px!important;max-width:84px!important;height:48px!important;min-height:48px!important}
}

@media (max-width:1399px){
  .dport-hero{
    display:flex!important;align-items:center!important;flex-wrap:wrap!important;gap:10px!important;
    min-height:0!important;height:auto!important;max-height:none!important;overflow:visible!important;
  }
  .dport-brand{flex:1 1 100%!important;width:auto!important;min-width:0!important;max-width:100%!important}
  .dport-ultra-gpx-slot,
  .dport-ultra-device-slot{flex:1 1 100%!important;width:100%!important;min-width:0!important;max-width:100%!important}
}

/* 1100-1599px desktop: keep the approved single-row composition and readable text. */
@media (min-width:1100px) and (max-width:1599px){
  .dport-hero{
    display:grid!important;
    grid-template-columns:270px minmax(460px,1fr) 500px 74px!important;
    column-gap:10px!important;
    row-gap:0!important;
    align-items:center!important;
    justify-content:start!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    height:96px!important;
    min-height:96px!important;
    max-height:96px!important;
    padding:7px 10px!important;
    box-sizing:border-box!important;
    overflow:hidden!important;
    position:relative!important;
    z-index:3000!important;
  }
  .dport-hero-notifications{display:none!important;width:0!important;height:0!important}
  .dport-brand{
    grid-column:1!important;grid-row:1!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:82px!important;min-height:82px!important;max-height:82px!important;
    display:flex!important;align-items:center!important;
  }
  .dport-brand-icon{
    flex:0 0 82px!important;width:82px!important;height:82px!important;
    min-width:82px!important;min-height:82px!important;max-width:82px!important;max-height:82px!important;
    border-radius:15px!important;
  }
  .dport-brand-text{
    min-width:0!important;max-width:calc(100% - 90px)!important;
    margin-left:14px!important;overflow:hidden!important;
  }
  .dport-title{
    font-size:28px!important;line-height:1.05!important;font-weight:850!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-subtitle{
    margin-top:5px!important;font-size:12.5px!important;line-height:1.2!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-caption,
  #dport-pm3-status{
    margin-top:3px!important;font-size:11px!important;line-height:1.15!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-header-center{display:contents!important}
  .dport-standard-device-slot{display:none!important}

  .dport-ultra-gpx-slot{
    grid-column:2!important;grid-row:1!important;display:block!important;width:100%!important;min-width:0!important;max-width:none!important;
    height:76px!important;min-height:76px!important;max-height:76px!important;
    justify-self:stretch!important;align-self:center!important;
  }
  .dport-ultra-gpx-slot > *,
  .dport-ultra-gpx-slot .dport-gpx-card,
  .dport-ultra-gpx-slot .dport-gpx-head,
  .dport-ultra-gpx-slot .dport-gpx-grid{
    width:100%!important;min-width:0!important;max-width:none!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-card{
    height:76px!important;min-height:76px!important;max-height:76px!important;padding:5px 8px!important;
  }
  .dport-ultra-gpx-slot .dport-section-kicker{font-size:9.5px!important}
  .dport-ultra-gpx-slot .dport-section-title{
    font-size:18px!important;line-height:19px!important;font-weight:850!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-label{font-size:8.5px!important}
  .dport-ultra-gpx-slot .dport-gpx-speed-select{
    width:108px!important;min-width:108px!important;max-width:108px!important;height:27px!important;min-height:27px!important;font-size:11.5px!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-grid{
    display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:6px!important;
    height:44px!important;min-height:44px!important;max-height:44px!important;margin:4px 0 0!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item{
    height:44px!important;min-height:44px!important;max-height:44px!important;padding:5px 7px!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item span{font-size:10px!important;line-height:11px!important}
  .dport-ultra-gpx-slot .dport-gpx-item strong{font-size:14px!important;line-height:16px!important}

  .dport-ultra-device-slot{
    grid-column:3!important;grid-row:1!important;width:100%!important;min-width:0!important;max-width:none!important;
    height:82px!important;min-height:82px!important;max-height:82px!important;
  }
  .dport-ultra-device-slot .dport-connection-panel{
    width:100%!important;height:82px!important;min-height:82px!important;max-height:82px!important;padding:7px 8px!important;
  }
  .dport-ultra-device-slot .dport-section-kicker{font-size:8.5px!important}
  .dport-ultra-device-slot .dport-mini-title{font-size:14px!important}
  .dport-ultra-device-slot #device{height:42px!important;min-height:42px!important;font-size:13px!important}
  .dport-ultra-device-slot #refresh-device{
    width:88px!important;min-width:88px!important;max-width:88px!important;height:46px!important;min-height:46px!important;font-size:13px!important;
  }
  .dport-ultra-device-slot #connect,
  .dport-ultra-device-slot #disconnect{
    width:96px!important;min-width:96px!important;max-width:96px!important;height:46px!important;min-height:46px!important;font-size:13px!important;
  }
  .dport-hero-actions{
    grid-column:4!important;grid-row:1!important;display:flex!important;align-items:center!important;justify-content:flex-end!important;
    width:72px!important;min-width:72px!important;max-width:72px!important;height:82px!important;min-height:82px!important;max-height:82px!important;
  }
  .dport-hero-actions #exit-btn{
    width:74px!important;min-width:74px!important;max-width:74px!important;height:46px!important;min-height:46px!important;
    margin:0!important;align-self:center!important;font-size:12px!important;
  }
}

  /* Brand metadata: caption + live update result share one line. */
  .dport-brand-meta-row{
    display:flex!important;
    align-items:center!important;
    flex-wrap:nowrap!important;
    gap:8px!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    margin:0!important;
    padding:0!important;
    overflow:hidden!important;
  }
  .dport-brand-meta-row .dport-caption{
    flex:0 1 auto!important;
    min-width:0!important;
    max-width:100%!important;
    margin:0!important;
    font-size:11px!important;
    line-height:1.15!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
  }
  .dport-brand-meta-row #dport-pm3-status{
    flex:0 0 auto!important;
    min-width:0!important;
    max-width:46%!important;
    display:inline-block!important;
    margin:0!important;
    padding:0!important;
    font-size:11px!important;
    line-height:1.15!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    vertical-align:baseline!important;
  }

  /* GPX speed control: never collapse the label or the km/h value. */
  .dport-ultra-gpx-slot .dport-gpx-speed-wrap{
    display:flex!important;
    align-items:center!important;
    justify-content:flex-end!important;
    flex:0 0 auto!important;
    min-width:max-content!important;
    gap:6px!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-label{
    display:inline-block!important;
    flex:0 0 auto!important;
    width:auto!important;
    min-width:max-content!important;
    font-size:10px!important;
    line-height:1!important;
    white-space:nowrap!important;
    overflow:visible!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-select{
    flex:0 0 auto!important;
    width:132px!important;
    min-width:132px!important;
    max-width:132px!important;
    height:30px!important;
    min-height:30px!important;
    padding:3px 24px 3px 8px!important;
    font-size:11px!important;
    line-height:1.1!important;
    white-space:nowrap!important;
    overflow:hidden!important;
  }

</style>

<script id="dport-header-brand-version-final">
(function(){
  function findExactText(root,text){
    var nodes=root.querySelectorAll('*');
    var best=null;
    for(var i=0;i<nodes.length;i++){
      var el=nodes[i];
      if((el.textContent||'').trim()===text){
        if(!best || el.children.length<best.children.length) best=el;
      }
    }
    return best;
  }

  function arrangeBrandMeta(){
    var brand=document.querySelector('.dport-brand');
    var caption=document.querySelector('.dport-brand .dport-caption') ||
                 findExactText(brand||document,'iPhone 定位與 GPX 模擬工具');
    var status=document.querySelector('.dport-brand #dport-pm3-status') ||
                document.getElementById('dport-pm3-status');
    if(!brand || !caption || !status) return false;

    var parent=caption.parentElement;
    if(!parent) return false;

    var row=brand.querySelector('.dport-brand-meta-row');
    if(!row){
      row=document.createElement('div');
      row.className='dport-brand-meta-row';
      row.setAttribute('data-dport-final','brand-meta');

      var captionIndex=Array.prototype.indexOf.call(parent.children,caption);
      if(captionIndex<0) captionIndex=parent.children.length-1;

      parent.insertBefore(row,caption);
      row.appendChild(caption);
      row.appendChild(status);
    }else{
      if(caption.parentElement!==row) row.appendChild(caption);
      if(status.parentElement!==row) row.appendChild(status);
    }
    return true;
  }

  function fixSpeed(){
    var wrap=document.querySelector('.dport-ultra-gpx-slot .dport-gpx-speed-wrap');
    if(!wrap) return false;
    var label=wrap.querySelector('.dport-gpx-speed-label');
    var select=wrap.querySelector('.dport-gpx-speed-select');
    if(label){
      label.style.setProperty('display','inline-block','important');
      label.style.setProperty('flex','0 0 auto','important');
      label.style.setProperty('min-width','max-content','important');
      label.style.setProperty('white-space','nowrap','important');
    }
    if(select){
      select.style.setProperty('display','block','important');
      select.style.setProperty('flex','0 0 132px','important');
      select.style.setProperty('width','132px','important');
      select.style.setProperty('min-width','132px','important');
      select.style.setProperty('max-width','132px','important');
      select.style.setProperty('font-size','11px','important');
      return true;
    }
    return false;
  }

  function apply(){
    arrangeBrandMeta();
    fixSpeed();
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',apply,{once:true});
  }else{
    apply();
  }
  window.addEventListener('load',apply);
  window.addEventListener('resize',apply);
  [100,300,700,1200].forEach(function(ms){setTimeout(apply,ms);});
})();
</script>
"""

if "</body>" in html:
    html = html.replace("</body>", css + favorites_js + status_js + header_css + "\n</body>", 1)
else:
    html += css + favorites_js + status_js + header_css


# ==================== DPort USB enumeration optimization ====================
# iPhone USB enumeration may lag behind physical cable insertion. Reuse the
# existing Refresh button and retry with a short back-off instead of requiring
# the user to manually click Refresh several times. This only refreshes while
# no device is present and DPort is not already connected.
html += r'''
<style id="dport-usb-reconnect-notifications">
/* All legacy Toast notifications are removed from the lower-left UI. */
body > .toast-container,
body > div.toast-container,
.toast-container{
    display:none !important;
}
</style>

<script id="dport-usb-reconnect-final">
(function(){
    var burstTimer=null;
    var backgroundTimer=null;
    var refreshBusyUntil=0;
    var burstActive=false;

    function connected(){
        try{
            if(typeof isDeviceConnected!=='undefined' && isDeviceConnected===true) return true;
        }catch(e){}
        return false;
    }

    function selector(){
        return document.getElementById('device');
    }

    function hasRealDevice(){
        var sel=selector();
        if(!sel) return false;
        var options=Array.prototype.slice.call(sel.options||[]);
        return options.some(function(opt){
            var value=String(opt.value||'').trim();
            var label=String(opt.textContent||'').trim();
            if(!value) return false;
            if(/請選擇|選擇裝置|找不到|沒有裝置|無裝置/i.test(label)) return false;
            return true;
        });
    }

    function setGreenStatus(message){
        try{
            if(typeof geoportStatus==='function'){
                geoportStatus(message,false);
                return;
            }
        }catch(e){}
    }

    function clickRefresh(){
        var now=Date.now();
        if(now<refreshBusyUntil || connected()) return false;

        var btn=document.getElementById('refresh-device');
        if(!btn) return false;

        refreshBusyUntil=now+950;
        try{
            btn.disabled=false;
            btn.removeAttribute('aria-disabled');
            btn.click();
            return true;
        }catch(e){
            return false;
        }
    }

    function stopTimers(){
        if(burstTimer){
            clearTimeout(burstTimer);
            burstTimer=null;
        }
        burstActive=false;
    }

    function verifyAfterRefresh(){
        setTimeout(function(){
            if(hasRealDevice()){
                setGreenStatus('USB 裝置已重新偵測');
                stopTimers();
            }
        },350);
    }

    function startBurst(reason){
        if(connected() || hasRealDevice() || burstActive) return;
        burstActive=true;

        var delays=[0,900,1900,3200,5000,7500,10500,14000];
        var index=0;

        function next(){
            if(connected() || hasRealDevice() || index>=delays.length){
                if(hasRealDevice()) setGreenStatus('USB 裝置已重新偵測');
                burstActive=false;
                burstTimer=null;
                scheduleBackground();
                return;
            }

            var delay=delays[index++];
            burstTimer=setTimeout(function(){
                burstTimer=null;
                if(index===1) setGreenStatus('正在偵測 USB 裝置…');
                clickRefresh();
                verifyAfterRefresh();
                next();
            },delay);
        }

        next();
    }

    function scheduleBackground(){
        if(backgroundTimer) return;
        backgroundTimer=setTimeout(function(){
            backgroundTimer=null;
            if(!connected() && !hasRealDevice()){
                clickRefresh();
                verifyAfterRefresh();
                scheduleBackground();
            }
        },8000);
    }

    function watchDeviceList(){
        var sel=selector();
        if(!sel || sel.dataset.dportUsbReconnectWatch==='1') return;

        sel.dataset.dportUsbReconnectWatch='1';

        var observer=new MutationObserver(function(){
            if(hasRealDevice()){
                setGreenStatus('USB 裝置已重新偵測');
                stopTimers();
                return;
            }
            if(!connected()) scheduleBackground();
        });

        observer.observe(sel,{childList:true,subtree:true});

        sel.addEventListener('change',function(){
            if(hasRealDevice()) stopTimers();
        });
    }

    function watchRefreshButton(){
        var btn=document.getElementById('refresh-device');
        if(!btn || btn.dataset.dportUsbReconnectClick==='1') return;

        btn.dataset.dportUsbReconnectClick='1';
        btn.addEventListener('click',function(){
            setTimeout(function(){
                if(!connected() && !hasRealDevice()){
                    startBurst('manual-refresh');
                }
            },450);
        },true);
    }

    function wrapNativeCallback(name){
        try{
            if(typeof window[name]!=='function') return;
            if(window[name].__dportUsbReconnectWrapped) return;

            var original=window[name];
            var wrapped=function(){
                var result=original.apply(this,arguments);
                setTimeout(function(){
                    if(!connected()) startBurst(name);
                },300);
                return result;
            };
            wrapped.__dportUsbReconnectWrapped=true;
            wrapped.__dportUsbReconnectOriginal=original;
            window[name]=wrapped;
        }catch(e){}
    }

    function redirectLegacyToast(){
        // Future legacy displayToast calls become the existing left green status
        // message. This removes lower-left stacked notifications without
        // interfering with modal dialogs/prompts.
        if(typeof window.displayToast!=='function') return;

        if(window.displayToast.__dportStatusOnlyV2) return;

        window.displayToast=function(message){
            var msg=String(message==null?'':message).trim();
            if(!msg) return;
            setGreenStatus(msg);
        };
        window.displayToast.__dportStatusOnlyV2=true;
    }

    function boot(){
        redirectLegacyToast();
        watchDeviceList();
        watchRefreshButton();

        [
            'handleUsbCableRemoved',
            'handleUsbCableConnected',
            'refreshDeviceList',
            'refreshDevices',
            'scanDevices'
        ].forEach(wrapNativeCallback);

        // Covers the common physical sequence:
        // unplug -> OS clears the device -> plug in -> usbmux enumeration settles.
        setTimeout(function(){
            if(!connected() && !hasRealDevice()) startBurst('startup');
        },500);

        [1000,2500,5000,9000,15000].forEach(function(ms){
            setTimeout(function(){
                redirectLegacyToast();
                watchDeviceList();
                watchRefreshButton();
            },ms);
        });
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',boot,{once:true});
    }else{
        boot();
    }

    window.addEventListener('load',function(){
        redirectLegacyToast();
        watchDeviceList();
        watchRefreshButton();
    });
})();
</script>
'''


# ==================== DPort USB reconnect optimization ====================
# Re-enumerating an iPhone can take several seconds after the cable is
# reinserted. Reuse the existing Refresh action with a bounded retry window.
# Also redirect legacy toast notifications to the existing left green status
# area so the lower-left notification panel is never used.
html += r'''
<style id="dport-usb-reconnect-final">
/* The lower-left toast/notification UI is intentionally disabled. */
.toast-container,
.toast-container.show,
body > .toast-container,
body > div.toast-container{
    display:none!important;
    visibility:hidden!important;
    pointer-events:none!important;
}

/* Keep the green status area visually above map content. */
.dport-status,
#dport-status,
.geoport-status,
#geoport-status{
    position:relative;
    z-index:3200!important;
}
</style>

<script id="dport-usb-reconnect-final-script">
(function(){
    var retryTimer=null;
    var retryStep=0;
    var retryActive=false;
    var backgroundTimer=null;
    var refreshLockedUntil=0;

    function isConnected(){
        try{
            if(typeof isDeviceConnected!=='undefined' && isDeviceConnected===true) return true;
        }catch(e){}
        return false;
    }

    function deviceSelect(){
        return document.getElementById('device');
    }

    function hasDevice(){
        var select=deviceSelect();
        if(!select) return false;
        var options=Array.prototype.slice.call(select.options||[]);
        return options.some(function(opt){
            var value=String(opt.value||'').trim();
            var label=String(opt.textContent||'').trim();
            if(!value) return false;
            if(/請選擇|選擇裝置|找不到|沒有裝置|無裝置/i.test(label)) return false;
            return true;
        });
    }

    function greenStatus(message){
        try{
            if(typeof geoportStatus==='function'){
                geoportStatus(String(message||''),false);
                return true;
            }
        }catch(e){}
        return false;
    }

    function refreshOnce(){
        var now=Date.now();
        if(now<refreshLockedUntil || isConnected()) return false;

        var btn=document.getElementById('refresh-device');
        if(!btn) return false;

        try{
            refreshLockedUntil=now+850;
            btn.disabled=false;
            btn.removeAttribute('aria-disabled');
            btn.click();
            return true;
        }catch(e){
            return false;
        }
    }

    function stopRetry(){
        retryActive=false;
        retryStep=0;
        if(retryTimer){
            clearTimeout(retryTimer);
            retryTimer=null;
        }
    }

    function startRetry(reason){
        if(isConnected() || hasDevice() || retryActive) return;

        retryActive=true;
        retryStep=0;

        // Covers the usual Windows USB/usbmux enumeration delay without
        // hammering the device bridge.
        var delays=[0,700,1500,2600,4200,6500,9000,12000,16000];

        function next(){
            if(isConnected() || hasDevice() || retryStep>=delays.length){
                if(hasDevice()){
                    greenStatus('USB 裝置已重新偵測');
                }else if(!isConnected()){
                    greenStatus('USB 裝置仍在辨識中，將持續自動偵測');
                }
                stopRetry();
                scheduleBackground();
                return;
            }

            var delay=delays[retryStep++];
            retryTimer=setTimeout(function(){
                retryTimer=null;
                if(retryStep===1){
                    greenStatus('正在偵測 USB 裝置…');
                }
                refreshOnce();
                setTimeout(next,220);
            },delay);
        }

        next();
    }

    function scheduleBackground(){
        if(backgroundTimer) return;
        backgroundTimer=setTimeout(function(){
            backgroundTimer=null;
            if(!isConnected() && !hasDevice()){
                refreshOnce();
                scheduleBackground();
            }
        },8000);
    }

    function watchDeviceList(){
        var select=deviceSelect();
        if(!select || select.dataset.dportUsbReconnectWatch==='1') return;
        select.dataset.dportUsbReconnectWatch='1';

        var observer=new MutationObserver(function(){
            if(hasDevice()){
                greenStatus('USB 裝置已重新偵測');
                stopRetry();
            }else if(!isConnected()){
                scheduleBackground();
            }
        });

        observer.observe(select,{childList:true,subtree:true});
    }

    function watchRefresh(){
        var btn=document.getElementById('refresh-device');
        if(!btn || btn.dataset.dportUsbReconnectWatch==='1') return;
        btn.dataset.dportUsbReconnectWatch='1';

        btn.addEventListener('click',function(){
            setTimeout(function(){
                if(!isConnected() && !hasDevice()){
                    startRetry('manual-refresh');
                }
            },350);
        },true);
    }

    function redirectLegacyToast(){
        if(typeof window.displayToast!=='function') return;
        if(window.displayToast.__dportStatusOnlyFinal) return;

        window.displayToast=function(message){
            var msg=String(message==null?'':message).trim();
            if(!msg) return;
            greenStatus(msg);
        };
        window.displayToast.__dportStatusOnlyFinal=true;
    }

    function wrapReconnectCallbacks(){
        [
            'handleUsbCableRemoved',
            'handleUsbCableConnected',
            'refreshDeviceList',
            'refreshDevices',
            'scanDevices'
        ].forEach(function(name){
            try{
                if(typeof window[name]!=='function') return;
                if(window[name].__dportUsbReconnectFinal) return;

                var original=window[name];
                var wrapped=function(){
                    var result=original.apply(this,arguments);
                    setTimeout(function(){
                        if(!isConnected()) startRetry(name);
                    },250);
                    return result;
                };

                wrapped.__dportUsbReconnectFinal=true;
                wrapped.__dportUsbReconnectOriginal=original;
                window[name]=wrapped;
            }catch(e){}
        });
    }

    function boot(){
        redirectLegacyToast();
        watchDeviceList();
        watchRefresh();
        wrapReconnectCallbacks();

        // Initial scan plus delayed retries for the physical reconnect case:
        // unplug -> Windows clears usbmux -> plug in -> device enumerates.
        setTimeout(function(){
            if(!isConnected() && !hasDevice()) startRetry('startup');
        },500);

        [1200,3000,6000,10000,15000].forEach(function(ms){
            setTimeout(function(){
                redirectLegacyToast();
                watchDeviceList();
                watchRefresh();
            },ms);
        });
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',boot,{once:true});
    }else{
        boot();
    }

    window.addEventListener('load',boot);
})();
</script>
'''

path.write_text(html, encoding="utf-8")

print("DPort final header rebuilt from one authoritative layout.")
print("Order: Brand -> GPX -> Device -> Refresh -> Connect -> Exit.")
print("Header notification removed; left green status area remains the reminder location.")
print("Typography and spacing tuned for clarity against the visual reference.")
