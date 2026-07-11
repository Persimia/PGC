/****************************************************************************
 *
 * PGC custom build plugin — Persimia Ground Control.
 *
 * This file is part of the PGC QGroundControl overlay and is licensed
 * under GPLv3 per the QGC custom-build Route A decision (design doc D7).
 *
 ****************************************************************************/

#pragma once

#include "SurveyComplexItem.h"

Q_DECLARE_LOGGING_CATEGORY(PGCSolarScanLog)

/// "Solar Scan" pattern (design doc D13): a native Plan-view pattern whose
/// transects come from the Mission Engine CLI (keep-out aware, proprietary,
/// out-of-process) instead of QGC's built-in grid code.
///
/// Engine discovery: PGC_ENGINE_CLI env var, else mission-engine.exe next to
/// the app executable. Fence libraries: every .kml in Documents/PGC/fences is
/// passed to the engine on each generation (D11 fail-loud validation).
///
/// Failure semantics:
///  - engine unavailable / infrastructure failure -> stock Survey generation
///    (pattern tool never dead)
///  - engine REFUSAL (exit 2, e.g. keep-out conflict) -> transects cleared and
///    the error surfaced; deliberately NO fallback, a refused mission must
///    never silently render a path through a hazard (D11)
class PGCSolarScanItem : public SurveyComplexItem
{
    Q_OBJECT
    Q_PROPERTY(QString lastEngineError READ lastEngineError NOTIFY lastEngineErrorChanged)
    Q_PROPERTY(int fenceFileCount READ fenceFileCount NOTIFY fenceFileCountChanged)
    Q_PROPERTY(QVariantList fenceZones READ fenceZones NOTIFY fenceZonesChanged)

public:
    PGCSolarScanItem(PlanMasterController *masterController, bool flyView, const QString &kmlOrShpFile);
    ~PGCSolarScanItem();

    QString lastEngineError() const { return _lastEngineError; }
    int fenceFileCount() const { return _fenceFileCount; }
    QVariantList fenceZones() const { return _fenceZones; }

    // Overrides from VisualMissionItem / ComplexMissionItem
    void save(QJsonArray &planItems) final;
    bool load(const QJsonObject &complexObject, int sequenceNumber, QString &errorString) final;
    QString mapVisualQML() const final { return QStringLiteral("qrc:/custom/qml/PGCSolarScanMapVisual.qml"); }

    static const QString name;
    static constexpr const char *jsonComplexItemTypeValue = "PGCSolarScan";

signals:
    void lastEngineErrorChanged();
    void fenceFileCountChanged();
    void fenceZonesChanged();

protected:
    // Overrides from TransectStyleComplexItem (via SurveyComplexItem)
    void _rebuildTransectsPhase1() final;

private:
    QString _engineCliPath() const;
    QStringList _fenceFiles();
    void _setEngineError(const QString &error);
    void _refreshFenceZones(const QStringList &fenceFiles);
    QByteArray _buildParamsJson();
    void _requestEngineRun(const QString &key, const QByteArray &paramsJson, const QStringList &fenceFiles);
    void _engineRunFinished(int exitCode, int exitStatus);

    QString _lastEngineError;
    int _fenceFileCount = 0;
    QVariantList _fenceZones;
    QString _fenceZonesKey; ///< fence file list the current _fenceZones was loaded from

    // Async engine state: one request in flight at a time, results cached by
    // a params hash. During regeneration the previous (stale) transects stay
    // on the map so polygon drags feel smooth.
    class QProcess *_engineProcess = nullptr;
    QString _inFlightKey;
    QString _appliedKey;
    QString _wptsPath;
    QList<QList<CoordInfo_t>> _engineTransects;
};
