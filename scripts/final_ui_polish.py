from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

html = path.read_text(encoding="utf-8")


# Route DPort's dynamic displayToast() messages to the ultra-wide header.
# The original source sends ultra-wide toasts into the left control-card slot.
# Replace that exact target block while building the final map template.
toast_target_old = """const ultraMode = document.body.classList.contains('dport-layout-ultrawide');
      const ultraSlot = document.getElementById('dport-ultra-notification-slot');
      const heroContainer = document.querySelector('.dport-hero-notifications');
      const target = ultraMode && ultraSlot ? ultraSlot : heroContainer;
      if (!target) return;
"""
toast_target_new = """const ultraMode = document.body.classList.contains('dport-layout-ultrawide');
      const ultraSlot = document.getElementById('dport-ultra-notification-slot');
      const heroContainer = document.querySelector('.dport-hero-notifications');
      const target = ultraMode && heroContainer ? heroContainer : (ultraSlot || heroContainer);
      if (!target) return;
"""
if toast_target_old not in html:
    raise SystemExit("displayToast target block not found in source template")
html = html.replace(toast_target_old, toast_target_new, 1)
# Remove only previous generated final UI layers.
for pattern in (
    r'\s*<style id="dport-final-ui-polish-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-final-favorites-render-v[0-9]+">.*?</script>\s*',
    r'\s*<script id="dport-map-status-overlay-script">.*?</script>\s*',
    r'\s*<style id="dport-top-header-layout-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-top-header-layout-script-v[0-9]+">.*?</script>\s*',
    r'\s*<style id="dport-ultra-header-notification-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-ultra-header-notification-v[0-9]+-script">.*?</script>\s*',
):
    html = re.sub(pattern, "\n", html, flags=re.S)

