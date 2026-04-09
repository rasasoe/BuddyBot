# BuddyBot AI Handoff

이 파일은 팀원이 `BuddyBot` 작업을 다른 AI에게 바로 넘길 때 사용하는 단일 인수인계 문서다.

원칙:
- 이 파일 하나만 먼저 읽고 바로 작업을 이어갈 수 있어야 한다.
- 현재 우선순위는 `BuddyBot-ai`가 아니라 `BuddyBot` 본체 오프라인 완성이다.
- 서버컴 연동은 후순위다.
- 웨이크 워드와 제어 명령은 `BuddyBot` 내부에서 먼저 완성한다.

## 1. 현재 목표

최우선 목표:
- Pi5 + Pico + LiDAR + 카메라 기준으로 `BuddyBot` 자체를 오프라인에서 완성
- `버디봇`이라고 부르면 응답하고 제어 명령 수행
- 추종 / waypoint / 수동이동 / LiDAR 맵 / 로컬 패널 / 로컬 음성까지 서버 없이 동작

후순위:
- `BuddyBot-ai` 서버 연동
- 고급 자연어 대화
- 서버 PC 기반 기능 확대

## 2. 현재 상태 요약

이미 연결된 것:
- 로컬 패널에서 수동 이동 / 추종 on-off / waypoint 요청 / 로컬 chat 명령 처리
- follow controller가 `/follow/enabled`를 실제로 받아서 동작
- waypoint manager가 Nav2 action 또는 local fallback controller로 이동 시도
- panel이 `/scan`을 받아 `scan_local` 맵까지 표시 가능
- `buddybot_voice`가 오프라인 우선 local command router로 바뀜

현재 가장 중요한 실기 포인트:
- 전후진 / 측면이동은 실기에서 동작
- 회전은 기존에 안 움직였고, Pico kinematics mixer를 수정해 둔 상태
- 따라서 다음 AI는 "회전이 실기에서 정상화됐는지"를 가장 먼저 검증해야 함
- USB 웹캠(C920)은 한동안 정상 인식되다가 실기 중간에 사라질 수 있었음
- 이 현상은 현재 코드보다 Pi 전원/USB 안정성 이슈로 보는 것이 맞음

## 2-0. 최신 하드웨어 결론: 카메라 끊김은 전원/USB 문제 가능성이 큼

2026-04-09 실기에서 확인한 사실:
- 카메라가 사라진 시점에는 `lsusb`에 `046d`가 보이지 않았음
- `v4l2-ctl --list-devices`에도 C920이 아니라 Pi 내부 `pispbe`, `rpivid`만 보였음
- 즉 카메라 노드나 ROS 문제가 아니라, USB 레벨에서 장치 자체가 떨어진 상태였음
- 재부팅 후에는 다시 `lsusb`에 `046d:08e5 Logitech, Inc. C920 PRO HD Webcam`이 보였고 `v4l2-ctl`에도 복귀했음
- 이전 부팅 커널 로그에는 `Undervoltage detected!`가 반복적으로 다수 찍혀 있었음

현재 가장 그럴듯한 해석:
- 문제의 1차 원인은 `전력 부족 / 순간 전압 강하`
- 그 결과 USB 장치가 리셋되거나 허브 아래에서 재열거에 실패하면서 카메라가 사라졌을 가능성이 큼
- "LiDAR와 카메라를 소프트웨어적으로 동시에 못 돌림"으로 단정하면 안 됨

그때 관찰된 USB 구성:
- `Bus 002 Device 002: ID 2148:7022 USB2.0 HUB`
- `Bus 002 Device 003: ID 10c4:ea60 Silicon Labs CP210x UART Bridge` (LiDAR)
- `Bus 002 Device 004: ID 046d:08e5 Logitech, Inc. C920 PRO HD Webcam`
- 즉 LiDAR와 C920이 같은 USB2 허브 아래에 있었음

따라서 다음 AI는 카메라 문제를 볼 때 다음 순서로 판단해야 함:
1. 먼저 `lsusb`와 `v4l2-ctl --list-devices`에서 C920이 실제로 보이는지 확인
2. 안 보이면 ROS나 OpenCV를 보기 전에 전원/USB 이슈로 판단
3. `journalctl -k -b -1 | grep -Ei 'under-voltage|usb|disconnect|reset high-speed|descriptor read|over-current|enumerate|not enough power'`
4. 실시간 재현 시 `sudo dmesg -w`

