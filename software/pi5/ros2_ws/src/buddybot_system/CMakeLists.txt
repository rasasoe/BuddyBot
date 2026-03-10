cmake_minimum_required(VERSION 3.8)
project(buddybot_system)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(diagnostic_msgs REQUIRED)
find_package(buddybot_msgs REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  scripts/system_monitor.py
  scripts/diagnostics.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()