css = """
<style id="dport-final-ui-polish-v8">
:root{
    --dport-panel:#2a3240;
    --dport-panel-hover:#323c4e;
    --dport-border:#5d6c88;
    --dport-border-hover:#8295bd;
    --dport-text:#f7f9fc;
    --dport-muted:#aeb8ca;
    --dport-blue:#5669e7;
    --dport-blue-hover:#697bf4;
    --dport-action-bg:rgba(67,78,98,.66);
    --dport-action-hover:rgba(87,101,126,.84);
    --dport-action-border:rgba(127,143,171,.72);
    --dport-action-text:#edf2fa;
}

/* DPort application buttons. Map controls are intentionally excluded. */
body button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a){
    box-sizing:border-box !important;
    font-family:inherit !important;
    font-weight:700 !important;
    border-radius:10px !important;
    transition:
        background .16s ease,
        border-color .16s ease,
        color .16s ease,
        box-shadow .16s ease,
        transform .16s ease !important;
}
body button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a):hover{
    transform:translateY(-1px) !important;
}
body button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a):active{
    transform:translateY(0) !important;
}
body button:disabled{
    opacity:.48 !important;
    cursor:not-allowed !important;
    transform:none !important;
}

/* Dark blue-gray utility / clear family. */
#geoport-copy-coordinates,
#geoport-load-last,
#geoport-clear-coordinates,
.geoport-recent-delete-selected,
.geoport-recent-clear,
.geoport-fav-clear-all{
    background:var(--dport-action-bg) !important;
    border:1px solid var(--dport-action-border) !important;
    color:var(--dport-action-text) !important;
    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;
}
#geoport-copy-coordinates:hover,
#geoport-load-last:hover,
#geoport-clear-coordinates:hover,
.geoport-recent-delete-selected:hover,
.geoport-recent-clear:hover,
.geoport-fav-clear-all:hover{
    background:var(--dport-action-hover) !important;
    border-color:var(--dport-border-hover) !important;
    color:#fff !important;
    box-shadow:0 6px 15px rgba(0,0,0,.18) !important;
}

/* Favorite section. */
.geoport-favorites-title{
    display:flex !important;
    align-items:center !important;
    justify-content:space-between !important;
    gap:10px !important;
    margin:14px 0 8px !important;
}
.geoport-favorites-actions{
    display:flex !important;
    align-items:center !important;
}
.geoport-fav-count{
    color:var(--dport-muted) !important;
    font-size:13px !important;
    font-weight:700 !important;
}
.geoport-fav-list{
    display:grid !important;
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    grid-template-rows:repeat(3,68px) !important;
    grid-auto-rows:68px !important;
    gap:8px !important;
    padding:9px !important;
    margin:0 !important;
    height:236px !important;
    max-height:236px !important;
    overflow-y:auto !important;
    overflow-x:hidden !important;
    border:1px solid #46536b !important;
    border-radius:14px !important;
    background:rgba(29,35,47,.74) !important;
    scrollbar-width:thin !important;
    scrollbar-color:#68758d transparent !important;
}
.geoport-fav-list::-webkit-scrollbar{width:7px}
.geoport-fav-list::-webkit-scrollbar-track{background:transparent}
.geoport-fav-list::-webkit-scrollbar-thumb{background:#68758d;border-radius:999px}

.geoport-fav-card{
    position:relative !important;
    width:100% !important;
    height:68px !important;
    min-width:0 !important;
    min-height:68px !important;
    overflow:hidden !important;
    border-radius:11px !important;
}
.geoport-fav-open{
    position:absolute !important;
    inset:0 !important;
    width:100% !important;
    height:100% !important;
    min-height:0 !important;
    box-sizing:border-box !important;
    display:flex !important;
    align-items:center !important;
    justify-content:flex-start !important;
    text-align:left !important;
    padding:8px 28px 8px 13px !important;
    border:1px solid #5d6c88 !important;
    border-radius:11px !important;
    background:var(--dport-panel) !important;
    color:var(--dport-text) !important;
    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;
    overflow:hidden !important;
    z-index:1 !important;
}
.geoport-fav-open:hover{
    background:var(--dport-panel-hover) !important;
    border-color:var(--dport-border-hover) !important;
    box-shadow:0 7px 16px rgba(0,0,0,.20) !important;
}
.geoport-fav-name{
    display:-webkit-box !important;
    width:100% !important;
    max-width:100% !important;
    margin:0 !important;
    padding:0 !important;
    color:var(--dport-text) !important;
    font-size:15px !important;
    font-weight:700 !important;
    line-height:1.17 !important;
    white-space:normal !important;
    overflow:hidden !important;
    text-overflow:clip !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    overflow-wrap:anywhere !important;
}
.geoport-fav-name.long{font-size:14px !important}
.geoport-fav-name.xlong{font-size:12.5px !important;line-height:1.08 !important}
.geoport-fav-detail{display:none !important}

/* Keep a comfortable click target, but show the X as a small chip in the
   bottom-right INSIDE the card. */
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete{
    position:absolute !important;
    top:auto !important;
    left:auto !important;
    right:2px !important;
    bottom:2px !important;
    width:30px !important;
    min-width:30px !important;
    max-width:30px !important;
    height:30px !important;
    min-height:30px !important;
    max-height:30px !important;
    margin:0 !important;
    padding:0 !important;
    border:0 !important;
    border-radius:8px !important;
    background:transparent !important;
    color:transparent !important;
    font-size:0 !important;
    line-height:0 !important;
    box-shadow:none !important;
    overflow:visible !important;
    transform:none !important;
    z-index:20 !important;
    cursor:pointer !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::before{
    content:'' !important;
    position:absolute !important;
    right:6px !important;
    bottom:6px !important;
    width:18px !important;
    height:18px !important;
    border-radius:5px !important;
    background:rgba(67,78,98,.70) !important;
    border:1px solid rgba(127,143,171,.72) !important;
    box-sizing:border-box !important;
    box-shadow:0 2px 6px rgba(0,0,0,.15) !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::after{
    content:'×' !important;
    position:absolute !important;
    right:6px !important;
    bottom:6px !important;
    width:18px !important;
    height:18px !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    color:#edf2fa !important;
    font-size:12px !important;
    line-height:18px !important;
    font-weight:800 !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::before{
    background:rgba(87,101,126,.88) !important;
    border-color:#8fa1c1 !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::after{
    color:#ffffff !important;
}

/* Favorite clear-all button stays compact and in the same blue-gray family. */
.geoport-fav-clear-all{
    min-width:56px !important;
    min-height:38px !important;
    height:38px !important;
    padding:5px 13px !important;
    border-radius:9px !important;
}

/* Top-right status notification, always clipped inside the map frame. */
#dport-map-status-overlay{
    position:absolute !important;
    top:8px !important;
    right:8px !important;
    left:auto !important;
    bottom:auto !important;
    z-index:900 !important;
    width:min(320px,34%) !important;
    max-width:calc(100% - 16px) !important;
    min-width:0 !important;
    margin:0 !important;
    padding:0 !important;
    box-sizing:border-box !important;
    pointer-events:none !important;
    overflow:hidden !important;
}
#dport-map-status-overlay > *{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
    box-sizing:border-box !important;
    padding:7px 10px !important;
    margin:0 !important;
    background:rgba(31,38,50,.93) !important;
    border:1px solid rgba(92,108,137,.84) !important;
    border-radius:9px !important;
    color:#f5f7fb !important;
    box-shadow:0 7px 18px rgba(0,0,0,.22) !important;
    backdrop-filter:blur(7px) !important;
    overflow:hidden !important;
    font-size:13px !important;
    line-height:1.3 !important;
}
#dport-map-status-overlay > * *{
    max-width:100% !important;
    font-size:13px !important;
    line-height:1.3 !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
}
@media (max-width:1100px){
    #dport-map-status-overlay{
        width:min(280px,42%) !important;
    }
    #dport-map-status-overlay > *,
    #dport-map-status-overlay > * *{
        font-size:12px !important;
    }
}
@media (max-width:700px){
    #dport-map-status-overlay{
        top:6px !important;
        right:6px !important;
        width:min(245px,56%) !important;
        max-width:calc(100% - 12px) !important;
    }
}
</style>
"""

