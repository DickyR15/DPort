from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

text = path.read_text(encoding="utf-8")
original = text

# ---------------------------------------------------------------------------
# 1. Device refresh button fix
# ---------------------------------------------------------------------------
legacy_pattern = re.compile(
    r'''\s*<script>\s*\(function\(\)\{\s*
        function\s+syncDeviceRefreshButton\(\)\s*\{.*?
        document\.addEventListener\(\s*['"]DOMContentLoaded['"]\s*,\s*function\(\)\{\s*
        syncDeviceRefreshButton\(\);\s*
        setInterval\(syncDeviceRefreshButton\s*,\s*500\);\s*
        \}\);\s*
        \}\)\(\);\s*</script>\s*''',
    re.S | re.X,
)
text, legacy_removed = legacy_pattern.subn("\n", text)

text = text.replace(
    "button.disabled = (typeof isDeviceConnected !== 'undefined' && isDeviceConnected);",
    "button.disabled = false;",
)

handler_pattern = re.compile(
    r'''(function\s+handleUsbCableRemoved\(\)\s*\{.*?
        if\s*\(spinnerElement\)\s*spinnerElement\.style\.display\s*=\s*'none';)''',
    re.S | re.X,
)
if "refreshButtonAfterUsbRemoval.disabled = false;" not in text:
    def handler_repl(match):
        return match.group(1) + """
    var refreshButtonAfterUsbRemoval = document.getElementById('refresh-device');
    if (refreshButtonAfterUsbRemoval) {
        refreshButtonAfterUsbRemoval.disabled = false;
        refreshButtonAfterUsbRemoval.removeAttribute('aria-disabled');
    }"""
    text, handler_hits = handler_pattern.subn(handler_repl, text, count=1)
else:
    handler_hits = 0

text = text.replace(
    'title="重新讀取 USB 裝置清單"',
    'title="重新讀取 USB / Wi-Fi 裝置清單"',
)

# ---------------------------------------------------------------------------
# 2. Normal map-click -> coordinate + reverse geocode
# ---------------------------------------------------------------------------
map_click_old = """    // DPort: ordinary map clicks are inert. Drawing mode is the only mode
    // where a map click is allowed to add a route point.
    map.on('click', function(event){
        if (typeof isDrawingMode !== 'undefined' && isDrawingMode) {
            handleMapClick(event);
        }
    });"""

map_click_new = """    // Normal map clicks select a coordinate and identify the place.
    // Drawing mode keeps the existing route-point behavior.
    map.on('click', function(event){
        if (typeof isDrawingMode !== 'undefined' && isDrawingMode) {
            handleMapClick(event);
            return;
        }

        const lat = Number(event.latlng.lat);
        const lng = Number(event.latlng.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

        if (typeof geoportSetMapOnlyCoordinates === 'function') {
            geoportSetMapOnlyCoordinates(lat, lng);
        }
        if (typeof geoportMoveActiveMarker === 'function') {
            geoportMoveActiveMarker(lat, lng, 15);
        }
        if (typeof geoportScheduleReverseGeocode === 'function') {
            geoportScheduleReverseGeocode(lat, lng);
        }
        if (typeof geoportStatus === 'function') {
            geoportStatus('正在辨識地點……', false);
        }
    });"""

if map_click_old in text:
    text = text.replace(map_click_old, map_click_new, 1)
elif "Normal map clicks select a coordinate and identify the place." not in text:
    raise SystemExit("Expected map click handler was not found.")

