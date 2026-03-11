# BuddyBot USB Serial Protocol

이 프로토콜은 Pi 5 ↔ Pico 간 **USB Serial (`/dev/ttyACM0`)** 통신용입니다.  
GPIO UART는 현재 사용하지 않습니다.

## 규칙
- ASCII 텍스트, 한 줄 1메시지
- `\n` 개행으로 메시지 종료
- 쉼표 구분
- 잘못된 패킷은 무시(크래시 금지)

---

## Pi 5 → Pico

### 1) Heartbeat
- `HB`
- 응답: `ACK,HB`

### 2) Velocity command
- `CMD,vx,vy,wz`
- 예: `CMD,0.200,0.000,0.100`
- 각 값은 `[-1.0, 1.0]`로 클램프
- 응답: `ACK,CMD`

### 3) Brake
- `BRAKE`
- 즉시 정지 + 안전 이벤트
- 응답: `ACK,BRAKE`

### 4) Clear estop latch
- `CLEAR`
- 응답: `ACK,CLEAR`

---

## Pico → Pi 5

### 1) Acknowledge
- `ACK,<type>`
- 예: `ACK,CMD`

### 2) Status
- `STAT,estop=<0|1>,timeout=<0|1>,mode=<MODE>`
- 예: `STAT,estop=0,timeout=0,mode=NORMAL`

### 3) RPM summary
- `RPM,m0=<...>,m1=<...>,m2=<...>`
- 예: `RPM,m0=10.0,m1=9.8,m2=10.2`

### 4) Safety event
- `SAFE,<reason>`
- 예: `SAFE,watchdog_timeout`

---

## 워치독/안전 동작
- Pico는 monotonic tick 기반 워치독 사용
- 타임아웃 시 모터 정지 + `SAFE,watchdog_timeout`
- 물리 E-STOP이 배선되지 않은 경우, 현 단계는 소프트웨어 안전 계층(BRAKE/timeout latch)로 운영