favorites_js = """
<script id="dport-final-favorites-render-v8">
(function(){
    function renderFavorites(){
        var box=document.getElementById('geoport-favorites');
        if(!box || typeof geoportGetFavorites!=='function') return;
        var items=geoportGetFavorites() || [];
        box.innerHTML='';

        var count=document.getElementById('geoport-fav-count');
        if(count) count.textContent=items.length + '/20';

        if(!items.length){
            box.innerHTML='<div class="geoport-fav-empty">還沒有儲存的位置</div>';
            return;
        }

        items.forEach(function(item,index){
            var card=document.createElement('div');
            card.className='geoport-fav-card';

            var open=document.createElement('button');
            open.type='button';
            open.className='geoport-fav-open';
            open.title='前往 ' + String(item.name || '未命名位置');

            var name=document.createElement('span');
            name.className='geoport-fav-name';
            var text=String(item.name || '未命名位置');
            if(text.length > 16) name.classList.add('long');
            if(text.length > 28) name.classList.add('xlong');
            name.textContent=text;

            open.appendChild(name);
            open.onclick=function(){
                geoportSetMapOnlyCoordinates(item.lat,item.lng);
                geoportMoveActiveMarker(item.lat,item.lng,15);
                if(typeof geoportStatus==='function'){
                    geoportStatus('已載入最愛位置',false);
                }
            };

            var del=document.createElement('button');
            del.type='button';
            del.className='geoport-fav-delete';
            del.textContent='×';
            del.title='刪除 ' + text;
            del.setAttribute('aria-label','刪除 ' + text);
            del.onclick=function(event){
                event.preventDefault();
                event.stopPropagation();
                var next=geoportGetFavorites() || [];
                next.splice(index,1);
                geoportSetFavorites(next);
                renderFavorites();
            };

            card.appendChild(open);
            card.appendChild(del);
            box.appendChild(card);
        });
    }

    window.geoportRenderFavorites=renderFavorites;

    function init(){
        renderFavorites();
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',init,{once:true});
    }else{
        init();
    }
})();
</script>
"""

status_js = """
<script id="dport-map-status-overlay-script">
(function(){
    function findStatusCard(){
        var found=[];
        document.querySelectorAll('body *').forEach(function(el){
            if(!el || el.id==='dport-map-status-overlay') return;
            var t=(el.innerText||'').replace(/\\s+/g,' ').trim();
            if(
                (t.indexOf('準備就緒')>=0 || t.indexOf('定位套用失敗')>=0 ||
                 t.indexOf('定位成功')>=0 || t.indexOf('目前尚未偵測')>=0) &&
                (t.indexOf('USB')>=0 || t.indexOf('裝置')>=0 || t.indexOf('座標')>=0)
            ){
                var r=el.getBoundingClientRect();
                if(r.width>=140 && r.height>=28 && r.width<=700 && r.height<=280){
                    found.push(el);
                }
            }
        });
        found.sort(function(a,b){
            var ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
            return (ra.width*ra.height)-(rb.width*rb.height);
        });
        return found[0] || null;
    }

    function getMapFrame(){
        var selectors=['.leaflet-container','#map','.map-container'];
        for(var i=0;i<selectors.length;i++){
            var map=document.querySelector(selectors[i]);
            if(!map) continue;
            var r=map.getBoundingClientRect();
            if(r.width>=250 && r.height>=180) return map;
        }
        return null;
    }

    function mount(){
        if(document.getElementById('dport-map-status-overlay')) return true;
        var map=getMapFrame();
        var source=findStatusCard();
        if(!map || !source) return false;

        var holder=document.createElement('div');
        holder.id='dport-map-status-overlay';
        map.appendChild(holder);
        holder.appendChild(source);
        return true;
    }

    function ensure(){
        if(mount()) return;
        [200,500,1000,1800,3000].forEach(function(ms){
            setTimeout(mount,ms);
        });
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',ensure,{once:true});
    }else{
        ensure();
    }
    window.addEventListener('load',ensure);
})();
</script>
"""


header_css = """
<style id="dport-top-header-layout-v3">
/* Keep the connection controls compact and pushed to the far right. */
#dport-top-device-shell-v3{
    box-sizing:border-box !important;
    width:280px !important;
    min-width:280px !important;
    max-width:280px !important;
}
#dport-top-device-shell-v3 select,
#dport-top-device-shell-v3 [role="combobox"]{
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    box-sizing:border-box !important;
}
@media (min-width:1800px){
    #dport-top-device-shell-v3{
        width:300px !important;
        min-width:300px !important;
        max-width:300px !important;
    }
}
@media (max-width:999px){
    #dport-top-device-shell-v3{
        width:240px !important;
        min-width:240px !important;
        max-width:240px !important;
    }
}
#dport-top-notice-v3{
    position:fixed !important;
    z-index:3500 !important;
    box-sizing:border-box !important;
    margin:0 !important;
    padding:0 !important;
    pointer-events:auto !important;
}
#dport-top-notice-v3,
#dport-top-notice-v3 > *{
    max-width:100% !important;
    box-sizing:border-box !important;
}
</style>
"""