# ---------------------------------------------------------------------------
# 3. Favorite place-name resolver
# ---------------------------------------------------------------------------
reverse_marker = "function geoportScheduleReverseGeocode(lat,lng){"
resolver = """window.geoportResolvePlaceNameForCoordinates = async function(lat,lng){
    var cached=geoportGetCurrentPlaceNameForCoordinates(lat,lng);
    if(cached) return cached;

    var a=Number(lat),b=Number(lng);
    if(!Number.isFinite(a)||!Number.isFinite(b)) return '';

    var url='https://nominatim.openstreetmap.org/reverse?format=jsonv2'
        +'&lat='+encodeURIComponent(a)
        +'&lon='+encodeURIComponent(b)
        +'&zoom=18&addressdetails=1&namedetails=1'
        +'&accept-language=zh-TW,zh;q=0.9,en;q=0.7';

    try{
        var data=await fetchJsonWithTimeout(url,5000);
        if(!data) return '';

        var name='';
        if(typeof geoportFormatReverseName==='function'){
            name=geoportFormatReverseName(data);
        }
        return name || String(data.display_name||'').trim();
    }catch(e){
        return '';
    }
};

"""
if "async function geoportResolvePlaceNameForCoordinates" not in text:
    if reverse_marker not in text:
        raise SystemExit("Reverse geocode function marker was not found.")
    text = text.replace(reverse_marker, resolver + reverse_marker, 1)

# ---------------------------------------------------------------------------
# 4. Favorites UI: 2 columns normally, 3 on wide screens, 6 visible slots
# ---------------------------------------------------------------------------
fav_render_old = """function geoportRenderFavorites(){
    const box=document.getElementById('geoport-favorites'); if(!box) return;
    const items=geoportGetFavorites(); box.innerHTML='';
    if(!items.length){ box.innerHTML='<small>沒有已儲存的位置。</small>'; return; }
    items.forEach((item,i)=>{
        const b=document.createElement('button'); b.type='button'; b.className='btn btn-sm btn-outline-secondary'; b.textContent=item.name;
        b.onclick=()=>{geoportSetMapOnlyCoordinates(item.lat,item.lng); geoportMoveActiveMarker(item.lat,item.lng,15)};
        box.appendChild(b);
        const d=document.createElement('button'); d.type='button'; d.className='btn btn-sm btn-outline-danger'; d.textContent='×'; d.title='刪除 '+item.name;
        d.onclick=()=>{const a=geoportGetFavorites();a.splice(i,1);geoportSetFavorites(a);geoportRenderFavorites()}; box.appendChild(d);
    });
}"""

fav_render_new = """function geoportRenderFavorites(){
    const box=document.getElementById('geoport-favorites'); if(!box) return;
    const items=geoportGetFavorites(); box.innerHTML='';

    const count=document.getElementById('geoport-fav-count');
    if(count) count.textContent=items.length + '/20';

    if(!items.length){
        box.innerHTML='<div class="geoport-fav-empty">還沒有儲存的位置</div>';
        return;
    }

    items.forEach((item,i)=>{
        const card=document.createElement('div');
        card.className='geoport-fav-card';

        const open=document.createElement('button');
        open.type='button';
        open.className='geoport-fav-open';
        open.title='前往 ' + String(item.name || '未命名位置');

        const name=document.createElement('span');
        name.className='geoport-fav-name';
        name.textContent=String(item.name || '未命名位置');

        const detail=document.createElement('span');
        detail.className='geoport-fav-detail';
        detail.textContent=Number(item.lat).toFixed(6) + ', ' + Number(item.lng).toFixed(6);

        open.appendChild(name);
        open.appendChild(detail);
        open.onclick=()=>{
            geoportSetMapOnlyCoordinates(item.lat,item.lng);
            geoportMoveActiveMarker(item.lat,item.lng,15);
            geoportStatus('已載入最愛位置', false);
        };

        const del=document.createElement('button');
        del.type='button';
        del.className='geoport-fav-delete';
        del.textContent='×';
        del.title='刪除 ' + String(item.name || '未命名位置');
        del.setAttribute('aria-label','刪除 ' + String(item.name || '未命名位置'));
        del.onclick=(event)=>{
            event.preventDefault();
            event.stopPropagation();
            const next=geoportGetFavorites();
            next.splice(i,1);
            geoportSetFavorites(next);
            geoportRenderFavorites();
        };

        card.appendChild(open);
        card.appendChild(del);
        box.appendChild(card);
    });
}"""

if fav_render_old in text:
    text = text.replace(fav_render_old, fav_render_new, 1)
elif "geoport-fav-card" not in text:
    raise SystemExit("Favorite renderer was not found.")

