# BuddyBot Bring-up Checklist (Lab Practical)

## 0) 안전 준비
- [ ] 로봇 바퀴를 지면에서 띄우고 시작
- [ ] 첫 테스트는 저속/단일 모터부터 수행
- [ ] 방향 확인 전 전체 주행 명령 금지
- [ ] 타임아웃 정지 기능을 반드시 검증

## 1) Pico 펌웨어 준비
- [ ] `firmware/pico_motor_controller/`의 모듈을 Pico로 복사
- [ ] 진입 파일은 `main.py` 사용 (`/main.py`)
- [ ] 부팅 로그/동작 확인 (멈춤 없이 루프 실행)

### Pico 단독 통신 테스트 (USB 시리얼)
- [ ] 시리얼 모니터에서 `HB` 전송 → `ACK,HB` 확인
- [ ] `CMD,0.1,0.0,0.0` 전송 → `ACK,CMD` 및 상태 메시지 확인
- [ ] `BRAKE` 전송 → `ACK,BRAKE` 및 `SAFE,brake_command` 확인
- [ ] `CLEAR` 전송 → `ACK,CLEAR` 확인

### 모터/엔코더 기본 확인
- [ ] 한 모터씩 짧게 구동하여 방향 확인
- [ ] 엔코더 카운트 변화 확인 (`RPM`/상태 텍스트)
- [ ] 방향 반대면 모터 배선 또는 제어 부호를 점검

## 2) Pi 5 환경 준비
- [ ] ROS 2 Jazzy 환경 로드
- [ ] 워크스페이스 경로: `software/pi5/ros2_ws`
- [ ] 빌드: `colcon build`
- [ ] 소스: `source install/setup.bash`

## 3) USB 연결 확인
- [ ] Pico USB 연결 후 `ls /dev/ttyACM*`에서 `ttyACM0` 확인
- [ ] 권한 문제 시 사용자 dialout 그룹 확인

## 4) 브리지 노드 실행
- [ ] `ros2 run buddybot_base pico_bridge_node`
- [ ] 기본 포트 `/dev/ttyACM0` 연결 로그 확인
- [ ] Heartbeat/상태 수신 로그 확인

## 5) 명령 테스트
- [ ] `cmd_vel_final`로 소규모 속도 명령 송신
- [ ] 정지 명령(0,0,0) 정상 반영 확인
- [ ] 브리지 중단 시 Pico 워치독 정지 동작 확인

## 6) 상위 노드 순차 기동
- [ ] `buddybot_system` (명령 중재/안전)
- [ ] `buddybot_vision`
- [ ] `buddybot_nav`

---

## Troubleshooting

### A. `/dev/ttyACM0`가 안 보임
- USB 케이블 데이터 지원 여부 확인
- Pico 재연결/재부팅
- `dmesg | tail`로 커널 인식 로그 확인

### B. 시리얼 권한 오류
- `groups`에서 `dialout` 포함 여부 확인
- 미포함 시 `sudo usermod -a -G dialout $USER` 후 재로그인

### C. Pico 응답 없음
- 펌웨어 파일 누락 여부 확인 (`main.py`, `uart_protocol.py` 등)
- 개행 포함 라인 프로토콜 사용 여부 확인
- 브리지 포트 파라미터가 `/dev/ttyACM0`인지 재확인

### D. 모터 방향이 반대
- 모터 배선(IN1/IN2) 또는 소프트웨어 부호 확인
- 큰 속도 테스트 전 저속으로 교정

### E. 엔코더 카운트 변화 없음
- ENCA/ENCB 배선 접촉 확인
- 핀맵이 실제 배선(문서)과 일치하는지 확인
- 엔코더 전원/GND 점검
