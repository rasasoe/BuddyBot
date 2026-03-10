cmake_minimum_required(VERSION 3.8)
project(buddybot_navigation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(nav2_bringup REQUIRED)
find_package(slam_toolbox REQUIRED)
find_package(buddybot_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  scripts/waypoint_navigator.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install config files
install(DIRECTORY
  config
  launch
  maps
  DESTINATION share/${PROJECT_NAME}
)

ament_package()