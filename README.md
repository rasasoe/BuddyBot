# BuddyBot

안전하고 자율적인 홈 어시스턴트 로봇으로, **Brain vs Spinal Cord** 아키텍처를 특징으로 하며, Raspberry Pi 5 + Raspberry Pi Pico 기반으로 신뢰할 수 있는 인간-로봇 상호작용을 구현합니다.

BuddyBot은 단순 기능 데모가 아니라, **캡스톤 발표/포트폴리오/실험실 재현성**까지 고려한 프로젝트입니다.

---

## 개요

BuddyBot은 모듈식, 안전 우선의 자율 로봇을 통해 고급 로보틱스 엔지니어링 원칙을 시연하는 졸업 프로젝트입니다.  
이 시스템은 "Brain vs Spinal Cord" 아키텍처를 구현하여 고수준 인지 기능(Pi 5)을 저수준 safety-critical 모터 제어(Pico)로부터 분리하고, 상위 계층 장애 시에도 fail-safe 정지를 보장합니다.

- OS/미들웨어: Ubuntu 24.04 + ROS 2 Jazzy
- 고수준 기능: LiDAR 기반 네비게이션, 비전 기반 사람 추적
- 저수준 기능: 모터 구동, 엔코더 피드백, watchdog/브레이크 안전 계층

---

## 주요 기능

- **자율 네비게이션**: LiDAR 기반 맵/경로 파이프라인
- **사람 추적**: 실시간 비전 기반 follow 동작
- **다중 계층 안전**: 하드웨어/펌웨어/소프트웨어 안전 모델
- **명령 중재(command mux)**: 충돌 명령 우선순위 기반 중재
- **전방향 이동**: 3륜 옴니휠 베이스
- **로컬 처리**: 온디바이스 인지/의사결정
- **확장성**: 음성 인터페이스/고급 기능 확장 고려

---

## 시스템 아키텍처

### Brain vs Spinal Cord 설계

```text
┌─────────────────┐ USB Serial ┌─────────────────┐
│   Raspberry Pi 5 │◄──────────►│  Raspberry Pico │
│     (The Brain)  │            │ (The Spinal Cord)
│                  │            │                  │
│ • ROS 2          │            │ • Motor Control  │
│ • Computer Vision│            │ • Safety Systems │
│ • Navigation     │            │ • Watchdog       │
│ • AI Processing  │            │ • E-Stop logic   │
└─────────────────┘            └─────────────────┘
         │                              │
         ├─ LiDAR (Navigation)         ├─ Motors
         └─ Camera (Vision)            └─ Encoders
```

### LiDAR / Vision 역할 분리

- **LiDAR**: 전역 이동/맵/경로 계획
- **Vision**: 사람 인식/추적, 근거리 상호작용
- 두 명령 소스는 `buddybot_system`의 command mux에서 정책 기반으로 최종 `/cmd_vel_final`로 통합됩니다.

### 명령 우선순위 계층

1. **E-STOP** (하드웨어/펌웨어)
2. **Manual stop** (운영자)
3. **Safety override** (안전 계층)
4. **Follow/Nav** (자율 계층)
5. **Idle** (기본 정지)

---

## 실제 하드웨어 고정 제약 (중요)

다음 항목은 현재 저장소의 고정 조건입니다.

1. **기존 실제 배선 유지**
2. **Pi 5 ↔ Pico 통신은 USB Serial 유지** (`/dev/ttyACM0`)
3. **GPIO UART 전환 금지** (이번 범위)
4. 물리 미배선 항목은 과장 없이 TODO/소프트웨어 안전 계층으로 명시

### Pico 실배선 핀 매핑 (Source of Truth)

- Motor 0: PWM GP2, IN1 GP0, IN2 GP1, ENCA GP3, ENCB GP14
- Motor 1: PWM GP8, IN1 GP6, IN2 GP7, ENCA GP9, ENCB GP15
- Motor 2: PWM GP12, IN1 GP10, IN2 GP11, ENCA GP13, ENCB GP16
- I2C: SDA GP20, SCL GP21

> 상세 핀맵: `docs/pin_mapping.md`

---

## 저장소 구조

