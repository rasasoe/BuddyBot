# BuddyBot 현장 작업 로그 / Codex 인수인계

이 문서는 Pi5 실기 디버깅 내용을 날짜별로 남기는 운영 로그입니다.

목적:
- 다음 작업자가 같은 문제를 다시 처음부터 파지 않도록 하기
- 다른 작업환경에서 새로 붙은 Codex가 최근 이슈와 현재 상태를 빠르게 파악하게 하기
- "무엇을 했는지 / 무엇이 문제였는지 / 무엇이 해결됐는지 / 무엇이 아직 남았는지"를 사실 기준으로 기록하기

기록 원칙:
- 날짜, 환경, 기준 커밋을 먼저 적습니다.
- 증상과 재현 조건을 먼저 적고, 추측은 따로 분리합니다.
- 성공한 확인 절차와 실패한 절차를 둘 다 남깁니다.
- 해결되지 않은 항목은 "미해결"로 명시합니다.

새 작업환경에서 Codex가 먼저 읽을 것:
1. `README.md`
2. `docs/bringup.md`
3. 이 문서의 최신 날짜 항목

## 2026-04-09

환경:
- 장비: Raspberry Pi 5 (`pi@pi-desktop`)
- 메인 레포: `BuddyBot`
- 기준 메인 커밋: `3d88df4`
- 디버그 브랜치: `codex/panel-qos-fix`
- 관련 PR: `#4 Fix panel QoS for scan/map subscriptions`

그날 메인에 반영된 내용:
- LiDAR 포트 오인식 감소
- 카메라 시작 뒤 `/scan`이 끊기면 런처가 LiDAR를 1회 자동 재시작
- `check_all_devices.sh`가 카메라 시작 후 LiDAR 생존 여부까지 확인

주요 실행 커맨드:

```bash
cd ~/BuddyBot && git pull && bash scripts/start_mapping_one_terminal.sh
```

카메라 영향 분리 테스트:

```bash
cd ~/BuddyBot && git pull && BUDDYBOT_DISABLE_CAMERA=1 BUDDYBOT_DISABLE_PICO=1 bash scripts/start_mapping_real_lidar.sh
```

증상:
- 로컬 패널은 열리지만 맵 영역이 계속 `Map: synthetic`으로 표시됨
- `/api/status`에서 `scan_available=false`, `map_available=false`, `scan_frames_received=0`
- `/api/map`은 계속 `source: "synthetic"` 반환
- 브라우저 문제라기보다 패널 API가 실제로 synthetic 데이터를 주는 상태였음

같이 관찰된 로그:
- 카메라 미연결 상태에서는 `camera: none`
- OpenCV의 `can't open camera by index` 경고가 반복될 수 있음
- 이 경고 자체는 LiDAR 단독 확인 단계에서는 핵심 원인이 아니었음

확인된 정상 항목:
- `bash scripts/check_all_devices.sh`에서 LiDAR PASS
- `ros2 topic list` 기준 `/scan`, `/map` 토픽 존재 확인
- `slam.log`에서 `slam_toolbox` 활성화 로그 확인
- 직접 LiDAR만 띄우면 `ros2 topic echo --once /scan` 정상 수신
- `ros2 topic hz /scan` 약 7 Hz 수준 확인
- 별도 Python 디버그 리스너로 `/scan` 구독 시 다수 프레임 수신 확인

그때 사용한 직접 확인 예시:

```bash
source /opt/ros/jazzy/setup.bash
source ~/BuddyBot/software/pi5/ros2_ws/install/setup.bash
ros2 topic echo --once /scan
ros2 topic hz /scan
curl -s http://127.0.0.1:8090/api/status | python3 -m json.tool
curl -s http://127.0.0.1:8090/api/map | python3 -m json.tool | sed -n '1,20p'
```

