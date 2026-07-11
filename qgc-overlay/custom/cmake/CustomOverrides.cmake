# PGC identity. Variables defined upstream in cmake/CustomOptions.cmake.
set(QGC_APP_NAME "PGC" CACHE STRING "App Name" FORCE)
set(QGC_APP_DESCRIPTION "PGC - Persimia Ground Control" CACHE STRING "Description" FORCE)
set(QGC_APP_COPYRIGHT "Copyright (c) 2026 Persimia LLC. All rights reserved." CACHE STRING "Copyright" FORCE)
set(QGC_ORG_NAME "Persimia" CACHE STRING "Org Name" FORCE)
set(QGC_ORG_DOMAIN "persimia.com" CACHE STRING "Domain" FORCE)

if(EXISTS ${CMAKE_SOURCE_DIR}/custom/deploy/windows/PGC.ico)
    set(QGC_WINDOWS_ICON_PATH "${CMAKE_SOURCE_DIR}/custom/deploy/windows/PGC.ico" CACHE FILEPATH "Windows Icon Path" FORCE)
    # The exe icon comes from the static .rc compiled into the target (upstream
    # adds it via target_sources, which makes Qt ignore QT_TARGET_RC_ICONS).
    # Point the rc at one that references PGC.ico ("./" = build deploy dir,
    # where the copy step places both files).
    set(QGC_WINDOWS_RESOURCE_FILE_PATH "${CMAKE_SOURCE_DIR}/custom/deploy/windows/PGC.rc" CACHE FILEPATH "Windows Resource File Path" FORCE)
endif()

# TODO(branding pass): QGC_WINDOWS_INSTALL_HEADER_PATH, Linux/macOS icon paths.

# Vehicles are ArduPilot (CubePilot); PX4 support stays compiled for now —
# revisit during the simplification pass.