```text
BuddyBot/
├── firmware/
│   └── pico_motor_controller/       # Pico MicroPython (motor/safety)
├── software/
│   └── pi5/ros2_ws/src/             # ROS2 packages
│       ├── buddybot_base/           # Pi5↔Pico serial bridge
│       ├── buddybot_system/         # command mux / safety supervisor
│       ├── buddybot_nav/            # navigation
│       ├── buddybot_vision/         # vision/follow
│       ├── buddybot_msgs/           # custom msgs
│       └── buddybot_bringup/        # launch orchestration
├── docs/
│   ├── architecture.md
│   ├── pin_mapping.md
│   ├── bringup.md
│   └── uart_protocol.md
└── tools/
    └── usb_serial_test.py
```

---

## 하드웨어 스택

### 핵심 컴포넌트
- Raspberry Pi 5: ROS 2 및 AI 처리 메인 컴퓨터
- Raspberry Pi Pico: 실시간 모터 제어 및 안전 계층
- LiDAR: 네비게이션/맵핑용 2D 거리 센서
- Camera: 사람 추적/근거리 인식
- Omni-wheel base: 3륜 홀로노믹 이동

### 인터페이스
- **USB Serial**: Pi 5↔Pico 통신 (`/dev/ttyACM0`)
- USB: 카메라/센서 연결
- GPIO/PWM: 모터/엔코더/보조 I/O

---

## 소프트웨어 스택

### ROS 2 Jazzy (Ubuntu 24.04)
- 미들웨어: ROS 2
- 네비게이션: Nav2 기반 구성
- 비전: OpenCV/딥러닝 기반 파이프라인
- 안전: supervisor + mux + Pico watchdog 계층

### 주요 패키지
- `buddybot_base`: USB serial 통신 브리지
- `buddybot_system`: 명령 중재/모드/안전 감독
- `buddybot_nav`: 네비게이션 및 맵 기능
- `buddybot_vision`: 사람 감지/추적

### Pico 펌웨어
- 모터 제어(PWM/방향)
- 엔코더 피드백
- watchdog timeout 안전 정지
- 텍스트 기반 USB serial 프로토콜

---

## 개발 상태

### 완료 ✅
- Brain vs Spinal Cord 기본 구조
- Pi5↔Pico USB serial 프로토콜
- 기본 모터 제어 + safety stop
- command mux 기반 명령 중재
- 문서 기반 bring-up 체계

### 진행 중 🚧
- Nav2 통합 안정화
- 비전/네비 연동 품질 개선
- 고급 안전 검증 시나리오

### 계획 📋
- 원격 모니터링
- 음성 명령 확장
- 다중 센서 융합 고도화
- 장기 운영 자동화

---

## 빠른 시작

### 사전 요구사항
- Ubuntu 24.04 LTS
- ROS 2 Jazzy
- Raspberry Pi 5 + Pico
- LiDAR + Camera

### Pi 5 설정

```bash
git clone https://github.com/rasasoe/BuddyBot.git
cd BuddyBot

cd software/pi5/ros2_ws
colcon build
source install/setup.bash

ros2 run buddybot_base pico_bridge_node
```

### Pico 설정

```bash
cd firmware/pico_motor_controller
# MicroPython 기준으로 파일 배포/플래시
# 상세 절차는 docs/bringup.md 참고
```

### 기본 bring-up 문서
- `docs/bringup.md`
- `docs/uart_protocol.md`
- `docs/architecture.md`

---

## Safety Philosophy

**Safety First**: BuddyBot은 기능보다 안전을 우선합니다.

### 원칙
- **Defense in Depth**: 다층 안전 장치
- **Fail-Safe Defaults**: 실패 시 정지 상태
- **Transparent Operation**: 상태/이벤트 가시화
- **Conservative Design**: 검증된 경로 우선

### 안전 계층
1. Hardware layer
2. Firmware layer (Pico watchdog, command validation)
3. Software layer (ROS safety supervisor)
4. System layer (command mux, mode management)

---

## 로드맵

1단계: 하드웨어 호환성 안정화 (완료)  
2단계: 자율 동작 품질 개선 (진행 중)  
3단계: 시스템 통합/검증 고도화  
4단계: 발표/운영 자동화 및 확장

---

## 문서 링크

- [System Architecture](docs/architecture.md)
- [Pin Mapping](docs/pin_mapping.md)
- [Bring-up Guide](docs/bringup.md)
- [USB Serial Protocol](docs/uart_protocol.md)