현재 운영 권장:
- 개발 중에는 카메라가 필요 없으면 `BUDDYBOT_DISABLE_CAMERA=1`로 분리
- C920를 계속 쓸 경우 Pi5 본체 포트 직결 우선
- LiDAR / Pico / 카메라는 가능하면 같은 허브에 몰지 않기
- 최종 포터블 완성형은 `CSI 카메라 + USB LiDAR + USB Pico` 구성이 더 적합
- `5V 5A`급 전원/UPS는 도움될 가능성이 높지만, "표기 스펙"보다 실제 부하 시 전압 유지가 중요함

## 2-1. 왜 7주 / 8주가 건너뛴 것처럼 보이는가

결론부터:
- **실제로 완전히 건너뛴 것은 아님**
- **`docs/development_plan.md` 체크리스트가 현재 코드 상태를 따라가지 못해서 그렇게 보이는 것**

정리:
- 7주 `LiDAR 통합`은 실제로 상당 부분 구현되어 있음
- 8주 `센서 융합`도 일부는 구현되어 있지만, 문서에 적힌 "완전한 센서 융합" 수준까지는 아직 아님
- 그런데 9-13주 기능이 먼저 눈에 띄게 완성되면서, 7-8주가 비어 있는 것처럼 보이게 됨

즉:
- **7주는 부분적으로 구현 완료 + 체크리스트 미갱신**
- **8주는 부분 구현만 있고, 진짜 의미의 full fusion은 아직 미완**

### 7주 LiDAR 통합이 실제로 들어간 위치

다음이 실제 구현 근거다.

- LiDAR bringup / `/scan` 확인 / 자동 재시작
  - `scripts/start_mapping_panel.sh`
  - `scripts/start_offline_demo.sh`
  - `scripts/start_mapping_real_lidar.sh`
  - `scripts/check_all_devices.sh`
- LiDAR 기반 안전 회피
  - `software/pi5/ros2_ws/src/buddybot_system/buddybot_system/lidar_avoidance_node.py`
- LiDAR 기반 SLAM / Nav2 파라미터
  - `software/pi5/ros2_ws/src/buddybot_nav/config/nav_params.yaml`
  - `software/pi5/ros2_ws/src/buddybot_nav/launch/nav.launch.py`
