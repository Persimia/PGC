# QGC overlay — PGC custom build

Holds the contents of our QGC custom build overlay (branding, feature flags,
Mission Studio + Box Control QML panels). Synced into a separate upstream QGC
clone's `custom/` directory — see the QGC dev guide "Custom Builds" and the
in-tree `custom-example/`. The QGC source itself is NOT vendored here.

**License note (D7, Route A):** everything under `custom/` is compiled into
the GPLv3 QGC binary and is therefore GPLv3. No proprietary logic goes here —
it belongs in the Mission Engine / Box services behind the process boundary.

## Layout & workflow

```
qgc-overlay/
  custom/               <- mirrored verbatim into <qgc-clone>/custom/
    CMakeLists.txt        build wiring (CUSTOMCLASS=CustomPlugin)
    cmake/CustomOverrides.cmake   app name "PGC", org, copyright
    custom.qrc            brand image resources
    res/img/              Persimia mark + horizontal logo (copies from ../Logos)
    src/CustomPlugin.{h,cc}  QGCCorePlugin subclass: brand images, orange
                             palette accents, ArduPilot offline-edit defaults
  sync-to-qgc.ps1       <- robocopy /MIR overlay into C:\dev\qgroundcontrol\custom
```

Workflow: edit here → `.\sync-to-qgc.ps1` → rebuild (`cmake --build
C:\dev\qgc-build --target all`). Reconfigure first whenever CMake files
changed or on the first-ever sync (the `custom/` dir is detected at
configure time).

## Solar Scan pattern (D13)

`PGCSolarScanItem` puts a "Solar Scan" entry in the Plan view Pattern menu.
Its transects come from the Mission Engine CLI, not QGC's grid code:

- **Engine discovery:** `PGC_ENGINE_CLI` env var (dev: point it at
  `mission_engine\.venv\Scripts\mission-engine.exe`), else
  `mission-engine.exe` next to `PGC.exe` (production bundling, Phase 5).
- **Fence libraries:** every `.kml` in `Documents\PGC\fences\` is validated
  against on each generation (zone tags `[keepout]`, `[min_alt=N]`,
  `[inclusion]` — see D11). `qgc-overlay/test-assets/demo_keepout.kml` is a
  ready-made refusal test.
- **Failure semantics:** engine *refusal* (exit 2 — keep-out conflict, bad
  params) clears the flight path, pops an app message, and shows a banner in
  the item editor — deliberately no fallback (a refused mission must never
  silently render a path through a hazard). Engine *unavailable* falls back
  to stock Survey generation so the tool is never dead.
- **Plan files** save with `complexItemType: "PGCSolarScan"` and round-trip
  through the plugin factory back into a Solar Scan.
- Editor QML: `custom/res/PGCSolarScanEditor.qml` (extends the stock
  transect editor — Grid/Camera/Terrain/Presets tabs stay native).

Known gaps (tracked): synchronous engine call hitches on polygon drag with
the venv Python (frozen engine will be faster); fence selection is
directory-convention rather than per-site picker; concave sites are refused
by the engine (matches current engine scope).

---

## Windows build environment setup (captured 2026-07-09)

Working recipe for building stock QGC **v5.0.8** from source on Windows 11.
Total setup time ~1 hr of downloads plus the compile. Everything is
unattended-installable — no Qt account, no GUI installers.

### Version pins (do not drift)

| Thing | Version | Why |
|---|---|---|
| QGC | `v5.0.8` tag | Latest stable release; design doc R4 says pin releases |
| Qt | **6.8.3** `win64_msvc2022_64` | v5.0.8's CI pin (`.github/workflows/windows.yml`). Note: QGC *master* docs say 6.10.1 — that applies to master, not v5.0.8. Match the tag you build. |
| MSVC | Build Tools 2026, toolset 14.50 | ABI-compatible with Qt's msvc2022 binaries; works fine |
| CMake / Ninja | 3.29.2 / 1.12 (Strawberry Perl's, already on PATH) | ≥3.25 required |

### Steps

1. **Prereqs already present on the dev machine** (install if missing):
   Visual Studio Build Tools with "Desktop development with C++"
   (MSVC + Windows SDK), CMake, Ninja, Git, Python 3.

2. **Clone QGC outside OneDrive** (the tree + build dir is multi-GB and
   OneDrive sync will choke):

   ```powershell
   git clone --recursive --shallow-submodules --depth 1 --branch v5.0.8 `
       https://github.com/mavlink/qgroundcontrol.git C:\dev\qgroundcontrol
   ```

