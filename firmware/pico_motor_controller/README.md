# firmware/pico_motor_controller

BuddyBot 모터 제어를 위한 라즈베리 파이 피코 펌웨어.

## 하드웨어 연결

### 모터 드라이버 (L298N x 3)
- **모터 1 (왼쪽)**: PWM GP0, DIR1 GP1, DIR2 GP2
- **모터 2 (오른쪽)**: PWM GP4, DIR1 GP5, DIR2 GP6
- **모터 3 (뒤쪽)**: PWM GP8, DIR1 GP9, DIR2 GP10

### 엔코더
- **왼쪽 엔코더**: A GP11, B GP12
- **오른쪽 엔코더**: A GP13, B GP14
- **뒤쪽 엔코더**: A GP15, B GP16

### 안전 시스템
- **비상 정지 버튼**: GP17 (풀업 저항, 액티브 로우)

### 배터리 모니터링
- **배터리 ADC**: GP26 (ADC0, 전압 분배기 필요)

### 통신
- **Pi 5 통신**: USB 시리얼 (/dev/ttyACM0)
- **UART 핀**: GPIO UART 미사용 (USB CDC 사용)

## 펌웨어 플래시

1. Thonny IDE 또는 mpy-cross로 컴파일
2. Pico를 부트로더 모드로 설정 (BOOTSEL 버튼)
3. main.py와 모든 모듈을 Pico에 업로드

## 테스트

USB 시리얼 터미널에서 테스트:
```
CMD,0.5,0.0,0.0  # 전진
BRAKE             # 정지
```

## 파일

- **main.py**: 모터 제어, PID, 워치독, 안전을 포함한 메인 마이크로파이썬 스크립트
- **pins.py**: 실제 하드웨어 핀 매핑
- **config.py**: 제어 루프 및 통신 설정
- **motor_driver.py**: 저수준 모터 PWM 제어
- **encoder.py**: 엔코더 카운팅 및 RPM 계산
- **kinematics.py**: 옴니휠 운동학 계산
- **pid.py**: PID 제어기 구현
- **uart_protocol.py**: USB 시리얼 프로토콜 처리
- **safety.py**: 워치독 및 비상 정지 관리
- **watchdog.py**: 통신 타임아웃 감시
- **state.py**: 시스템 상태 관리

## 목적

"척수" 기능을 구현:
- 옴니휠 드라이브용 모터 제어
- 엔코더 피드백 및 PID 제어
- 안전을 위한 워치독 타이머
- 비상 정지 메커니즘
- Pi 5와의 USB 시리얼 통신