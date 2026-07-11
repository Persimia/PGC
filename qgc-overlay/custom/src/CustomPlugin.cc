/****************************************************************************
 *
 * PGC custom build plugin — Persimia Ground Control.
 *
 * This file is part of the PGC QGroundControl overlay and is licensed
 * under GPLv3 per the QGC custom-build Route A decision (design doc D7).
 *
 ****************************************************************************/

#include "CustomPlugin.h"
#include "AppSettings.h"
#include "BrandImageSettings.h"
#include "FactMetaData.h"
#include "PGCSolarScanItem.h"
#include "QGCLoggingCategory.h"
#include "QGCMAVLink.h"
#include "QGCPalette.h"

#include <QtCore/QApplicationStatic>
#include <QtCore/QFile>
#include <QtGui/QGuiApplication>
#include <QtGui/QIcon>
#include <QtQml/QQmlApplicationEngine>

QGC_LOGGING_CATEGORY(CustomLog, "gcs.custom.customplugin")

Q_APPLICATION_STATIC(CustomPlugin, _customPluginInstance);

// Persimia brand palette. Placeholders sampled from Persimia_mark_RGB.png
// until the official hex values arrive (design doc D12).
namespace PGCBrand {
    constexpr const char *orange     = "#EE4023"; // primary accent
    constexpr const char *rust       = "#802217"; // mid gradient tone
    constexpr const char *maroon     = "#3D150B"; // dark gradient tone
    constexpr const char *orangeSoft = "#F8C0B4"; // light-theme highlight fill
}

PGCFlyViewOptions::PGCFlyViewOptions(PGCOptions *options, QObject *parent)
    : QGCFlyViewOptions(options, parent)
{
}

PGCOptions::PGCOptions(QGCCorePlugin *plugin, QObject *parent)
    : QGCOptions(parent)
    , _plugin(plugin)
    , _flyViewOptions(new PGCFlyViewOptions(this, this))
{
}

QGCFlyViewOptions *PGCOptions::flyViewOptions() const
{
    return _flyViewOptions;
}

// Firmware flashing is an engineer task: visible only in Advanced Mode.
bool PGCOptions::showFirmwareUpgrade() const
{
    return _plugin->showAdvancedUI();
}

CustomPlugin::CustomPlugin(QObject *parent)
    : QGCCorePlugin(parent)
    , _options(new PGCOptions(this, this))
{
    // Client builds start simple; engineers flip Advanced Mode in the
    // application menu to reach calibration/param/firmware tooling.
    _showAdvancedUI = false;
}

QGCOptions *CustomPlugin::options()
{
    return _options;
}

CustomPlugin::~CustomPlugin()
{
}

void CustomPlugin::cleanup()
{
    if (_qmlEngine) {
        _qmlEngine->removeUrlInterceptor(_interceptor);
    }
    delete _interceptor;
    _interceptor = nullptr;

    QGCCorePlugin::cleanup();
}

QQmlApplicationEngine *CustomPlugin::createQmlApplicationEngine(QObject *parent)
{
    _qmlEngine = QGCCorePlugin::createQmlApplicationEngine(parent);
    _interceptor = new CustomOverrideInterceptor();
    _qmlEngine->addUrlInterceptor(_interceptor);

    // Upstream sets the window icon in the QGCApplication constructor, which
    // runs before plugin hooks — re-set it here so ours wins.
    QGuiApplication::setWindowIcon(QIcon(QStringLiteral(":/custom/img/persimia_mark.png")));

    return _qmlEngine;
}

QGCCorePlugin *CustomPlugin::instance()
{
    return _customPluginInstance();
}

QString CustomPlugin::brandImageIndoor() const
{
    return QStringLiteral("/custom/img/persimia_mark.png");
}

QString CustomPlugin::brandImageOutdoor() const
{
    return QStringLiteral("/custom/img/persimia_mark.png");
}

QStringList CustomPlugin::complexMissionItemNames(Vehicle *vehicle, const QStringList &complexMissionItemNames)
{
    QStringList names = complexMissionItemNames;
    names.prepend(PGCSolarScanItem::name);
    return QGCCorePlugin::complexMissionItemNames(vehicle, names);
}

ComplexMissionItem *CustomPlugin::createComplexMissionItem(const QString &complexItemType, PlanMasterController *masterController, bool flyView, const QString &kmlOrShpFile)
{
    // Matched two ways: pattern-menu insertion passes the display name;
    // plan-file load passes the JSON complexItemType discriminator.
    if (complexItemType == PGCSolarScanItem::name
            || complexItemType == QLatin1String(PGCSolarScanItem::jsonComplexItemTypeValue)) {
        return new PGCSolarScanItem(masterController, flyView, kmlOrShpFile);
    }
    return QGCCorePlugin::createComplexMissionItem(complexItemType, masterController, flyView, kmlOrShpFile);
}

