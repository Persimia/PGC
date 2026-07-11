/****************************************************************************
 *
 * PGC custom build plugin — Persimia Ground Control.
 *
 * This file is part of the PGC QGroundControl overlay and is licensed
 * under GPLv3 per the QGC custom-build Route A decision (design doc D7).
 *
 ****************************************************************************/

#include "PGCSolarScanItem.h"
#include "CameraCalc.h"
#include "QGCApplication.h"
#include "QGCLoggingCategory.h"

#include <QtCore/QCoreApplication>
#include <QtCore/QCryptographicHash>
#include <QtCore/QDir>
#include <QtCore/QFile>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QProcess>
#include <QtCore/QProcessEnvironment>
#include <QtCore/QStandardPaths>
#include <QtPositioning/QGeoCoordinate>

QGC_LOGGING_CATEGORY(PGCSolarScanLog, "gcs.custom.solarscan")

const QString PGCSolarScanItem::name(QT_TRANSLATE_NOOP("PGCSolarScanItem", "Solar Scan"));

PGCSolarScanItem::PGCSolarScanItem(PlanMasterController *masterController, bool flyView, const QString &kmlOrShpFile)
    : SurveyComplexItem(masterController, flyView, kmlOrShpFile)
{
    _editorQml = QStringLiteral("qrc:/custom/qml/PGCSolarScanEditor.qml");
}

PGCSolarScanItem::~PGCSolarScanItem()
{
    if (_engineProcess && _engineProcess->state() != QProcess::NotRunning) {
        _engineProcess->disconnect(this);
        _engineProcess->kill();
    }
}

void PGCSolarScanItem::save(QJsonArray &planItems)
{
    // Survey writes its own complexItemType; re-stamp ours so the plan file
    // round-trips back through the plugin factory as a Solar Scan.
    const int countBefore = planItems.count();
    SurveyComplexItem::save(planItems);
    if (planItems.count() > countBefore) {
        QJsonObject saveObject = planItems.last().toObject();
        saveObject[ComplexMissionItem::jsonComplexItemTypeKey] = jsonComplexItemTypeValue;
        planItems[planItems.count() - 1] = saveObject;
    }
}

bool PGCSolarScanItem::load(const QJsonObject &complexObject, int sequenceNumber, QString &errorString)
{
    // Survey's loader validates version keys only, not the type discriminator,
    // so the payload (which is Survey-shaped) loads as-is.
    return SurveyComplexItem::load(complexObject, sequenceNumber, errorString);
}

QString PGCSolarScanItem::_engineCliPath() const
{
    const QString envPath = QProcessEnvironment::systemEnvironment().value(QStringLiteral("PGC_ENGINE_CLI"));
    if (!envPath.isEmpty() && QFile::exists(envPath)) {
        return envPath;
    }

    // Frozen onedir build staged by mission_engine/build-exe.ps1 -StageTo
    const QString staged = QCoreApplication::applicationDirPath() + QStringLiteral("/pgc-engine/mission-engine.exe");
    if (QFile::exists(staged)) {
        return staged;
    }

    const QString bundled = QCoreApplication::applicationDirPath() + QStringLiteral("/mission-engine.exe");
    if (QFile::exists(bundled)) {
        return bundled;
    }

    return QString();
}

QStringList PGCSolarScanItem::_fenceFiles()
{
    const QString fenceDir = QStandardPaths::writableLocation(QStandardPaths::DocumentsLocation) + QStringLiteral("/PGC/fences");
    QStringList files;
    const QFileInfoList entries = QDir(fenceDir).entryInfoList({ QStringLiteral("*.kml") }, QDir::Files, QDir::Name);
    for (const QFileInfo &entry : entries) {
        files.append(entry.absoluteFilePath());
    }

    if (files.count() != _fenceFileCount) {
        _fenceFileCount = files.count();
        emit fenceFileCountChanged();
    }
    _refreshFenceZones(files);
    return files;
}

