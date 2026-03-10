# buddybot_msgs

BuddyBot 통신을 위한 사용자 정의 ROS 2 메시지.

## 메시지

- **Command**: 모터 제어를 위한 속도 명령 (linear_x, linear_y, angular_z)
- **Status**: 피코로부터의 상태 (배터리, 엔코더, 비상 정지)
- **Waypoint**: 네비게이션 웨이포인트 (x, y, theta)