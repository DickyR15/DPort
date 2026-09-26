from pathlib import Path

MAP = Path("src/templates/map.html")

START_STYLE_ID = "dport-startup-render-gate"
START_SCRIPT_ID = "dport-startup-render-gate-script"
REVEAL_SCRIPT_ID = "dport-startup-render-reveal"

GATE_STYLE = r'''
<style id="dport-startup-render-gate">
html.dport-startup-gated {
  background: #11151c !important;
}
html.dport-startup-gated body {
  visibility: hidden !important;
  opacity: 0 !important;
}
html.dport-startup-ready body {
  visibility: visible !important;
  opacity: 1 !important;
}
</style>
'''

GATE_SCRIPT = r'''
<script id="dport-startup-render-gate-script">
(function () {
  document.documentElement.classList.add('dport-startup-gated');
})();
</script>
'''

REVEAL_SCRIPT = r'''
<script id="dport-startup-render-reveal">
(function () {
  'use strict';

  var revealed = false;

  function reveal() {
    if (revealed) return;
    revealed = true;
    document.documentElement.classList.remove('dport-startup-gated');
    document.documentElement.classList.add('dport-startup-ready');
  }

  function afterDomReady() {
    var styleLinks = Array.prototype.slice.call(
      document.querySelectorAll('link[rel="stylesheet"]')
    );

    var stylePromises = styleLinks.map(function (link) {
      if (link.sheet) return Promise.resolve();
      return new Promise(function (resolve) {
        var done = false;
        function finish() {
          if (done) return;
          done = true;
          resolve();
        }
        link.addEventListener('load', finish, { once: true });
        link.addEventListener('error', finish, { once: true });
      });
    });

    var fontsReady =
      document.fonts && document.fonts.ready
        ? document.fonts.ready.catch(function () {})
        : Promise.resolve();

    Promise.all(stylePromises.concat([fontsReady]))
      .then(function () {
        requestAnimationFrame(function () {
          requestAnimationFrame(reveal);
        });
      })
      .catch(reveal);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', afterDomReady, { once: true });
  } else {
    afterDomReady();
  }

  // Safety fallback: never leave the app invisible forever if an external
  // CDN resource fails independently of DPort.
  setTimeout(reveal, 5000);

  // Once every page resource has loaded, ensure the gate is removed.
  window.addEventListener('load', reveal, { once: true });
})();
</script>
'''

html = MAP.read_text(encoding="utf-8")

# Idempotent: do not add another startup gate when the clean source package
# is rebuilt by GitHub Actions.
if START_STYLE_ID in html or REVEAL_SCRIPT_ID in html:
    print("DPort startup render gate already present.")
else:
    head_pos = html.lower().find("<head")
    head_end = html.find(">", head_pos)
    if head_pos < 0 or head_end < 0:
        raise SystemExit("HTML <head> opening tag not found.")
    html = html[:head_end + 1] + GATE_STYLE + GATE_SCRIPT + html[head_end + 1:]

    body_pos = html.lower().rfind("</body>")
    if body_pos < 0:
        raise SystemExit("HTML </body> marker not found.")
    html = html[:body_pos] + REVEAL_SCRIPT + html[body_pos:]

    MAP.write_text(html, encoding="utf-8")
    print("DPort startup render gate installed.")
