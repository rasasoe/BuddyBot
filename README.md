# BuddyBot

안전하고 자율적인 홈 어시스턴트 로봇으로, Brain vs Spinal Cord 아키텍처를 특징으로 하며, 라즈베리 파이 5와 라즈베리 파이 피코를 사용하여 신뢰할 수 있는 인간-로봇 상호작용을 구현합니다.

## 개요

BuddyBot은 모듈식, 안전 우선의 자율 로봇을 통해 고급 로보틱스 엔지니어링 원칙을 시연하는 졸업 프로젝트입니다. 이 시스템은 "Brain vs Spinal Cord" 아키텍처를 구현하여 고수준 인지 기능(Pi 5)을 저수준 안전-critical 모터 제어(Pico)로부터 분리하여 시스템 실패 시에도 fail-safe 작동을 보장합니다. Ubuntu 24.04에서 ROS 2 Jazzy를 사용하여 BuddyBot은 LiDAR 기반 네비게이션, 컴퓨터 비전, 로컬 AI 처리를 자연스러운 인간-로봇 상호작용을 위해 통합합니다.

## 주요 기능

- **자율 네비게이션**: 의미적 웨이포인트 관리를 갖춘 LiDAR 기반 SLAM
- **사람 추적**: 부드러운 추적 알고리즘을 갖춘 실시간 컴퓨터 비전 추적
- **다중 모달 안전**: 비상 정지를 갖춘 하드웨어, 펌웨어, 소프트웨어 안전 계층
- **명령 중재**: 충돌하는 이동 명령을 방지하는 우선순위 기반 멀티플렉싱
- **전방향 이동**: 부드럽고 정확한 네비게이션을 위한 3륜 홀로노믹 드라이브
- **로컬 AI 처리**: 온디바이스 컴퓨터 비전 및 의사결정
- **음성 통합**: 자연어 명령 처리 (계획됨)

## 시스템 아키텍처

### Brain vs Spinal Cord 설계

BuddyBot은 인지와 제어를 분리하는 분산 아키텍처를 구현합니다:

```
┌─────────────────┐    UART     ┌─────────────────┐
│   Raspberry Pi 5 │◄──────────►│  Raspberry Pico │
│     (The Brain)  │            │ (The Spinal Cord)│
│                  │            │                  │
│ • ROS 2          │            │ • Motor Control  │
│ • Computer Vision│            │ • Safety Systems │
│ • Navigation     │            │ • Watchdog       │
│ • AI Processing  │            │ • E-Stop         │
└─────────────────┘            └─────────────────┘
         │                              │
         ├─ LiDAR (Navigation)         ├─ Motors
         └─ Camera (Vision)            └─ Encoders
```

### 명령 우선순위 계층

1. **E-STOP** (하드웨어/펌웨어): 물리적 비상 정지, 워치독 타임아웃
2. **수동** (인간): 직접 조이스틱/키보드 제어
3. **안전** (자율): 충돌 회피, 장애물 감지
4. **네비게이션** (자율): 웨이포인트 추종, 경로 계획
5. **추적** (자율): 사람 추적
6. **대기** (기본값): 정지 안전 상태

## 저장소 구조

```
BuddyBot/
├── firmware/           # Pico 마이크로컨트롤러 코드
│   └── pico_motor_controller/
├── software/           # ROS 2 워크스페이스
│   └── pi5/
│       └── ros2_ws/
│           └── src/    # ROS 2 패키지
│               ├── buddybot_base/      # Pi 5 ↔ Pico 통신
│               ├── buddybot_vision/    # 컴퓨터 비전 파이프라인
│               ├── buddybot_nav/       # 네비게이션 및 매핑
│               ├── buddybot_system/    # 명령 중재 및 안전
│               ├── buddybot_voice/     # 음성 인터페이스 (계획됨)
│               └── buddybot_bringup/   # 시스템 기동 구성
├── docs/              # 문서
├── tools/             # 개발 유틸리티
└── README.md          # 이 파일
```

## 하드웨어 스택

### 핵심 컴포넌트
- **라즈베리 파이 5**: ROS 2 및 AI 처리를 실행하는 메인 컴퓨터
- **라즈베리 파이 피코**: 실시간 모터 제어 및 안전 시스템
- **LiDAR 센서**: 네비게이션 및 매핑을 위한 2D 레이저 스캐너
- **카메라**: 컴퓨터 비전 및 사람 추적을 위한 RGB 카메라
- **옴니휠 드라이브**: 부드러운 이동을 위한 3륜 홀로노믹 베이스

### 주변 인터페이스
- **UART**: Pi 5와 Pico 간 결정론적 통신
- **USB**: 카메라 및 센서 연결
- **GPIO**: 모터 드라이버 및 안전 인터록
- **전력 관리**: 배터리 모니터링 및 분배

## 소프트웨어 스택

### ROS 2 Jazzy (Ubuntu 24.04)
- **미들웨어**: 프로세스 간 통신을 위한 ROS 2
- **네비게이션**: SLAM 및 경로 계획을 갖춘 Nav2 스택
- **비전**: 맞춤형 컴퓨터 비전 파이프라인을 갖춘 OpenCV
- **안전**: 다중 계층 안전 모니터링 및 제어

