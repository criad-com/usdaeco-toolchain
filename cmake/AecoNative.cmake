include_guard(GLOBAL)
include(CMakePackageConfigHelpers)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

# Shared libraries are the only supported native-plugin shape.
function(aeco_native_plugin)
    cmake_parse_arguments(ARG "" "NAME;DESCRIPTOR" "DEPENDENCIES" ${ARGN})
    if(NOT TARGET ${ARG_NAME})
        message(FATAL_ERROR "Create the shared target before aeco_native_plugin")
    endif()
    get_target_property(target_type ${ARG_NAME} TYPE)
    if(NOT target_type STREQUAL "SHARED_LIBRARY")
        message(FATAL_ERROR "Native plugins must be shared libraries")
    endif()
    target_compile_features(${ARG_NAME} PUBLIC cxx_std_17)
    set_target_properties(${ARG_NAME} PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
        CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)
    file(READ "${CMAKE_CURRENT_SOURCE_DIR}/library.json" manifest)
    string(JSON manifest_name GET "${manifest}" name)
    if(NOT manifest_name STREQUAL ARG_NAME)
        message(FATAL_ERROR "library.json name must equal target name")
    endif()
    string(JSON version GET "${manifest}" version)
    string(JSON tier GET "${manifest}" tier)
    string(JSON requires GET "${manifest}" requires)
    string(JSON requirement_count LENGTH "${requires}")
    if(requirement_count GREATER 0)
        math(EXPR last_requirement "${requirement_count} - 1")
        foreach(index RANGE ${last_requirement})
            string(JSON dependency MEMBER "${requires}" ${index})
            list(APPEND ARG_DEPENDENCIES "${dependency}")
        endforeach()
    endif()
    list(REMOVE_DUPLICATES ARG_DEPENDENCIES)
    set(AECO_FIND_DEPENDENCIES "")
    foreach(dependency IN LISTS ARG_DEPENDENCIES)
        string(APPEND AECO_FIND_DEPENDENCIES "find_dependency(${dependency} CONFIG)\n")
    endforeach()
    set(AECO_METADATA "{\"version\":\"${version}\",\"tier\":\"${tier}\",\"requires\":${requires}}")
    set(resources "lib/${ARG_NAME}/resources")
    if(NOT ARG_DESCRIPTOR)
        set(ARG_DESCRIPTOR "${CMAKE_CURRENT_SOURCE_DIR}/plugInfo.json.in")
    endif()
    file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/${resources}")
    configure_file("${ARG_DESCRIPTOR}"
        "${CMAKE_BINARY_DIR}/${resources}/plugInfo.json" @ONLY)
    file(WRITE "${CMAKE_BINARY_DIR}/lib/plugInfo.json"
        "{\"Includes\": [\"*/resources/\"]}\n")
    install(TARGETS ${ARG_NAME} EXPORT ${ARG_NAME}Targets LIBRARY DESTINATION lib)
    install(FILES "${CMAKE_BINARY_DIR}/lib/plugInfo.json" DESTINATION lib)
    install(FILES "${CMAKE_BINARY_DIR}/${resources}/plugInfo.json" DESTINATION "${resources}")
    install(EXPORT ${ARG_NAME}Targets NAMESPACE ${ARG_NAME}:: DESTINATION "lib/cmake/${ARG_NAME}")
    set(AECO_TARGET_NAME ${ARG_NAME})
    configure_package_config_file("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/AecoNativeConfig.cmake.in"
        "${CMAKE_BINARY_DIR}/${ARG_NAME}Config.cmake"
        INSTALL_DESTINATION "lib/cmake/${ARG_NAME}")
    write_basic_package_version_file("${CMAKE_BINARY_DIR}/${ARG_NAME}ConfigVersion.cmake"
        VERSION "${version}" COMPATIBILITY SameMajorVersion)
    install(FILES "${CMAKE_BINARY_DIR}/${ARG_NAME}Config.cmake"
        "${CMAKE_BINARY_DIR}/${ARG_NAME}ConfigVersion.cmake"
        DESTINATION "lib/cmake/${ARG_NAME}")
endfunction()

