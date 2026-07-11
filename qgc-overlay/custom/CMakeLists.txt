message(STATUS "PGC: Adding custom plugin")

# Enable custom build
set_property(DIRECTORY ${CMAKE_SOURCE_DIR}
    APPEND PROPERTY COMPILE_DEFINITIONS
    QGC_CUSTOM_BUILD
    CUSTOMHEADER="CustomPlugin.h"
    CUSTOMCLASS=CustomPlugin
)

# Our own, custom resources
list(APPEND CUSTOM_RESOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/custom.qrc
)
set(QGC_RESOURCES ${QGC_RESOURCES} ${CUSTOM_RESOURCES} CACHE STRING "Paths to .qrc Resources" FORCE)

set(CUSTOM_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/CustomPlugin.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/src/CustomPlugin.h
    ${CMAKE_CURRENT_SOURCE_DIR}/src/PGCSolarScanItem.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/src/PGCSolarScanItem.h
    CACHE INTERNAL "" FORCE
)

set(CUSTOM_INCLUDE_DIRECTORIES
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    CACHE INTERNAL "" FORCE
)
