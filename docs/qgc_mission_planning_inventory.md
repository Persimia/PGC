# QGC v5.0.8 Mission Planning Inventory

**Date:** 2026-07-10 · **Source:** full sweep of `src/MissionManager` + Plan view QML in the pinned v5.0.8 tree at `C:\dev\qgroundcontrol`. Written to inform Mission Studio integration (design doc §5.1, Phase 3).

## 1. What QGC Plan view already does

### Pattern generators (complex items)

| Pattern | What it does | Key parameters | Files |
|---|---|---|---|
| **Survey** | Serpentine grid over polygon, camera-driven spacing | Grid angle, turnaround distance, entry corner (4 options, rotatable), hover-and-capture, refly at 90° offset, images-in-turnarounds, fly-alternate-transects | `SurveyComplexItem.cc` (59 KB) |
| **Corridor Scan** | Transects along a polyline corridor (roads, fence lines) | Corridor width (0 = single pass), same camera/turnaround set | `CorridorScanComplexItem.cc` |
| **Structure Scan** | Orbits a structure in vertical layers (towers, facades) | Structure height, layers, scan bottom alt, entrance/exit alt, gimbal pitch, start top/bottom | `StructureScanComplexItem.cc` |
| **FW / VTOL landing patterns** | Full approach→land geometry | Final approach alt, glide slope, loiter, landing distance/heading | `LandingComplexItem.cc` (40 KB) |

All patterns support **user presets** (save/apply/delete named parameter sets).

### Camera model & GSD math (`CameraCalc` / `CameraSpec`)
- Known-camera library from `src/Camera/CameraMetaData.json` (brand→model pickers), plus Custom (enter sensor/focal specs) and Manual (raw spacing) modes.
- Full GSD math: drive by ground resolution (cm/px) **or** altitude; front/side overlap % → transect spacing + camera trigger distance. This is exactly the OQ8 milestone math.

### Terrain awareness
- Transect patterns can terrain-follow two ways: QGC pre-computes AMSL waypoints along terrain (with tolerance, max climb/descent rates, interior waypoint insertion) or emits `MAV_FRAME_GLOBAL_TERRAIN_ALT` for the vehicle to follow.
- Terrain profile chart panel (altitude vs mission distance) with collision flagging.

### Editing UX
- Polygon tools: vertex drag, edge split, whole-polygon drag, circle mode, click-to-trace, per-vertex menus, **KML/SHP import** into any pattern area.
- Mission item list: insert waypoint/ROI/takeoff/land after current, split segments on the flight line, per-item command picker filtered by firmware (`MissionCommandTree`), raw param edit in advanced mode.
- Per-item sections: camera actions (photo interval time/distance, video, mode, gimbal pitch/yaw) + flight speed (DO_CHANGE_SPEED).
- Mission settings item: global altitude mode, default waypoint alt, mission-start camera actions, planned home, cruise/hover speeds for time estimates.

### Fence & rally
- GeoFence tab: inclusion/exclusion **polygons and circles**, breach return point + altitude, firmware fence params surfaced (ArduPilot `FENCE_*`). Uploads via MAVLink `MISSION_TYPE_FENCE`.
- Rally tab: rally points with alt, `MISSION_TYPE_RALLY` upload.

### File I/O & sync
- Opens `.plan`, `.mission`, `.waypoints`/`.txt`; saves `.plan`; exports mission as KML. Imports KML/SHP for areas.
- One-click "Plan creators" gallery (Blank / Survey / Corridor / Structure).
- Battle-tested MAVLink mission protocol upload/download/clear with retry/ack state machine (`PlanManager`), resume-mission generation.

## 2. Known limitations found in the sweep

- **Concave polygon splitting is shipped-but-disabled** (`SurveyComplexItem.h:132`, `#if 0` — comment says it infinite-loops). Survey still clips transects to concave polygons, but no smart decomposition. Solar sites are frequently concave — relevant to us.
- **No exclusion/keep-out awareness in pattern generation.** GeoFence exclusion zones exist but Survey transects fly straight through them — nothing connects fences to pattern generation.
- No multi-polygon survey, no per-site reusable asset model (presets are parameter sets, not geographic assets).
- Minor upstream bug: `CameraCalc.cc:404,407` sets `_disableRecalc = true` twice (never restores) in a V3-load path.

## 3. Overlap with our Mission Engine — honest assessment

| Capability | QGC built-in | Our engine today | Verdict |
|---|---|---|---|
| Serpentine survey from polygon | ✅ mature (angle, entry, turnarounds) | ✅ basic (spacing/heading/speed) | **QGC ahead** for generic scans |
| Camera/GSD spacing | ✅ full math + camera DB | ❌ (OQ8 milestone pending) | QGC ahead; engine math is a port of the same formulas |
| Terrain following | ✅ two modes + profile UI | ❌ | QGC ahead |
| Keep-outs honored by generated path | ❌ (fences don't affect patterns) | ✅ fail-loud validation vs KML fence libraries (D11) | **Engine ahead — this is differentiation** |
| Durable fence libraries (per-site KML assets, keepout/min_alt/inclusion) | ❌ (fences live per-plan) | ✅ | **Engine ahead — differentiation** |
| Concave/odd solar-site polygons | ⚠️ clipping only, splitting disabled | ✅ engine owns its geometry | Engine advantage grows with site complexity |
| Parametric/scriptable generation (Python, no GCS) | ❌ | ✅ core design (F9) | Engine-only — feeds box dispatch + future Fleet Console (D2/D9) |
| Corridor / structure scan | ✅ | ❌ | QGC-only; not our use case yet |
| Upload protocol, editing UX, item editors | ✅ | n/a | Always QGC's job (design doc: "subtract, don't rebuild") |

## 4. Integration implication for Mission Studio (recommendation)

The design doc's data flow (draw polygon → engine → .plan → QGC review) stands, but the split of labor should be explicit:

1. **Don't hide QGC's Survey/Corridor/Structure.** For generic ad-hoc scans they're better than our v1 engine and cost us nothing. Keep them available (at minimum in engineer mode).
2. **Mission Studio = the solar-site workflow**, not a generic survey clone: pick site → load fence library (D11 KML assets) → parameters → engine generates mission that *provably respects keep-outs* → loads into QGC's native plan view for review/edit/upload. The engine's moat is site assets + keep-out honoring + scriptability + box/fleet dispatch — not serpentine math.
3. **OQ8 camera math**: port `CameraCalc`'s formulas (documented above: GSD ↔ altitude, overlap → spacing/trigger) into the engine rather than inventing — keeps our numbers consistent with what operators see in QGC editors.
4. **Reuse, not rebuild, in the panel**: Mission Studio QML should reuse `QGCMapPolygonVisuals` (polygon draw/edit + KML import) and the plan-view map rather than custom drawing code.
5. **Fence upload**: QGC's GeoFenceController handles inclusion/exclusion upload; engine-generated `.plan` files already carry the geoFence section — verify round-trip of our exclusion polygons into QGC's fence tab (good Phase 3 smoke test).