function(aeco_codeful_schema)
    cmake_parse_arguments(ARG "" "NAME;PYTHON_MODULE" "LIBRARIES" ${ARGN})
    set(schema "${CMAKE_CURRENT_SOURCE_DIR}/${ARG_NAME}")
    include("${schema}/native-schema.cmake")
    file(GLOB sources CONFIGURE_DEPENDS "${schema}/*.cpp")
    list(FILTER sources EXCLUDE REGEX "/(wrap[^/]*|module)\\.cpp$")
    file(GLOB wrappers CONFIGURE_DEPENDS "${schema}/wrap*.cpp")
    add_library(${ARG_NAME} SHARED ${sources})
    string(TOUPPER "${ARG_NAME}" exports)
    target_compile_definitions(${ARG_NAME} PRIVATE ${exports}_EXPORTS)
    get_filename_component(include_parent "${CMAKE_BINARY_DIR}/include/${AECO_SCHEMA_INCLUDE_PATH}" DIRECTORY)
    file(MAKE_DIRECTORY "${include_parent}")
    file(CREATE_LINK "${schema}" "${CMAKE_BINARY_DIR}/include/${AECO_SCHEMA_INCLUDE_PATH}" SYMBOLIC)
    target_include_directories(${ARG_NAME} PUBLIC
        "$<BUILD_INTERFACE:${CMAKE_BINARY_DIR}/include>" "$<INSTALL_INTERFACE:include>")
    target_link_libraries(${ARG_NAME} PUBLIC usd usdGeom ${ARG_LIBRARIES})
    aeco_native_plugin(NAME ${ARG_NAME} DESCRIPTOR "${schema}/plugInfo.json.in")
    # usdGenSchema exports methods individually. Its class RTTI must also be
    # visible to the separately linked Python wrapper (the upstream default).
    set_target_properties(${ARG_NAME} PROPERTIES CXX_VISIBILITY_PRESET default)
    install(DIRECTORY "${schema}/" DESTINATION "include/${AECO_SCHEMA_INCLUDE_PATH}"
        FILES_MATCHING PATTERN "*.h")
    set(resources "lib/${ARG_NAME}/resources")
    configure_file("${schema}/generatedSchema.usda"
        "${CMAKE_BINARY_DIR}/${resources}/generatedSchema.usda" COPYONLY)
    file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/${resources}/${ARG_NAME}")
    configure_file("${schema}/schema.usda"
        "${CMAKE_BINARY_DIR}/${resources}/${ARG_NAME}/schema.usda" COPYONLY)
    install(FILES "${schema}/generatedSchema.usda" DESTINATION "${resources}")
    install(FILES "${schema}/schema.usda" DESTINATION "${resources}/${ARG_NAME}")
    set(module "_${ARG_NAME}")
    add_library(${module} MODULE "${schema}/module.cpp" ${wrappers})
    target_compile_features(${module} PRIVATE cxx_std_17)
    target_compile_definitions(${module} PRIVATE
        MFB_PACKAGE_NAME=${ARG_NAME} MFB_ALT_PACKAGE_NAME=${ARG_NAME}
        MFB_PACKAGE_MODULE=${ARG_PYTHON_MODULE})
    target_link_libraries(${module} PRIVATE ${ARG_NAME} tf Python3::Module)
    file(RELATIVE_PATH lib_relative
        "${CMAKE_INSTALL_PREFIX}/${AECO_PYTHON_INSTALL_DIR}/pxr/${ARG_PYTHON_MODULE}"
        "${CMAKE_INSTALL_PREFIX}/lib")
    if(APPLE)
        set(module_rpath "@loader_path/${lib_relative}")
    else()
        set(module_rpath "$ORIGIN/${lib_relative}")
    endif()
    set_target_properties(${module} PROPERTIES PREFIX "" SUFFIX ".so"
        INSTALL_RPATH "${module_rpath}"
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/python/pxr/${ARG_PYTHON_MODULE}")
    file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/python/pxr/${ARG_PYTHON_MODULE}")
    file(WRITE "${CMAKE_BINARY_DIR}/python/pxr/__init__.py"
        "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n")
    configure_file("${schema}/__init__.py"
        "${CMAKE_BINARY_DIR}/python/pxr/${ARG_PYTHON_MODULE}/__init__.py" COPYONLY)
    # Extend pxr so the plugin prefix and upstream USD can be separate paths.
    install(FILES "${CMAKE_BINARY_DIR}/python/pxr/__init__.py" DESTINATION "${AECO_PYTHON_INSTALL_DIR}/pxr")
    install(TARGETS ${module} LIBRARY DESTINATION "${AECO_PYTHON_INSTALL_DIR}/pxr/${ARG_PYTHON_MODULE}")
    install(FILES "${schema}/__init__.py" DESTINATION "${AECO_PYTHON_INSTALL_DIR}/pxr/${ARG_PYTHON_MODULE}")
endfunction()
