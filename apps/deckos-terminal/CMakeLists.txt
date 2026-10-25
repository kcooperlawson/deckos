cmake_minimum_required(VERSION 3.22)

# The DecKoOS release (VERSION at the top of the repo) unless the PKGBUILD passes one.
if(NOT DECKOS_VERSION)
  file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../../VERSION" DECKOS_VERSION)
  string(STRIP "${DECKOS_VERSION}" DECKOS_VERSION)
endif()
project(deckos-terminal VERSION ${DECKOS_VERSION} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
include(CheckIPOSupported)
check_ipo_supported(RESULT HAVE_LTO OUTPUT LTO_ERROR)
include(GNUInstallDirs)

# FindKF6 (the umbrella over the KF6 components) comes with extra-cmake-modules.
find_package(ECM 6.0 REQUIRED NO_MODULE)
list(APPEND CMAKE_MODULE_PATH ${ECM_FIND_MODULE_DIR})
find_package(Qt6 6.6 REQUIRED COMPONENTS Core Gui Widgets Svg DBus)
find_package(KF6 6.0 REQUIRED COMPONENTS CoreAddons Config DBusAddons)
find_package(qtermwidget6 2.0 REQUIRED)

# The DecKoOS look is DecKoOS Files' (palette, line icons, chrome QSS): one copy for both apps.
set(FILES_SRC ${CMAKE_CURRENT_SOURCE_DIR}/../deckos-files/src)

add_executable(deckos-terminal
  src/main.cpp
  src/project.cpp
  src/terminalpane.cpp
  src/tabpage.cpp
  src/modewatch.cpp
  src/mainwindow.cpp
  src/snapshotbar.cpp
  ${FILES_SRC}/style.cpp
)
target_include_directories(deckos-terminal PRIVATE ${FILES_SRC})
target_compile_definitions(deckos-terminal PRIVATE
  DECKOS_VERSION="${DECKOS_VERSION}"
  # A checkout's icons and colour scheme, for running a build straight from the repo.
  DECKOS_SOURCE_ICONS="${CMAKE_CURRENT_SOURCE_DIR}/../../pkg/deckos-settings/rootfs/usr/share/deckos/icons"
  DECKOS_SOURCE_SCHEMES="${CMAKE_CURRENT_SOURCE_DIR}/data"
  QT_NO_FOREACH QT_USE_QSTRINGBUILDER)
target_link_libraries(deckos-terminal PRIVATE
  Qt6::Widgets Qt6::Svg Qt6::DBus
  KF6::CoreAddons KF6::ConfigCore KF6::ConfigGui KF6::DBusAddons
  qtermwidget6)
if(HAVE_LTO)
  set_property(TARGET deckos-terminal PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

install(TARGETS deckos-terminal RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES data/org.deckos.terminal.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)
install(FILES data/deckos-terminal.svg DESTINATION ${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps)
install(FILES data/DeckOS.colorscheme DESTINATION ${CMAKE_INSTALL_DATADIR}/deckos-terminal/color-schemes)

# Offscreen checks of copy, paste and the Undo bar through the real window (not built by the PKGBUILD).
option(DECKOS_TERMINAL_TESTS "Build the DecKoOS Terminal tests" OFF)
if(DECKOS_TERMINAL_TESTS)
  find_package(Qt6 REQUIRED COMPONENTS Test)
  add_executable(keys_test tests/keys_test.cpp
    src/project.cpp src/terminalpane.cpp src/tabpage.cpp src/modewatch.cpp src/mainwindow.cpp
    src/snapshotbar.cpp ${FILES_SRC}/style.cpp)
  target_include_directories(keys_test PRIVATE src ${FILES_SRC})
  get_target_property(_defs deckos-terminal COMPILE_DEFINITIONS)
  target_compile_definitions(keys_test PRIVATE ${_defs})
  get_target_property(_libs deckos-terminal LINK_LIBRARIES)
  target_link_libraries(keys_test PRIVATE ${_libs} Qt6::Test)
endif()
