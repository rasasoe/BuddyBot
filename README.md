# BuddyBot

BuddyBot은 **Raspberry Pi 5 + Raspberry Pi Pico** 기반 3륜 옴니휠 로봇으로,
ROS 2 Jazzy 위에서 LiDAR 네비게이션, 비전 기반 사람 추적, 안전 중심 제어를 통합한 캡스톤/포트폴리오 프로젝트입니다.

## 1) Project overview

이 프로젝트의 핵심은 "지능(Brain)"과 "실시간 안전 제어(Spinal Cord)"를 분리해,
상위 AI/ROS 계층 장애가 있어도 하위 모터 제어 계층이 fail-safe로 정지할 수 있도록 설계한 것입니다.

- Brain: Pi 5 (ROS 2, 비전, 네비게이션, 시스템 조율)
- Spinal Cord: Pico (모터 제어, watchdog, 안전 정지)

## 2) Key features

- LiDAR 기반 지도화/자율 주행 파이프라인
- 카메라 기반 사람 추적
- 우선순위 기반 command mux(충돌 명령 중재)
- USB serial 기반 Pi5↔Pico 텍스트 프로토콜
- watchdog + estop latch 기반 safety-first 제어
- 모듈형 ROS2 패키지 구조

## 3) Brain vs Spinal Cord architecture

```text
Pi 5 (Brain)  <---USB CDC serial--->  Pico (Spinal Cord)
- ROS2 nodes                               - Motor driver control loop
- Navigation / Vision                      - Encoder feedback
- Command arbitration                       - Watchdog timeout stop
- High-level mission logic                  - Emergency stop behavior
```

이 분리를 통해 복잡한 상위 소프트웨어와 안전 필수 하위 제어를 독립적으로 유지할 수 있습니다.

## 4) LiDAR / Vision role separation

- **LiDAR**: 전역 이동, 맵/경로, 장애물 지형 인식
- **Vision**: 사람/근거리 상호작용, 추적 입력
- 두 서브시스템의 속도 명령은 **command mux**에서 정책 기반으로 최종 1개로 결정됩니다.

## 5) Real hardware constraints (fixed)

다음 제약은 현재 리포지토리에서 고정입니다.

1. 기존 실제 배선 유지
2. Pi 5 ↔ Pico 통신은 USB serial 유지 (`/dev/ttyACM0`)
3. GPIO UART로 마이그레이션하지 않음
4. 실물 미배선 항목은 TODO/소프트웨어 안전 계층으로 정직하게 문서화

### Real Pico pin mapping (source of truth)
- Motor 0: PWM GP2, IN1 GP0, IN2 GP1, ENCA GP3, ENCB GP14
- Motor 1: PWM GP8, IN1 GP6, IN2 GP7, ENCA GP9, ENCB GP15
- Motor 2: PWM GP12, IN1 GP10, IN2 GP11, ENCA GP13, ENCB GP16
- I2C: SDA GP20, SCL GP21

## 6) Pin mapping documentation link

- `docs/pin_mapping.md`

## 7) Bring-up documentation link

- `docs/bringup.md`
- `docs/uart_protocol.md`

## 8) Repository structure

```text
BuddyBot/
├── firmware/
│   └── pico_motor_controller/     # Pico MicroPython firmware
├── software/
│   └── pi5/ros2_ws/src/           # ROS2 packages
│       ├── buddybot_base/
│       ├── buddybot_system/
│       ├── buddybot_nav/
│       ├── buddybot_vision/
│       ├── buddybot_msgs/
│       └── buddybot_bringup/
├── docs/
│   ├── architecture.md
│   ├── pin_mapping.md
│   ├── bringup.md
│   └── uart_protocol.md
└── tools/
    └── usb_serial_test.py
```

## 9) Development roadmap

- Phase A: 하드웨어 호환성/안전 bring-up 안정화 (진행)
- Phase B: Nav/Follow 통합 품질 향상
- Phase C: 고급 안전 검증 및 데모 시나리오 확장
- Phase D: 발표/문서/운영 자동화 고도화

## Quick bring-up (short)

```bash
cd software/pi5/ros2_ws
colcon build
source install/setup.bash
ros2 run buddybot_base pico_bridge_node
```

> 상세 순서와 안전 체크리스트는 `docs/bringup.md`를 따르세요.
