import QtQuick
import QtLocation
import QtPositioning

import QGroundControl
import QGroundControl.Controls
import QGroundControl.FlightMap
import QGroundControl.Palette

// Solar Scan map visuals (design doc D13): stock transect visuals plus the
// fence-library zones the Mission Engine validates against, so the operator
// can see WHY a generation was refused.
//   [keepout]  red fill        [min_alt=N]  orange fill        [inclusion]  green outline
TransectStyleMapVisuals {
    id: _root

    polygonInteractive: true

    QGCPalette { id: _pgcZonePal }

    Instantiator {
        model: _missionItem.fenceZones

        delegate: MapPolygon {
            path:           modelData.path
            border.width:   modelData.kind === "inclusion" ? 2 : 1
            border.color:   modelData.kind === "keepout"  ? _pgcZonePal.colorRed
                          : modelData.kind === "min_alt"  ? _pgcZonePal.colorOrange
                                                          : _pgcZonePal.colorGreen
            color:          modelData.kind === "keepout"  ? Qt.rgba(1, 0, 0, 0.25)
                          : modelData.kind === "min_alt"  ? Qt.rgba(1, 0.55, 0, 0.15)
                                                          : Qt.rgba(0, 0, 0, 0)
            opacity:        _root.opacity
        }

        onObjectAdded: (index, object) => _root.map.addMapItem(object)
        onObjectRemoved: (index, object) => _root.map.removeMapItem(object)
    }
}
