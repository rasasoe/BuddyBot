# Pico Motor Controller Firmware

기존 BuddyBot 실물 배선을 기준으로 동작하는 MicroPython 펌웨어입니다.

## 핵심 제약
- 배선 변경 금지
- Pi 5 통신은 USB serial (`/dev/ttyACM0`) 사용
- GPIO UART 미사용

## 실제 핀 매핑
- Motor 0: PWM GP2 / IN1 GP0 / IN2 GP1 / ENCA GP3 / ENCB GP14
- Motor 1: PWM GP8 / IN1 GP6 / IN2 GP7 / ENCA GP9 / ENCB GP15
- Motor 2: PWM GP12 / IN1 GP10 / IN2 GP11 / ENCA GP13 / ENCB GP16
- I2C: SDA GP20 / SCL GP21

## 모터 방향 보정
- 실물 배선과 드라이버 극성 차이 때문에 소프트웨어 기준의 `정방향`과 실제 바퀴 방향이 다를 수 있습니다.
- 재배선 대신 `config.py`의 `MOTOR_DIRECTION_SIGNS`로 바퀴별 방향을 보정합니다.
- 2026-04 현장 기준 기본값은 `left=+1`, `right=-1`, `back=+1` 입니다.
- 전진 명령에서 제자리 회전이 나면 먼저 이 값을 확인합니다.

## 파일 배치
Pico에 아래 파일을 복사합니다.
- `main.py` (entrypoint)
- `config.py`, `pins.py`, `motor_driver.py`, `encoder.py`
- `pid.py`, `kinematics.py`, `uart_protocol.py`, `watchdog.py`, `safety.py`, `state.py`

## 안전 모델
- watchdog timeout 시 즉시 정지
- `BRAKE` 명령으로 estop latch
- `CLEAR` 명령으로 해제
- 물리 E-STOP 핀은 현재 미배선 상태(소프트웨어 안전 계층 사용)
