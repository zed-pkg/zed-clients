cmake_minimum_required(VERSION 3.20)
project(zed_pkg_client_cpp VERSION 0.1.0 LANGUAGES CXX)

add_library(zed_pkg_client INTERFACE)
target_include_directories(
  zed_pkg_client
  INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_features(zed_pkg_client INTERFACE cxx_std_20)

option(ZED_PKG_BUILD_TESTS "Build the dependency-free C++ client tests" ON)

if(ZED_PKG_BUILD_TESTS)
  include(CTest)
  enable_testing()

  add_executable(zed_pkg_client_tests tests/client_test.cpp)
  target_link_libraries(zed_pkg_client_tests PRIVATE zed_pkg_client)

  if(MSVC)
    target_compile_options(zed_pkg_client_tests PRIVATE /W4 /WX)
  else()
    target_compile_options(
      zed_pkg_client_tests
      PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Werror
    )
  endif()

  add_test(NAME zed_pkg_client_tests COMMAND zed_pkg_client_tests)
endif()
