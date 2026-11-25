cmake_minimum_required(VERSION 3.22)

# The DecKoOS release (VERSION at the top of the repo) unless the PKGBUILD passes one.
if(NOT DECKOS_VERSION)
  file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../../VERSION" DECKOS_VERSION)
  string(STRIP "${DECKOS_VERSION}" DECKOS_VERSION)
endif()
project(deckos-extract VERSION ${DECKOS_VERSION} LANGUAGES CXX)

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
find_package(Qt6 6.6 REQUIRED COMPONENTS Core Gui Widgets Svg WebSockets)
find_package(KF6 6.0 REQUIRED COMPONENTS CoreAddons Config DBusAddons Notifications)

# The DecKoOS look is DecKoOS Files' (palette, line icons, chrome QSS): one copy for every app.
set(FILES_SRC ${CMAKE_CURRENT_SOURCE_DIR}/../deckos-files/src)

set(EXTRACT_SOURCES src/archiveset.cpp src/extractjob.cpp src/jobcard.cpp src/mainwindow.cpp ${FILES_SRC}/style.cpp)
add_executable(deckos-extract src/main.cpp ${EXTRACT_SOURCES})
target_include_directories(deckos-extract PRIVATE ${FILES_SRC})
target_compile_definitions(deckos-extract PRIVATE
  DECKOS_VERSION="${DECKOS_VERSION}"
  # A checkout's icons, for running a build straight from the repo.
  DECKOS_SOURCE_ICONS="${CMAKE_CURRENT_SOURCE_DIR}/../../pkg/deckos-settings/rootfs/usr/share/deckos/icons"
  QT_NO_FOREACH QT_USE_QSTRINGBUILDER)
target_link_libraries(deckos-extract PRIVATE
  Qt6::Widgets Qt6::Svg Qt6::WebSockets
  KF6::CoreAddons KF6::ConfigCore KF6::ConfigGui KF6::DBusAddons KF6::Notifications)
if(HAVE_LTO)
  set_property(TARGET deckos-extract PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

install(TARGETS deckos-extract RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES data/org.deckos.extract.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)
install(FILES data/deckos-extract.svg DESTINATION ${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps)
# "Extract here" in DecKoOS Files' right-click menu (KFileItemActions reads KIO service menus).
install(FILES data/deckos-extract-servicemenu.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/kio/servicemenus)

# Split-set grouping and real 7-Zip runs on generated archives (not built by the PKGBUILD).
option(DECKOS_EXTRACT_TESTS "Build the DecKoOS Extract tests" OFF)
if(DECKOS_EXTRACT_TESTS)
  find_package(Qt6 REQUIRED COMPONENTS Test)
  add_executable(extract_test tests/extract_test.cpp ${EXTRACT_SOURCES})
  target_include_directories(extract_test PRIVATE src ${FILES_SRC})
  get_target_property(_defs deckos-extract COMPILE_DEFINITIONS)
  target_compile_definitions(extract_test PRIVATE ${_defs})
  get_target_property(_libs deckos-extract LINK_LIBRARIES)
  target_link_libraries(extract_test PRIVATE ${_libs} Qt6::Test)
endif()
