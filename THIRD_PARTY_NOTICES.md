# DPort Third-Party Notices

Copyright © 2026 DickyR15 / DPort for DPort-specific contributions.

This project contains, derives from, or distributes third-party software and services.
DPort's own copyright does not replace or override any third-party license.

## 1. Upstream project: GeoPort

- Project: GeoPort
- Repository: https://github.com/davesc63/GeoPort
- License: GNU GPL v3.0
- DPort relationship: DPort Windows is derived from and substantially modified from the GeoPort codebase.
- Upstream credit: davesc63 and the GeoPort contributors.

DPort-specific changes include UI changes, Traditional Chinese (Taiwan) localization, DPort
branding, update/build tooling, and other project-specific changes. The source history and
repository contents should be used to identify exact modified portions.

## 2. Python dependencies

| Component | Declared version | License | Upstream |
|---|---:|---|---|
| pymobiledevice3 | 11.19.4 | GPL-3.0-or-later | https://github.com/doronz88/pymobiledevice3 |
| Flask | build-time version | BSD-3-Clause | https://github.com/pallets/flask |
| requests | build-time version | Apache-2.0 | https://github.com/psf/requests |
| pyuac | build-time version | MIT | https://github.com/Preston-Landers/pyuac |
| psutil | build-time version | BSD-3-Clause | https://github.com/giampaolo/psutil |
| pycountry | build-time version | LGPL-2.1-or-later (verify exact release) | https://github.com/flyingcircusio/pycountry |
| PyInstaller | build-time version | GPL-2.0-or-later with PyInstaller exception | https://github.com/pyinstaller/pyinstaller |
| inquirer3 | build-time version | MIT | https://github.com/kazeburo/inquirer3 |
| readchar | build-time version | MIT | https://github.com/magmax/python-readchar |
| pyimg4 | build-time version | GPL-3.0 | https://github.com/iOSForensics/pyimg4 |
| pytun-pmd3 | build-time version | GPL-3.0-or-later | https://github.com/doronz88/pytun-pmd3 |

The exact versions shipped in a release may be determined by the build environment. Release
documentation should be kept consistent with the produced build and, where possible, an
automated dependency/license manifest should be retained with each release.

## 3. Front-end libraries referenced by map.html

DPort's map UI references third-party libraries loaded from public CDNs, including:

| Component | Version shown in source | License / notes |
|---|---:|---|
| Leaflet | 1.9.4 | BSD-2-Clause |
| Bootstrap | 5.1.3 | MIT |
| jQuery | 3.3.1 | MIT |
| @popperjs/core | 2.10.2 | MIT |
| Leaflet Providers | 2.0.0 | Follow upstream license |
| Leaflet GeoSearch | 3.0.0 | Follow upstream license |
| leaflet-gpx | 1.7.0 | Follow upstream license |
| leaflet-omnivore | 0.3.1 | Follow upstream license |
| leaflet-filelayer | 1.2.0 | Follow upstream license |
| Leaflet Routing Machine | 3.2.12 | Follow upstream license |
| Leaflet EasyButton | 2.4.0 | Follow upstream license |
| Font Awesome | 6.5.2 | Code/font assets have separate license terms |
| Lineicons | 4.0 | Follow upstream license |

The repository should retain appropriate attribution and must not imply ownership of these
libraries, icons, fonts, or other third-party assets.

## 4. Map data and tile providers

The map template contains attribution for services/data including OpenStreetMap, Stadia Maps,
OpenMapTiles, Humanitarian OpenStreetMap Team, and other providers.

Map and tile services can have separate terms of use, rate limits, attribution requirements,
API keys, or commercial restrictions. A tile URL in source code does not itself grant a right
to copy, cache, redistribute, or commercially use provider content.

## 5. Apple trademarks and services

Apple, iPhone, iPad, iOS, iPadOS and related names are trademarks or other protected marks of
Apple Inc. DPort is an independent project and does not claim Apple endorsement, sponsorship,
certification, or affiliation.

## 6. GPL source and binary distribution

When distributing a release containing GPL-covered material, comply with the GPL terms that
apply to the distributed work. For binary distributions, make the corresponding source and
other required materials available in a manner permitted by the GPL.

DPort does not use its branding or project notices to remove, restrict, or replace rights
granted by GPL-covered material.

## 7. License hierarchy

For any component that is not DPort-original material, the component's own copyright and
license continue to control that component. Where a third-party license grants rights or
imposes obligations different from this project's summary text, the actual third-party
license controls.

## 8. Sources

- GeoPort: https://github.com/davesc63/GeoPort
- pymobiledevice3: https://github.com/doronz88/pymobiledevice3
- pyimg4: https://github.com/iOSForensics/pyimg4
- pytun-pmd3: https://github.com/doronz88/pytun-pmd3
- Leaflet: https://github.com/Leaflet/Leaflet
- GNU GPL v3: https://www.gnu.org/licenses/gpl-3.0.html
