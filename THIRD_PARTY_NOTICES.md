# DPort Third-Party Notices

This document identifies the principal third-party software and external resources used by DPort.
Third-party software remains owned by its respective authors and is governed by its own license.

This file supplements, and does not replace, the original LICENSE / NOTICE files supplied by
the respective upstream projects.

## 1. Upstream project

DPort Windows is derived from and incorporates code from:

- **GeoPort** — https://github.com/davesc63/GeoPort
- License: **GNU General Public License v3.0 (GPL-3.0)**

DPort contains DPort-specific modifications, including UI, Traditional Chinese (Taiwan)
localization, GPX-related behavior, device-state handling, build/release integration and
other project-specific changes.

The original GeoPort copyright and GPL rights remain applicable to covered portions.

## 2. Python dependencies

The versions below reflect the current direct requirements in `requirements-build.txt`.

| Component | Requirement | License | Upstream |
|---|---|---|---|
| pymobiledevice3 | 11.19.4 | GPL-3.0-or-later | https://github.com/doronz88/pymobiledevice3 |
| Flask | unpinned | BSD-3-Clause | https://github.com/pallets/flask |
| Requests | unpinned | Apache-2.0 | https://github.com/psf/requests |
| pyuac | unpinned | MIT | https://github.com/Preston-Landers/pyuac |
| psutil | unpinned | BSD-3-Clause | https://github.com/giampaolo/psutil |
| pycountry | unpinned | LGPL-2.1-or-later / release-specific | https://github.com/pycountry/pycountry |
| PyInstaller | unpinned | GPL-2.0-or-later with special exception | https://github.com/pyinstaller/pyinstaller |
| inquirer3 | unpinned | MIT | https://github.com/kazeburo/inquirer3 |
| readchar | unpinned | MIT | https://github.com/magmax/python-readchar |
| pyimg4 | unpinned | GPL-3.0 | https://github.com/iOSForensics/pyimg4 |
| pytun-pmd3 | unpinned | GPL-3.0-or-later | https://github.com/doronz88/pytun-pmd3 |

### GPL components

DPort's current dependency set includes GPL-covered software. The GPL terms apply to the
relevant covered components and to the DPort distribution to the extent required by those
licenses.

DPort's top-level GPL-3.0 license is intended to be compatible with these GPL-covered
components. DPort does not use its license to remove or restrict rights granted by a
third-party GPL license.

## 3. Web / frontend libraries referenced by DPort

The DPort map interface currently references third-party browser libraries and plugins,
including:

- jQuery
- Bootstrap
- Popper
- Leaflet
- Leaflet Providers
- Leaflet GeoSearch
- Leaflet GPX
- Leaflet Omnivore / Mapbox plugin
- Leaflet FileLayer
- Leaflet Routing Machine
- Leaflet EasyButton
- Font Awesome
- Lineicons

These libraries are loaded from their respective upstream/CDN locations in the map
interface. Their respective copyright notices, licenses and terms remain applicable.

DPort does not claim ownership of these libraries.

## 4. Map data and map providers

DPort references external map tile/data services including OpenStreetMap, Stadia Maps,
OpenMapTiles and other providers present in the map configuration.

Their data, tiles, trademarks, usage limits, API requirements and attribution requirements
remain controlled by the respective providers.

DPort's source code does not transfer or grant any rights in third-party map data or
provider trademarks.

Where attribution is required by the provider, DPort's map interface should retain the
applicable attribution.

## 5. License preservation

When distributing DPort source code or executable builds:

1. Preserve the applicable copyright and license notices for third-party components.
2. Do not remove or replace upstream GPL notices.
3. Provide the source code / corresponding source required by applicable GPL terms for
   distributed GPL-covered builds.
4. Do not impose additional restrictions on rights granted by GPL-covered components.
5. Retain the relevant third-party license and notice files with release materials when
   required by the applicable license.
6. Keep this document synchronized with the actual dependency set used by the build.

## 6. Dependency version accuracy

Only direct dependencies are listed above. Most requirements are intentionally unpinned, so
the exact transitive dependency versions in a given build may differ.

For each formal release, the release source tag and build environment should be treated as
the authoritative record of the source used to create that release.

## 7. Security and secrets

The repository must not contain:

- API keys
- passwords
- access tokens
- private keys
- code-signing certificates
- Apple Developer secrets
- other confidential credentials

The repository contains only example configuration such as `moenv_api_key.txt.example`.
Actual credentials must remain in local configuration or GitHub Secrets.

## 8. Trademarks

DPort and Dicky are project branding used by DickyR15.

Apple, iPhone, iPad, iOS, iPadOS and related names/logos are trademarks of Apple Inc.
DPort is not an Apple product and does not claim affiliation, sponsorship or endorsement by
Apple.

Third-party project names and logos remain the property of their respective owners.

## 9. Important scope statement

This file is a practical attribution and compliance guide. It is not intended to replace the
full license text supplied by each upstream project.

Where a third-party license conflicts with this summary, the original third-party license
controls.
