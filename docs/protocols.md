# BuddyBot 통신 프로토콜

## 시리얼 프로토콜 (Pi 5 ↔ 피코)

### 메시지 형식
- **명령**: 12 바이트 (3 플로트: linear_x, linear_y, angular_z)
- **상태**: 17 바이트 (플로트 배터리 + 3 인트 엔코더 + 불 emerg)

### 전송 속도
- 115200

## ROS 2 토픽

### 핵심 토픽
- `/velocity_command` (buddybot_msgs/Command)
- `/pico_status` (buddybot_msgs/Status)
- `/robot_mode` (std_msgs/String)

### 네비게이션 토픽
- `/waypoint_goal` (buddybot_msgs/Waypoint)
- `/nav_command` (buddybot_msgs/Command)

### 비전 토픽
- `/follow_command` (buddybot_msgs/Command)
- `/emergency_stop` (buddybot_msgs/Command)

### 음성 토픽
- `/voice_trigger` (std_msgs/String)
- `/voice_command_text` (std_msgs/String)