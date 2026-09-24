from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

html = path.read_text(encoding="utf-8")

# Remove only previous generated final UI layers.
for pattern in (
    r'\s*<style id="dport-final-ui-polish-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-final-favorites-render-v[0-9]+">.*?</script>\s*',
    r'\s*<script id="dport-map-status-overlay-script">.*?</script>\s*',
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

if "</body>" in html:
    html = html.replace("</body>", css + favorites_js + status_js + "\n</body>", 1)
else:
    html += css + favorites_js + status_js

path.write_text(html, encoding="utf-8")

print("DPort final UI polish v8 applied successfully.")
print("Favorite X: bottom-right inside card; 30px hit target + 18px visual chip.")
print("Favorite buttons: dark blue-gray, subtle hover.")
print("Status notification: top-right inside map frame, constrained and readable.")
