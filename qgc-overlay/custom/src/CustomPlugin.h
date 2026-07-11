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

class QQmlApplicationEngine;

Q_DECLARE_LOGGING_CATEGORY(CustomLog)

class CustomPlugin : public QGCCorePlugin
{
    Q_OBJECT

public:
    explicit CustomPlugin(QObject *parent = nullptr);
    ~CustomPlugin();

    static QGCCorePlugin *instance();

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
