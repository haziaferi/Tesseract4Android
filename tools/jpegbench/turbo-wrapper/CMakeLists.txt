##
# libjpeg-turbo as the "jpeg" library.
#
# libjpeg-turbo refuses add_subdirectory() (see the top of src/CMakeLists.txt) and
# asks for ExternalProject_Add() instead. It is built as a static library with the
# same Android toolchain and ABI, then linked whole into libjpeg.so, so that the
# library keeps its name (System.loadLibrary("jpeg")) and its unversioned SONAME.
##

cmake_minimum_required(VERSION 3.18.1)

include(ExternalProject)

set(TURBO_SRC ${CMAKE_CURRENT_SOURCE_DIR}/src)
set(TURBO_BIN ${CMAKE_CURRENT_BINARY_DIR}/turbo)
set(TURBO_LIB ${TURBO_BIN}/libjpeg.a)

ExternalProject_Add(turbo_ep
        SOURCE_DIR ${TURBO_SRC}
        BINARY_DIR ${TURBO_BIN}
        CMAKE_ARGS
            -DCMAKE_TOOLCHAIN_FILE=${CMAKE_TOOLCHAIN_FILE}
            -DCMAKE_MAKE_PROGRAM=${CMAKE_MAKE_PROGRAM}
            -DANDROID_ABI=${ANDROID_ABI}
            -DANDROID_PLATFORM=${ANDROID_PLATFORM}
            -DANDROID_NDK=${ANDROID_NDK}
            -DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON
            -DCMAKE_BUILD_TYPE=Release
            -DCMAKE_POSITION_INDEPENDENT_CODE=ON
            -DENABLE_SHARED=OFF
            -DENABLE_STATIC=ON
            -DWITH_TURBOJPEG=OFF
            -DWITH_TOOLS=OFF
            -DWITH_TESTS=OFF
        BUILD_COMMAND ${CMAKE_COMMAND} --build ${TURBO_BIN} --target jpeg-static
        INSTALL_COMMAND ""
        BUILD_BYPRODUCTS ${TURBO_LIB})

add_library(jpeg SHARED stub.c)
add_dependencies(jpeg turbo_ep)
target_link_libraries(jpeg PRIVATE "-Wl,--whole-archive" ${TURBO_LIB} "-Wl,--no-whole-archive")
# jpeglib.h and friends are in src/src; jconfig.h is generated into the build dir.
target_include_directories(jpeg PUBLIC ${TURBO_SRC}/src ${TURBO_BIN})
