<launch>
  <include file="$(find-pkg-share nav2_bringup)/launch/navigation_launch.py">
    <arg name="params_file" value="$(find-pkg-share buddybot_navigation)/config/nav2_params.yaml"/>
  </include>
  
  <include file="$(find-pkg-share slam_toolbox)/launch/online_async_launch.py">
    <arg name="params_file" value="$(find-pkg-share buddybot_navigation)/config/slam_params.yaml"/>
  </include>
  
  <node pkg="buddybot_navigation" exec="waypoint_navigator" name="waypoint_navigator"/>
</launch>