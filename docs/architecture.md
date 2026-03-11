# BuddyBot Architecture

## 시스템 목적
BuddyBot은 실험실/캡스톤 환경에서 **안전성 + 설명가능성 + 실기동성**을 동시에 만족하도록,
Pi5 고수준 지능 계층과 Pico 저수준 제어 계층을 분리한 구조를 사용합니다.

## 1. Brain vs Spinal Cord 설계 근거

### Pi 5 = Brain (AI/ROS2 layer)
- ROS 2 Jazzy 노드 실행
- LiDAR/비전 인지 처리
- 모드 관리 및 mission 로직
- command mux 및 시스템 상태 조율

### Pico = Spinal Cord (motor/safety layer)
- 모터 PWM/방향 제어
- 엔코더 카운트/속도 피드백
- watchdog timeout safety stop
- BRAKE/CLEAR 기반 estop latch

이 분리는 상위 소프트웨어 문제가 발생해도 하위 계층이 안전 정지를 강제할 수 있도록 하기 위한 것입니다.

## 2. 왜 기존 배선을 유지하는가

실제 제작/검증된 하드웨어 배선을 변경하면,
- 회로 재작업 리스크
- 디버깅 기준 붕괴
- 캡스톤 일정 지연
이 발생합니다.

따라서 본 브랜치의 정책은 **새 구조를 유지하되, 배선은 기존 실물 기준으로 고정**입니다.

## 3. 왜 USB serial을 유지하는가

Pi 5 ↔ Pico 링크는 현재 **USB CDC (`/dev/ttyACM0`)**를 사용합니다.

- 이미 실기동 검증된 경로
- bring-up 재현성이 높음
- GPIO UART 핀 충돌 회피(엔코더 핀 사용 중)
- 디버그/로그 확인이 쉬움

즉, 이번 작업 범위에서는 GPIO UART 전환을 하지 않습니다.

## 4. 제어/안전 우선순위

BuddyBot 명령 우선순위는 다음을 기준으로 합니다.

`E-STOP > Manual stop > Safety override > Follow/Nav > Idle`

- safety active 상태에서는 최종 속도를 0으로 강제
- stop latch가 걸리면 명시적 해제 전까지 유지
- 상위 인지/네비게이션 명령은 안전 계층을 우회할 수 없음

## 5. LiDAR vs Vision 책임 분리

- **LiDAR**: 전역 지도/경로 계획, 공간 구조 인식
- **Vision**: 사람 추적/근거리 상호작용
- 두 소스의 명령은 mux에서 중재되어 단일 `/cmd_vel_final`로 출력

## 6. 통신 인터페이스

- Pi5 브리지: `buddybot_base/pico_bridge_node.py`
- Pico 프로토콜: `firmware/pico_motor_controller/uart_protocol.py`
- 형식: line-based text protocol (`HB`, `CMD`, `BRAKE`, `CLEAR`, `STAT`, `RPM`, `SAFE`)

## 7. 현재 하드웨어 제약 명시

- 실배선 소스오브트루스는 `docs/pin_mapping.md`
- 물리 E-STOP 전용 핀이 미배선이면 소프트웨어 안전 계층으로 운영(TODO 명시)
- bring-up 절차는 `docs/bringup.md`를 기준으로 통일

## 8. 워크스페이스/패키지 구조 원칙

- canonical workspace: `software/pi5/ros2_ws`
- 모듈성 유지: base / system / nav / vision / msgs / bringup
- 중복 산출물(`__pycache__`, `.pyc`)은 소스 품질 판단에서 제외
