import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import QGroundControl
import QGroundControl.ScreenTools
import QGroundControl.Controls
import QGroundControl.FactSystem
import QGroundControl.FactControls
import QGroundControl.Palette

// Solar Scan editor (design doc D13). Extends the stock transect editor so we
// keep the native Grid / Camera / Terrain / Presets tabs; adds the engine
// status banner and fence-library readout. Altitude & spacing are edited on
// the Grid tab (CameraCalcGrid), same as Survey.
TransectStyleComplexItemEditor {
    transectAreaDefinitionComplete: missionItem.surveyAreaPolygon.isValid
    transectAreaDefinitionHelp:     qsTr("Use the Polygon Tools to outline the solar site scan area.")
    transectValuesHeaderName:       qsTr("Solar Scan")
    transectValuesComponent:        _solarValuesComponent
    presetsTransectValuesComponent: _solarValuesComponent

    // The following properties must be available up the hierarchy chain
    //  property real   availableWidth    ///< Width for control
    //  property var    missionItem       ///< Mission Item for editor

    property real _margin: ScreenTools.defaultFontPixelWidth / 2

    Component {
        id: _solarValuesComponent

        ColumnLayout {
            Layout.fillWidth:   true
            spacing:            _margin

            // Fail-loud engine refusal banner (D11): shown when the Mission
            // Engine rejected generation (e.g. keep-out conflict).
            Rectangle {
                Layout.fillWidth:   true
                visible:            missionItem.lastEngineError.length !== 0
                color:              qgcPal.alertBackground
                border.color:       qgcPal.alertBorder
                radius:             _margin
                implicitHeight:     _errorLabel.implicitHeight + (_margin * 4)

                QGCLabel {
                    id:                 _errorLabel
                    anchors.fill:       parent
                    anchors.margins:    _margin * 2
                    text:               missionItem.lastEngineError
                    color:              qgcPal.alertText
                    wrapMode:           Text.WordWrap
                }
            }

            GridLayout {
                Layout.fillWidth:   true
                columnSpacing:      _margin
                rowSpacing:         _margin
                columns:            2

                QGCLabel { text: qsTr("Angle") }
                FactTextField {
                    fact:               missionItem.gridAngle
                    Layout.fillWidth:   true
                }

                QGCLabel { text: qsTr("Fence libraries") }
                QGCLabel {
                    text: missionItem.fenceFileCount > 0
                              ? qsTr("%1 KML file(s) validated").arg(missionItem.fenceFileCount)
                              : qsTr("none found (Documents/PGC/fences)")
                }
            }
        }
    }
}