3. **Install Qt via aqtinstall** (unattended; no Qt account needed).
   Module list comes straight from QGC's own CI workflow:

   ```powershell
   python -m venv C:\dev\aqt-venv
   C:\dev\aqt-venv\Scripts\pip install aqtinstall
   C:\dev\aqt-venv\Scripts\aqt install-qt windows desktop 6.8.3 win64_msvc2022_64 `
       -m qtcharts qtlocation qtpositioning qtspeech qt5compat qtmultimedia `
          qtserialport qtimageformats qtshadertools qtconnectivity qtquick3d qtsensors `
       -O C:\Qt
   ```

4. **Configure** from an MSVC x64 shell (`vcvars64.bat`), using Qt's
   `qt-cmake` wrapper:

   ```bat
   "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
   C:\Qt\6.8.3\msvc2022_64\bin\qt-cmake.bat -S C:\dev\qgroundcontrol -B C:\dev\qgc-build -G Ninja ^
       -DCMAKE_BUILD_TYPE=Release ^
       -DQGC_ENABLE_GST_VIDEOSTREAMING=OFF ^
       -DQGC_ENABLE_QT_VIDEOSTREAMING=ON
   ```

   Configure takes ~1 min (CPM downloads MAVLink, SDL2, etc. on first run).

5. **Build:**

   ```bat
   cmake --build C:\dev\qgc-build --target all
   ```

### Deliberate deviations from QGC CI

- **GStreamer OFF for now** (`QGC_ENABLE_GST_VIDEOSTREAMING=OFF`, Qt
  Multimedia backend ON instead). Avoids the GStreamer 1.22.12 devel MSI
  dependency for the first build. Revisit during the Herelink video spike
  (R9) — the *prebuilt* stock QGC in `C:\Program Files\QGroundControl`
  ships full GStreamer and is the right tool for that field test.
- **No Vulkan SDK.** CI installs it but v5.0.8 CMake only emits an optional
  "Could NOT find WrapVulkanHeaders" notice; Qt Quick 3D uses D3D at runtime
  on Windows. Install only if 3D viewer shader issues appear.
- **No NSIS yet** — only needed when we start producing installers (Phase 2 CI).

### Carried patches on the v5.0.8 clone

Captured as git patch files in `patches/` — apply to a fresh clone with
`.\apply-patches.ps1` (idempotent; fails loudly if upstream drift breaks
one). They are the entire delta between our tree and the v5.0.8 tag, and the
Phase 2 CI build script must run the same apply step. Fresh-machine setup is
therefore: clone (step 2 above) → `apply-patches.ps1` → configure → build.

1. **gpsdrivers pin** — `src/GPS/CMakeLists.txt` fetches `PX4/PX4-GPSDrivers`
   at unpinned `GIT_TAG main`, which no longer compiles with v5.0.8
   (`GPSProvider.cc(223): error C2661`). Pinned to
   `0b9695881bd1e8f830ab4538ab3acc0050019eba` (last commit before release).
2. **createComplexMissionItem backport (D13)** — upstream master added a
   `QGCCorePlugin::createComplexMissionItem()` factory hook so custom builds
   can register their own complex mission items; v5.0.8 predates it and
   hardcodes the item dispatch. Backported: virtual added in
   `src/API/QGCCorePlugin.h`, factory fallback called at the three dispatch
   sites in `src/MissionManager/MissionController.cc` (insert, insert-from-KML,
   plan-file load — search for "PGC backport"). Dissolves when we move to the
   next upstream release.
3. **`SurveyComplexItem` virtuals un-finaled** — `_rebuildTransectsPhase1`
   (also moved `private slots` → `protected`), `save`, and `load` changed
   `final` → `override` so `PGCSolarScanItem` can replace transect generation
   with the engine call and stamp its own `complexItemType`. Goes away when
   the Solar Scan item is rewritten as a direct `TransectStyleComplexItem`
   subclass with its own editor + save/load.

### Gotchas encountered

- OneDrive: never clone or build under the OneDrive folder. `C:\dev` is the
  convention.
- The `python` on PATH may resolve to the mission_engine venv — use a
  separate venv for aqtinstall (step 3) so project deps stay clean.
- MSVC Build Tools **2026** (toolset 14.50 / compiler 19.50) builds QGC
  v5.0.8 fine against Qt's msvc2022 kit — no need to hunt down VS 2022.
- **Windows exe icon**: `QGC_WINDOWS_ICON_PATH` alone does NOT change the
  exe icon — upstream compiles a static `.rc` into the target
  (`QGC_WINDOWS_RESOURCE_FILE_PATH`), and a target that already has an .rc
  source makes Qt ignore `QT_TARGET_RC_ICONS`. Override BOTH: point
  `QGC_WINDOWS_RESOURCE_FILE_PATH` at `custom/deploy/windows/PGC.rc`
  (references `./PGC.ico`) and keep `QGC_WINDOWS_ICON_PATH` for the NSIS
  installer icon.
- **Runtime window/taskbar icon**: upstream calls `setWindowIcon()` in the
  QGCApplication constructor before plugin hooks, and its qrc resource can't
  be shadowed (upstream registration wins). Re-set the icon in
  `CustomPlugin::createQmlApplicationEngine`.
- **Toolbar logo**: stock `/res/QGCLogoFull.svg` is swapped via the QML URL
  interceptor (`:/Custom/res/QGCLogoFull.svg` shadow). Raster art works if
  wrapped in an SVG container (base64-embedded PNG).
- **Top-right toolbar brand image** (`brandImageIndoor/Outdoor`) only renders
  when a vehicle is connected — don't chase it with no link up.

### Overlay mechanism notes (from `custom-example/`)

To activate an overlay: copy/sync this repo's overlay content into
`C:\dev\qgroundcontrol\custom\` (dir named exactly `custom`), clean the build
dir, reconfigure, rebuild. Key pieces upstream provides:

- `custom/CMakeLists.txt` + `cmake/CustomOverrides.cmake` — build wiring,
  app name/branding variables
- `src/CustomPlugin.{h,cc}` — `QGCCorePlugin` subclass: hide settings/UI,
  override palette, feature-flag panels (this is where Mission Studio and
  Box Control get registered)
- `src/FirmwarePlugin/…` — per-vehicle behavior overrides
- `res/…` — QML widget overrides, logos, color palette
- Note: upstream's `QGC_ENABLE_HERELINK` CMake option is an **Android-only**
  workaround (pins Qt 6.6.3 for Herelink's onboard controller). Irrelevant to
  our desktop builds — the desktop app talks to the Herelink ground unit over
  ordinary UDP/USB, no build flag needed.