header_js = """
<script id="dport-top-header-layout-script-v3">
(function(){
    function textOf(el){
        return String((el && (el.innerText || el.textContent)) || '')
            .replace(/\\s+/g,' ')
            .trim();
    }

    function rect(el){
        return el && el.getBoundingClientRect ? el.getBoundingClientRect() : null;
    }

    function area(el){
        var r=rect(el);
        return r ? Math.max(0,r.width)*Math.max(0,r.height) : 0;
    }

    function findDeviceControl(){
        var selects=Array.prototype.slice.call(document.querySelectorAll('select'));
        var matches=selects.filter(function(el){
            var t=textOf(el);
            var opts=Array.prototype.slice.call(el.options || [])
                .map(function(o){return textOf(o);}).join(' ');
            return /USB\\s*:/i.test(t+' '+opts) && /iOS/i.test(t+' '+opts);
        });
        if(matches.length){
            return matches.sort(function(a,b){return area(a)-area(b);})[0];
        }

        var all=Array.prototype.slice.call(document.querySelectorAll('body *'));
        var fallback=all.filter(function(el){
            var t=textOf(el), r=rect(el);
            return r && r.width>120 && r.height>25 &&
                /USB\\s*:/i.test(t) && /iOS/i.test(t);
        });
        return fallback.sort(function(a,b){return area(a)-area(b);})[0] || null;
    }

    function findDeviceShell(control){
        if(!control) return null;
        var cur=control;
        for(var i=0;i<9 && cur;i++,cur=cur.parentElement){
            var t=textOf(cur), r=rect(cur);
            if(r && r.width>180 && r.height>30 &&
                /USB\\s*:/i.test(t) &&
                /重新整理/i.test(t) &&
                /離開/i.test(t)){
                return cur;
            }
        }
        return control.parentElement || control;
    }

    function findNoticeTextNode(){
        var all=Array.prototype.slice.call(document.querySelectorAll('body *'));
        var hits=all.filter(function(el){
            if(el.id==='dport-top-notice-v3') return false;
            var t=textOf(el), r=rect(el);
            return r && r.width>120 && r.height>20 &&
                /請先連接裝置/i.test(t) &&
                /再進行模擬定位/i.test(t);
        });
        return hits.sort(function(a,b){return area(a)-area(b);})[0] || null;
    }

    function findNoticeCard(node){
        if(!node) return null;

        /* The previous status-overlay pass may already have moved the real
           card into #dport-map-status-overlay. Pull that existing card out
           rather than creating a duplicate. */
        var overlay=document.getElementById('dport-map-status-overlay');
        if(overlay){
            var candidates=Array.prototype.slice.call(overlay.children || []);
            var existing=candidates.find(function(el){
                var t=textOf(el);
                return /請先連接裝置/i.test(t);
            });
            if(existing) return existing;
        }

        var cur=node;
        var best=node;
        for(var i=0;i<7 && cur;i++,cur=cur.parentElement){
            var t=textOf(cur), r=rect(cur);
            if(!r) continue;
            if(/請先連接裝置/i.test(t) &&
                r.width>=220 && r.width<=700 &&
                r.height>=45 && r.height<=300){
                best=cur;
            } else if(best!==node){
                break;
            }
        }
        return best;
    }

    function compactDevice(device){
        if(!device) return;
        device.id='dport-top-device-shell-v3';
        device.style.setProperty('width','280px','important');
        device.style.setProperty('min-width','280px','important');
        device.style.setProperty('max-width','280px','important');
        device.style.setProperty('flex','0 0 280px','important');

        var select=device.querySelector('select');
        if(select){
            select.style.setProperty('width','100%','important');
            select.style.setProperty('max-width','100%','important');
            select.style.setProperty('min-width','0','important');
        }

        var p=device.parentElement;
        var p2=p ? p.parentElement : null;
        [p,p2].forEach(function(host){
            if(!host) return;
            var cs=getComputedStyle(host);
            if(cs.display==='flex' || cs.display==='inline-flex'){
                host.style.setProperty('justify-content','flex-end','important');
            }
        });
    }

    function moveNoticeBesideDevice(notice,device){
        if(!notice || !device) return false;

        notice.id='dport-top-notice-v3';

        /* Reparent the existing notification. DOM event handlers stay attached
           when a node is moved, so device/status behavior is preserved. */
        if(notice.parentElement !== document.body){
            document.body.appendChild(notice);
        }

        var dr=rect(device);
        if(!dr || dr.width<=0 || dr.height<=0) return false;

        var deviceWidth=dr.width;
        var gap=12;
        var available=Math.max(160,dr.left-gap-8);
        var preferred=320;

        var noticeWidth=Math.min(preferred,available);
        if(window.innerWidth>=1800){
            noticeWidth=Math.min(350,available);
        }

        /* Preserve the required left-of-device arrangement. On narrower
           windows the notification contracts instead of jumping elsewhere. */
        if(noticeWidth<160) noticeWidth=Math.max(120,available);

        var left=Math.max(8,dr.left-gap-noticeWidth);
        var top=Math.max(8,dr.top);

        notice.style.setProperty('position','fixed','important');
        notice.style.setProperty('left',left+'px','important');
        notice.style.setProperty('top',top+'px','important');
        notice.style.setProperty('width',noticeWidth+'px','important');
        notice.style.setProperty('max-width',noticeWidth+'px','important');

        if(dr.bottom<0 || dr.top>window.innerHeight){
            notice.style.setProperty('visibility','hidden','important');
        }else{
            notice.style.setProperty('visibility','visible','important');
        }

        return true;
    }

    function arrange(){
        var control=findDeviceControl();
        var device=findDeviceShell(control);
        var node=findNoticeTextNode();
        var notice=findNoticeCard(node);

        if(!device || !notice) return false;

        compactDevice(device);
        moveNoticeBesideDevice(notice,device);
        return true;
    }

    function follow(){
        var device=document.getElementById('dport-top-device-shell-v3');
        var notice=document.getElementById('dport-top-notice-v3');
        if(device && notice){
            moveNoticeBesideDevice(notice,device);
        }else{
            arrange();
        }
    }

    function boot(){
        arrange();
        [200,500,1000,1800,3000].forEach(function(ms){
            setTimeout(arrange,ms);
        });
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',boot,{once:true});
    }else{
        boot();
    }
    window.addEventListener('load',follow);
    window.addEventListener('resize',follow);
    window.addEventListener('scroll',follow,{passive:true});
})();
</script>
"""