void PGCSolarScanItem::_refreshFenceZones(const QStringList &fenceFiles)
{
    const QString key = fenceFiles.join(QLatin1Char(';'));
    if (key == _fenceZonesKey) {
        return; // same fence file set as last load
    }
    _fenceZonesKey = key;

    QVariantList zones;
    const QString cli = _engineCliPath();

    if (!cli.isEmpty() && !fenceFiles.isEmpty()) {
        QStringList args = { QStringLiteral("fences") };
        for (const QString &fence : fenceFiles) {
            args << QStringLiteral("--fence") << fence;
        }
        const QString zonesPath = QStandardPaths::writableLocation(QStandardPaths::TempLocation) + QStringLiteral("/pgc_fence_zones.json");
        args << QStringLiteral("-o") << zonesPath;

        QProcess engine;
        engine.start(cli, args);
        if (engine.waitForStarted(3000) && engine.waitForFinished(10000)
                && engine.exitStatus() == QProcess::NormalExit && engine.exitCode() == 0) {
            QFile zonesFile(zonesPath);
            if (zonesFile.open(QIODevice::ReadOnly)) {
                const QJsonArray zonesJson = QJsonDocument::fromJson(zonesFile.readAll()).object().value(QStringLiteral("zones")).toArray();
                for (const QJsonValue &zoneValue : zonesJson) {
                    const QJsonObject zoneObj = zoneValue.toObject();
                    QVariantList path;
                    const QJsonArray polygon = zoneObj.value(QStringLiteral("polygon")).toArray();
                    for (const QJsonValue &vertexValue : polygon) {
                        const QJsonArray vertex = vertexValue.toArray();
                        path.append(QVariant::fromValue(QGeoCoordinate(vertex[0].toDouble(), vertex[1].toDouble())));
                    }
                    QVariantMap zone;
                    zone[QStringLiteral("name")] = zoneObj.value(QStringLiteral("name")).toString();
                    zone[QStringLiteral("kind")] = zoneObj.value(QStringLiteral("kind")).toString();
                    zone[QStringLiteral("minAlt")] = zoneObj.value(QStringLiteral("min_alt_m")).toDouble(0);
                    zone[QStringLiteral("path")] = path;
                    zones.append(zone);
                }
            }
        } else {
            engine.kill();
            qCWarning(PGCSolarScanLog) << "Fence zone dump failed:"
                                       << QString::fromUtf8(engine.readAllStandardError()).trimmed();
        }
    }

    _fenceZones = zones;
    emit fenceZonesChanged();
    qCDebug(PGCSolarScanLog) << "Fence zones refreshed:" << zones.count() << "zone(s)";
}

void PGCSolarScanItem::_setEngineError(const QString &error)
{
    if (error == _lastEngineError) {
        return; // don't re-popup the same refusal on every polygon drag tick
    }
    _lastEngineError = error;
    emit lastEngineErrorChanged();
    if (!error.isEmpty()) {
        qgcApp()->showAppMessage(error, tr("Solar Scan"));
    }
}

QByteArray PGCSolarScanItem::_buildParamsJson()
{
    QJsonArray polygonJson;
    for (const QGeoCoordinate &vertex : surveyAreaPolygon()->coordinateList()) {
        polygonJson.append(QJsonArray({ vertex.latitude(), vertex.longitude() }));
    }

    QJsonObject params;
    params[QStringLiteral("polygon")] = polygonJson;
    params[QStringLiteral("altitude_m")] = cameraCalc()->distanceToSurface()->rawValue().toDouble();
    params[QStringLiteral("spacing_m")] = cameraCalc()->adjustedFootprintSide()->rawValue().toDouble();
    params[QStringLiteral("heading_deg")] = gridAngle()->rawValue().toDouble();
    return QJsonDocument(params).toJson();
}

void PGCSolarScanItem::_rebuildTransectsPhase1()
{
    const QString cli = _engineCliPath();
    if (cli.isEmpty()) {
        // Engine not installed: behave as stock Survey so the pattern tool is
        // never dead. Refusals do NOT take this path.
        qCWarning(PGCSolarScanLog) << "Mission Engine CLI not found (set PGC_ENGINE_CLI); falling back to stock Survey generation";
        SurveyComplexItem::_rebuildTransectsPhase1();
        return;
    }

    if (surveyAreaPolygon()->coordinateList().count() < 3) {
        _transects.clear();
        return;
    }

    const QStringList fenceFiles = _fenceFiles();
    const QByteArray paramsJson = _buildParamsJson();
    const QString key = QString::fromLatin1(QCryptographicHash::hash(
        paramsJson + fenceFiles.join(QLatin1Char(';')).toUtf8(), QCryptographicHash::Md5).toHex());

    // Serve from cache (also the path taken when our own completion handler
    // re-triggers the rebuild), else show the previous result while the
    // engine regenerates in the background — no UI stall on polygon drags.
    _transects = _engineTransects;
    if (key != _appliedKey) {
        _requestEngineRun(key, paramsJson, fenceFiles);
    }
}

