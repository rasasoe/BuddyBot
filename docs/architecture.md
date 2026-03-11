# BuddyBot Architecture

## 시스템 목적

BuddyBot의 아키텍처 목표는 아래 3가지를 동시에 만족하는 것입니다.

1. **실기동성**: 실제 실험실 하드웨어에서 바로 재현 가능해야 함
2. **안전성**: 상위 소프트웨어 이상 시에도 하위 제어가 fail-safe 정지해야 함
3. **설명가능성**: 캡스톤/포트폴리오 발표 시 구조적 근거를 명확히 설명할 수 있어야 함

---

## 1) Brain vs Spinal Cord 설계 근거

### Pi 5 = Brain (AI/ROS2 layer)

- ROS 2 Jazzy 노드 실행 및 오케스트레이션
- LiDAR/비전 인지 및 상위 의사결정
- 모드 관리, 명령 중재, 시스템 상태 집계

### Pico = Spinal Cord (motor/safety layer)

- 모터 PWM/방향 제어
- 엔코더 피드백 수집
- watchdog timeout safety stop
- BRAKE/CLEAR 기반 estop latch

### 왜 분리하는가

- Pi 5는 고성능이지만 범용 OS 환경이라 지연/장애 가능성이 있습니다.
- Pico는 단순하고 결정론적인 제어 루프를 유지하기 쉽습니다.
- 따라서 지능과 안전을 분리하면, 고수준 장애가 저수준 안전을 무너뜨리지 않습니다.

---

## 2) 왜 기존 배선을 유지하는가

현재 프로젝트는 이미 동작 검증된 실물 배선을 기반으로 진행 중입니다.

배선을 임의 변경하면:
- 디버깅 기준이 붕괴되고
- 하드웨어 재작업 리스크가 증가하며
- 캡스톤 일정이 지연됩니다.

그래서 정책은 명확합니다: **새 소프트웨어 구조는 유지하되, 배선은 기존 실물 기준을 고정**합니다.

실제 핀맵은 `docs/pin_mapping.md`가 source of truth입니다.

---

## 3) 왜 USB serial(`/dev/ttyACM0`)을 유지하는가

Pi 5 ↔ Pico 통신은 현재 USB CDC 기반입니다.

- 실험실에서 이미 검증된 링크
- bring-up 재현성 높음
- GPIO UART 핀 충돌(엔코더 핀 재사용 문제) 회피
- 사람이 읽는 텍스트 프로토콜 디버깅이 쉬움

이번 범위에서는 GPIO UART 전환을 하지 않습니다.

---

## 4) 제어 및 안전 우선순위

최종 명령 우선순위 정책:

`E-STOP > Manual stop > Safety override > Follow/Nav > Idle`

의미:
- 안전 상태 활성화 시 최종 속도는 무조건 0
- 정지 래치가 걸리면 명시적 해제 전까지 유지
- 네비게이션/추적 등 고수준 명령은 안전 계층을 우회할 수 없음

이 정책은 `buddybot_system/command_mux_node.py`에서 구현됩니다.

---

## 5) LiDAR / Vision 책임 분리

### LiDAR
- 맵/경로 계획
- 전역 위치 기반 이동 결정

### Vision
- 사람 추적
- 근거리 상호작용 신호

다중 명령 소스 충돌은 command mux가 중재하고 단일 `/cmd_vel_final`만 Pico 브리지로 전달됩니다.

---

## 6) 통신 아키텍처

### 링크
- 물리/논리 링크: USB CDC serial
- Pi 5 장치명(기본): `/dev/ttyACM0`

### 프로토콜
- line-based text protocol
- Pi→Pico: `HB`, `CMD,vx,vy,wz`, `BRAKE`, `CLEAR`
- Pico→Pi: `ACK,*`, `STAT,*`, `RPM,*`, `SAFE,*`

설계 의도:
- 직렬 모니터로 즉시 디버깅 가능
- malformed packet에 대해 fail-safe 동작
- 안전 이벤트를 상위 계층으로 투명하게 보고

자세한 명세는 `docs/uart_protocol.md`를 따릅니다.

---

## 7) 안전 모델

- Pico watchdog은 monotonic ticks 기반으로 타임아웃 감지
- 타임아웃 시 모터 정지 + `SAFE,watchdog_timeout` 보고
- 물리 E-STOP 전용 핀이 없는 구성에서는 소프트웨어 래치(BRAKE/CLEAR + timeout)를 사용
- 물리 E-STOP 확장은 TODO로 문서화하고, 현재 상태를 과장하지 않음

---

## 8) 계층 간 책임 경계

### Pi5 계층 책임
- 인지/계획/모드/시나리오
- 사용자 입력/상위 정책
- ROS2 토픽/노드 오케스트레이션

### Pico 계층 책임
- 모터 구동 및 엔코더
- watchdog 기반 fail-safe
- 단순/강건 프로토콜 처리

이 책임 경계가 유지되어야 유지보수와 발표 설명력이 모두 좋아집니다.