if "</body>" in html:
    html = html.replace("</body>", css + favorites_js + status_js + header_css + header_js + "\n</body>", 1)
else:
    html += css + favorites_js + status_js + header_css + header_js


# DPort UI FINAL v4 — Ultra-wide notification placement.
# The existing application has two separate notification mechanisms:
# 1) .dport-hero-notifications (header)
# 2) #dport-ultra-notification-slot (left control card)
# On ultra-wide layouts, always surface the live toast in the header, directly
# to the left of the compact device connection panel.
header_v4 = """
<style id="dport-ultra-header-notification-v4">
@media (min-width:1400px){
  body.dport-layout-ultrawide .dport-hero{
    display:grid !important;
    grid-template-columns:
      max-content
      minmax(330px,0.92fr)
      minmax(280px,340px)
      minmax(320px,390px)
      max-content !important;
    align-items:center !important;
    column-gap:10px !important;
    row-gap:0 !important;
  }

  body.dport-layout-ultrawide .dport-brand{
    grid-column:1 !important;
    min-width:0 !important;
  }

  body.dport-layout-ultrawide .dport-header-center{
    display:contents !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot{
    display:block !important;
    grid-column:2 !important;
    min-width:0 !important;
    width:100% !important;
    margin:0 !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications{
    display:block !important;
    grid-column:3 !important;
    grid-row:1 !important;
    align-self:center !important;
    justify-self:stretch !important;
    width:100% !important;
    max-width:none !important;
    min-width:0 !important;
    margin:0 !important;
    padding:0 !important;
    order:initial !important;
    overflow:visible !important;
    z-index:20 !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot{
    display:block !important;
    grid-column:4 !important;
    grid-row:1 !important;
    align-self:center !important;
    justify-self:stretch !important;
    width:100% !important;
    min-width:0 !important;
    margin:0 !important;
    padding:0 !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-connection-panel{
    width:100% !important;
    min-width:0 !important;
    max-width:none !important;
    box-sizing:border-box !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot #device{
    min-width:0 !important;
    max-width:none !important;
  }

  body.dport-layout-ultrawide .dport-hero-actions{
    display:flex !important;
    grid-column:5 !important;
    grid-row:1 !important;
    justify-self:end !important;
    align-self:center !important;
    min-width:0 !important;
    width:auto !important;
    margin:0 !important;
    padding:0 !important;
    order:initial !important;
  }

  /* Dynamic DPort toast becomes a normal compact header card. */
  body.dport-layout-ultrawide .dport-hero-notifications .toast{
    display:block !important;
    width:100% !important;
    max-width:none !important;
    margin:0 !important;
    border:1px solid rgba(92,108,137,.84) !important;
    border-radius:10px !important;
    background:rgba(31,38,50,.94) !important;
    color:#f5f7fb !important;
    box-shadow:0 7px 18px rgba(0,0,0,.22) !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications .toast-header{
    min-height:32px !important;
    padding:5px 9px !important;
    background:#3d4653 !important;
    color:#fff !important;
    border-bottom:1px solid #566171 !important;
    font-size:12px !important;
    font-weight:800 !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications .toast-body{
    padding:8px 10px !important;
    background:#252d37 !important;
    color:#fff !important;
    font-size:13px !important;
    line-height:1.35 !important;
    font-weight:700 !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications #liveToast{
    display:none !important;
  }

  body.dport-layout-ultrawide .dport-ultra-notification-slot{
    display:none !important;
  }
}

@media (min-width:2200px){
  body.dport-layout-ultrawide .dport-hero{
    grid-template-columns:
      max-content
      minmax(420px,0.95fr)
      minmax(300px,350px)
      minmax(340px,400px)
      max-content !important;
    column-gap:11px !important;
  }
}

@media (max-width:1399px){
  body.dport-layout-ultrawide .dport-hero-notifications{
    display:none !important;
  }
}
</style>
"""

header_v4_js = """
<script id="dport-ultra-header-notification-v4-script">
(function(){
  function isUltra(){
    return document.body && document.body.classList.contains('dport-layout-ultrawide');
  }

  function headerTarget(){
    return document.querySelector('.dport-hero-notifications');
  }

  function leftCard(){
    return document.getElementById('dport-ultra-notification-slot');
  }

  function moveToast(toast){
    if(!toast || !isUltra()) return;

    var target=headerTarget();
    if(!target) return;

    var left=leftCard();
    if(left && left.contains(toast)){
      target.appendChild(toast);
    }

    if(toast.parentElement===target){
      target.classList.add('dport-header-has-toast');
      target.querySelectorAll('.toast').forEach(function(other){
        if(other!==toast){
          other.remove();
        }
      });
    }
  }

  function scan(){
    if(!isUltra()) return;

    var target=headerTarget();
    if(!target) return;

    var left=leftCard();
    if(left){
      left.querySelectorAll('.toast').forEach(moveToast);
    }

    target.querySelectorAll('.toast').forEach(function(toast){
      if(toast.id==='liveToast') return;
      moveToast(toast);
    });
  }

  function boot(){
    scan();

    if(window.MutationObserver){
      var observer=new MutationObserver(function(){
        scan();
      });
      observer.observe(document.body,{childList:true,subtree:true});
    }

    /* displayToast creates the toast dynamically after user actions. */
    var original=window.displayToast;
    if(typeof original==='function' && !original.__dportUltraHeaderV4){
      var wrapped=function(){
        var result=original.apply(this,arguments);
        setTimeout(scan,0);
        setTimeout(scan,40);
        return result;
      };
      wrapped.__dportUltraHeaderV4=true;
      window.displayToast=wrapped;
    }

    window.addEventListener('resize',scan);
    window.addEventListener('load',scan);
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',boot,{once:true});
  }else{
    boot();
  }
})();
</script>
"""