void PGCSolarScanItem::_requestEngineRun(const QString &key, const QByteArray &paramsJson, const QStringList &fenceFiles)
{
    if (_engineProcess && _engineProcess->state() != QProcess::NotRunning) {
        if (_inFlightKey == key) {
            return; // identical request already running
        }
        // Newer params supersede the in-flight run
        _engineProcess->disconnect(this);
        _engineProcess->kill();
        _engineProcess->deleteLater();
        _engineProcess = nullptr;
    }

    const QString tmpDir = QStandardPaths::writableLocation(QStandardPaths::TempLocation);
    const QString paramsPath = tmpDir + QStringLiteral("/pgc_solarscan_params.json");
    _wptsPath = tmpDir + QStringLiteral("/pgc_solarscan_wpts.json");

    QFile paramsFile(paramsPath);
    if (!paramsFile.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        qCWarning(PGCSolarScanLog) << "Cannot write engine params file" << paramsPath;
        return;
    }
    paramsFile.write(paramsJson);
    paramsFile.close();

    QStringList args = { QStringLiteral("generate"), QStringLiteral("-i"), paramsPath, QStringLiteral("-o"), _wptsPath };
    for (const QString &fence : fenceFiles) {
        args << QStringLiteral("--fence") << fence;
    }

    _inFlightKey = key;
    _engineProcess = new QProcess(this);
    connect(_engineProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, [this](int exitCode, QProcess::ExitStatus exitStatus) {
        _engineRunFinished(exitCode, static_cast<int>(exitStatus));
    });
    _engineProcess->start(_engineCliPath(), args);
}

void PGCSolarScanItem::_engineRunFinished(int exitCode, int exitStatus)
{
    QProcess *engine = _engineProcess;
    if (!engine) {
        return;
    }
    _engineProcess = nullptr;
    engine->deleteLater();

    const QString key = _inFlightKey;
    _inFlightKey.clear();

    if (static_cast<QProcess::ExitStatus>(exitStatus) != QProcess::NormalExit) {
        qCWarning(PGCSolarScanLog) << "Mission Engine crashed";
        return; // keep previous result; next param change retries
    }

    if (exitCode != 0) {
        // Engine REFUSED (exit 2: keep-out conflict or invalid parameters).
        // Fail loud per D11: clear the flight path and tell the operator.
        // Falling back to stock generation here could draw a path through a
        // hazard, so we intentionally do not.
        const QString stderrText = QString::fromUtf8(engine->readAllStandardError()).trimmed();
        qCWarning(PGCSolarScanLog) << "Mission Engine refused (exit" << exitCode << "):" << stderrText;
        _engineTransects.clear();
        _appliedKey = key; // a refusal IS the result for these params
        _setEngineError(stderrText.isEmpty() ? tr("Mission Engine rejected the mission (no details)") : stderrText);
    } else {
        QFile wptsFile(_wptsPath);
        if (!wptsFile.open(QIODevice::ReadOnly)) {
            qCWarning(PGCSolarScanLog) << "Engine output missing:" << _wptsPath;
            return;
        }
        const QJsonArray waypoints = QJsonDocument::fromJson(wptsFile.readAll()).object().value(QStringLiteral("waypoints")).toArray();
        wptsFile.close();
        if (waypoints.count() < 2 || (waypoints.count() % 2) != 0) {
            qCWarning(PGCSolarScanLog) << "Engine returned malformed waypoint list, count:" << waypoints.count();
            return;
        }

        // Engine waypoints are ordered [entry, exit] pairs, one per flight line.
        _engineTransects.clear();
        for (int i = 0; i < waypoints.count(); i += 2) {
            const QJsonArray entry = waypoints[i].toArray();
            const QJsonArray exit = waypoints[i + 1].toArray();

            QList<CoordInfo_t> transect;
            transect.append(CoordInfo_t{ QGeoCoordinate(entry[0].toDouble(), entry[1].toDouble()), CoordTypeSurveyEntry });
            transect.append(CoordInfo_t{ QGeoCoordinate(exit[0].toDouble(), exit[1].toDouble()), CoordTypeSurveyExit });
            _engineTransects.append(transect);
        }
        _appliedKey = key;
        _setEngineError(QString());
        qCDebug(PGCSolarScanLog) << "Engine generated" << _engineTransects.count() << "flight lines";
    }

    // Push the fresh result through the normal rebuild pipeline. String-based
    // queued invoke: _rebuildTransects is a private slot on the base class.
    QMetaObject::invokeMethod(this, "_rebuildTransects", Qt::QueuedConnection);
}
