from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

html = path.read_text(encoding="utf-8")

# Remove any previous version of this final polish so the build is idempotent.
html = re.sub(
    r'\s*<style id="dport-final-ui-polish-v2">.*?</style>\s*',
    '\n',
    html,
    flags=re.S,
)
html = re.sub(
    r'\s*<script id="dport-final-favorites-render-v2">.*?</script>\s*',
    '\n',
    html,
    flags=re.S,
)

block = r'''
<style id="dport-final-ui-polish-v2">
:root{
    --dport-bg:#1f2632;
    --dport-surface:#272f3d;
    --dport-surface-2:#2d3646;
    --dport-border:#4e5b72;
    --dport-border-soft:#3e495d;
    --dport-text:#f4f7fb;
    --dport-muted:#aab4c6;
    --dport-primary:#6477f5;
    --dport-primary-hover:#7183ff;
    --dport-danger-bg:rgba(157,72,72,.30);
    --dport-danger-bg-hover:rgba(181,80,80,.48);
    --dport-danger-border:rgba(224,148,148,.58);
    --dport-danger-text:#ffe8e8;
}

/* ---- Unified destructive buttons: same geometry as DPort secondary actions,
       but use a restrained translucent red for destructive intent. ---- */
#geoport-clear-coordinates,
.geoport-recent-delete-selected,
.geoport-recent-clear,
.geoport-fav-clear-all{
    min-height:50px !important;
    border-radius:10px !important;
    background:var(--dport-danger-bg) !important;
    border:1px solid var(--dport-danger-border) !important;
    color:var(--dport-danger-text) !important;
    box-shadow:none !important;
    transition:
        transform .16s ease,
        background .16s ease,
        border-color .16s ease,
        box-shadow .16s ease !important;
}
#geoport-clear-coordinates:hover,
.geoport-recent-delete-selected:hover,
.geoport-recent-clear:hover,
.geoport-fav-clear-all:hover{
    background:var(--dport-danger-bg-hover) !important;
    border-color:rgba(239,173,173,.78) !important;
    color:#ffffff !important;
    transform:translateY(-1px);
    box-shadow:0 5px 14px rgba(0,0,0,.18) !important;
}
#geoport-clear-coordinates:active,
.geoport-recent-delete-selected:active,
.geoport-recent-clear:active,
.geoport-fav-clear-all:active{
    transform:translateY(0);
}

/* ---- Favorite panel ---- */
.geoport-favorites-title{
    display:flex !important;
    align-items:center !important;
    justify-content:space-between !important;
    gap:10px !important;
    margin-top:14px !important;
    margin-bottom:8px !important;
}
.geoport-favorites-title > span:first-child{
    display:flex !important;
    align-items:baseline !important;
    gap:6px !important;
}
.geoport-fav-count{
    color:var(--dport-muted) !important;
    font-size:13px !important;
    font-weight:700 !important;
    letter-spacing:.2px;
}
.geoport-favorites-actions{
    display:flex !important;
    align-items:center !important;
}

/* Keep exactly six favorite cards visible: 2 columns × 3 rows. */
.geoport-fav-list{
    display:grid !important;
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    grid-template-rows:repeat(3,68px) !important;
    grid-auto-rows:68px !important;
    gap:8px !important;
    padding:9px !important;
    margin:0 !important;
    max-height:236px !important;
    overflow-y:auto !important;
    overflow-x:hidden !important;
    border:1px solid var(--dport-border-soft) !important;
    border-radius:14px !important;
    background:rgba(27,33,44,.68) !important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.025) !important;
    scrollbar-width:thin !important;
    scrollbar-color:#65718a transparent !important;
}
.geoport-fav-list::-webkit-scrollbar{
    width:7px;
}
.geoport-fav-list::-webkit-scrollbar-track{
    background:transparent;
}
.geoport-fav-list::-webkit-scrollbar-thumb{
    background:#5f6b82;
    border-radius:999px;
}

/* Favorite card: clear hierarchy and a subtle hover lift. */
.geoport-fav-card{
    position:relative !important;
    min-width:0 !important;
    min-height:68px !important;
}
.geoport-fav-open{
    position:relative !important;
    width:100% !important;
    height:68px !important;
    min-height:68px !important;
    box-sizing:border-box !important;
    display:flex !important;
    align-items:center !important;
    justify-content:flex-start !important;
    text-align:left !important;
    padding:8px 30px 8px 13px !important;
    border:1px solid #50617d !important;
    border-radius:11px !important;
    background:var(--dport-surface) !important;
    color:var(--dport-text) !important;
    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;
    overflow:hidden !important;
    transition:
        transform .16s ease,
        background .16s ease,
        border-color .16s ease,
        box-shadow .16s ease !important;
}
.geoport-fav-open:hover{
    background:var(--dport-surface-2) !important;
    border-color:#768cff !important;
    transform:translateY(-1px) !important;
    box-shadow:0 7px 16px rgba(0,0,0,.22) !important;
}
.geoport-fav-open:active{
    transform:translateY(0) !important;
}
.geoport-fav-name{
    display:-webkit-box !important;
    width:100% !important;
    max-width:100% !important;
    margin:0 !important;
    padding:0 !important;
    color:#f7f9fc !important;
    font-size:15.5px !important;
    font-weight:700 !important;
    line-height:1.18 !important;
    white-space:normal !important;
    overflow:hidden !important;
    text-overflow:clip !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    overflow-wrap:anywhere !important;
}
.geoport-fav-detail{
    display:none !important;
}

/* Tiny top-right delete control. The actual red button is deliberately
   small; the card itself supplies the larger touch/click target. */
.geoport-fav-delete{
    position:absolute !important;
    top:6px !important;
    right:6px !important;
    z-index:10 !important;
    width:16px !important;
    min-width:16px !important;
    max-width:16px !important;
    height:16px !important;
    min-height:16px !important;
    max-height:16px !important;
    margin:0 !important;
    padding:0 !important;
    display:grid !important;
    place-items:center !important;
    box-sizing:border-box !important;
    border-radius:4px !important;
    background:var(--dport-danger-bg) !important;
    border:1px solid var(--dport-danger-border) !important;
    color:var(--dport-danger-text) !important;
    font-size:9px !important;
    font-weight:800 !important;
    line-height:14px !important;
    box-shadow:none !important;
    opacity:.90 !important;
    transition:
        transform .14s ease,
        background .14s ease,
        border-color .14s ease,
        opacity .14s ease !important;
}
.geoport-fav-delete:hover{
    background:var(--dport-danger-bg-hover) !important;
    border-color:rgba(239,173,173,.82) !important;
    color:#ffffff !important;
    transform:scale(1.08) !important;
    opacity:1 !important;
}

/* The clear-all control in the Favorite header is compact but shares the
   same destructive family. */
.geoport-fav-clear-all{
    min-height:38px !important;
    height:38px !important;
    min-width:56px !important;
    padding:5px 13px !important;
    font-size:14px !important;
    font-weight:700 !important;
}

/* Give the list title and actions a cohesive visual rhythm. */
.geoport-favorites-title .geoport-fav-clear-all{
    margin:0 !important;
}
.geoport-fav-empty{
    grid-column:1 / -1 !important;
    display:grid !important;
    place-items:center !important;
    min-height:68px !important;
    padding:12px !important;
    color:var(--dport-muted) !important;
    font-size:14px !important;
}
@media (max-width:700px){
    .geoport-fav-list{
        grid-template-columns:repeat(2,minmax(0,1fr)) !important;
        grid-template-rows:repeat(3,64px) !important;
        grid-auto-rows:64px !important;
        max-height:224px !important;
    }
    .geoport-fav-card,
    .geoport-fav-open{
        height:64px !important;
        min-height:64px !important;
    }
    .geoport-fav-name{
        font-size:14px !important;
    }
}
</style>

<script id="dport-final-favorites-render-v2">
(function(){
    function renderFavoritesV2(){
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
            name.textContent=String(item.name || '未命名位置');

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
            del.title='刪除 ' + String(item.name || '未命名位置');
            del.setAttribute('aria-label','刪除 ' + String(item.name || '未命名位置'));

            del.onclick=function(event){
                event.preventDefault();
                event.stopPropagation();

                var next=geoportGetFavorites() || [];
                next.splice(index,1);
                geoportSetFavorites(next);
                renderFavoritesV2();
            };

            card.appendChild(open);
            card.appendChild(del);
            box.appendChild(card);
        });
    }

    window.geoportRenderFavorites=renderFavoritesV2;

    function applyFavoriteTitle(){
        var title=document.querySelector('.geoport-favorites-title:not(.geoport-recent-title)');
        if(!title) return;

        var count=document.getElementById('geoport-fav-count');
        if(count && !count.parentElement){
            var span=document.createElement('span');
            span.id='geoport-fav-count';
            span.className='geoport-fav-count';
            span.textContent=(geoportGetFavorites ? geoportGetFavorites().length : 0) + '/20';
            title.appendChild(span);
        }

        var action=title.querySelector('.geoport-favorites-actions');
        if(!action){
            action=document.createElement('div');
            action.className='geoport-favorites-actions';

            var clear=document.createElement('button');
            clear.type='button';
            clear.className='geoport-fav-clear-all';
            clear.textContent='清除';
            clear.title='一鍵清除全部我的最愛';
            clear.addEventListener('click',function(){
                if(typeof window.geoportClearFavorites==='function'){
                    window.geoportClearFavorites();
                }
            });

            action.appendChild(clear);
            title.appendChild(action);
        }
    }

    function init(){
        applyFavoriteTitle();
        renderFavoritesV2();
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',init,{once:true});
    }else{
        init();
    }
})();
</script>
'''

inject_at = '</body>'
if inject_at in html:
    html = html.replace(inject_at, block + '\n</body>', 1)
else:
    html += block

path.write_text(html, encoding="utf-8")
print("FINAL UI polish applied.")
print("Favorite grid: 2 columns × 3 visible rows.")
print("Favorite delete: 16x16, top-right, translucent red.")
print("Destructive buttons: unified translucent-red DPort style with hover.")
