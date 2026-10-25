cmake_minimum_required(VERSION 3.22)

# The DeckOS release (VERSION at the top of the repo) unless the PKGBUILD passes one.
if(NOT DECKOS_VERSION)
  file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../../VERSION" DECKOS_VERSION)
  string(STRIP "${DECKOS_VERSION}" DECKOS_VERSION)
endif()
project(deckos-editor VERSION ${DECKOS_VERSION} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
include(CheckIPOSupported)
check_ipo_supported(RESULT HAVE_LTO OUTPUT LTO_ERROR)
include(GNUInstallDirs)

find_package(ECM 6.0 REQUIRED NO_MODULE)
list(APPEND CMAKE_MODULE_PATH ${ECM_FIND_MODULE_DIR})
find_package(Qt6 6.6 REQUIRED COMPONENTS Core Gui Widgets Svg DBus)
find_package(KF6 6.0 REQUIRED COMPONENTS CoreAddons Config DBusAddons SyntaxHighlighting)

# The DeckOS look is DeckOS Files' (palette, line icons, chrome QSS): one copy for every app.
set(FILES_SRC ${CMAKE_CURRENT_SOURCE_DIR}/../deckos-files/src)

set(EDITOR_SOURCES
  src/document.cpp
  src/editorview.cpp
  src/findbar.cpp
  src/mainwindow.cpp
  ${FILES_SRC}/style.cpp
)
add_executable(deckos-editor src/main.cpp ${EDITOR_SOURCES})
target_include_directories(deckos-editor PRIVATE src ${FILES_SRC})
target_compile_definitions(deckos-editor PRIVATE
  DECKOS_VERSION="${DECKOS_VERSION}"
  # A checkout's icons and syntax theme, for running a build straight from the repo.
  DECKOS_SOURCE_ICONS="${CMAKE_CURRENT_SOURCE_DIR}/../../pkg/deckos-settings/rootfs/usr/share/deckos/icons"
  DECKOS_SOURCE_DATA="${CMAKE_CURRENT_SOURCE_DIR}/data"
  QT_NO_FOREACH QT_USE_QSTRINGBUILDER)
set(EDITOR_LIBS Qt6::Widgets Qt6::Svg Qt6::DBus
  KF6::CoreAddons KF6::ConfigCore KF6::ConfigGui KF6::DBusAddons KF6::SyntaxHighlighting)
target_link_libraries(deckos-editor PRIVATE ${EDITOR_LIBS})
if(HAVE_LTO)
  set_property(TARGET deckos-editor PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

install(TARGETS deckos-editor RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES data/org.deckos.editor.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)
install(FILES data/deckos-editor.svg DESTINATION ${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps)
install(FILES data/themes/deckos.theme DESTINATION ${CMAKE_INSTALL_DATADIR}/deckos-editor/themes)

# Offscreen checks of loading, saving and editing through the real classes (not built by the PKGBUILD).
option(DECKOS_EDITOR_TESTS "Build the DeckOS Editor tests" OFF)
if(DECKOS_EDITOR_TESTS)
  find_package(Qt6 REQUIRED COMPONENTS Test)
  add_executable(editor_test tests/editor_test.cpp ${EDITOR_SOURCES})
  target_include_directories(editor_test PRIVATE src ${FILES_SRC})
  get_target_property(_defs deckos-editor COMPILE_DEFINITIONS)
  target_compile_definitions(editor_test PRIVATE ${_defs})
  target_link_libraries(editor_test PRIVATE ${EDITOR_LIBS} Qt6::Test)
endif()
