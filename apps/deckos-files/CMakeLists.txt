cmake_minimum_required(VERSION 3.22)

# The DeckOS release (VERSION at the top of the repo) unless the PKGBUILD passes one.
if(NOT DECKOS_VERSION)
  file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../../VERSION" DECKOS_VERSION)
  string(STRIP "${DECKOS_VERSION}" DECKOS_VERSION)
endif()
project(deckos-files VERSION ${DECKOS_VERSION} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
include(CheckIPOSupported)
check_ipo_supported(RESULT HAVE_LTO OUTPUT LTO_ERROR)
include(GNUInstallDirs)

find_package(Qt6 6.6 REQUIRED COMPONENTS Core Gui Widgets Svg DBus Concurrent)
find_package(KF6 6.0 REQUIRED COMPONENTS CoreAddons Config KIO DBusAddons JobWidgets Solid)
find_package(KF6Baloo 6.0)

add_executable(deckos-files
  src/main.cpp
  src/style.cpp
  src/foldermodel.cpp
  src/itemdelegate.cpp
  src/folderview.cpp
  src/folderpane.cpp
  src/sidebar.cpp
  src/operations.cpp
  src/mainwindow.cpp
)
target_compile_definitions(deckos-files PRIVATE
  DECKOS_VERSION="${DECKOS_VERSION}"
  # A checkout's icons, for running a build straight from the repo.
  DECKOS_SOURCE_ICONS="${CMAKE_CURRENT_SOURCE_DIR}/../../pkg/deckos-settings/rootfs/usr/share/deckos/icons"
  QT_NO_FOREACH QT_USE_QSTRINGBUILDER)
target_link_libraries(deckos-files PRIVATE
  Qt6::Widgets Qt6::Svg Qt6::DBus Qt6::Concurrent
  KF6::CoreAddons KF6::ConfigCore KF6::ConfigGui KF6::DBusAddons KF6::JobWidgets KF6::Solid
  KF6::KIOCore KF6::KIOGui KF6::KIOWidgets KF6::KIOFileWidgets)
if(KF6Baloo_FOUND)
  target_link_libraries(deckos-files PRIVATE KF6::Baloo)
  target_compile_definitions(deckos-files PRIVATE HAVE_BALOO=1)
endif()
if(HAVE_LTO)
  set_property(TARGET deckos-files PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

install(TARGETS deckos-files RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES data/org.deckos.files.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)
install(FILES data/deckos-files.svg DESTINATION ${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps)
install(FILES data/org.deckos.files.FileManager1.service DESTINATION ${CMAKE_INSTALL_DATADIR}/dbus-1/services)
# Folders open in DeckOS Files from every app (a user's own choice in mimeapps.list still wins).
install(FILES data/mimeapps.list DESTINATION ${CMAKE_INSTALL_FULL_SYSCONFDIR}/xdg)
