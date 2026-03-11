# BuddyBot Pico Pin Mapping (Real Hardware)

이 문서는 **실제 조립된 BuddyBot 하드웨어** 기준 핀 매핑입니다.  
이 매핑은 임의 변경 금지이며, 배선 변경 없이 펌웨어/소프트웨어가 호환되어야 합니다.

## 모터/엔코더 매핑 (Source of Truth)

### Motor 0
- PWM: **GP2**
- IN1: **GP0**
- IN2: **GP1**
- ENCA: **GP3**
- ENCB: **GP14**

### Motor 1
- PWM: **GP8**
- IN1: **GP6**
- IN2: **GP7**
- ENCA: **GP9**
- ENCB: **GP15**

### Motor 2
- PWM: **GP12**
- IN1: **GP10**
- IN2: **GP11**
- ENCA: **GP13**
- ENCB: **GP16**

## I2C
- SDA: **GP20**
- SCL: **GP21**

## Pi 5 ↔ Pico 통신
- 통신 방식: **USB Serial (CDC)**
- Pi 5 기본 디바이스: **`/dev/ttyACM0`**
- GPIO UART(TX/RX): **현재 미사용**

## 안전 관련 주의
- GP16은 Motor 2 encoder B(ENCB)로 이미 사용 중이므로 UART 핀으로 재사용 불가
- 현재 하드웨어에 물리 E-STOP 전용 핀이 연결되지 않았다면, 펌웨어는 이를 소프트웨어 TODO로 유지해야 함