문제 분리 결과:
- LiDAR 드라이버 자체는 정상으로 보였음
- `slam_toolbox`도 적어도 프로세스와 토픽 레벨에서는 살아 있었음
- 문제는 `buddybot_panel`이 `/scan`과 `/map`을 패널 상태로 반영하지 못하는 쪽으로 좁혀졌음

디버그 브랜치에서 시도한 변경:
- `/map` 구독 QoS를 `TRANSIENT_LOCAL + RELIABLE`로 조정
- `/scan` 구독 QoS를 `RELIABLE`로 조정
- map/scan subscription 레퍼런스를 멤버로 유지
- `rclpy.spin(...)` 대신 executor 기반 spin loop 추가
- `/api/status`에 아래 디버그 필드 추가
  - `spin_error`
  - `spin_thread_alive`
  - `last_scan_error`
  - `last_map_error`
- `/api/map`에서 ROS 구독이 비어 있으면 `ros2 topic echo --once /scan` 결과로 `scan_local` 맵을 만드는 CLI fallback 추가

그 시점 상태:
- `buddybot_local_panel`는 ROS graph 상에서 `/scan`, `/map` subscriber로 보였음
- 하지만 패널 상태는 여전히 `scan_frames_received=0`
- `spin_thread_alive=true`, `spin_error=null`, `last_scan_error=null`, `last_map_error=null`
- 즉 "죽지는 않았는데 반영도 안 되는" 상태였음

마지막으로 확인한 추가 단서:
- `ros2 topic echo --once /scan` 출력은 길면 YAML 배열 끝이 `'...'`로 잘릴 수 있음
- CLI fallback이 그 문자열을 그대로 `float(...)` 하다가 실패했을 가능성이 큼
- 그래서 마지막 로컬 보강은 `ranges` 파싱 시 숫자로 변환 가능한 값만 사용하도록 수정하는 것이었음

2026-04-09 종료 시점 결론:
- `3d88df4`의 LiDAR 재시작/포트 인식 개선은 의미 있는 변경
- 실기 LiDAR 데이터는 들어오고 있음
- 그러나 패널 맵 반영 문제는 완전히 해결됐다고 확정하지 못함
- 특히 `buddybot_panel` 런타임 경로와 실제 구독/폴백 반영 경로를 계속 의심해야 함

다음 작업환경에서 우선 확인할 순서:
1. `git rev-parse HEAD`로 기준 커밋 확인
2. `bash scripts/check_all_devices.sh`
3. `curl -s http://127.0.0.1:8090/api/status | python3 -m json.tool`
4. `curl -s http://127.0.0.1:8090/api/map | python3 -m json.tool | sed -n '1,20p'`
5. `ros2 topic list | grep -E '^/scan$|^/map$'`
6. `ros2 topic echo --once /scan`
7. `python3 -c "import inspect, buddybot_panel.panel_server as m; print(inspect.getsourcefile(m))"`

다음 작업환경에서 권장 시작점:

```bash
cd ~/BuddyBot
git pull
cd ~/BuddyBot/software/pi5/ros2_ws
colcon build --symlink-install --packages-select buddybot_panel
source install/setup.bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=1 bash scripts/start_mapping_one_terminal.sh
```

메모:
- 카메라가 실제로 안 붙어 있으면 `BUDDYBOT_DISABLE_CAMERA=1`로 먼저 분리해서 보는 편이 좋음
- 매핑 스택을 띄운 뒤 바로 `Ctrl+C`를 누르면 이후 패널/토픽 상태 확인이 왜곡됨
- 패널만 synthetic이면 브라우저 문제보다 API 응답을 먼저 확인할 것

## 2026-04-09 추가 작업: 기능 연결 마무리

이번 라운드에서는 "버튼은 있는데 실제 동작으로 안 이어지는" 경로를 정리하는 데 집중했다.