fav_save_old = """async function geoportSaveFavorite(){
    const c=geoportParseCoordinates(document.getElementById('coordinates').value);
    if(!c){dportUiAlert('請輸入緯度與經度。');return;}
    const suggestedName =
        geoportGetCurrentPlaceNameForCoordinates(c.lat,c.lng) ||
        '自訂位置';
    const name=await dportUiPrompt('請輸入此地點名稱', suggestedName);
    if(name===null) return;
    const cleanName=String(name).trim();
    if(!cleanName){dportUiAlert('地點名稱不可空白。');return;}
    const a=geoportGetFavorites().filter(x=>!(x.lat===c.lat&&x.lng===c.lng)); a.unshift({name:cleanName,lat:c.lat,lng:c.lng}); geoportSetFavorites(a); geoportRenderFavorites();
}"""

fav_save_new = """async function geoportSaveFavorite(){
    const c=geoportParseCoordinates(document.getElementById('coordinates').value);
    if(!c){dportUiAlert('請輸入緯度與經度。');return;}

    let suggestedName=geoportGetCurrentPlaceNameForCoordinates(c.lat,c.lng);
    if(!suggestedName && typeof geoportResolvePlaceNameForCoordinates==='function'){
        suggestedName=await geoportResolvePlaceNameForCoordinates(c.lat,c.lng);
    }
    suggestedName=suggestedName || '自訂位置';

    const name=await dportUiPrompt(
        '請輸入此地點名稱（可直接使用自動辨識名稱）',
        suggestedName
    );
    if(name===null) return;

    const cleanName=String(name).trim();
    if(!cleanName){dportUiAlert('地點名稱不可空白。');return;}

    const a=geoportGetFavorites().filter(x=>!(x.lat===c.lat&&x.lng===c.lng));
    a.unshift({name:cleanName,lat:c.lat,lng:c.lng});
    geoportSetFavorites(a);
    geoportRenderFavorites();
}"""

if fav_save_old in text:
    text = text.replace(fav_save_old, fav_save_new, 1)
elif "geoportResolvePlaceNameForCoordinates(c.lat,c.lng)" not in text:
    raise SystemExit("Favorite save routine was not found.")

# ---------------------------------------------------------------------------
# 5. Repeatable positioning: never present success as "已定位"
# ---------------------------------------------------------------------------
text = text.replace(
    "geoportStatus('已定位', true);",
    "geoportStatus('定位成功，可再次定位', true);",
)

text = text.replace(
    "const isLocated = /即時定位已啟用|已定位/.test(text);",
    "const isLocated = false; // 定位成功後仍可再次定位",
)

# ---------------------------------------------------------------------------
# 6. Favorites count
# ---------------------------------------------------------------------------
title_old = '<div class="geoport-favorites-title">我的最愛位置</div>'
title_new = '<div class="geoport-favorites-title">我的最愛位置 <span id="geoport-fav-count" class="geoport-fav-count">0/20</span></div>'
if title_old in text:
    text = text.replace(title_old, title_new, 1)

# ---------------------------------------------------------------------------
# 7. Favorites CSS
# ---------------------------------------------------------------------------
css_old = '.geoport-fav-list{padding:9px 11px !important;border:1.5px solid #aaa}'
css_new = """.geoport-fav-list{
    display:grid !important;
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:8px;
    padding:10px !important;
    border:1px solid rgba(170,170,170,.65);
    border-radius:12px;
    max-height:236px;
    overflow-y:auto;
    overflow-x:hidden;
    scrollbar-width:thin;
}
.geoport-fav-card{position:relative;min-width:0}
.geoport-fav-open{
    width:100%;
    min-height:64px;
    border:1px solid rgba(180,190,215,.55) !important;
    border-radius:10px !important;
    display:flex;
    flex-direction:column;
    align-items:flex-start;
    justify-content:center;
    text-align:left;
    padding:9px 36px 9px 12px !important;
    overflow:hidden;
}
.geoport-fav-open:hover{filter:brightness(1.08)}
.geoport-fav-name{
    width:100%;
    font-size:16px !important;
    font-weight:700 !important;
    line-height:1.25;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.geoport-fav-detail{
    width:100%;
    margin-top:3px;
    font-size:11px;
    opacity:.72;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.geoport-fav-delete{
    position:absolute;
    top:6px;
    right:6px;
    width:26px;
    height:26px;
    padding:0 !important;
    border:1px solid rgba(220,150,150,.75) !important;
    border-radius:8px !important;
    background:transparent !important;
    color:inherit !important;
    font-size:18px !important;
    line-height:24px;
    font-weight:700;
    cursor:pointer;
}
.geoport-fav-empty{
    grid-column:1 / -1;
    padding:14px 10px;
    text-align:center;
    opacity:.72;
    font-size:14px;
}
.geoport-fav-count{
    font-size:13px !important;
    font-weight:600 !important;
    opacity:.68;
    margin-left:6px;
}
@media (min-width:1180px){
    .geoport-fav-list{grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media (max-width:700px){
    .geoport-fav-list{grid-template-columns:repeat(2,minmax(0,1fr));max-height:220px}
    .geoport-fav-open{min-height:60px;padding-left:10px !important}
    .geoport-fav-name{font-size:15px !important}
}"""

