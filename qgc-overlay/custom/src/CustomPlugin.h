/****************************************************************************
 *
 * PGC custom build plugin — Persimia Ground Control.
 *
 * This file is part of the PGC QGroundControl overlay and is licensed
 * under GPLv3 per the QGC custom-build Route A decision (design doc D7).
 *
 ****************************************************************************/

#pragma once

#include <QtQml/QQmlAbstractUrlInterceptor>

#include "QGCCorePlugin.h"
#include "QGCOptions.h"

class QQmlApplicationEngine;

Q_DECLARE_LOGGING_CATEGORY(CustomLog)

/// Simplification pass (design doc §5.1): PGC clients are single-vehicle
/// ArduPilot operators. Engineer-grade features stay reachable through QGC's
/// built-in Advanced Mode toggle; these options trim the default experience.
class PGCOptions;

class PGCFlyViewOptions : public QGCFlyViewOptions
{
public:
    PGCFlyViewOptions(PGCOptions *options, QObject *parent = nullptr);

    // Overrides from QGCFlyViewOptions
    bool showMultiVehicleList() const final { return false; }               // single-vehicle product (multi-vehicle is D9 console territory)
};

class PGCOptions : public QGCOptions
{
public:
    PGCOptions(QGCCorePlugin *plugin, QObject *parent = nullptr);

    // Overrides from QGCOptions
    QGCFlyViewOptions *flyViewOptions() const final;
    bool multiVehicleEnabled() const final { return false; }
    bool showFirmwareUpgrade() const final;                                 // engineer task (advanced mode only)
    bool showPX4LogTransferOptions() const final { return false; }          // ArduPilot fleet
    bool checkFirmwareVersion() const final { return false; }               // we qualify firmware, not the operator
    bool allowJoystickSelection() const final { return false; }             // manual flight stays on Herelink (D6)

private:
    QGCCorePlugin *_plugin = nullptr;
    PGCFlyViewOptions *_flyViewOptions = nullptr;
};

class CustomPlugin : public QGCCorePlugin
{
    Q_OBJECT

public:
    explicit CustomPlugin(QObject *parent = nullptr);
    ~CustomPlugin();

    static QGCCorePlugin *instance();

    QGCOptions *options() final;

    // Overrides from QGCCorePlugin
    void cleanup() final;
    QString brandImageIndoor() const final;
    QString brandImageOutdoor() const final;
    bool overrideSettingsGroupVisibility(const QString &name) final;
    bool adjustSettingMetaData(const QString &settingsGroup, FactMetaData &metaData) final;
    void paletteOverride(const QString &colorName, QGCPalette::PaletteColorInfo_t &colorInfo) final;
    QQmlApplicationEngine *createQmlApplicationEngine(QObject *parent) final;
    QStringList complexMissionItemNames(Vehicle *vehicle, const QStringList &complexMissionItemNames) final;
    ComplexMissionItem *createComplexMissionItem(const QString &complexItemType, PlanMasterController *masterController, bool flyView, const QString &kmlOrShpFile) final;

private:
    QQmlApplicationEngine *_qmlEngine = nullptr;
    class CustomOverrideInterceptor *_interceptor = nullptr;
    PGCOptions *_options = nullptr;
};

/*===========================================================================*/

// Redirects any qrc URL the QML engine resolves to :/Custom/<same path> when
// such a resource exists, letting the overlay shadow stock assets (e.g. the
// toolbar logo /res/QGCLogoFull.svg) without touching upstream files.
class CustomOverrideInterceptor : public QQmlAbstractUrlInterceptor
{
public:
    CustomOverrideInterceptor() = default;

    QUrl intercept(const QUrl &url, QQmlAbstractUrlInterceptor::DataType type) final;
};
