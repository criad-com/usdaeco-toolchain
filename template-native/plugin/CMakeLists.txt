cmake_minimum_required(VERSION 3.24)
project(usdAecoExampleHello VERSION 0.1.0 LANGUAGES CXX)
find_package(pxr CONFIG REQUIRED)
include("${AECO_NATIVE_CMAKE}/AecoNative.cmake")
add_library(usdAecoExampleHello SHARED hello.cpp)
target_link_libraries(usdAecoExampleHello PRIVATE tf)
aeco_native_plugin(NAME usdAecoExampleHello)
include(CTest)
add_test(NAME hello COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/testenv/testHello.py")
set_tests_properties(hello PROPERTIES ENVIRONMENT
    "PXR_PLUGINPATH_NAME=${CMAKE_BINARY_DIR}/lib;PYTHONPATH=${AECO_USD_PYTHON}")