- 로컬 패널에서 `/scan`을 받아 `scan_local` 맵 생성
  - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py`

그래서 7주 체크리스트 기준으로 보면:
- `LiDAR 센서 통신 설정`: 사실상 구현됨
- `기본 장애물 감지 추가`: `lidar_avoidance_node.py`로 구현됨
- `ROS 네비게이션 스택과 통합`: Nav2 / slam_toolbox / `/scan` 기반 파라미터로 상당 부분 구현됨
- `포인트 클라우드 처리 구현`: **이건 엄밀히 말하면 안 되어 있음**
  - 현재 BuddyBot은 2D LiDAR `/scan` 기반이지 point cloud 처리 구조는 아님

즉 7주는 "완료 3개 + 항목 wording 1개 불일치"에 가깝다.

### 8주 센서 융합이 실제로 들어간 위치

부분 구현 근거:
- 카메라와 LiDAR가 동시에 올라오는 bringup / 상태 확인
  - `scripts/check_all_devices.sh`
  - `scripts/start_mapping_panel.sh`
  - `scripts/start_offline_demo.sh`
- 카메라 시작 후 LiDAR `/scan`이 살아 있는지 확인하고 필요 시 자동 재시작
  - `scripts/start_mapping_panel.sh`
  - `scripts/check_all_devices.sh`
- 센서 health monitoring 성격의 상태 집계
  - `software/pi5/ros2_ws/src/buddybot_system/buddybot_system/safety_supervisor_node.py`
  - `scripts/probe_pi5_devices.py`
  - `scripts/check_all_devices.sh`
- 패널에서 camera / map / local scan 상태를 함께 보여줌
  - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py`
  - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`

하지만 아직 부족한 것:
- 카메라 detection 결과와 LiDAR obstacle을 같은 공통 표현으로 결합하는 노드 없음
- 명시적 time synchronization 노드 없음
- "통합 obstacle representation"을 별도 topic / costmap layer로 내는 구조 없음

즉 8주는:
- `센서 건강 모니터링 추가`: **부분 구현됨**
- 나머지 3개는 **진짜 의미로는 아직 미완**

따라서 7, 8주가 완전히 건너뛴 게 아니라:
- 7주는 실제 구현이 문서보다 앞서 있음
- 8주는 부분 구현만 있고 later phase로 밀린 항목이 있음

## 2-2. 지금까지 AI 작업 워크플로우 요약

처음부터 현재까지의 큰 흐름:

1. **하드웨어 bringup**
   - Pi5 <-> Pico 시리얼 브리지
   - Pico motor control / encoder / PID
   - 기본 ROS 2 stack 연결

2. **기본 motion / safety**
   - `/cmd_vel_final` 기반 수동 제어
   - watchdog / emergency stop / safety supervisor

3. **vision / follow**
   - camera pipeline
   - detector
   - follow controller

4. **LiDAR / mapping / panel**
   - LiDAR autostart
   - `/scan` 기반 safety avoidance
   - slam_toolbox bringup
   - panel에서 map / scan / waypoints / teleop

5. **명령 중재 / navigation**
   - command mux
   - mode manager
   - waypoint manager
   - local nav fallback

6. **오프라인 완성 쪽으로 우선순위 변경**
   - `BuddyBot-ai`보다 `BuddyBot` 본체 우선
   - panel local command 강화
   - `buddybot_voice`를 offline-first로 재작성
   - 회전 mixer 수정

## 2-3. AI가 파일을 어떻게 건드려 왔는지

주요 수정 히스토리 기준:

### bringup / 진단
- `scripts/probe_pi5_devices.py`
  - 장치 탐지
- `scripts/check_all_devices.sh`
  - Pico / LiDAR / camera / mic health 확인
- `scripts/start_mapping_panel.sh`
  - 실기 bringup 메인
- `scripts/start_offline_demo.sh`
  - 오프라인 데모 기동

### base / pico
- `software/pi5/ros2_ws/src/buddybot_base/buddybot_base/pico_bridge_node.py`
  - Pi5 -> Pico 속도 명령 전달
- `firmware/pico_motor_controller/*`
  - 실제 motor / encoder / PID / kinematics

### system / safety
- `software/pi5/ros2_ws/src/buddybot_system/buddybot_system/command_mux_node.py`
  - 명령 우선순위 중재
- `software/pi5/ros2_ws/src/buddybot_system/buddybot_system/lidar_avoidance_node.py`
  - LiDAR 기반 soft safety
- `software/pi5/ros2_ws/src/buddybot_system/buddybot_system/safety_supervisor_node.py`
  - safety aggregation

### vision
- `software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/camera_node.py`
- `software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/detector_node.py`
- `software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/follow_controller_node.py`

### navigation
- `software/pi5/ros2_ws/src/buddybot_nav/buddybot_nav/waypoint_manager_node.py`
- `software/pi5/ros2_ws/src/buddybot_nav/config/nav_params.yaml`
- `software/pi5/ros2_ws/src/buddybot_nav/launch/nav.launch.py`

### panel / local operator UX
- `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py`
- `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`

### voice
- `software/pi5/ros2_ws/src/buddybot_voice/buddybot_voice/voice_interface.py`

## 2-4. 지금 AI가 어디를 손봐야 하는가

다음 AI가 우선적으로 봐야 하는 파일 순서:

1. 회전 실기 문제
   - `firmware/pico_motor_controller/kinematics.py`
   - `firmware/pico_motor_controller/config.py`
   - 필요하면 `firmware/pico_motor_controller/motor_driver.py`
   - 필요하면 `firmware/pico_motor_controller/encoder.py`

2. 오프라인 voice
   - `software/pi5/ros2_ws/src/buddybot_voice/buddybot_voice/voice_interface.py`
   - `scripts/start_mapping_panel.sh`
   - `scripts/start_offline_demo.sh`

3. 로컬 panel command path
   - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py`
   - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`

4. navigation / follow 충돌
   - `software/pi5/ros2_ws/src/buddybot_nav/buddybot_nav/waypoint_manager_node.py`
   - `software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/follow_controller_node.py`
   - `software/pi5/ros2_ws/src/buddybot_system/buddybot_system/command_mux_node.py`

## 3. 이번 작업에서 바뀐 핵심

### A. 회전 문제

원인 판단:
- ROS에서 `angular.z`가 Pico까지 안 가는 문제는 아님
- `pico_bridge_node.py`는 `angular.z`를 정상 전달함
- 문제는 `firmware/pico_motor_controller/kinematics.py`가 회전 성분을 물리 길이 배율로 너무 작게 섞고 있었던 점

수정 내용:
- `firmware/pico_motor_controller/config.py`
  - `ROTATION_MIX_GAIN` 추가
- `firmware/pico_motor_controller/kinematics.py`
  - pure rotation이 충분한 크기의 wheel command가 되도록 normalized mixer 방식으로 변경
  - wheel output 자동 normalize 추가

핵심 가정:
- 기존 전후진 / 측면 이동 감각은 최대한 유지
- 회전만 "너무 약해서 사실상 안 도는" 상태를 먼저 깨는 방향

실기에서 회전이 여전히 약하면:
- `ROTATION_MIX_GAIN = 1.2` 또는 `1.5` 정도로 재조정

### B. 오프라인 음성

기존 문제:
- `buddybot_voice` README는 웨이크 워드 / 명령 인식을 말하지만 실제 구현은 BuddyBot AI 서버 포워딩뿐이었음

수정 내용:
- `software/pi5/ros2_ws/src/buddybot_voice/buddybot_voice/voice_interface.py`
  - 오프라인 우선 구조로 재작성
  - `/voice/text`를 직접 받아 local command 수행
  - `버디봇`, `버디봇아`, `버디`, `buddybot`, `buddy` 웨이크 워드 처리
  - 명령:
    - 정지
    - 전진 / 후진
    - 왼쪽 이동 / 오른쪽 이동
    - 좌회전 / 우회전
    - 추종 시작 / 추종 중지
    - 상태
    - 주방 / 거실 / 충전
  - 직접 publish:
    - `/cmd_vel_manual`
    - `/follow/enabled`
    - `/nav/cancel`
    - `/nav/waypoint_goal`
  - `/voice/response` 응답 publish 유지
  - `SpeechRecognition`이 설치되면 로컬 마이크 listener를 optional로 사용 가능

### C. 로컬 패널

패널 쪽 정리:
- `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py`
  - local command parser가 `버디봇` 호출에 응답
  - `버디봇, 좌회전` 같은 명령도 로컬에서 처리
- `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`
  - 브라우저 voice/TTS 경로는 이미 보강돼 있음

### D. bringup / 실행 스크립트

오프라인 voice 자동 기동 추가:
- `scripts/start_mapping_panel.sh`
- `scripts/start_offline_demo.sh`

관련 환경 변수:
- `BUDDYBOT_ENABLE_OFFLINE_VOICE=1`
- `BUDDYBOT_ENABLE_MIC_LISTENER=1`

Pi 패키지 설치 추가:
- `scripts/setup_pi5.sh`
  - `python3-speechrecognition`
  - `python3-pyaudio`
  - `python3-pocketsphinx`

## 4. 지금 작업 트리에서 수정된 주요 파일

다음 파일들은 이미 로컬 변경이 들어가 있다:

- `README.md`
- `docs/README.md`
- `docs/field_log.md`
- `firmware/pico_motor_controller/config.py`
- `firmware/pico_motor_controller/kinematics.py`
- `scripts/setup_pi5.sh`
- `scripts/start_mapping_panel.sh`
- `scripts/start_offline_demo.sh`
- `software/pi5/ros2_ws/src/buddybot_nav/buddybot_nav/waypoint_manager_node.py`
- `software/pi5/ros2_ws/src/buddybot_nav/package.xml`
- `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py`
- `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`
- `software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/follow_controller_node.py`
- `software/pi5/ros2_ws/src/buddybot_voice/CMakeLists.txt`
- `software/pi5/ros2_ws/src/buddybot_voice/buddybot_voice/voice_interface.py`
- `software/pi5/ros2_ws/src/buddybot_voice/package.xml`

## 5. 다음 AI가 바로 해야 할 일

순서대로:

1. Pi5에서 회전 실기 검증
2. 오프라인 voice node가 실제로 올라오는지 확인
3. `버디봇` 호출 후 수동 제어 명령이 실제 base motion으로 이어지는지 확인
4. Pico speaker는 핀 정보가 확인되면 그때 ACK tone부터 붙이기

## 6. Pi5에서 바로 실행할 명령

### 빌드

```bash
cd ~/BuddyBot/software/pi5/ros2_ws
colcon build --symlink-install --packages-select buddybot_panel buddybot_voice buddybot_nav buddybot_vision
source install/setup.bash
```

### 실행

```bash
cd ~/BuddyBot
bash scripts/start_mapping_one_terminal.sh
```

카메라 분리 테스트가 필요하면:

```bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=1 bash scripts/start_mapping_one_terminal.sh
```

### voice 명령 직접 테스트

새 터미널:

```bash
source /opt/ros/jazzy/setup.bash
source ~/BuddyBot/software/pi5/ros2_ws/install/setup.bash
ros2 topic pub --once /voice/text std_msgs/msg/String "{data: '버디봇'}"
ros2 topic pub --once /voice/text std_msgs/msg/String "{data: '버디봇 앞으로'}"
ros2 topic pub --once /voice/text std_msgs/msg/String "{data: '버디봇 좌회전'}"
ros2 topic pub --once /voice/text std_msgs/msg/String "{data: '버디봇 정지'}"
ros2 topic echo /voice/response
```

### panel / map 상태 확인

```bash
curl -s http://127.0.0.1:8090/api/status | python3 -m json.tool
curl -s http://127.0.0.1:8090/api/map | python3 -m json.tool | sed -n '1,20p'
```

## 7. 기대 결과

정상이면:
- `/api/status`에서 `scan_available: true`
- `/api/status`에서 `map_available: true`
- `/api/map`의 `source`가 `synthetic`가 아니라 `scan_local` 또는 `ros_map`
- `ros2 topic pub /voice/text ... '버디봇 좌회전'` 이후 base가 실제 회전
- `ros2 topic echo /voice/response`에서 한국어 응답 출력

## 8. 미해결 / 주의점

### 1. Pico speaker

아직 모르는 것:
- Pico speaker가 어느 핀에 연결돼 있는지 레포에 없음
- 현재 Pico firmware에는 speaker/buzzer/audio 구현이 없음

의미:
- 지금은 `버디봇` 호출과 명령 처리까지는 완성 방향
- Pico speaker로 실제 음성 재생은 아직 아님
- 핀 정보가 확인되면 먼저 tone / beep ACK부터 구현하는 것이 안전

### 2. 회전

수정은 했지만 실기 검증이 아직 필요함.

회전이 여전히 안 되면 의심 순서:
1. `ROTATION_MIX_GAIN` 부족
2. wheel direction sign 불일치
3. back/left/right wheel orientation 실제 배선과 코드 가정 불일치
4. encoder / PID 단위 mismatch 때문에 작은 회전 명령이 죽는 상황

### 3. 완전한 hands-free STT

현재 구조:
- `/voice/text`는 완성
- 브라우저 voice 버튼 경로도 있음
- `speech_recognition + pocketsphinx`가 있으면 Pi 로컬 마이크 listener를 붙일 수 있음

주의:
- 이건 하드웨어 마이크 품질과 설치 패키지 상태에 따라 달라짐
- 실기에서 `voice.log`를 반드시 확인할 것

## 9. 다음 AI를 위한 작업 지침

이 저장소에서 이어서 작업하는 AI는 다음 원칙을 따라야 한다.

- `BuddyBot-ai`는 지금 건드리지 말 것
- `BuddyBot` 오프라인 완성이 우선
- 회전 실기 검증이 첫 번째
- speaker는 "실제 TTS"보다 "확인음 / ACK tone"부터 붙일 것
- 한 번에 너무 넓게 바꾸지 말고, Pi에서 바로 검증 가능한 작은 단위로 진행할 것

권장 다음 작업:
1. 회전 실기 검증
2. `ROTATION_MIX_GAIN` 미세조정
3. `voice.log` 확인으로 microphone listener 점검
4. Pico speaker 핀 확인
5. speaker ACK tone 추가

## 10. 참고 파일

필요하면 다음을 추가로 보면 된다.

- `docs/field_log.md`
- `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py`
- `software/pi5/ros2_ws/src/buddybot_voice/buddybot_voice/voice_interface.py`
- `firmware/pico_motor_controller/kinematics.py`
- `firmware/pico_motor_controller/config.py`

하지만 기본적으로는 이 파일 하나만 보고 바로 이어서 작업해도 되게 작성했다.
