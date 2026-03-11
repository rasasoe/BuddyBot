# BuddyBot

BuddyBot은 **Raspberry Pi 5 + Raspberry Pi Pico** 기반 3륜 옴니휠 로봇입니다.  
이 저장소는 단순 데모 코드가 아니라, **캡스톤 발표/포트폴리오/실험실 bring-up**까지 고려한 전체 시스템 베이스를 목표로 합니다.

핵심 철학은 명확합니다.

- **Brain (Pi 5)**: AI/ROS2/인지/계획
- **Spinal Cord (Pico)**: 모터/엔코더/워치독/안전 정지

즉, 상위 지능 계층이 실패해도 하위 안전 계층이 로봇을 멈출 수 있어야 합니다.

---

## 1. Project overview

BuddyBot은 ROS 2 Jazzy(ubuntu 24.04) 기반으로 다음을 통합합니다.

- LiDAR 기반 네비게이션
- 비전 기반 사람 추적
- 안전 우선 제어 아키텍처
- Pi5↔Pico 분리형 제어 구조

목표는 “기능이 많은 로봇”이 아니라, **실제 하드웨어에서 재현 가능한 안전한 로봇**입니다.

## 2. Key features

- **Brain vs Spinal Cord** 이원화 구조
- **3륜 옴니휠** 전방향 이동 제어
- **LiDAR / Vision 역할 분리**
- **우선순위 기반 command mux**
- **USB serial 기반 Pi5↔Pico 텍스트 프로토콜**
- **watchdog timeout + 소프트웨어 estop latch**
- 발표/유지보수 가능한 문서 구조

## 3. Brain vs Spinal Cord architecture

```text
Pi 5 (Brain)                           Pico (Spinal Cord)
---------------------------------------------------------
ROS2 orchestration                     PWM + direction control
Navigation / Vision / Mode logic   <-> Encoder feedback
Command arbitration                    Watchdog timeout stop
System-level safety decisions          Brake/Clear latch behavior
```

- Pi 5는 고수준 판단을 담당합니다.
- Pico는 저수준 모터/안전 동작을 독립적으로 보장합니다.

## 4. LiDAR / Vision role separation

- **LiDAR**: 전역 경로/맵 기반 주행, 공간 구조 인식
- **Vision**: 사람 추적, 근거리 상호작용/추종
- 다중 소스 명령은 `buddybot_system/command_mux_node.py`에서 단일 최종 명령으로 중재됩니다.

## 5. Real hardware constraints (fixed)

이 저장소는 아래 제약을 **고정 조건**으로 둡니다.

1. 기존 실제 배선 유지
2. Pi5↔Pico 통신은 USB serial 유지 (`/dev/ttyACM0`)
3. GPIO UART 마이그레이션은 이번 범위에서 금지
4. 물리 미배선 항목은 TODO/소프트웨어 안전 계층으로 명시

### Real Pico pin mapping (source of truth)

- Motor 0: PWM GP2, IN1 GP0, IN2 GP1, ENCA GP3, ENCB GP14
- Motor 1: PWM GP8, IN1 GP6, IN2 GP7, ENCA GP9, ENCB GP15
- Motor 2: PWM GP12, IN1 GP10, IN2 GP11, ENCA GP13, ENCB GP16
- I2C: SDA GP20, SCL GP21

## 6. Pin mapping doc

- [docs/pin_mapping.md](docs/pin_mapping.md)

## 7. Bring-up / protocol docs

- [docs/bringup.md](docs/bringup.md)
- [docs/uart_protocol.md](docs/uart_protocol.md)
- [docs/architecture.md](docs/architecture.md)

## 8. Repository structure

```text
BuddyBot/
├── firmware/
│   └── pico_motor_controller/        # Pico MicroPython firmware (motor/safety)
├── software/
│   └── pi5/ros2_ws/src/              # ROS2 packages on Pi5
│       ├── buddybot_base/            # Pico bridge + protocol
│       ├── buddybot_system/          # command mux / safety supervision
│       ├── buddybot_nav/             # navigation
│       ├── buddybot_vision/          # person following / perception
│       ├── buddybot_msgs/            # custom ROS messages
│       └── buddybot_bringup/         # launch orchestration
├── docs/
└── tools/
```

## 9. Development roadmap

- **Phase 1 (완료/안정화)**: 하드웨어 호환 pin/USB serial/safety bring-up
- **Phase 2 (진행중)**: Nav + Follow 동시 운용 품질 개선
- **Phase 3**: 안전 검증 시나리오/실험 데이터 정량화
- **Phase 4**: 발표/데모 자동화 및 운영 문서 고도화

---

## Quick start (Pi 5)

```bash
cd software/pi5/ros2_ws
colcon build
source install/setup.bash
ros2 run buddybot_base pico_bridge_node
```

실험실 최초 기동은 반드시 `docs/bringup.md`의 안전 체크리스트를 먼저 따르세요.
