cmake_minimum_required(VERSION 3.24)
project(usdAecoExampleNative VERSION 0.1.0 LANGUAGES CXX)
find_package(pxr CONFIG REQUIRED)
include("${AECO_NATIVE_CMAKE}/AecoNative.cmake")
aeco_codeful_schema(NAME usdAecoExampleNative PYTHON_MODULE UsdAecoExampleNative)
include(CTest)
add_test(NAME schema COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/testenv/testSchema.py")
set_tests_properties(schema PROPERTIES ENVIRONMENT
    "PXR_PLUGINPATH_NAME=${CMAKE_BINARY_DIR}/lib;PYTHONPATH=${CMAKE_BINARY_DIR}/python:${AECO_USD_PYTHON}")