if "</body>" in html:
    html = html.replace("</body>", header_v4 + header_v4_js + "\n</body>", 1)
else:
    html += header_v4 + header_v4_js



# DPort UI FINAL v8 — deterministic, responsive ultra-wide header.
# Visual order:
#   DPort logo/brand -> GPX playback -> transient notification -> device connection -> Exit
# The notification is NOT persistent. The grid opens its notification column only
# when a Bootstrap toast is actually visible.
header_v8_css = """
<style id="dport-ultra-header-layout-v8">
@media (min-width:1400px){
  body.dport-layout-ultrawide .dport-hero{
    display:grid !important;
    grid-template-columns:
      195px
      minmax(360px,1fr)
      0px
      minmax(390px,1fr)
      66px !important;
    align-items:center !important;
    justify-content:space-between !important;
    column-gap:10px !important;
    row-gap:0 !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    padding:10px 12px !important;
    box-sizing:border-box !important;
    overflow:hidden !important;
  }

  /* Open exactly one notification column only while a real toast is shown. */
  body.dport-layout-ultrawide .dport-hero:has(.dport-hero-notifications .toast.show){
    grid-template-columns:
      195px
      minmax(360px,1fr)
      200px
      minmax(390px,1fr)
      66px !important;
  }

  body.dport-layout-ultrawide .dport-brand{
    grid-column:1 !important;
    grid-row:1 !important;
    width:195px !important;
    min-width:195px !important;
    max-width:195px !important;
    min-height:58px !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
    box-sizing:border-box !important;
    display:flex !important;
    align-items:center !important;
  }

  body.dport-layout-ultrawide .dport-brand-icon{
    width:58px !important;
    height:58px !important;
    min-width:58px !important;
    flex:0 0 58px !important;
    border-radius:13px !important;
  }

  body.dport-layout-ultrawide .dport-brand-text{
    min-width:0 !important;
    max-width:calc(100% - 70px) !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-name-row{
    min-width:0 !important;
    gap:0 !important;
  }

  body.dport-layout-ultrawide .dport-title{
    font-size:25px !important;
    line-height:1 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }

  body.dport-layout-ultrawide .dport-subtitle{
    margin-top:4px !important;
    font-size:12px !important;
    line-height:1.2 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }

  body.dport-layout-ultrawide .dport-caption{
    margin-top:2px !important;
    font-size:10px !important;
    line-height:1.15 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }

  body.dport-layout-ultrawide #dport-pm3-status{
    margin-top:2px !important;
    max-width:100% !important;
    font-size:9.5px !important;
    line-height:1.15 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }

  body.dport-layout-ultrawide .dport-header-center{
    display:contents !important;
    min-width:0 !important;
  }

  body.dport-layout-ultrawide .dport-standard-device-slot{
    display:none !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot{
    grid-column:2 !important;
    grid-row:1 !important;
    display:block !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
    box-sizing:border-box !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-card{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
    margin:0 !important;
    padding:6px 8px !important;
    box-sizing:border-box !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-head{
    display:grid !important;
    grid-template-columns:minmax(0,1fr) auto auto !important;
    align-items:center !important;
    gap:6px !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    margin:0 0 4px !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-section-kicker{
    font-size:8px !important;
    line-height:1 !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-section-title{
    font-size:13px !important;
    line-height:1.05 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-status-pill{
    max-width:115px !important;
    padding:2px 6px !important;
    font-size:9px !important;
    line-height:14px !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-speed-wrap{
    display:flex !important;
    align-items:center !important;
    min-width:0 !important;
    gap:4px !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-speed-label{
    font-size:8px !important;
    line-height:1 !important;
    white-space:nowrap !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-speed-select{
    width:108px !important;
    min-width:108px !important;
    max-width:108px !important;
    height:27px !important;
    padding:3px 24px 3px 7px !important;
    font-size:10px !important;
    line-height:1 !important;
    box-sizing:border-box !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-grid{
    display:grid !important;
    grid-template-columns:repeat(4,minmax(0,1fr)) !important;
    gap:5px !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-item{
    min-width:0 !important;
    height:31px !important;
    min-height:31px !important;
    max-height:31px !important;
    padding:4px 6px !important;
    box-sizing:border-box !important;
    overflow:hidden !important;
    border-radius:7px !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-item span{
    display:block !important;
    font-size:8px !important;
    line-height:9px !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot .dport-gpx-item strong{
    display:block !important;
    margin-top:1px !important;
    font-size:11.5px !important;
    line-height:13px !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }

  /* Transient notification: zero footprint until an actual toast is shown. */
  body.dport-layout-ultrawide .dport-hero-notifications{
    grid-column:3 !important;
    grid-row:1 !important;
    display:block !important;
    position:static !important;
    width:0 !important;
    min-width:0 !important;
    max-width:0 !important;
    height:0 !important;
    min-height:0 !important;
    max-height:0 !important;
    margin:0 !important;
    padding:0 !important;
    overflow:visible !important;
    box-sizing:border-box !important;
    z-index:30 !important;
  }

  body.dport-layout-ultrawide .dport-hero:has(.dport-hero-notifications .toast.show) .dport-hero-notifications{
    width:200px !important;
    min-width:200px !important;
    max-width:200px !important;
    height:58px !important;
    min-height:58px !important;
    max-height:58px !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications .toast{
    display:none !important;
    position:static !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    height:58px !important;
    min-height:58px !important;
    max-height:58px !important;
    margin:0 !important;
    padding:0 !important;
    border-radius:9px !important;
    box-sizing:border-box !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications .toast.show{
    display:block !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications #liveToast:not(.show){
    display:none !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications .toast-header{
    height:25px !important;
    min-height:25px !important;
    max-height:25px !important;
    padding:3px 7px !important;
    font-size:10px !important;
    line-height:19px !important;
    box-sizing:border-box !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications .toast-body{
    height:33px !important;
    min-height:33px !important;
    max-height:33px !important;
    padding:6px 8px !important;
    font-size:11.5px !important;
    line-height:21px !important;
    font-weight:700 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    box-sizing:border-box !important;
  }

  body.dport-layout-ultrawide .dport-hero-notifications .toast-body *{
    max-width:100% !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot{
    grid-column:4 !important;
    grid-row:1 !important;
    display:block !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
    box-sizing:border-box !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-connection-panel{
    display:block !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    margin:0 !important;
    padding:7px 8px !important;
    box-sizing:border-box !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-connection-title{
    margin:0 0 4px !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-section-kicker{
    font-size:8px !important;
    line-height:1 !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-mini-title{
    font-size:12px !important;
    line-height:1.05 !important;
    font-weight:800 !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-connection-body{
    display:flex !important;
    flex-direction:row !important;
    align-items:center !important;
    flex-wrap:nowrap !important;
    gap:7px !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-connection-body > form{
    flex:1 1 auto !important;
    width:auto !important;
    min-width:0 !important;
    max-width:none !important;
    margin:0 !important;
    padding:0 !important;
    overflow:hidden !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-connection-body form > .mb-3{
    width:100% !important;
    min-width:0 !important;
    margin:0 !important;
    padding:0 !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-connection-body form > .mb-3 > .row{
    display:flex !important;
    align-items:center !important;
    flex-wrap:nowrap !important;
    gap:7px !important;
    width:100% !important;
    min-width:0 !important;
    margin:0 !important;
    padding:0 !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-connection-body form > .mb-3 > .row > .col{
    flex:1 1 auto !important;
    width:auto !important;
    min-width:0 !important;
    max-width:none !important;
    margin:0 !important;
    padding:0 !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot #device{
    display:block !important;
    width:100% !important;
    min-width:0 !important;
    max-width:none !important;
    height:40px !important;
    min-height:40px !important;
    padding:6px 28px 6px 10px !important;
    font-size:12.5px !important;
    font-weight:800 !important;
    line-height:1.1 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
    box-sizing:border-box !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot .dport-connection-body form > .mb-3 > .row > .col-auto{
    flex:0 0 92px !important;
    width:92px !important;
    min-width:92px !important;
    max-width:92px !important;
    margin:0 !important;
    padding:0 !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot #refresh-device{
    display:inline-flex !important;
    align-items:center !important;
    justify-content:center !important;
    width:92px !important;
    min-width:92px !important;
    max-width:92px !important;
    height:40px !important;
    min-height:40px !important;
    padding:5px 4px !important;
    margin:0 !important;
    font-size:11.5px !important;
    line-height:1 !important;
    white-space:nowrap !important;
    overflow:hidden !important;
    box-sizing:border-box !important;
  }

  body.dport-layout-ultrawide .dport-ultra-device-slot #connect,
  body.dport-layout-ultrawide .dport-ultra-device-slot #disconnect{
    flex:0 0 92px !important;
    width:92px !important;
    min-width:92px !important;
    max-width:92px !important;
    height:40px !important;
    min-height:40px !important;
    padding:5px 5px !important;
    margin:0 !important;
    font-size:11.5px !important;
    line-height:1 !important;
    white-space:nowrap !important;
  }

  body.dport-layout-ultrawide .dport-hero-actions{
    grid-column:5 !important;
    grid-row:1 !important;
    display:flex !important;
    align-items:center !important;
    justify-content:flex-end !important;
    justify-self:end !important;
    width:66px !important;
    min-width:66px !important;
    max-width:66px !important;
    margin:0 !important;
    padding:0 !important;
  }

  body.dport-layout-ultrawide .dport-hero-actions #exit-btn{
    width:66px !important;
    min-width:66px !important;
    max-width:66px !important;
    height:38px !important;
    min-height:38px !important;
    padding:5px 7px !important;
    margin:0 !important;
    font-size:12px !important;
    white-space:nowrap !important;
  }
}

@media (min-width:1800px){
  body.dport-layout-ultrawide .dport-hero{
    grid-template-columns:
      220px
      minmax(520px,1fr)
      0px
      minmax(500px,600px)
      70px !important;
    column-gap:12px !important;
    padding:10px 14px !important;
  }

  body.dport-layout-ultrawide .dport-hero:has(.dport-hero-notifications .toast.show){
    grid-template-columns:
      220px
      minmax(520px,1fr)
      220px
      minmax(500px,600px)
      70px !important;
  }

  body.dport-layout-ultrawide .dport-brand{
    width:220px !important;
    min-width:220px !important;
    max-width:220px !important;
  }

  body.dport-layout-ultrawide .dport-hero:has(.dport-hero-notifications .toast.show) .dport-hero-notifications{
    width:220px !important;
    min-width:220px !important;
    max-width:220px !important;
  }

  body.dport-layout-ultrawide .dport-hero-actions,
  body.dport-layout-ultrawide .dport-hero-actions #exit-btn{
    width:70px !important;
    min-width:70px !important;
    max-width:70px !important;
  }
}

@media (min-width:2200px){
  body.dport-layout-ultrawide .dport-hero{
    grid-template-columns:
      240px
      minmax(600px,820px)
      0px
      600px
      72px !important;
    justify-content:space-between !important;
    column-gap:14px !important;
  }

  body.dport-layout-ultrawide .dport-hero:has(.dport-hero-notifications .toast.show){
    grid-template-columns:
      240px
      minmax(600px,820px)
      240px
      600px
      72px !important;
  }

  body.dport-layout-ultrawide .dport-brand{
    width:240px !important;
    min-width:240px !important;
    max-width:240px !important;
  }

  body.dport-layout-ultrawide .dport-hero:has(.dport-hero-notifications .toast.show) .dport-hero-notifications{
    width:240px !important;
    min-width:240px !important;
    max-width:240px !important;
  }
}

@media (max-width:1399px){
  body.dport-layout-ultrawide .dport-hero{
    display:flex !important;
    align-items:center !important;
    flex-wrap:wrap !important;
    gap:10px !important;
    overflow:visible !important;
  }

  body.dport-layout-ultrawide .dport-brand{
    flex:1 1 100% !important;
    width:auto !important;
    min-width:0 !important;
    max-width:100% !important;
  }

  body.dport-layout-ultrawide .dport-ultra-gpx-slot,
  body.dport-layout-ultrawide .dport-ultra-device-slot,
  body.dport-layout-ultrawide .dport-hero-notifications{
    flex:1 1 100% !important;
    width:100% !important;
    min-width:0 !important;
    max-width:100% !important;
  }
}
</style>
"""

