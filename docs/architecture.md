# BuddyBot Architecture (Hardware-Compatible Revision)

## 핵심 원칙
1. 기존 실제 배선 유지
2. Pi 5 ↔ Pico 통신은 USB Serial 유지 (`/dev/ttyACM0`)
3. 신규 모듈 구조는 유지하되, 실제 하드웨어와 호환되도록 수정
4. 안전 우선 (watchdog/estop latch)

## 시스템 구성
- **Pi 5 (ROS 2 Jazzy / Ubuntu 24.04)**: 비전, 네비게이션, 명령 중재, 브리지
- **Pico (MicroPython)**: 모터/엔코더 제어, watchdog, 안전 정지
- **LiDAR/Camera**: 상위 인지 계층

## 통신 모델
- Pi 5 `buddybot_base/pico_bridge_node` ↔ Pico `uart_protocol.py`
- 전송 매체: USB CDC serial
- 기본 포트: `/dev/ttyACM0`
- GPIO UART는 현재 설계 범위에서 제외

## 명령 중재 우선순위
`E-STOP > Manual stop > Safety override > Follow/Nav > Idle`

`buddybot_system/command_mux_node.py`는 안전 활성 시 항상 0속도를 출력하며,
수동 stop(0속도)이 latch되면 최고 우선순위 정지를 유지합니다.

## 워크스페이스 레이아웃
- Canonical ROS 워크스페이스: `software/pi5/ros2_ws`
- 중복 중첩 workspace(`software/pi5/ros2_ws/ros2_ws`)는 정리함

## 참고 문서
- 핀맵: `docs/pin_mapping.md`
- 프로토콜: `docs/uart_protocol.md`
- 브링업: `docs/bringup.md`