무엇이 문제였나:
- `follow`는 패널/AI 웹앱에서 플래그만 바꾸고 실제 ROS 제어 토픽으로 연결되지 않았음
- `waypoint`는 YAML 저장과 UI 선택은 되지만 실기 주행 경로가 placeholder에 가까웠음
- 로컬 Pi5 패널의 음성 버튼은 브라우저 STT만 있고, 응답 TTS가 빠져 있었음
- AI 웹앱도 ROS waypoint/follow 토픽과 같은 규약으로 묶여 있지 않았음

이번에 반영한 내용:
- `buddybot_vision/follow_controller_node.py`
  - `/follow/enabled` 토픽 구독 추가
  - follow off 시 즉시 0 속도 publish
  - bbox 유실 timeout 시 안전 정지
- `buddybot_nav/waypoint_manager_node.py`
  - Nav2 action goal 전송 구현
  - `/nav/cancel` topic cancel 경로 추가
  - `/system/mode`와 `/system/current_mode` 둘 다 수신하도록 보강
  - Nav2 서버가 없으면 현재 pose 기반 로컬 waypoint controller로 `/cmd_vel_nav` 직접 publish 하도록 fallback 추가
- `buddybot_panel/panel_server.py`
  - `/follow/enabled`, `/nav/cancel`, `/nav/navigation_status` 연동
  - follow/manual/nav 전환 시 서로 충돌하는 상태를 정리하도록 보강
  - 로컬 command parser에 한국어 키워드 추가
- `buddybot_panel/static/index.html`
  - chat 응답을 브라우저 speech synthesis로 읽어주도록 추가
  - voice recognition 언어를 브라우저 언어 기준으로 사용
  - navigation status를 상태 카드에 표시
- `BuddyBot-ai/app/tools/robot_tool.py`
  - `/follow/enabled`, `/nav/waypoint_goal`, `/nav/cancel` publish 추가
  - dock를 실제 `charging_station` waypoint 요청으로 연결
  - manual에 strafe/rotate 구분 추가
- `BuddyBot-ai/app/tools/navigation_tool.py`
  - waypoint save / go 요청을 ROS topic에도 같이 publish
- `BuddyBot-ai/app/core/intent_router.py`
  - "왼쪽 이동"과 "좌회전"을 구분하도록 방향 추출 보강
- `BuddyBot-ai/app/static/index.html`, `app/static/app.js`
  - strafe/rotate 버튼 보강
  - 버튼 기반 응답도 TTS로 읽어주도록 보강

이번 작업환경에서 확인한 것:
- Python 문법 검사(`py_compile`)는 통과
- 현재 Codex 작업환경에는 ROS/`colcon`이 없어 여기서 실제 `colcon build` 검증은 못 함

다음 실기 확인 우선순위:
1. `colcon build --symlink-install --packages-select buddybot_panel buddybot_nav buddybot_vision`
2. `bash scripts/start_mapping_one_terminal.sh`
3. Follow on/off 시 `/follow/enabled`와 `/cmd_vel_follow` 동작 확인
4. waypoint go 시 `/nav/navigation_status`가 `navigating_local:*` 또는 `nav2_active:*`로 바뀌는지 확인
5. 로컬 패널 voice 버튼으로 말했을 때 응답 TTS가 재생되는지 확인

## 2026-04-09 추가 작업: BuddyBot 오프라인 완성 우선

이번 라운드에서는 `BuddyBot-ai`보다 `BuddyBot` 본체를 먼저 완성하는 쪽으로 우선순위를 바꿨다.

사용자 요구:
- 오프라인에서 BuddyBot 자체만으로 기능 완성
- `버디봇`이라고 부르면 대답하고 제어 명령 가능해야 함
- 스피커는 Pico에 연결되어 있지만, 서버컴 연동은 후순위
- 현재 실기에서 전후진 / 측면 이동은 되는데 회전은 안 움직임