header_v8_js = """
<script id="dport-ultra-header-layout-v8-script">
(function(){
  function ultra(){
    return !!(document.body &&
      document.body.classList.contains('dport-layout-ultrawide'));
  }


  function keepToastInHeader(toast){
    if(!ultra() || !toast) return;
    var target=document.querySelector('.dport-hero-notifications');
    if(target && toast.parentElement!==target){
      target.appendChild(toast);
    }
  }

  function enforceNotificationMode(){
    if(!ultra()) return;
    var target=document.querySelector('.dport-hero-notifications');
    if(!target) return;

    /* The application uses a transient Bootstrap toast. No persistent card. */
    target.querySelectorAll('.dport-persistent-notification').forEach(function(el){
      el.remove();
    });

    target.querySelectorAll('.toast').forEach(function(toast){
      toast.classList.toggle('dport-active-toast', toast.classList.contains('show'));
    });
  }

  function boot(){
    enforceNotificationMode();

    var target=document.querySelector('.dport-hero-notifications');
    if(target && window.MutationObserver){
      var observer=new MutationObserver(function(mutations){
        mutations.forEach(function(m){
          Array.prototype.slice.call(m.addedNodes || []).forEach(function(node){
            if(node.nodeType!==1) return;

            if(node.id==='dport-persistent-notification'){
              node.remove();
              return;
            }

            if(node.classList && node.classList.contains('toast')){
              keepToastInHeader(node);
            }

            if(node.querySelectorAll){
              node.querySelectorAll('.toast').forEach(keepToastInHeader);
            }
          });
        });

        enforceNotificationMode();
      });
      observer.observe(document.body,{childList:true,subtree:true});
    }

  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',boot,{once:true});
  }else{
    boot();
  }
})();
</script>
"""

