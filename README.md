# GCS Monorepo — [Product Name TBD]

Everything we build for our ground-control product lives here: the Mission
Engine (our IP), box services, and the QGC custom-build overlay. The QGC
source itself is a **separate upstream clone** — only our overlay content is
versioned here. Full architecture and rationale: `docs/gcs_design_document.md`.
First-time setup: `SETUP_CHECKLIST.md`.

## Layout

```
mission_engine/   Parametric mission generation (pure Python, zero deps). Phase 1 — ACTIVE.
qgc-overlay/      Our QGC custom build overlay (branding + QML panels). Phase 2 — placeholder.
box/              Box services: Box API, mavlink-router/MediaMTX configs.  Phase 4 — placeholder.
docs/             Design document (source of truth for decisions D1–D10).
```

## Quickstart (Mission Engine)

```bash
cd mission_engine
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .
python -m unittest discover -s tests            # 37 tests, all stdlib
mission-engine generate -i examples/solar_farm_params.json -o /tmp/demo.plan
```

Then open `/tmp/demo.plan` in stock QGroundControl or Mission Planner
(File → Open/Load) — seeing the serpentine + fence render there is the real
acceptance test, and it works today with the tools we already use.

## Fence libraries (KML)

Fences are durable assets separate from any mission: draw them once in
Google Earth (company-wide or per-site) and generate every mission against
them with repeatable `--fence` flags:

```bash
mission-engine generate -i examples/solar_farm_params.json \
    -f examples/site_fences.kml -o /tmp/demo.plan
```

Tag each polygon in its placemark **name** (or description):
`[keepout]` never enter · `[min_alt=40]` enter only at/above 40 m ·
`[inclusion]` stay inside (max one). Untagged polygons are rejected; pins
and paths are ignored. On any conflict the engine **fails loudly with the
zone names — it never clips or reroutes** (design doc D11); redraw the area
instead. `[keepout]`/`[inclusion]` zones are embedded in the `.plan`
geofence for vehicle-side enforcement; `.waypoints` output carries no fence
(upload separately in Mission Planner). Not validated: the takeoff climb,
the RTL path (both depend on launch position), and the camera swath between
flight lines — the flown path is what's checked.

## Params schema

```json
{
  "polygon": [[lat, lon], ...],   // >= 3 vertices, WGS84
  "altitude_m": 60,               // above home
  "spacing_m": 25,                // distance between flight lines
  "heading_deg": null,            // optional; null = auto (longest edge)
  "speed_ms": 8                   // optional; null = vehicle default
}
```

## Working rules (from the design doc)

- The engine stays **pure Python with no GCS/Qt imports** in `core/` (D2) and
  **zero third-party deps**. Exclusion zones are validated against, never
  clipped around (D11), which is why Shapely never became necessary.
- The CLI is **stateless** (D3): params in, `.plan` out, process exits. The
  future QGC panel and Box API are thin adapters over the same `core`.
- v1 survey limits (documented, enforced with clear errors): convex-ish
  polygons only; default geofence = survey polygon, overridable by a KML
  `[inclusion]` zone (safety margin is a follow-up).
- Every box capability must exist as an API endpoint before/alongside any UI
  for it (FC1); auth + TLS from day one (FC2).

## CI

GitHub Actions runs the test suite + a CLI smoke test on Ubuntu and Windows,
Python 3.11/3.12, on every push and PR (`.github/workflows/ci.yml`).