원인 분석:
- 회전 불능은 ROS `cmd_vel` 전달 문제보다 Pico 펌웨어 mixer 문제일 가능성이 높았음
- 실제로 `pico_bridge_node.py`는 `angular.z`를 Pico까지 정상 전달하고 있었음
- 그런데 `firmware/pico_motor_controller/kinematics.py`는 `wz`에 바퀴 간 거리(미터)를 곱해서 회전 성분을 너무 작게 만들어, 순수 회전 명령이 전진/측면 이동 대비 약 10% 수준으로 줄어들고 있었음
- 음성 쪽은 `buddybot_voice` README는 wake word / command recognition을 말하지만 실제 구현은 BuddyBot AI 서버 포워딩뿐이었음

이번에 반영한 내용:
- `firmware/pico_motor_controller/config.py`
  - `ROTATION_MIX_GAIN` 추가
- `firmware/pico_motor_controller/kinematics.py`
  - 회전 성분을 물리 길이 배율이 아니라 정규화된 mixer 기준으로 변경
  - pure rotate 명령이 forward / strafe와 비슷한 크기의 wheel command가 되도록 보강
  - wheel output이 1.0을 넘으면 자동 normalize 하도록 추가
- `software/pi5/ros2_ws/src/buddybot_voice/buddybot_voice/voice_interface.py`
  - AI bridge 중심 구조를 오프라인 우선 구조로 재작성
  - `/voice/text`에서 `버디봇`, `buddybot` wake word 인식
  - local command parser 추가: 정지 / 전진 / 후진 / 왼쪽 이동 / 오른쪽 이동 / 좌회전 / 우회전 / 추종 on/off / 상태 / 주방 / 거실 / 충전
  - `/voice/response` 응답 publish 유지
  - `/cmd_vel_manual`, `/follow/enabled`, `/nav/cancel`, `/nav/waypoint_goal` 직접 publish
  - `SpeechRecognition`이 있으면 로컬 마이크 listener를 붙일 수 있도록 optional path 추가
  - AI 서버는 `offline_mode:=false`일 때만 secondary path로 사용
- `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py`
  - 로컬 chat parser도 `버디봇` 호출에 "네, 부르셨어요?"로 응답하도록 보강
  - `버디봇, 좌회전` 같은 한 문장 명령도 같은 parser 규칙으로 동작하도록 정리
- `scripts/start_mapping_panel.sh`
  - 오프라인 voice node 자동 실행 추가
  - `BUDDYBOT_ENABLE_OFFLINE_VOICE`
  - `BUDDYBOT_ENABLE_MIC_LISTENER`
- `scripts/start_offline_demo.sh`
  - 동일하게 오프라인 voice node 자동 실행 추가
- `scripts/setup_pi5.sh`
  - `python3-speechrecognition`, `python3-pyaudio`, `python3-pocketsphinx` 설치 추가

제약 / 메모:
- Pico speaker 핀 정보는 아직 레포에 없음
- 따라서 이번 라운드에서는 "Pico speaker로 실제 음성 재생"까지는 완성하지 못했고, 먼저 BuddyBot 내부의 wake word + local command path를 완성하는 데 집중함
- 현재 구조에서는 panel browser voice 또는 `/voice/text` publisher가 있으면 AI 서버 없이도 BuddyBot 로컬 명령 실행이 가능함
- hands-free 오프라인 STT는 Pi5 패키지 설치 상태와 microphone 환경에 좌우되므로, 실기에서 `voice.log` 확인이 필요함

다음 실기 확인 우선순위:
1. `colcon build --symlink-install --packages-select buddybot_panel buddybot_nav buddybot_vision buddybot_voice`
2. `bash scripts/start_mapping_one_terminal.sh`
3. 패널 또는 `/voice/text`로 `버디봇`, `버디봇 앞으로`, `버디봇 좌회전`, `버디봇 정지` 확인
4. `tail -n 120 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/voice.log`
5. 회전이 여전히 약하면 `ROTATION_MIX_GAIN`를 `1.2 ~ 1.5`로 소폭 올려 재검증

