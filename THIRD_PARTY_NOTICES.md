# DPort Third-Party Notices

Copyright © 2026 DickyR15 / DPort

This file records the principal third-party Python packages directly declared by DPort in
`requirements-build.txt`. These components are **not owned by DickyR15 / DPort** and remain
subject to their respective original licenses.

This notice is informational and does not replace the license files distributed by the
respective upstream projects.

## Direct dependencies

| Component | DPort requirement | License | Upstream |
|---|---|---|---|
| pymobiledevice3 | 11.19.1 | GPL-3.0-or-later | https://github.com/doronz88/pymobiledevice3 |
| Flask | unpinned | BSD-3-Clause | https://github.com/pallets/flask |
| Requests | unpinned | Apache-2.0 | https://github.com/psf/requests |
| pyuac | unpinned | MIT | https://github.com/Preston-Landers/pyuac |
| psutil | unpinned | BSD-3-Clause | https://github.com/giampaolo/psutil |
| pycountry | unpinned | LGPL-2.1-or-later / LGPL-2.1 for some releases | https://github.com/pycountry/pycountry |
| PyInstaller | unpinned | GPL-2.0-or-later with PyInstaller's special exception; some files Apache-2.0 | https://github.com/pyinstaller/pyinstaller |
| inquirer3 | unpinned | MIT | https://github.com/kazeburo/inquirer3 |
| readchar | unpinned | MIT | https://github.com/magmax/python-readchar |
| pyimg4 | unpinned | GPL-3.0 | https://github.com/iOSForensics/pyimg4 |
| pytun-pmd3 | unpinned | GPL-3.0-or-later | https://github.com/doronz88/pytun-pmd3 |

## Important GPL components

DPort currently declares GPL-licensed components, including:

- `pymobiledevice3` — GPL-3.0-or-later.
- `pyimg4` — GPL-3.0.
- `pytun-pmd3` — GPL-3.0-or-later.

The presence of these components is important when distributing a DPort executable that
contains or links to them. DPort's own license does **not** override, restrict, or replace
the licenses of these components.

The DPort project must comply with the applicable GPL terms when distributing versions that
include GPL-covered components.

## LGPL component

`pycountry` is LGPL-licensed. The exact LGPL expression can vary by release, so the
license supplied with the installed/distributed version should be retained and checked.

## PyInstaller exception

PyInstaller uses GPL licensing with a special exception that permits PyInstaller to be used
to bundle non-free and commercial applications, subject to the licenses of the application's
dependencies.

This exception does **not** remove or change the license obligations of other dependencies
included in the resulting executable.

## License and copyright preservation

When distributing DPort builds containing third-party components:

1. Do not claim third-party source code as DPort original work.
2. Preserve applicable copyright notices and license texts.
3. Follow the redistribution requirements of each applicable license.
4. For GPL-covered components, provide the source-code rights and corresponding materials
   required by the applicable GPL terms when required for the distributed form.
5. Do not use the DPort License to impose restrictions on rights that the applicable
   third-party license grants to recipients.
6. Keep this notice synchronized with the actual dependencies included in release builds.

## Version accuracy

The direct requirements in `requirements-build.txt` currently leave most packages unpinned.
Therefore, the exact dependency versions included in a particular release may differ.

For a legally precise release notice, the build should record the exact installed package
versions and their license metadata (for example, from the build environment or a generated
SBOM) and retain the corresponding upstream license texts.

Transitive dependencies of the packages listed above are not exhaustively enumerated here.
They may have additional licenses and copyright notices and should be included in a complete
release-level software bill of materials.

## Sources

- pymobiledevice3: https://github.com/doronz88/pymobiledevice3
- Flask: https://github.com/pallets/flask
- Requests: https://github.com/psf/requests
- pyuac: https://github.com/Preston-Landers/pyuac
- psutil: https://github.com/giampaolo/psutil
- pycountry: https://github.com/pycountry/pycountry
- PyInstaller: https://github.com/pyinstaller/pyinstaller
- inquirer3: https://github.com/kazeburo/inquirer3
- readchar: https://github.com/magmax/python-readchar
- pyimg4: https://github.com/iOSForensics/pyimg4
- pytun-pmd3: https://github.com/doronz88/pytun-pmd3

## DPort License

DPort's own original code and assets are governed by the DPort License in `LICENSE`,
except where a file or component is explicitly identified as third-party code.

Third-party licenses always control the third-party components to which they apply.