if '.geoport-fav-card{' not in text:
    if css_old not in text:
        raise SystemExit("Favorite CSS block was not found.")
    text = text.replace(css_old, css_new, 1)

path.write_text(text, encoding="utf-8")

print(f"legacy refresh timer removed: {legacy_removed}")
print(f"USB removal handler patched: {handler_hits}")
print("6.9.1 location/favorites UI improvements applied.")
print("- Map click restores coordinate picking + reverse geocoding")
print("- Favorite name resolves automatically before save")
print("- Favorite list shows 6 slots in a compact grid and scrolls after overflow")
print("- Successful simulation keeps the location button reusable")


# ==================== DPort 6.9.1 speed / favorites polish ====================

# The first 6.9.1 pass waited for reverse-geocoding before showing the Favorite
# prompt. Keep saving instant: create the Favorite immediately and let the
# place-name lookup finish in the background. Only replace the temporary name
# if the user has not manually changed it.
text += r'''
<style>
/* DPort 6.9.1 Favorite palette: match the main blue/red controls and keep
   contrast strong in dark mode. */
.geoport-favorites-title{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:10px;
}
.geoport-favorites-actions{
    display:flex;
    align-items:center;
    gap:7px;
}
.geoport-fav-clear-all{
    min-height:34px;
    padding:5px 11px !important;
    border-radius:9px !important;
    font-size:13px !important;
    font-weight:700 !important;
    color:#fff !important;
    background:#a33b3b !important;
    border:1px solid #ffaaaa !important;
    cursor:pointer;
}
.geoport-fav-clear-all:hover{
    filter:brightness(1.08);
}
.geoport-fav-list{
    display:grid !important;
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    grid-template-rows:repeat(3,64px);
    grid-auto-rows:64px;
    gap:8px;
    padding:10px !important;
    border:1px solid #667086 !important;
    border-radius:12px;
    max-height:228px !important; /* 3 rows = 6 visible Favorite buttons */
    overflow-y:auto !important;
    overflow-x:hidden !important;
    scrollbar-width:thin;
}
.geoport-fav-card{
    position:relative;
    min-width:0;
    min-height:64px;
}
.geoport-fav-open{
    width:100%;
    height:64px;
    min-height:64px !important;
    border:1px solid #9ab3ff !important;
    border-radius:10px !important;
    background:#2f3542 !important;
    color:#ffffff !important;
    display:flex;
    align-items:center;
    justify-content:flex-start;
    text-align:left;
    padding:8px 35px 8px 12px !important;
    overflow:hidden;
    box-shadow:none !important;
}
.geoport-fav-open:hover{
    background:#36415a !important;
    border-color:#9ab3ff !important;
}
.geoport-fav-open:focus-visible{
    outline:2px solid #9ab3ff !important;
    outline-offset:1px;
}
.geoport-fav-name{
    width:100%;
    font-size:16px !important;
    font-weight:700 !important;
    line-height:1.2;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
    color:#fff !important;
}
.geoport-fav-name.long{
    font-size:14px !important;
    line-height:1.18;
    white-space:normal;
    overflow:hidden;
    text-overflow:clip;
    display:-webkit-box;
    -webkit-box-orient:vertical;
    -webkit-line-clamp:2;
    word-break:break-word;
}
.geoport-fav-name.xlong{
    font-size:13px !important;
    line-height:1.15;
}
.geoport-fav-detail{display:none !important;}
.geoport-fav-delete{
    position:absolute;
    top:50%;
    right:6px;
    transform:translateY(-50%);
    width:22px;
    height:22px;
    padding:0 !important;
    border:1px solid #69758b !important;
    border-radius:6px !important;
    background:rgba(86,96,116,.38) !important;
    color:#c8d0df !important;
    font-size:14px !important;
    line-height:20px !important;
    font-weight:700 !important;
    cursor:pointer;
    opacity:.86;
}
.geoport-fav-delete:hover{
    border-color:#a7b1c5 !important;
    background:rgba(110,120,142,.58) !important;
    color:#ffffff !important;
    opacity:1;
}
.geoport-fav-empty{
    grid-column:1 / -1;
    padding:16px 10px;
    text-align:center;
    opacity:.76;
    font-size:14px;
}
.geoport-fav-count{
    font-size:13px !important;
    font-weight:600 !important;
    opacity:.7;
    margin-left:5px;
}
.geoport-fav-resolving{
    opacity:.72;
}
@media (max-width:700px){
    .geoport-fav-list{
        grid-template-columns:repeat(2,minmax(0,1fr)) !important;
        grid-auto-rows:60px;
        max-height:216px !important;
    }
    .geoport-fav-card,.geoport-fav-open{
        height:60px;
        min-height:60px !important;
    }
    .geoport-fav-name{font-size:15px !important;}
}
</style>

<script>
(function(){
    // Faster reverse geocoding: POI/landmark and map-label lookups run in
    // parallel instead of waiting on each other. Address is a final fallback.
    var geoportFastReverseController = null;

    window.geoportScheduleReverseGeocode = function(lat,lng){
        var a=Number(lat), b=Number(lng);
        if(!Number.isFinite(a)||!Number.isFinite(b)) return;

        if(geoportFastReverseController){
            try{geoportFastReverseController.abort();}catch(e){}
        }

        var controller=new AbortController();
        geoportFastReverseController=controller;
        clearTimeout(window.geoportReverseGeocodeTimer);

        window.geoportReverseGeocodeTimer=setTimeout(async function(){
            var url='https://nominatim.openstreetmap.org/reverse?format=jsonv2'
                +'&lat='+encodeURIComponent(a)
                +'&lon='+encodeURIComponent(b)
                +'&zoom=18&addressdetails=1&namedetails=1'
                +'&accept-language=zh-TW,zh;q=0.9,en;q=0.7';

            try{
                var data=await fetchJsonWithTimeout(url,5000);
                if(controller.signal.aborted || !data) return;

                var finalName='';
                if(typeof geoportFormatReverseName==='function'){
                    finalName=geoportFormatReverseName(data);
                }
                finalName=finalName || String(data.display_name||'').trim();
                finalName=finalName || '未辨識地點';

                if(typeof geoportSetCurrentPlaceName==='function'){
                    geoportSetCurrentPlaceName(finalName,a,b);
                }
                if(typeof window.dportUpdateRecentPlaceName==='function'){
                    window.dportUpdateRecentPlaceName(a,b,finalName);
                }

                var status=document.getElementById('geoport-status');
                if(status && /正在辨識地點/.test(status.textContent||'')){
                    status.textContent='已辨識地點';
                }
            }catch(e){
                if(!controller.signal.aborted){
                    console.debug('快速反向地理編碼略過一次:',e);
                }
            }
        },80);
    };

    // Save immediately. Reverse-geocoding and the optional name prompt run
    // asynchronously after the Favorite has already been persisted.
    window.geoportSaveFavorite = function(){
        var c=geoportParseCoordinates(document.getElementById('coordinates').value);
        if(!c){dportUiAlert('請輸入緯度與經度。');return;}

        var current=geoportGetCurrentPlaceNameForCoordinates(c.lat,c.lng);
        var placeholder='自動辨識中…';
        var suggested=current || placeholder;

        var items=geoportGetFavorites().filter(function(x){
            return !(x.lat===c.lat && x.lng===c.lng);
        });

        // Persist first, so clicking「儲存最愛位置」never has to wait for
        // reverse geocoding.
        var item={name:suggested,lat:c.lat,lng:c.lng};
        items.unshift(item);
        geoportSetFavorites(items);
        geoportRenderFavorites();

        if(typeof displayToast==='function'){
            displayToast('已加入我的最愛');
        }

        // Keep the manual naming feature, but do not block the save on it.
        Promise.resolve()
            .then(function(){
                return dportUiPrompt(
                    '請輸入此地點名稱（可稍後再命名）',
                    suggested
                );
            })
            .then(function(name){
                if(name===null) return;
                var cleanName=String(name).trim();
                if(!cleanName){
                    dportUiAlert('地點名稱不可空白。');
                    return;
                }

                var latest=geoportGetFavorites();
                var match=latest.find(function(x){
                    return x.lat===c.lat && x.lng===c.lng;
                });
                if(!match) return;

                match.name=cleanName;
                geoportSetFavorites(latest);
                geoportRenderFavorites();

                // A custom name supplied by the user is final.
                match._dportManualName=true;
                geoportSetFavorites(latest);
            })
            .catch(function(e){
                console.debug('最愛位置命名視窗略過一次:',e);
            });

        // Background name recognition. It can finish whenever it does; the
        // Favorite already exists and the UI never waits for this request.
        (async function(){
            if(current) return;

            var resolved='';
            try{
                if(typeof geoportResolvePlaceNameForCoordinates==='function'){
                    resolved=await geoportResolvePlaceNameForCoordinates(c.lat,c.lng);
                }
            }catch(e){}

            if(!resolved) return;

            var latest=geoportGetFavorites();
            var match=latest.find(function(x){
                return x.lat===c.lat && x.lng===c.lng;
            });
            if(!match) return;

            // Never overwrite a name the user has already entered.
            if(match.name===placeholder && !match._dportManualName){
                match.name=resolved;
                geoportSetFavorites(latest);
                geoportRenderFavorites();
            }
        })();
    };

    // One-click clear: remove all Favorite locations at once.
    window.geoportClearFavorites = function(){
        localStorage.removeItem('geoportFavorites');
        geoportRenderFavorites();
        if(typeof displayToast==='function'){
            displayToast('我的最愛位置已全部刪除');
        }
    };

    // Render Favorite cards without coordinates. Keep the list to six visible
    // cards, with a scrollbar only when there are more.
    window.geoportRenderFavorites = function(){
        var box=document.getElementById('geoport-favorites');
        if(!box) return;

        var items=geoportGetFavorites();
        box.innerHTML='';

        var count=document.getElementById('geoport-fav-count');
        if(count) count.textContent=items.length+'/20';

        if(!items.length){
            box.innerHTML='<div class="geoport-fav-empty">還沒有儲存的位置</div>';
            return;
        }

        items.forEach(function(item,i){
            var card=document.createElement('div');
            card.className='geoport-fav-card';

            var open=document.createElement('button');
            open.type='button';
            open.className='geoport-fav-open';
            open.title='前往 '+String(item.name || '未命名位置');

            var name=document.createElement('span');
            const favNameText = String(item.name || '未命名位置');
            name.className='geoport-fav-name';
            if (favNameText.length > 16) name.classList.add('long');
            if (favNameText.length > 28) name.classList.add('xlong');
            name.textContent=favNameText;

            open.appendChild(name);
            open.onclick=function(){
                geoportSetMapOnlyCoordinates(item.lat,item.lng);
                geoportMoveActiveMarker(item.lat,item.lng,15);
                geoportStatus('已載入最愛位置',false);
            };

            var del=document.createElement('button');
            del.type='button';
            del.className='geoport-fav-delete';
            del.textContent='×';
            del.title='刪除 '+String(item.name || '未命名位置');
            del.setAttribute('aria-label','刪除 '+String(item.name || '未命名位置'));
            del.onclick=function(event){
                event.preventDefault();
                event.stopPropagation();

                var next=geoportGetFavorites();
                next.splice(i,1);
                geoportSetFavorites(next);
                geoportRenderFavorites();
            };

            card.appendChild(open);
            card.appendChild(del);
            box.appendChild(card);
        });
    };
})();
</script>
'''