# Remove all previous generated ultra-wide header layers from the source template.
for pattern in (
    r'\s*<style id="dport-ultra-header-layout-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-ultra-header-layout-v[0-9]+-script">.*?</script>\s*',
    r'\s*<style id="dport-top-header-layout-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-top-header-layout-script-v[0-9]+">.*?</script>\s*',
    r'\s*<style id="dport-ultra-header-notification-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-ultra-header-notification-v[0-9]+-script">.*?</script>\s*',
):
    html = re.sub(pattern, "\n", html, flags=re.S)

# Keep the status label exactly as requested.
html = html.replace("DPort：檢查 GitHub 最新正式版…", "")
html = html.replace(
    "el.textContent='DPort：'+current+'（最新）';",
    "el.textContent='DPort：v6.9.0（最新）';"
)

if "</body>" in html:
    html = html.replace("</body>", header_v8_css + header_v8_js + "\n</body>", 1)
else:
    html += header_v8_css + header_v8_js

# Version label is intentionally blank at startup. The normal updater check
# populates it; when the check reaches the latest state it becomes:
# DPort：v6.9.0（最新）
path.write_text(html, encoding="utf-8")

print("DPort final UI polish v8 applied successfully.")
print("Header order: DPort logo -> GPX -> transient notification -> device connection -> Exit.")
print("Notification: Bootstrap toast only; no persistent notification card.")
print("Device selector: widened to keep iPhone list readable.")
print("GPX: compact typography and four readable information cells.")
print("Version label: shown only after the update check reports the current release.")
