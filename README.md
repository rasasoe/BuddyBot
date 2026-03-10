# BuddyBot

BuddyBot은 **Raspberry Pi 5 + Raspberry Pi Pico** 기반 3륜 옴니휠 로봇입니다.  
현재 리비전의 목표는 "새 모듈 구조 유지 + 기존 실제 하드웨어 100% 호환"입니다.

## 고정 제약 (이 리포지토리 기준)
- 기존 배선 유지
- Pi 5 ↔ Pico 통신은 **USB Serial** 유지 (`/dev/ttyACM0`)
- GPIO UART 마이그레이션 금지(현 단계)
- 물리 배선되지 않은 하드웨어는 문서에서 TODO로 명시

## 실제 Pico 핀 매핑 (Source of Truth)
- Motor 0: PWM GP2, IN1 GP0, IN2 GP1, ENCA GP3, ENCB GP14
- Motor 1: PWM GP8, IN1 GP6, IN2 GP7, ENCA GP9, ENCB GP15
- Motor 2: PWM GP12, IN1 GP10, IN2 GP11, ENCA GP13, ENCB GP16
- I2C: SDA GP20, SCL GP21

상세 표: `docs/pin_mapping.md`

## 통신
- Pi 5 브리지 노드: `buddybot_base/pico_bridge_node.py`
- Pico 프로토콜: `firmware/pico_motor_controller/uart_protocol.py`
- 프로토콜 문서: `docs/uart_protocol.md`
- 기본 시리얼 포트: `/dev/ttyACM0`

## 리포지토리 구조
- `firmware/pico_motor_controller/`: Pico MicroPython 펌웨어
- `software/pi5/ros2_ws/`: ROS 2 Jazzy 워크스페이스 (canonical)
- `docs/`: 아키텍처/핀맵/프로토콜/브링업 문서

## Bring-up Quick Order
1. Pico 펌웨어 플래시 (`firmware/pico_motor_controller/main.py` 포함)
2. Pico USB 연결 후 Pi 5에서 `/dev/ttyACM0` 확인
3. Pi 5에서 ROS workspace 빌드 및 source
4. `ros2 run buddybot_base pico_bridge_node` 실행
5. 저속 명령 테스트 후 상위 노드(`buddybot_system`, `buddybot_vision`, `buddybot_nav`) 순차 기동

전체 체크리스트: `docs/bringup.md`

## 안전
- Pico watchdog timeout 시 모터 정지
- BRAKE/CLEAR 기반 소프트웨어 estop latch 유지
- 물리 E-STOP 전용 핀은 현재 미배선(문서 TODO)

추가 설명: `docs/architecture.md`