### Python 패키지
- **buddybot_base**: UART 통신 브리지
- **buddybot_vision**: 사람 감지 및 추적
- **buddybot_nav**: 웨이포인트 네비게이션 및 매핑
- **buddybot_system**: 명령 멀티플렉싱 및 안전 감독

### Pico 펌웨어
- **모터 제어**: PID 기반 전방향 제어
- **안전 시스템**: 워치독 타이머 및 비상 정지
- **통신**: UART 프로토콜 구현

## 개발 상태

### 완료 ✅
- Brain vs Spinal Cord 아키텍처 구현
- Pi 5와 Pico 간 UART 통신 프로토콜
- PID 알고리즘을 갖춘 기본 모터 제어
- 컴퓨터 비전 사람 감지 (MobileNet-SSD)
- 우선순위 멀티플렉싱을 갖춘 명령 중재 시스템
- 네비게이션 웨이포인트 관리
- 시스템 모드 관리 (대기/수동/추적/네비게이션)
- 다중 계층 안전 시스템

### 진행 중 🚧
- 전체 Nav2 네비게이션 스택 통합
- 음성 명령 처리
- 다중 센서 융합 (LiDAR + 카메라)
- 고급 안전 시스템 테스트

### 계획됨 📋
- 원격 모니터링을 위한 클라우드 통합
- 다중 로봇 조율 기능
- 행동 적응을 위한 학습 시스템
- 상용 배포 준비

## 빠른 시작

### 사전 요구사항
- Ubuntu 24.04 LTS
- ROS 2 Jazzy Jalisco
- 라즈베리 파이 5 및 Pico 하드웨어
- LiDAR 및 카메라 센서

### Pi 5 설정 (ROS 2)
```bash
# 저장소 클론
git clone https://github.com/rasasoe/BuddyBot.git
cd BuddyBot

# 설정 스크립트 실행
./tools/setup.sh

# ROS 2 패키지 빌드
cd software/pi5/ros2_ws
colcon build

# 워크스페이스 소스
source install/setup.bash

# 기본 기능 테스트
ros2 run buddybot_base pico_bridge_node
```

### Pico 설정 (펌웨어)
```bash
# 펌웨어 디렉토리로 이동
cd BuddyBot/firmware/pico_motor_controller

# 펌웨어 빌드 및 플래시 (적절한 Pico 개발 설정 사용)
# 구현은 Pico 개발 설정에 따라 다름
```

### 기본 시스템 테스트
```bash
# 비전 시스템 기동
ros2 launch buddybot_vision vision.launch.py

# 네비게이션 기동
ros2 launch buddybot_nav nav.launch.py

# 시스템 제어 기동
ros2 launch buddybot_system system.launch.py
```

## 로드맵

### 1단계: 기초 (완료)
- [x] Brain vs Spinal Cord 아키텍처
- [x] UART 통신 프로토콜
- [x] 기본 모터 제어 및 안전
- [x] 컴퓨터 비전 통합

### 2단계: 자율 동작 (진행 중)
- [x] 사람 추적
- [x] 웨이포인트 네비게이션
- [ ] 전체 Nav2 통합
- [ ] 음성 명령

### 3단계: 시스템 통합 (2026년 2분기)
- [ ] 다중 센서 융합
- [ ] 고급 안전 테스트
- [ ] 성능 최적화
- [ ] 사용자 인터페이스 개발

### 4단계: 고급 기능 (2026년 3-4분기)
- [ ] 클라우드 연결성
- [ ] 다중 로봇 조율
- [ ] 학습 기능
- [ ] Commercial deployment

## Safety Philosophy

**Safety First**: BuddyBot prioritizes human safety above all other system capabilities. The robot must never cause harm to humans or property, even at the expense of functionality.

### Safety Principles
- **Defense in Depth**: Multiple independent safety layers
- **Fail-Safe Defaults**: Safest possible state when systems fail
- **Transparent Operation**: Safety status always visible and logged
- **Conservative Design**: Safety margins exceed requirements

### Safety Layers
1. **Hardware Layer**: Physical E-stop, motor driver safeties
2. **Firmware Layer**: Pico watchdog, command validation
3. **Software Layer**: ROS safety supervisor, collision detection
4. **System Layer**: Command arbitration, mode management

### Safety Verification
- **Testing**: Comprehensive safety system validation
- **Monitoring**: Continuous safety status reporting
- **Training**: Operator safety procedures and emergency protocols
- **Documentation**: Complete safety analysis and procedures

## Contributing

This is a capstone project demonstrating robotics engineering principles. Contributions should:

1. Follow ROS 2 best practices and safety guidelines
2. Include comprehensive testing, especially safety systems
3. Update documentation for any architectural changes
4. Maintain the Brain vs Spinal Cord separation of concerns

## License

Apache 2.0 - See LICENSE file for details.

## Acknowledgments

- Raspberry Pi Foundation for hardware platforms
- ROS 2 community for the robotics framework
- Open source computer vision and navigation communities
- Capstone project advisors and mentors

## Documentation

- [System Architecture](docs/architecture.md)
- [Safety Policy](docs/safety_policy.md)
- [UART Protocol](docs/uart_protocol.md)
- [Development Plan](docs/development_plan.md)