bool CustomPlugin::overrideSettingsGroupVisibility(const QString &name)
{
    // Brand imagery is fixed by this build; hide the setting that changes it.
    if (name == BrandImageSettings::name) {
        return false;
    }
    return true;
}

bool CustomPlugin::adjustSettingMetaData(const QString &settingsGroup, FactMetaData &metaData)
{
    const bool parentResult = QGCCorePlugin::adjustSettingMetaData(settingsGroup, metaData);

    if (settingsGroup == AppSettings::settingsGroup) {
        // Offline plan editing should default to our fleet: ArduPilot multirotors.
        if (metaData.name() == AppSettings::offlineEditingFirmwareClassName) {
            metaData.setRawDefaultValue(QGCMAVLink::FirmwareClassArduPilot);
            return false;
        }
        if (metaData.name() == AppSettings::offlineEditingVehicleClassName) {
            metaData.setRawDefaultValue(QGCMAVLink::VehicleClassMultiRotor);
            return false;
        }
    }

    return parentResult;
}

void CustomPlugin::paletteOverride(const QString &colorName, QGCPalette::PaletteColorInfo_t &colorInfo)
{
    // Minimal accent re-skin: green/blue interaction colors become Persimia
    // orange. Structural greys stay stock until the full skinning pass.
    if (colorName == QStringLiteral("primaryButton")) {
        colorInfo[QGCPalette::Dark][QGCPalette::ColorGroupEnabled]   = QColor(PGCBrand::orange);
        colorInfo[QGCPalette::Light][QGCPalette::ColorGroupEnabled]  = QColor(PGCBrand::orange);
    }
    else if (colorName == QStringLiteral("primaryButtonText")) {
        colorInfo[QGCPalette::Dark][QGCPalette::ColorGroupEnabled]   = QColor("#ffffff");
        colorInfo[QGCPalette::Light][QGCPalette::ColorGroupEnabled]  = QColor("#ffffff");
    }
    else if (colorName == QStringLiteral("buttonHighlight")) {
        colorInfo[QGCPalette::Dark][QGCPalette::ColorGroupEnabled]   = QColor(PGCBrand::orange);
        colorInfo[QGCPalette::Light][QGCPalette::ColorGroupEnabled]  = QColor(PGCBrand::orangeSoft);
    }
    else if (colorName == QStringLiteral("hoverColor")) {
        colorInfo[QGCPalette::Dark][QGCPalette::ColorGroupEnabled]   = QColor(PGCBrand::rust);
        colorInfo[QGCPalette::Light][QGCPalette::ColorGroupEnabled]  = QColor(PGCBrand::orangeSoft);
    }
    else if (colorName == QStringLiteral("mapButtonHighlight")) {
        colorInfo[QGCPalette::Dark][QGCPalette::ColorGroupEnabled]   = QColor(PGCBrand::orange);
        colorInfo[QGCPalette::Light][QGCPalette::ColorGroupEnabled]  = QColor(PGCBrand::rust);
    }
    else if (colorName == QStringLiteral("brandingPurple")) {
        colorInfo[QGCPalette::Dark][QGCPalette::ColorGroupEnabled]   = QColor(PGCBrand::maroon);
        colorInfo[QGCPalette::Dark][QGCPalette::ColorGroupDisabled]  = QColor(PGCBrand::maroon);
        colorInfo[QGCPalette::Light][QGCPalette::ColorGroupEnabled]  = QColor(PGCBrand::maroon);
        colorInfo[QGCPalette::Light][QGCPalette::ColorGroupDisabled] = QColor(PGCBrand::maroon);
    }
    else if (colorName == QStringLiteral("brandingBlue")) {
        colorInfo[QGCPalette::Dark][QGCPalette::ColorGroupEnabled]   = QColor(PGCBrand::orange);
        colorInfo[QGCPalette::Dark][QGCPalette::ColorGroupDisabled]  = QColor(PGCBrand::rust);
        colorInfo[QGCPalette::Light][QGCPalette::ColorGroupEnabled]  = QColor(PGCBrand::orange);
        colorInfo[QGCPalette::Light][QGCPalette::ColorGroupDisabled] = QColor(PGCBrand::rust);
    }
}

/*===========================================================================*/

QUrl CustomOverrideInterceptor::intercept(const QUrl &url, QQmlAbstractUrlInterceptor::DataType type)
{
    switch (type) {
    case QQmlAbstractUrlInterceptor::QmlFile:
    case QQmlAbstractUrlInterceptor::UrlString:
        if (url.scheme() == QStringLiteral("qrc")) {
            const QString origPath = url.path();
            const QString overrideRes = QStringLiteral(":/Custom%1").arg(origPath);
            if (QFile::exists(overrideRes)) {
                QUrl result;
                result.setScheme(QStringLiteral("qrc"));
                result.setPath(QStringLiteral("/Custom%1").arg(origPath));
                return result;
            }
        }
        break;
    default:
        break;
    }

    return url;
}