## 2026-04-09 추가 작업: 카메라 끊김 원인 진단

상황:
- 같은 날 실기에서 "아까까지 보이던 C920이 중간에 사라지는" 현상이 발생
- `start_mapping_one_terminal.sh` 로그에는 `camera: none`, `CAMERA_DEVICE=`, `V4L_BY_ID=`가 찍혔고
- OpenCV `can't open camera by index` 경고가 반복됨

실제 확인 결과:

문제가 발생한 시점:

```bash
ls -l /dev/v4l/by-id
v4l2-ctl --list-devices
lsusb | grep -i -E '046d|camera|webcam'
```

관찰:
- `/dev/v4l/by-id` 자체가 없었음
- `v4l2-ctl --list-devices`에는 Pi 내부 `pispbe`, `rpivid`만 보였음
- `lsusb | grep -i 046d`도 비어 있었음

의미:
- 카메라 노드가 죽은 것이 아니라 USB 레벨에서 C920 자체가 사라진 상태
- 따라서 ROS, OpenCV, panel API를 먼저 의심하면 안 됨

재부팅 후 확인:

```bash
echo '=== previous boot kernel hints ==='
journalctl -k -b -1 2>/dev/null | grep -Ei 'under-voltage|voltage|usb|disconnect|reset high-speed|descriptor read|over-current|enumerate|not enough power' | tail -n 80

echo '=== current usb ==='
lsusb

echo '=== current camera devices ==='
v4l2-ctl --list-devices
```

관찰:
- 이전 부팅 커널 로그에 `Undervoltage detected!` / `Voltage normalised`가 반복적으로 다수 존재
- 현재 부팅에서는 다시 `046d:08e5 Logitech, Inc. C920 PRO HD Webcam`이 보였음
- `v4l2-ctl --list-devices`에도 `HD Pro Webcam C920 (usb-xhci-hcd.0-2.4)`가 복귀
- 같은 시점 USB 목록에는 다음이 함께 보였음:
  - `2148:7022 USB2.0 HUB`
  - `10c4:ea60 Silicon Labs CP210x UART Bridge` (LiDAR)
  - `046d:08e5 Logitech C920`

결론:
- 카메라 끊김은 코드 버그보다 `전력 부족 / 순간 전압 강하 / USB 허브 안정성` 문제일 가능성이 큼
- 특히 LiDAR와 C920이 같은 USB2 허브 아래에 있는 구성이 리스크를 높였을 수 있음
- "LiDAR와 카메라를 동시에 소프트웨어적으로 못 돌린다"로 결론 내리면 안 됨

운영 가이드:
- 카메라가 필요 없는 개발 단계는 `BUDDYBOT_DISABLE_CAMERA=1`
- 카메라를 쓸 때는 C920를 Pi5 본체 포트에 직접 연결하는 것을 우선 검토
- LiDAR / Pico / 카메라는 가능한 한 같은 허브에 몰지 않기
- 재현 확인은 `sudo dmesg -w`를 켜 두고 장치가 사라질 때 마지막 로그를 보는 방식이 가장 확실
- 포터블 최종형 관점에서는 `CSI 카메라 + USB LiDAR + USB Pico` 구성이 더 적합
- `5V 5A`급 전원/UPS는 도움이 될 가능성이 높지만, 실제 부하 시 전압 유지 품질이 중요함

다음 작업환경에서 카메라가 다시 사라지면:
1. `lsusb | grep -i 046d`
2. `v4l2-ctl --list-devices`
3. `sudo dmesg -w`
4. `journalctl -k -b -1 | grep -Ei 'under-voltage|usb|disconnect|reset high-speed|descriptor read|over-current|enumerate|not enough power'`

위 1, 2에서 C920이 사라져 있으면 소프트웨어보다 하드웨어/전원부터 봐야 한다.