# Add the clear-all action to the Favorite title.
old_title = '<div class="geoport-favorites-title">我的最愛位置 <span id="geoport-fav-count" class="geoport-fav-count">0/20</span></div>'
new_title = '''<div class="geoport-favorites-title">
    <span>我的最愛位置 <span id="geoport-fav-count" class="geoport-fav-count">0/20</span></span>
    <div class="geoport-favorites-actions">
        <button type="button" class="geoport-fav-clear-all" onclick="geoportClearFavorites()" title="一鍵清除全部我的最愛">清除</button>
    </div>
</div>'''
if old_title in text:
    text=text.replace(old_title,new_title,1)

# Avoid showing the old slower "resolved name required before save" wording in
# the button prompt because the save itself is now instant.
text=text.replace(
    'title="已載入最愛位置"',
    'title="載入此最愛位置"',
)


# Final DPort 6.9.1 action styling.
# Match the subdued semi-transparent red used by the existing recent-location
# delete action. Keep this override scoped so the rest of the dark UI is intact.
text += r'''
<style>
/* One consistent DPort "delete/clear" appearance. */
#geoport-clear-coordinates,
.geoport-recent-delete-selected,
.geoport-recent-clear,
.geoport-fav-clear-all{
    background:rgba(143,59,59,.58) !important;
    border:1px solid rgba(223,158,158,.72) !important;
    color:#f6eded !important;
    box-shadow:none !important;
}
#geoport-clear-coordinates:hover,
.geoport-recent-delete-selected:hover,
.geoport-recent-clear:hover,
.geoport-fav-clear-all:hover{
    background:rgba(157,67,67,.70) !important;
    border-color:rgba(239,178,178,.82) !important;
    color:#ffffff !important;
}

/* Favorite X: small, top-right, semi-transparent red, and outside the main
   text flow so the place name never runs beneath the button. */
.geoport-fav-card{
    position:relative !important;
}
.geoport-fav-open{
    padding-right:26px !important;
}
.geoport-fav-delete{
    position:absolute !important;
    top:6px !important;
    right:6px !important;
    width:16px !important;
    min-width:16px !important;
    max-width:16px !important;
    height:16px !important;
    min-height:16px !important;
    max-height:16px !important;
    padding:0 !important;
    margin:0 !important;
    border-radius:5px !important;
    background:rgba(143,59,59,.58) !important;
    border:1px solid rgba(223,158,158,.68) !important;
    color:#f6eded !important;
    font-size:10px !important;
    font-weight:700 !important;
    line-height:14px !important;
    text-align:center !important;
    box-shadow:none !important;
    opacity:.92 !important;
    z-index:5 !important;
}
.geoport-fav-delete:hover{
    background:rgba(157,67,67,.72) !important;
    border-color:rgba(239,178,178,.82) !important;
    color:#ffffff !important;
    opacity:1 !important;
}

/* Long names keep two lines while reserving just enough space for the tiny X. */
.geoport-fav-name.long{
    font-size:14px !important;
    line-height:1.16 !important;
    white-space:normal !important;
    display:-webkit-box !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    overflow:hidden !important;
    text-overflow:clip !important;
    word-break:break-word !important;
}
.geoport-fav-name.xlong{
    font-size:12.5px !important;
    line-height:1.1 !important;
}

/* The Favorite header action remains exactly「清除」. */
.geoport-fav-clear-all{
    min-width:58px !important;
    min-height:34px !important;
    padding:5px 12px !important;
    border-radius:9px !important;
}
</style>
'''
path.write_text(text, encoding='utf-8')
print("6.9.1 favorites/location polish applied.")
print("- Reverse geocoding runs faster via parallel lookups.")
print("- Favorite saving no longer waits for place-name recognition.")
print("- Favorites show names only, six visible cards, with clearer DPort colors.")
print("- Added one-click clear-all.")


