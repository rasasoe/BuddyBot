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

## 2026-04-16 추가 작업: Pi5 전원 완화와 모터 방향 보정

환경:
- 장비: Raspberry Pi 5 (`pi@pi-desktop`)
- 메인 레포: `BuddyBot`
- 기준 커밋: `8369eae`

실기 관찰:
- `PSU_MAX_CURRENT=5000` 적용 전후 비교에서 under-voltage 빈도는 줄었지만, 여전히 Pico USB CDC(`ttyACM0`) 재열거가 간헐적으로 보였음
- 매우 낮은 카메라 설정(`160x120 @ 5fps publish 2Hz`)에서는 bringup 자체는 더 자주 살아남았음
- 그런데 manual 전진/후진/회전/측면 이동 명령 모두에서 "제자리 회전"처럼 보이는 현상이 계속 보고됨
- 상위 ROS 경로는 이미 검증되어 있었으므로, 이번 증상은 Pico 하위 모터 극성/방향과 더 잘 맞았음

해석:
- `kinematics.py`의 회전 mixer 문제는 이전 커밋에서 이미 보강되어 있었음
- 이번 증상은 pure forward(`vx>0, vy=0, wz=0`)에서도 spin이 나는 패턴이라, front pair 중 한쪽 모터의 방향이 소프트웨어 모델과 반대일 가능성이 가장 큼
- 현장 기본 보정값으로 `right` 모터 방향을 반전하는 계층을 추가함

반영 내용:
- `firmware/pico_motor_controller/config.py`
  - `MOTOR_DIRECTION_SIGNS` 추가
  - 기본값: `left=+1`, `right=-1`, `back=+1`
- `firmware/pico_motor_controller/motor_driver.py`
  - 모터 출력 직전에 wheel-specific polarity를 적용하도록 변경
- `firmware/pico_motor_controller/README.md`
  - 방향 보정 위치와 현장 기본값 문서화

다음 실기 확인:
1. Pico에 최신 `config.py`, `motor_driver.py`, `main.py` 배포
2. bringup 후 manual 전진 버튼으로 `cmd_vel_final`이 `vx>0, vy=0, wz=0`인지 재확인
3. 전진 시 제자리 회전이 사라졌는지 확인
4. 만약 반대로 뒤로 가면 `left/right/back` 중 필요한 축만 `+1/-1`로 재조정

추가 관찰:
- `PSU_MAX_CURRENT=5000`를 EEPROM에 반영한 뒤 초기 bringup은 이전보다 조금 더 오래 살아남는 편이었음
- 그러나 `dmesg`에는 여전히 간헐적인 `usb 2-2: USB disconnect`와 `cdc_acm` 재열거가 보였음
- 매우 낮은 카메라 프로파일(`160x120 @ 5fps publish 2Hz`)에서는 `camera_node` 초기화 자체는 성공했음
- 하지만 `/camera/image_raw`가 실제 publish되지 않는 경우가 있었고, `camera.log`에는 과거 실행의 fatal line이 섞여 있어 단독 node 실행으로 재확인 필요했음
- `follow_controller_node`는 `/vision/person_bbox`에서 QoS mismatch 경고가 계속 보여서, 추종 path는 전원 문제와 별개로 추가 수정이 필요함

운영 메모:
- 서로 다른 노트북/세션에서 작업을 이어갈 때 매번 긴 프롬프트를 새로 쓰는 비용이 컸음
- 이 문제를 줄이기 위해 `docs/CODEX_RESUME_WORKFLOW.md`를 추가했고, 앞으로는
  1. `AI_HANDOFF.md`
  2. `docs/field_log.md` 최신 항목
  3. `docs/CODEX_RESUME_WORKFLOW.md`
  순서로 읽는 것을 표준 흐름으로 삼음
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

## 2026-04-13

환경:
- 장비: Raspberry Pi 5 (`pi@pi-desktop`)
- 메인 레포: `BuddyBot`
- 기준 커밋: `83ca43e` (Fix rotate mapping and localize mission panel)

변경 내용:

### panel_server.py 미니맵 탐색 / 추종 / 서버 상태 개선

1. **`_mini_map_timer` 완전 재작성** — 기존 단순 phase sweep 방식을 `_explore_*` 상태 기계로 교체
   - 상태: `"forward"` / `"turning"`
   - 전방 장애물(0.55 m) 감지 시 1.2s 회전 후 재전진
   - 측방 장애물(0.40 m) 감지 시 soft 방향 보정
   - 8초마다 coverage sweep (1.0–1.8s 좌/우 교번)
   - 안전 latch 또는 scan stale 시 즉시 정지
   - minimap 비활성 상태에서도 `/follow/enabled` 항상 publish

2. **`start_mini_map()`** — 탐색 상태 변수 매 세션 초기화 추가

3. **`status()` 블로킹 수정** — `check_server()` (1s timeout 블로킹) → `_cached_server_connected()` (15s 캐시) 교체

4. **`_cached_server_connected()` 신규 메서드** — assistant 미활성 시 즉시 False 반환, 이후 15s 간격 갱신

5. **`__init__` 상태 변수 추가**
   - `_explore_phase / _explore_turn_direction / _explore_turn_remaining / _explore_last_step`
   - `_server_connected / _server_check_at`
   - `_mini_map_known_cells / _mini_map_grid_*` (그리드 스캐폴딩, 현재 미사용)

검증: Python AST parse `SYNTAX OK`

미해결:
- 실기에서 회전 정상화 여부 아직 미확인
- 카메라 전원 문제 해결 안 됨 (하드웨어 이슈)

## 2026-04-15 ~ 2026-04-16

환경:
- 장비: Raspberry Pi 5 (`pi@pi-desktop`)
- 메인 레포: `BuddyBot`
- 현장 기준 커밋 흐름:
  - `be7e152` Guard Pi5 launcher against missing demo packages
  - `dc64fe3` Prevent manual drive dropouts when minimap is idle
  - `42b0b64` Improve panel diagnostics and debug bundle capture
  - `66231ab` Fix camera rate params and debug bundle cleanup
  - `6c45591` Add presentation mode for unstable USB power

이번 라운드 핵심 목표:
- 수동제어가 토글 방식으로 끊기지 않게 만들기
- Pi5에서 카메라 / LiDAR / Pico를 가능한 한 동시에 살려서 시연 가능 상태 만들기
- 디버그 로그를 한 번에 수집해서 원인을 다음 세션에서도 바로 이어받게 만들기
- 발표 직전용 저부하 런처와 문서를 정리하기

### 1. 수동제어 dropout 원인 확인 및 수정

증상:
- 패널에서 수동조작 버튼을 누르면 API는 `200 OK`
- 하지만 실제 주행은 짧게 들어갔다가 바로 끊기거나 `command_mux`가 `manual -> idle`로 빠르게 오갔음

원인:
- `panel_server.manual_command()`가 수동 명령 전에 minimap 종료 경로를 호출
- minimap이 실제로 돌고 있지 않아도 `stop_mini_map()`이 zero manual command를 inject
- 결과적으로 panel이 반복 `/api/manual`을 보내는 동안 manual motion이 계속 지워짐

수정:
- `buddybot_panel/panel_server.py`에서 minimap이 실제 active일 때만 `_clear_manual_motion()` 하도록 수정

확인 방법:
- `command_mux.log` 또는 디버그 번들의 `command_mux.tail.log`에서 `manual` 상태가 수 초 이상 유지되는지 확인

### 2. 누락 빌드 패키지 때문에 런처가 반쯤만 뜨는 문제 수정

증상:
- `start_all_pi5.sh` 실행 시 일부 노드가 뜨지 않거나
- preflight에서 토픽이 없고
- 사실상 `buddybot_msgs`, `buddybot_system`, `buddybot_vision` 등이 빌드되지 않은 상태였음

수정:
- `scripts/start_all_pi5.sh`에 필수 ROS 패키지 검사 추가
- 누락 시 런처가 즉시 중단되고 필요한 `colcon build --packages-select ...` 명령을 그대로 출력하게 변경

현장 기준 권장 빌드:

```bash
cd ~/BuddyBot/software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
rm -rf build install log
colcon build --symlink-install --packages-select \
  buddybot_msgs \
  buddybot_base \
  buddybot_system \
  buddybot_nav \
  buddybot_panel \
  buddybot_voice \
  buddybot_vision
source install/setup.bash
```

### 3. 카메라 정수 파라미터 타입 mismatch 수정

증상:
- `BUDDYBOT_CAMERA_FPS=10`
- `BUDDYBOT_CAMERA_PUBLISH_RATE=5`
- 같은 식으로 줬을 때 preflight camera test가 실패
- camera log에는 `Trying to set parameter 'fps' ... expecting type 'DOUBLE'`가 남음

수정:
- `scripts/check_all_devices.sh`
- `scripts/start_mapping_panel.sh`
- `scripts/start_offline_demo.sh`

위 세 스크립트에 `float_param_value()`를 넣어서 정수 문자열도 `10.0`, `5.0`처럼 넘기도록 수정

결과:
- 같은 값으로 다시 실행했을 때 preflight camera test가 PASS로 바뀜

### 4. 카메라 / LiDAR / Pico 동시 preflight PASS 확인

확인된 성공 케이스:
- `320x240`
- `10 fps`
- `5 Hz publish`
- 카메라 시작 지연 8초
- LiDAR settle 지연 8초

성공 시점 로그 기준:
- `/buddybot/pico_status` PASS
- `/scan` PASS
- `/camera/image_raw` PASS
- `lidar stability after camera start` PASS

즉:
- "세 개를 절대 동시에 못 돌린다"는 결론은 아님
- 적어도 bring-up / preflight 단계에서는 동시에 붙는 조합이 확인됨

### 5. 그런데 장시간 실기에서는 여전히 하드웨어성 실패가 남음

디버그 번들과 커널 로그에서 반복 확인된 것:
- `Undervoltage detected!`
- `USB disconnect`
- `can't set config #1, error -71`
- Pico 재연결 흔적
- `Serial receive error: device reports readiness to read but returned no data`

의미:
- ROS 노드가 아무리 살아 있어도 USB 레벨에서 장치가 잠깐 사라지면 완전한 소프트웨어 복구는 불가능
- 특히 Pico와 C920은 초기에 살아 있어도 나중에 다시 죽을 수 있음

현장 판단:
- 이 문제는 ROS QoS나 panel API 단독 문제로 보면 안 됨
- 저전압/순간 전압 강하/USB 재열거가 실제 원인 후보

### 6. 디버그 번들 수집 자동화

추가된 스크립트:
- `scripts/run_demo_debug_bundle.sh`

수집 항목:
- `/cmd_vel_manual`
- `/cmd_vel_final`
- `/buddybot/pico_status`
- `/scan`
- `/camera/image_raw`
- detector/navigation/command/safety status
- repo head / repo status / lsusb / v4l2 / vcgencmd / journalctl
- 각 노드 tail log

수정 포인트:
- 초기에 `exec` 때문에 cleanup이 건너뛰어졌는데 이를 제거해서 종료 후 번들이 항상 남도록 수정

현장 사용법:

```bash
cd ~/BuddyBot
bash scripts/run_demo_debug_bundle.sh mapping
```

최신 번들 확인:

```bash
BUNDLE_DIR="$(ls -dt /tmp/buddybot-debug-* | grep -v '\.tar\.gz$' | head -n 1)"
echo "$BUNDLE_DIR"
tail -n 120 "$BUNDLE_DIR/command_mux.tail.log"
tail -n 120 "$BUNDLE_DIR/pico_bridge.tail.log"
tail -n 120 "$BUNDLE_DIR/camera.tail.log"
grep -n "Undervoltage\\|USB disconnect\\|error -71" "$BUNDLE_DIR/system_snapshot.log" | tail -n 40
```

### 7. 발표 직전 대응: presentation mode 추가

추가된 스크립트:
- `scripts/start_presentation_mode.sh`

목적:
- 하드웨어를 당장 바꾸지 못하는 상황에서 시연 성공 확률을 높이기 위한 저부하 기본값 제공

기본 동작:
- preflight 재기동 비활성화
- microphone listener 비활성화
- Pi speaker 출력 비활성화
- 카메라 해상도/FPS/publish rate 낮춤
- MJPG + buffer size 1 유지
- `run_demo_debug_bundle.sh`를 통해 종료 후 자동 로그 수집

이번 라운드 추가 보강:
- detector 런타임 파라미터도 프레젠테이션 모드에서 낮게 넘기도록 정리
  - `BUDDYBOT_DETECT_INTERVAL`
  - `BUDDYBOT_DETECT_CONFIDENCE`
  - `BUDDYBOT_DETECT_HOG_RESIZE_WIDTH`
  - `BUDDYBOT_DETECT_ALLOW_HOG_FALLBACK`

권장 실행:

```bash
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

더 보수적인 값:

```bash
cd ~/BuddyBot
BUDDYBOT_CAMERA_WIDTH=320 \
BUDDYBOT_CAMERA_HEIGHT=240 \
BUDDYBOT_CAMERA_FPS=10 \
BUDDYBOT_CAMERA_PUBLISH_RATE=5 \
BUDDYBOT_CAMERA_PIXEL_FORMAT=MJPG \
BUDDYBOT_CAMERA_BUFFER_SIZE=1 \
BUDDYBOT_DETECT_INTERVAL=8 \
BUDDYBOT_DETECT_HOG_RESIZE_WIDTH=320 \
bash scripts/start_presentation_mode.sh mapping
```

### 8. 패널 UI/상태 표시 보강

정리된 내용:
- Pico 상태 카드가 단순 connected/not-connected 수준이 아니라 더 유의미한 상태 문자열과 encoder 값까지 보여주도록 보강
- minimap start/stop/refresh 버튼 겹침 완화
- camera toolbar 배치 조정

의미:
- 발표 중 "지금 연결됐는지", "바퀴가 실제로 응답하는지"를 패널만 보고 판단하기 쉬워짐

### 9. 미해결 / 다음 라운드 우선순위

미해결:
- 장시간 런에서 C920가 다시 사라지는 경우가 있음
- Pico USB가 짧게 끊기면 실시간 복구는 어려움
- `command_mux`/`camera_node` 종료 시점 ROS context 예외가 로그에 남음

다음 우선순위:
1. 발표 전에는 `start_presentation_mode.sh` 경로를 기준으로만 재검증
2. 새 로그를 받을 때는 반드시 번들 디렉토리 기준으로 해석
3. 커널 로그에 undervoltage / USB disconnect가 보이면 소프트웨어 원인보다 먼저 취급

## 2026-04-18

환경:
- 장비: Raspberry Pi 5 (`pi@pi-desktop`)
- 메인 레포: `BuddyBot`
- 기준 메인 커밋: `3e934b4`에서 후속 시연 안정화 작업 진행
- 운영 제약:
  - UPS 5V 5A, Ubuntu 24.04
  - USB current budget 1.6A 해제 상태 전제
  - C920는 USB 3.0 전담
  - LiDAR/Pico/기타는 USB 2.0 경로

현장 판단:
- 시연이 임박해 `풀스택은 유지하되 기본 프로파일을 전력/대역폭 제약에 맞게 보수적으로 고정`하는 방향으로 전환
- 지금 문제는 ROS 자체보다
  - USB/power jitter
  - camera topic 확인 QoS 혼선
  - detector/follow bbox QoS mismatch
  쪽이 더 직접적이었음

이번 라운드 코드 수정:
- `scripts/start_presentation_mode.sh`
  - 기본값을 시연용 풀기능 프로파일로 변경
  - microphone listener 기본 `1`
  - Pi speaker 기본 `1`
  - speaker volume target 기본 `35%`
  - camera 기본 `320x240 @ 15fps publish 15Hz`
  - detector interval 기본 `5`
- `scripts/start_mapping_panel.sh`
  - same profile defaults 적용
  - `BUDDYBOT_SPEAKER_VOLUME_PERCENT` 추가
  - voice node 실행 전 `wpctl` / `pactl` / `amixer` 중 가능한 경로로 볼륨 35% clamp
  - `/scan`, `/camera/image_raw` 확인을 `BEST_EFFORT -> RELIABLE` 순서로 보도록 수정
- `scripts/start_offline_demo.sh`
  - mapping 쪽과 동일한 demo-safe defaults / speaker volume clamp / BEST_EFFORT topic checks 적용
- `scripts/check_all_devices.sh`
  - preflight 기본 카메라 프로파일을 `320x240 @ 15/15`로 상향
  - `/camera/image_raw` 확인도 `BEST_EFFORT` 우선으로 변경
- `scripts/run_demo_debug_bundle.sh`
  - `/scan`, `/camera/image_raw` topic capture를 `--qos-reliability best_effort`로 수정
  - 이전처럼 "토픽이 실제론 살아 있는데 bundle에는 안 찍히는" 혼선을 줄이려는 목적
- `software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/camera_node.py`
  - 노드 기본값을 `320x240`, `15fps`, `publish_rate 15Hz`로 변경
- `software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/detector_node.py`
  - `hog_resize_width` 기본값을 `320`으로 낮춤
- `software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/follow_controller_node.py`
  - image size 기본값을 `320x240`으로 조정
  - `/vision/person_bbox` subscription QoS를 `BEST_EFFORT`로 변경
  - `/cmd_vel_follow`, `/follow/enabled`는 기존 `RELIABLE` 유지

무엇이 개선되나:
- presentation / mapping / offline demo가 같은 power-budget-aware 기본값을 공유
- camera가 `BEST_EFFORT`인데 shell check와 bundle capture가 `RELIABLE`이라서 생기던 false negative가 줄어듦
- detector -> follow bbox QoS mismatch가 제거되어 follow controller가 bbox를 실제로 받을 수 있게 됨
- speaker를 켜더라도 순간 전류를 줄이기 위해 기본 볼륨을 35%로 clamp

현장 재확인 포인트:
1. `bash scripts/start_presentation_mode.sh mapping`
2. `sudo dmesg -w | grep -Ei 'under-voltage|usb .*disconnect|usb .*reset|uvcvideo|cdc_acm'`
3. `ros2 topic echo --qos-reliability best_effort /camera/image_raw`
4. `tail -n 80 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/follow_controller.log`
5. panel/manual/follow 모두에서 실제 시연 경로가 끊기지 않는지 확인

여전히 남는 리스크:
- `PSU_MAX_CURRENT=5000` 적용 후에도 Pico `ttyACM0` 재연결이 완전히 사라졌다고 확정할 수는 없음
- C920는 초기화 후에도 장시간 런에서 reset이 다시 나타날 수 있음
- 전진이 제자리 회전으로 보이는 증상은 별도의 Pico wheel polarity / field wiring 검증이 계속 필요

추가 메모:
- 실기에서 "정지 버튼을 눌러도 계속 회전한다"는 증상이 다시 확인됨
- 로그상 `/cmd_vel_final`에는 `wz=0.0` zero command가 실제로 들어오기도 했지만, 물리적으로는 계속 도는 현상이 있었음
- 원인 후보:
  - 엔코더 피드백이 없거나 의미 없는 상태에서 PID 적분/잔류 출력이 남아 0 명령 뒤에도 계속 회전
- 후속 수정:
  - `firmware/pico_motor_controller/config.py`
    - `COMMAND_ZERO_DEADBAND = 0.02` 추가
    - `PID_KP = 0.6`, `PID_KI = 0.0`, `PID_KD = 0.0` 로 변경해 P-only 제어로 단순화
  - `firmware/pico_motor_controller/main.py`
    - target `(vx, vy, wz)`가 deadband 이하이면 즉시 `stop_all()`
    - 같은 조건에서 PID controller 전체 reset
    - estop 경로에서도 PID reset 후 정지
- 의미:
  - 이제는 "0 명령이면 PID 수렴을 기다리지 않고 모터 출력을 바로 차단"하는 쪽으로 바뀜
  - 엔코더 품질이 충분히 검증되기 전까지는 I/D를 빼고 P-only로 시연 우선 안정화
  - 이 변경은 Pico에 `config.py`, `main.py` 재배포가 필요함

추가 현장 수정:
- 증상:
  - panel에서 `forward`를 눌러도 실제로는 반시계 회전으로 보이는 경우가 계속 남음
  - `stop`은 가끔만 먹는 느낌이 있었고, toggle/manual 상태가 브라우저 쪽에서 남는 듯한 인상도 있었음
  - 한동안 `right motor polarity = -1`로 현장 보정을 시도했지만, 이 방식은 pure rotation/strafe/forward를 동시에 일관되게 맞추기 어려웠음
- 원인 해석:
  - 문제를 단일 wheel polarity로 때우기보다, 3-wheel kiwi base의 휠 방향 혼합 자체를 잘못 가정한 쪽이 더 유력했음
  - 초기에는 같은 GP2/8/12 순서를 쓰는 `AMR` 레퍼런스를 참고했지만, 이후 현장 검증 결과 BuddyBot 실물의 정면축/좌우 해석과 그대로 일치한다고 볼 수는 없었음
- 후속 수정:
  - `firmware/pico_motor_controller/config.py`
    - `MOTOR_DIRECTION_SIGNS`를 다시 `left/right/back = 1/1/1`로 정렬
    - 당시에는 임시로 `WHEEL_ANGLES_DEG = {left: 330, right: 90, back: 210}`을 추가해 AMR식 기준으로 정렬을 시도
  - `firmware/pico_motor_controller/kinematics.py`
    - ad-hoc `left=vx-vy-rot`, `right=vx+vy+rot`, `back=vy-rot` 믹서를 제거
    - 당시에는 AMR kiwi-drive 공식을 BuddyBot ROS 좌표계(`x=forward`, `y=left`)로 변환해 사용
    - pure forward / pure rotate / strafe-left 케이스가 일관되게 나오도록 재구성
  - `firmware/pico_motor_controller/test_kinematics.py`
    - 새 kiwi 믹싱에 맞춰 테스트 expectation을 갱신
    - 로컬 실행 시 `pure_forward`, `pure_rotate`, `strafe_left`, `zero_command` 모두 PASS 확인
  - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`
    - `stop` 전송을 한 번 더 120ms 뒤에 재발사하도록 보강
    - 목적은 browser/toggle 타이밍이 꼬여도 zero command가 한 번 더 들어가도록 하려는 것
- 의미:
  - "직진인데 계속 CCW 회전"을 wheel polarity 땜질이 아니라 kiwi kinematics 정렬로 바로잡는 방향
  - `stop`은 Pico zero-deadband 강제정지 + panel 재전송 두 겹으로 안정화
  - 이 변경은 Pico에 `config.py`, `kinematics.py`, `main.py` 재배포가 필요함

## 2026-04-19

환경:
- 장비: Raspberry Pi 5 (`pi@pi-desktop`), Ubuntu 24.04, ROS 2 Jazzy
- 기준 커밋: `66b4a0f`
- 운영 제약:
  - ROS 실행 중 `mpremote` 금지
  - destructive git 금지
  - 시연 우선

현장 재확인:
- `stop`은 이전 라운드보다 훨씬 안정적으로 즉시 반응함
- `command_mux.log` / `pico_bridge.log` 기준으로 manual `vx/wz` 명령은 Pico까지 정상 전달됨
- 다만 `forward`, `backward`, `rotate_left`, `rotate_right` 모두 물리적으로는 반시계 회전 쪽으로 무너지는 현상이 남았음
- 별도 `mpremote` 단품 테스트에서:
  - `back` 명령은 뒤 바퀴가 정상 반응
  - `left` 명령은 실제 오른쪽 바퀴가 반응
  - `right` 명령은 기대한 왼쪽 바퀴가 아닌 비정상 반응으로 보였음
- 추가 현장 관찰로 원인은 "받침대/차체 기준이 바뀌면서 현재 로봇의 물리 left/right가 기존 alias와 뒤집힌 상태"로 정리

후속 수정:
- `firmware/pico_motor_controller/pins.py`
  - `motor_pins['left']` / `motor_pins['right']` alias를 서로 교체
  - `encoder_pins['left']` / `encoder_pins['right']` alias도 동일하게 교체

의미:
- GP2/8/12 저수준 핀맵은 유지하면서, 상위 kiwi kinematics가 바라보는 좌/우 의미만 현장 하드웨어 기준에 맞춤
- 이번 수정은 `left/right` semantic mapping 보정이므로, Pi에서 `git pull` 후 Pico에 `pins.py` 포함 재배포가 필요함

Pi 재검증 순서:
1. `git pull origin main`
2. ROS를 올리기 전에 Pico에 `pins.py`, `config.py`, `kinematics.py`, `main.py` 재배포
3. `bash scripts/start_presentation_mode.sh mapping`
4. panel에서 `forward`, `backward`, `rotate_left`, `rotate_right`, `stop`을 짧게 재확인

추가 수정:
- 단품 테스트 기준으로 각 바퀴의 `+/-` 방향 반전은 정상적으로 확인됨
- 따라서 남은 핵심 문제는 모터 방향 부호보다는 `BuddyBot 정면축 정의와 맞지 않던 기존 kiwi 각도/좌표계 해석`으로 판단
- `firmware/pico_motor_controller/config.py`
  - `WHEEL_ANGLES_DEG`를 BuddyBot 실제 정면축 기준으로 재정의
    - `right = 30`
    - `left = 150`
    - `back = 270`
- `firmware/pico_motor_controller/kinematics.py`
  - AMR 좌표계 변환 경유 대신 ROS body frame (`x=forward`, `y=left`)에서 직접 휠 속도 계산으로 변경
- `firmware/pico_motor_controller/test_kinematics.py`
  - 새 정면축 기준 expectation 갱신

추가 시도:
- 상위 `cmd_vel`과 kiwi 각도 정의는 정상으로 보였지만, 실주행에서는 여전히 모든 명령이 CCW 쪽으로 무너지는 현상이 남음
- 팀 검토 결과 역기구학 뼈대보다는 실물 모터 극성과 수학적 부호 가정이 어긋났을 가능성을 우선 확인하기로 함
- `firmware/pico_motor_controller/config.py`
  - 1차 현장 실험용으로 `MOTOR_DIRECTION_SIGNS['left'] = -1` 적용
- 목적:
  - 현재 `forward` 기대식에서 `left < 0`, `right > 0`가 실제 바퀴 구동 방향과 일치하도록 맞추는지 확인

추가 방향 전환:
- 사용자가 ROS 이전에 실제로 잘 썼던 Pico 단일 파일 버전의 직접 혼합식을 다시 대조함
- 해당 레거시 식은 아래와 같았음:
  - `v0 = vx + 0.5 * vy + w`
  - `v1 = -vx + 0.5 * vy + w`
  - `v2 = -vy + w`
- 이 식은 현재 BuddyBot 의미상 바퀴 이름에 대응시키면:
  - `right = vx + 0.5 * vy + w`
  - `left = -vx + 0.5 * vy + w`
  - `back = -vy + w`
- 따라서 최신 각도 기반 일반식 대신, 현장에서 이미 주행 검증된 레거시 직접식을 `kinematics.py`에 복원하기로 함

추가 확인 및 수정:
- ROS 이전 단일 파일 버전과 현재 모듈화 버전을 대조한 결과, 저수준 모터 방향 출력 규약도 서로 달랐음
- 예전 단일 파일:
  - `+speed -> in1=0, in2=1`
  - `-speed -> in1=1, in2=0`
- 모듈화 이후 `motor_driver.py`는 이 방향이 반대로 들어가 있었음
- 후속 수정:
  - `firmware/pico_motor_controller/motor_driver.py`
    - 방향 출력을 예전 단일 파일과 같은 규약으로 복원
  - `firmware/pico_motor_controller/config.py`
    - 실험용으로 넣어둔 `MOTOR_DIRECTION_SIGNS['left'] = -1`를 제거하고 다시 `1/1/1`로 정렬
  - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`
    - 수동 주행 기본 속도 슬라이더를 `100% -> 60%`로 낮춤
    - forward/backward/strafe/rotate 기본 속도도 한 단계 낮춤

후속 현장 관찰:
- 기본 속도에서는 정지마찰 때문에 잘 안 움직였고, speed slider를 `110%`까지 올리면 다시 움직이기 시작함
- 다만 `forward`와 `backward`가 둘 다 같은 시계방향 회전으로 무너지는 현상이 남음
- 해석:
  - 직식 복원 이후에도 좌/우 앞바퀴 중 하나의 물리 극성이 여전히 현재 수학 가정과 어긋나 있는 상태일 가능성이 높음
- 추가 실험:
  - `firmware/pico_motor_controller/config.py`
    - `MOTOR_DIRECTION_SIGNS['left'] = -1`를 다시 적용해서, 직식 기준 `forward/backward`가 서로 반대 방향으로 분리되는지 확인

추가 정리:
- 팀 검토에서 ROS 이전 단일 Pico 코드의 핵심은 아래 두 가지로 정리됨
  - 1월 정상 맵핑 그대로 유지:
    - `m0 = left`
    - `m1 = right`
    - `m2 = back`
  - 직접 혼합식:
    - `left = vx + 0.5 * vy + w`
    - `right = -vx + 0.5 * vy + w`
    - `back = -vy + w`
- 이에 맞춰 모듈화 코드도 다시 정렬:
  - `pins.py`
    - left/right alias를 원래 January 채널 순서로 복원
  - `kinematics.py`
    - 직접 혼합식 유지
    - 바퀴별 부호 보정을 위한 `WHEEL_COMMAND_SIGNS` 훅 추가
  - `main.py`
    - 순수 PID 출력만 모터에 넣던 구조에서, 예전처럼 `base drive + RPM correction` 구조로 변경
  - `config.py`
    - `ENCODER_CPR=11`, `GEAR_RATIO=270`, `OUTPUT_CPR` 등 예전 단일 파일 기준 상수 복원
    - `PID_KP`도 예전 `P_GAIN=0.3`에 맞춤

추가 핵심 확인:
- 사용자가 체감한 최신 증상:
  - 전진/후진은 이제 "대체로 원하는 방향"으로는 가기 시작했지만,
  - 둘 다 조금씩 같은 방향으로 휘며 원호를 그림
- 코드 재대조 결과:
  - `encoder.py`의 현재 IRQ 부호가 예전 단일 파일과 반대로 구현돼 있었음
  - 예전 단일 파일:
    - `enc_b == 0 -> +count`
    - `enc_b == 1 -> -count`
  - 모듈화 버전:
    - 위 부호가 뒤집혀 있었음
- 후속 수정:
  - `firmware/pico_motor_controller/encoder.py`
    - 카운트 부호를 예전 단일 파일과 동일하게 복원
- 해석:
  - 지금 구조는 `base drive + RPM correction`이므로, 엔코더 부호가 반대로 잡히면 보정항이 계속 같은 방향으로 드리프트를 만들 수 있음
  - 특히 전진/후진 모두 같은 쪽으로 살짝 휘는 현상과 잘 맞는 후보임

추가 현장 결론:
- 현재 기준선에서는 전진/후진의 큰 방향성은 드디어 맞아 들어오기 시작했음
- 다만 최신 실기 체감은:
  - `forward`에서 조금씩 왼쪽으로 돎
  - `backward`에서도 조금씩 왼쪽으로 돎
- 같은 흐름을 커밋 관점으로 보면:
  - `78a7db3` 기준에서는 전진/후진의 큰 방향은 맞았지만 공통으로 오른쪽 편향이 남아 있었음
  - 그 다음 단계들까지 합친 현재 기준에서는 그 오른쪽 편향이 줄고, 대신 공통의 약한 왼쪽 편향으로 바뀜
- 중요 판단:
  - 이 상태는 "전체 방향 정의가 틀렸다"기보다, 공통 steering bias가 남아 있는 상태로 보는 것이 맞음
  - 따라서 다음 수정은 wheel geometry나 left/right/back 기준을 다시 뒤집는 쪽이 아니라, 현재 기준을 유지한 채 좌우 편향만 미세 조정해야 함

다음 작업 원칙:
1. 현재 Pico 기준선은 유지
   - `left = m0`
   - `right = m1`
   - `back = m2`
   - `left = vx + 0.5 * vy + w`
   - `right = -vx + 0.5 * vy + w`
   - `back = -vy + w`
   - `+speed -> in1=0, in2=1`
   - `-speed -> in1=1, in2=0`
2. 새 작업환경 / 새 Codex 세션에서도 위 기준을 먼저 읽고 시작
3. 이후에는 "전체 방향을 다시 바꾸는 실험"보다 "왼쪽으로 도는 편향을 얼마나 줄일지"에 집중

## 2026-04-27

현장 결과:
- 사용자가 최신 기준선을 두고 "너무 잘 움직여"라고 평가함
- 이번 라운드에서 수동 주행 체감, 전후진 응답, 회전 속도, 회피, Pico 전원 피크 안정화 방향이 실기에서 좋은 결과를 냈다고 판단
- 이 상태를 현재 BuddyBot 발표/현장 시연용 최고 기준선으로 취급

현재 기준선에서 기억할 점:
- 전진/후진은 이전보다 훨씬 자연스럽게 출발하고, 회전도 과속감이 줄어듦
- LiDAR 회피는 뒤 장애물에 끌려 제자리 회전하던 이전 상태보다 전방 기준 회피에 가까워짐
- Pico 출력 상승폭 제한 덕분에 급격한 명령 전환 때 USB/Pico 끊김 위험을 줄이는 방향으로 개선됨
- 앞으로는 이 기준선을 함부로 다시 흔들지 말고, 작은 미세조정만 하는 것이 맞음

문서화 원칙:
- 사용자가 특히 만족한 현장 기준선은 반드시 `docs/field_log.md`와 `AI_HANDOFF.md` 둘 다에 남긴다
- "잘 된다"는 사용자 피드백도 중요한 운영 신호이므로 기술 변경만 적지 말고 결과 평가까지 함께 기록한다

UI 후속 정리:
- 사용자가 마지막으로 요청한 UI 정리는 수동 화살표 제어를 `전방 카메라` 바로 아래, `빠른 명령` 바로 위에 두는 것
- 이 배치가 현장에서는 카메라를 보면서 바로 수동 조작하기 가장 편한 순서로 판단됨
- 관련 파일:
  - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`

운영 메모:
- Pi에서는 항상 `git pull origin main` 기준으로 업데이트하고, Pico는 필요한 펌웨어 파일만 재배포한 뒤 테스트한다
- 다음 세션이 시작되면 "현재 기준선은 이미 잘 움직인다"는 점을 기본 전제로 보고, 불필요한 전면 재설계를 다시 열지 않는다

추가 후속 조정:
- 우회전 체감이 좌회전보다 느리다는 현장 피드백에 맞춰 수동 우회전과 로컬 체크포인트 회전 모두 소폭 보정값을 추가했다
- `미니맵 생성` 버튼은 더 이상 로봇을 자동 배회시키는 용도로 쓰지 않고, 라이브 LiDAR 누적 시작으로 해석한다
- 이제 기준 운용 흐름은 `미니맵 시작 -> 수동 주행 또는 체크포인트 이동 -> 같은 화면에서 지도 누적 확인`이다
- 체크포인트 이동 불능을 막기 위해 waypoint manager는 요청 시점마다 waypoint YAML을 다시 읽고 `BUDDYBOT_WAYPOINT_FILE` 경로를 우선 사용한다

UI/운용 정리 추가:
- 체크포인트 이동은 미니맵 시작의 선행조건이 아니라는 점을 패널 문구와 API 응답에 명시했다
- 체크포인트/미니맵 영역은 `이동`, `저장`, `경로` 세 묶음으로 다시 정리했고, 체크포인트 목록은 선택 중심 리스트로 단순화했다
- 각 체크포인트 카드에서는 과한 `이동/삭제` 버튼을 빼고 `경로에 추가`만 남겨 현장 조작 실수를 줄이는 방향으로 정리했다
- 수동 좌우 회전은 기존보다 더 빠르게 반응하도록 패널 속도 프로파일 기본값을 올렸다
2026-04-28 추가 후속 조정:
- 현장 피드백:
  - 수동조작에서는 회피기동이 꼭 필요하지 않고, 자율주행일 때만 필요하다는 의견이 나왔다
  - 체크포인트 이동 버튼을 눌러도 아무 반응이 없는 것처럼 보이는 경우가 있었다
- 반영 내용:
  - 수동 주행 카드에 `수동 회피 ON/OFF` 토글을 추가했다
  - 기본값은 `OFF`로 두고, 이때 수동 주행은 LiDAR 회피를 우회한다
  - 자율주행/추종은 계속 LiDAR 회피를 사용한다
  - panel -> waypoint_manager 명령 토픽 QoS를 다시 맞춰 체크포인트/경로 요청이 조용히 유실될 가능성을 줄였다
  - 패널은 체크포인트/경로 요청 뒤 `waypoint_manager`의 상태 응답을 잠깐 기다리고, 응답이 없으면 조용히 성공 처리하지 않고 오류를 띄운다
- 운영 메모:
  - 수동 주행 감각을 우선할 때는 `수동 회피 OFF`
  - 아주 좁은 실내에서 천천히 점검할 때만 `수동 회피 ON`
  - 체크포인트 이동이 다시 멎으면 패널 에러 메시지와 `/nav/navigation_status`를 먼저 본다

## 2026-04-29

Handoff documentation pass:
- Added `docs/CURRENT_FIELD_HANDOFF.md` as the first-read document for another laptop, another Codex session, or the Pi5 field machine.
- Captured the current stable baseline:
  - manual driving feels good and should be treated as the locked hardware baseline
  - manual LiDAR avoidance is now toggleable from the UI
  - autonomous navigation and follow mode still keep LiDAR avoidance active
  - checkpoint movement does not require minimap start
- Captured the current blocker:
  - checkpoint movement requires pose from `/odom` or `/amcl_pose`
  - panel and waypoint manager both subscribe to these topics
  - no repo node currently appears to publish `/odom`
- Next recommended implementation:
  - add encoder odometry in `buddybot_base`
  - subscribe to `/buddybot/pico_status`
  - publish `nav_msgs/Odometry` on `/odom`
  - then retry local checkpoint navigation
- Pi operator note:
  - use `python3 -m json.tool`, not `python -m json.tool`, on the Pi desktop image

## 2026-05-04

Development resumed with `BuddyBot` as the main repo and `BuddyBot-ai` / `AMR` as references.

Implemented the next handoff task: encoder odometry from Pico feedback.

Changes:
- Pico `STAT` telemetry now includes cumulative left/right/back encoder counts.
- Pi `pico_bridge_node` parses encoder counts into `buddybot_msgs/Status`.
- Added `buddybot_base.encoder_odom_node`.
- `encoder_odom_node` subscribes to `/buddybot/pico_status`, integrates encoder deltas, publishes `/odom`, and broadcasts `odom -> base_link`.
- `scripts/start_mapping_panel.sh` starts `encoder_odom_node` after `pico_bridge`.
- `buddybot_base` now declares `nav_msgs` and `tf2_ros` dependencies and exposes `encoder_odom_node` as a console script.

Verification:
- Local Python syntax check passed for the changed Pi-side Python files.
- Full ROS build was not run in this Windows workspace.

Pi field-test steps:
1. Pull this change on the Pi.
2. Recopy Pico firmware files, including `main.py` and `uart_protocol.py`.
3. Rebuild `buddybot_base` or the full selected package set.
4. Run `bash scripts/start_presentation_mode.sh mapping`.
5. Check:

```bash
ros2 topic echo --once /buddybot/pico_status
ros2 topic echo --once /odom
tail -n 120 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/encoder_odom.log
```

Expected result:
- `/buddybot/pico_status` shows encoder counts changing while the robot moves.
- `/odom` publishes even without AMCL.
- Checkpoint navigation should no longer stop only because pose is unavailable.

Follow-up local navigation safety fix:
- Field test reached `pose_available` and `pico_connected`, but selecting `livingroom` caused a strong in-place spin.
- Root cause: local checkpoint navigation was treating saved waypoint `theta` as mandatory and rotating in place to match final heading.
- Changed local checkpoint navigation so `local_align_final_yaw` defaults to `False`.
- With the default, local checkpoint movement treats checkpoints as places, not final orientation poses:
  - when inside distance tolerance, it finishes immediately
  - while moving, it does not inject angular velocity just to match saved `theta`
- If final heading alignment is needed later, launch `waypoint_manager_node` with `local_align_final_yaw:=true`.

Follow-up conservative local checkpoint tuning:
- Field test showed close checkpoints were immediately considered arrived and farther checkpoints moved without spinning but traced triangular/unstable paths.
- Interpretation: encoder odom is now alive, but not yet calibrated enough for aggressive holonomic x/y local navigation.
- Changed local checkpoint defaults for stability:
  - `goal_tolerance` from `0.5` to `0.18`
  - `max_nav_linear_velocity` from `0.3` to `0.16`
  - `max_nav_angular_velocity` from `0.6` to `0.18`
  - `local_position_gain` from `0.75` to `0.45`
  - `local_heading_gain` from `1.2` to `0.45`
  - added `local_strafe_enabled`, default `False`
  - added gentle lateral heading correction instead of direct strafe by default
- Goal: make checkpoint movement behave like cautious short-distance dead reckoning until encoder signs/scale and odom frame are field-calibrated.

Follow-up user tracking usability/detection fix:
- Field test showed follow mode did not move because `person_not_detected` stayed active.
- Detector was alive, but MobileNet model files were missing, so it used HOG fallback only.
- HOG is weak at close-range 320x240 upper-body views, so added OpenCV face/upper-body cascade fallback after HOG.
- Presentation mode now defaults to a slightly faster detector interval and lower HOG threshold:
  - `BUDDYBOT_DETECT_INTERVAL=3`
  - `BUDDYBOT_DETECT_HOG_CONFIDENCE=0.08`
  - `BUDDYBOT_DETECT_ALLOW_CASCADE_FALLBACK=1`
- Moved follow start/stop controls into the camera toolbar next to camera close/refresh so the operator can watch the camera and arm follow in the same place.
- Corrected default `person_class_id` for SSD MobileNet v2 COCO from VOC-style `15` to COCO `1`.

## 2026-05-04 DNN 추종 불가 원인 분석 및 검출 박스 패널 표시

환경:
- 기준 커밋: d0a0f2c → 9422dea
- 패키지: `buddybot_vision`, `buddybot_panel`
- 모델: MobileNet-SSD v2 COCO (`frozen_inference_graph.pb` + `ssd_mobilenet_v2_coco_2018_03_29.pbtxt`)

증상:
- `추종 시작` 눌러도 로봇이 전혀 움직이지 않음
- 패널 상태판에 "person not detected" 고정 표시
- 패널 검출기 항목은 "DNN 준비" 정상 표시 (`dnn model loaded`)
- 카메라 앞에 사람이 서있는 것을 실물로 확인

확인된 원인 1 — confidence_threshold 0.5가 너무 높음:
- 실내 카메라(640×480, 30fps) 환경에서 MobileNet-SSD v2 COCO 검출 신뢰도가 0.3~0.49 구간에서 발생
- 기본값 0.5 미만은 전부 필터링되어 `/vision/person_bbox` 토픽에 메시지가 한 건도 발행되지 않음
- `follow_controller_node`는 bbox를 받지 못하니 velocity 명령을 내지 않음 → 로봇 무반응

확인된 원인 2 — QoS 불일치로 패널이 bbox를 절대 받지 못함:
- `detector_node`는 `/vision/person_bbox`를 `BEST_EFFORT, VOLATILE, depth=1` QoS로 발행
- `panel_server.py`는 `depth=10` 정수 인자로 구독 → rclpy 기본값인 `RELIABLE` QoS 적용
- ROS 2 규칙: BEST_EFFORT publisher + RELIABLE subscriber = **QoS 비호환, 메시지 전달 안 됨**
- 결과: 검출이 실제로 일어나도 패널은 항상 "person not detected" 표시

적용한 수정:
- `vision.launch.py`: `confidence_threshold` 0.5 → 0.2
- `vision.launch.py`: `publish_debug_image` False → True
- `panel_server.py`: `/vision/person_bbox` 구독 QoS를 `BEST_EFFORT, VOLATILE, depth=1`로 변경
- `panel_server.py`: `/vision/debug_image` 구독 추가 (동일 BEST_EFFORT QoS)
- `panel_server.py`: `_debug_image_callback` 추가 — 검출 박스가 그려진 프레임을 JPEG로 저장
- `panel_server.py`: `get_camera_frame()` 수정 — debug_image가 2초 이내 신선하면 우선 반환하여 패널 카메라 화면에 bbox 자동 표시
- `index.html`: `camera-toolbar`를 4열 → 2열 그리드로 변경 (좁은 화면에서도 세로 붕괴 없음)
- `index.html`: 버튼 배열을 [카메라닫기 | 추종시작] / [새로고침 | 추종끄기] 2×2 구조로 정리

현장 검증 방법:
```bash
cd ~/BuddyBot && git pull origin main
cd software/pi5/ros2_ws && source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select buddybot_vision buddybot_panel
source install/setup.bash
cd ~/BuddyBot && bash scripts/start_presentation_mode.sh mapping
```
- 패널 카메라 화면에 초록 박스가 뜨면 DNN 검출 성공
- 박스가 떠도 로봇이 안 움직이면 `follow_controller_node` 로그 확인
- confidence 0.2에서도 박스가 전혀 안 뜨면 모델 파일 경로 문제 → 아래 확인

```bash
ros2 run buddybot_vision detector_node --ros-args --log-level info 2>&1 | grep -E "model_|Model"
```

미해결 / 후속 확인 필요:
- Pi5에서 실제 검출 박스 표시 여부 현장 검증 대기 중
- confidence 0.2에서도 미검출 시 HOG 단독 또는 다른 모델 검토 필요

## 2026-05-06 Follow/Manual Turn Rate Tuning

Field feedback:
- Follow mode appears to track, but left/right correction rotates faster than the camera feedback cadence.
- Manual left/right rotation also feels too fast compared with forward/backward speed.

Changes:
- Follow angular control softened:
  - `BUDDYBOT_FOLLOW_CENTER_GAIN` default `0.008` -> `0.004`
  - `BUDDYBOT_FOLLOW_MAX_ANGULAR` default `0.80` -> `0.35`
- Manual rotate speed profile softened:
  - `rotate_left/right` profile from `offset=0.12, gain=0.14` to `offset=0.06, gain=0.07`

Expected result:
- Follow should turn more slowly and allow camera frames to catch up.
- Manual rotation should feel closer to forward/backward sensitivity instead of snapping around.

Follow-up adjustment:
- The first reduction was too slow in the field.
- Set turn rates to about 80% of the original aggressive baseline instead:
  - follow `center_x_gain`: `0.008` -> `0.0064`
  - follow `max_angular_velocity`: `0.80` -> `0.64`
  - manual rotate profile: `offset=0.12,gain=0.14` -> `offset=0.096,gain=0.112`

Follow-up linear speed adjustment:
- Field feedback: follow starts moving now, but the robot advances faster than the camera/detector loop can track.
- Kept turn-rate tuning from the 80% baseline adjustment.
- Reduced follow forward/backward aggression:
  - `BUDDYBOT_FOLLOW_HEIGHT_GAIN`: `0.012` -> `0.007`
  - `BUDDYBOT_FOLLOW_MAX_LINEAR`: `0.75` -> `0.45`
  - `BUDDYBOT_FOLLOW_MIN_LINEAR`: `0.40` -> `0.28`
- Goal: keep enough duty to overcome stiction while giving the camera/detector loop time to reacquire the person between corrections.

Follow smoothing and strafe recovery:
- Field feedback: follow motion pulses forward/stop/forward and can then lurch when detection catches up.
- Likely cause: follow commands were only published on bbox updates, while command_mux drops a source stale after 0.5s.
- Changed follow controller to keep a 10Hz smoothed command stream:
  - bbox updates now set a target command
  - command timer ramps current command toward target
  - default accel limits: linear `0.45/s`, angular `0.80/s`
  - `BUDDYBOT_FOLLOW_MIN_LINEAR`: `0.28` -> `0.18` because ramping now handles the start instead of a hard duty jump
- Restored manual strafe feel:
  - panel strafe profile: `offset=0.16,gain=0.10` -> `offset=0.26,gain=0.14`
  - backend `BUDDYBOT_MANUAL_STRAFE_LIMIT`: `0.34` -> `0.46`

Documentation rollup after follow/manual tuning:
- Updated `AI_HANDOFF.md` and `docs/CURRENT_FIELD_HANDOFF.md` to make `ef60ade` the current resume baseline.
- Updated `docs/CODEX_RESUME_WORKFLOW.md` so a new laptop/session starts from the current follow-first priority instead of the older missing-odom blocker.
- Current practical priority remains user-following mode:
  - checkpoint/local navigation has `/odom`, but encoder odom is not field-calibrated enough for reliable route driving
  - follow mode is the best next demo path because detection, command mux, Pico bridge, and safety behavior can be tested directly from the camera panel
- Current follow defaults to remember:
  - `BUDDYBOT_FOLLOW_CENTER_GAIN=0.0064`
  - `BUDDYBOT_FOLLOW_MAX_ANGULAR=0.64`
  - `BUDDYBOT_FOLLOW_HEIGHT_GAIN=0.007`
  - `BUDDYBOT_FOLLOW_MAX_LINEAR=0.45`
  - `BUDDYBOT_FOLLOW_MIN_LINEAR=0.18`
  - `BUDDYBOT_FOLLOW_COMMAND_RATE=10.0`
  - `BUDDYBOT_FOLLOW_LINEAR_ACCEL=0.45`
  - `BUDDYBOT_FOLLOW_ANGULAR_ACCEL=0.80`
- Current manual defaults to remember:
  - rotate profile: `offset=0.096,gain=0.112`
  - strafe profile: `offset=0.26,gain=0.14`
  - backend strafe limit: `0.46`
- Next Pi5 command for this slice:

```bash
cd ~/BuddyBot && git pull origin main
cd ~/BuddyBot/software/pi5/ros2_ws && source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select buddybot_vision buddybot_panel
source install/setup.bash
cd ~/BuddyBot && bash scripts/start_presentation_mode.sh mapping
```

- Next field checks:
  - panel camera shows green bbox
  - `/vision/person_bbox` publishes with BEST_EFFORT-compatible subscribers
  - `/cmd_vel_follow` stays alive at the smoothed command rate while follow is enabled
  - `/cmd_vel_final` selects follow and does not flip idle between detector frames
  - physical motion starts gradually instead of stop/start/lurch
- Next tuning order:
  - still lurching: lower `BUDDYBOT_FOLLOW_LINEAR_ACCEL`
  - smooth but too slow: raise `BUDDYBOT_FOLLOW_MAX_LINEAR` slightly
  - turn correction wrong: adjust `BUDDYBOT_FOLLOW_CENTER_GAIN` before changing `BUDDYBOT_FOLLOW_MAX_ANGULAR`

## 2026-05-11 User Follow Completion Pass

Context:
- Work resumed after about one week away from the robot.
- Current priority remains completing user-following mode before returning to checkpoint/local navigation.
- The previous baseline already smoothed `/cmd_vel_follow` at 10Hz, but the controller still reacted directly to raw bbox jumps and did not expose enough follow-controller internals in the panel/debug bundle.

Changes:
- Added bbox low-pass filtering inside `follow_controller_node`.
  - New default `BUDDYBOT_FOLLOW_BBOX_SMOOTHING_ALPHA=0.45`.
  - New default `BUDDYBOT_FOLLOW_BBOX_FILTER_RESET_SEC=0.9`.
  - Goal: reduce target velocity wobble from frame-to-frame bbox jitter while resetting quickly after a real detection gap.
- Added `/follow/status` JSON diagnostics from `follow_controller_node`.
  - Includes state, bbox age, raw bbox, filtered bbox, target command, current ramped command, and active tuning params.
- Panel now subscribes to `/follow/status`.
  - `/api/status` includes `follow_status`.
  - `sensor_fusion` includes `follow_controller_state` and `follow_controller_live`.
  - Follow note in the camera/control panel shows controller state and current command.
- Debug bundle now records `/follow/status` into `follow_status.log`.

Expected next Pi5 test:

```bash
cd ~/BuddyBot && git pull origin main
cd ~/BuddyBot/software/pi5/ros2_ws && source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select buddybot_vision buddybot_panel
source install/setup.bash
cd ~/BuddyBot && bash scripts/start_presentation_mode.sh mapping
```

Field verification:
- Open the panel and confirm the camera shows a green bbox.
- Press follow start.
- Watch the follow note for `follow_controller=tracking` and nonzero `cmd=...`.
- If motion still jitters but commands are smooth, suspect detector bbox jitter or motor/Pico response.
- If `/follow/status` is live but `/cmd_vel_final` is idle, inspect command mux status.
- If `/follow/status` is not live, verify `buddybot_vision` was rebuilt and `follow_controller_node` restarted.

Follow profile retuned against the old standalone controller:
- Field feedback after the diagnostics pass: camera reaction feels slow while motor rotation is too fast, causing the robot to snap into an in-place spin.
- Compared against the old `pc_controller` follow profile:
  - camera: `160x120`
  - target box height: `60px` (`0.50` of frame height)
  - center deadzone: `15px`
  - distance deadzone: `10px`
- The ROS profile had drifted too close/aggressive:
  - camera default `320x240`
  - target height ratio `0.80`
  - max angular `0.64`
- Retuned the presentation/default follow profile toward the old low-latency behavior:
  - camera default `320x240@15` -> `160x120@10`
  - `BUDDYBOT_FOLLOW_TARGET_HEIGHT`: `0.80` -> `0.50`
  - `BUDDYBOT_FOLLOW_CENTER_GAIN`: `0.0064` -> `0.0035`
  - `BUDDYBOT_FOLLOW_MAX_ANGULAR`: `0.64` -> `0.28`
  - `BUDDYBOT_FOLLOW_MAX_LINEAR`: `0.45` -> `0.28`
  - `BUDDYBOT_FOLLOW_MIN_LINEAR`: `0.18` -> `0.14`
  - `BUDDYBOT_FOLLOW_LINEAR_ACCEL`: `0.45` -> `0.25`
  - `BUDDYBOT_FOLLOW_ANGULAR_ACCEL`: `0.80` -> `0.35`
  - `BUDDYBOT_FOLLOW_BBOX_SMOOTHING_ALPHA`: `0.45` -> `0.35`
  - added script-level deadzone overrides:
    - `BUDDYBOT_FOLLOW_CENTER_DEADZONE=15`
    - `BUDDYBOT_FOLLOW_HEIGHT_DEADZONE=10`
- Goal: prefer slow, stable, wide-deadzone tracking over fast correction while camera/detector cadence is still limited.

Detection quality follow-up:
- User feedback: object/person recognition is now poor; likely from both lowered image resolution and model preprocessing mismatch.
- Important comparison with the old standalone controller:
  - Old code used `cv2.dnn.blobFromImage(frame, size=(300,300), swapRB=True, crop=False)` with default `scale=1.0` and `mean=0`.
  - ROS detector had been using `scale_factor=0.007843` and `mean_values=[127.5,127.5,127.5]`, which is more like the Caffe MobileNetSSD preprocessing path and can suppress TensorFlow SSD confidences.
- Updated detector defaults for TensorFlow SSD MobileNet v2 COCO:
  - `scale_factor=1.0`
  - `mean_values=[0,0,0]`
  - `confidence_threshold=0.2`
- Added model-path aliases so either naming convention works:
  - `mobilenet_ssd_v2_coco.pb` or `frozen_inference_graph.pb`
  - `mobilenet_ssd_v2_coco.pbtxt` or `ssd_mobilenet_v2_coco_2018_03_29.pbtxt`
  - checks `~/BuddyBot/models` and legacy `~/AI_CAR/OpencvDnn/models`
- Restored presentation camera input to `320x240 @ 10fps` while keeping the slow motor profile.
- Increased detection cadence to every 2 frames.
- Scaled deadzones for the 320x240 input:
  - center deadzone `15` at 160px wide -> `30` at 320px wide
  - height deadzone `10` at 120px high -> `20` at 240px high

## 2026-05-11 Follow lag-safe profile

Context:
- User feedback: person recognition is good, but camera response feels delayed by seconds while the robot turns/accelerates too fast, so follow mode can look like it is avoiding the user.
- The main risk is control using stale visual data, not just detector accuracy.

Changes:
- Camera node now drains queued UVC frames before publishing.
  - New parameter: `discard_buffered_frames`
  - Presentation default: `BUDDYBOT_CAMERA_DISCARD_BUFFERED_FRAMES=2`
- Detector now appends source image age to `/vision/person_bbox`.
- Follow controller rejects stale detections before they can command motion.
  - `BUDDYBOT_FOLLOW_BBOX_TIMEOUT=0.6`
  - `BUDDYBOT_FOLLOW_MAX_SOURCE_AGE=0.8`
- Follow motion is now intentionally lag-safe:
  - `BUDDYBOT_FOLLOW_CENTER_GAIN=0.0012`
  - `BUDDYBOT_FOLLOW_MAX_ANGULAR=0.10`
  - `BUDDYBOT_FOLLOW_HEIGHT_GAIN=0.0035`
  - `BUDDYBOT_FOLLOW_MAX_LINEAR=0.16`
  - `BUDDYBOT_FOLLOW_MIN_LINEAR=0.10`
  - `BUDDYBOT_FOLLOW_LINEAR_ACCEL=0.12`
  - `BUDDYBOT_FOLLOW_ANGULAR_ACCEL=0.12`
  - `BUDDYBOT_FOLLOW_CENTER_DEADZONE=50`
  - `BUDDYBOT_FOLLOW_HEIGHT_DEADZONE=30`
  - `BUDDYBOT_FOLLOW_ALLOW_REVERSE=0`

Expected behavior:
- If the camera/detector loop falls behind, follow should ramp to stop instead of continuing to turn on old bbox data.
- If the person is too close, follow should stop rather than reverse away from the user.
- This profile may feel deliberately slow; raise `BUDDYBOT_FOLLOW_MAX_LINEAR` only after confirming the camera view and robot motion stay in sync.

Follow hotfix after field feedback:
- User reported that the robot only detected the person and did not move.
- The stale-image gate was too strict for Pi5 DNN latency, so source-age rejection is disabled by default while still reporting image age in `/follow/status`.
- `BUDDYBOT_FOLLOW_BBOX_TIMEOUT` was relaxed from `0.6` to `1.6` so slow but valid detector updates can keep a command alive.
- `BUDDYBOT_FOLLOW_TARGET_HEIGHT` was nudged from `0.50` to `0.55` so the robot is less likely to treat a normal starting distance as already close enough.

Second no-motion correction:
- Field feedback still showed detection without motion.
- The likely cause is that the detected person bbox is taller than the old standalone target, so reverse-disabled follow clamps the command to zero as "too close".
- Raised `BUDDYBOT_FOLLOW_TARGET_HEIGHT` to `0.75`, keeping reverse disabled and low max speeds.
- Relaxed `BUDDYBOT_FOLLOW_BBOX_TIMEOUT` to `2.5` so Pi5 DNN latency does not drop the controller to idle between detections.
- Limited OpenCV to two threads by default for camera/detector nodes and kept camera buffer size at 1.
- Reduced `BUDDYBOT_CAMERA_DISCARD_BUFFERED_FRAMES` default to `1`; multiple blocking `grab()` calls inside a ROS timer can reduce publish cadence when the buffer is already empty.

Follow saturated-bbox correction:
- Field feedback: C920/MobileNet keeps the person bbox nearly full-frame, so height-based distance control still decides "too close" and clamps forward motion to zero because reverse is disabled.
- Added visible-person forward creep:
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD=0.08`
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD_CENTER_DEADZONE=120`
- When a person is visible and roughly centered, follow now commands a very slow forward crawl even if bbox height is saturated.
- `/follow/status` now exposes `control_reason`, and the panel follow note shows that reason beside the current command.
- LiDAR avoidance remains the layer that should stop/escape if the user is actually too close in front of the robot.

Camera bbox vs LiDAR distance correction:
- User compared the old standalone Tkinter follower, which worked without LiDAR at `160x120`.
- Key finding: the old controller's bbox-height distance heuristic happened to match its camera/model geometry. In the ROS stack, C920/MobileNet can keep the person bbox nearly full-frame even when the user steps away, so bbox height is no longer a reliable distance signal.
- Follow controller now uses camera bbox mainly for bearing/turning and uses LiDAR `/scan` for forward distance when available.
  - `BUDDYBOT_FOLLOW_USE_LIDAR_DISTANCE=1`
  - `BUDDYBOT_FOLLOW_TARGET_DISTANCE=0.95`
  - `BUDDYBOT_FOLLOW_DISTANCE_DEADZONE=0.18`
  - `BUDDYBOT_FOLLOW_MIN_DISTANCE=0.45`
  - `BUDDYBOT_FOLLOW_LIDAR_GAIN=0.24`
  - `BUDDYBOT_FOLLOW_LIDAR_SECTOR=18`
- Height-based distance and visible-forward creep remain as fallback when no fresh LiDAR distance is available.

Field correction after screenshots:
- Centered/far person did not move, while side-offset person caused some movement. This indicates LiDAR distance gating can falsely block centered forward motion in the corridor.
- Default follow distance is returned to the camera-height path that matched the old standalone follower:
  - `BUDDYBOT_FOLLOW_USE_LIDAR_DISTANCE=0`
  - `BUDDYBOT_FOLLOW_TARGET_HEIGHT=0.60`
  - `BUDDYBOT_FOLLOW_HEIGHT_DEADZONE=20`
- LiDAR remains active through the separate `lidar_avoidance_node` safety override, but it is no longer the default forward-distance controller.

Stiction correction after motor-squeal feedback:
- User reported that motors make a high-pitched drive sound when a person is in frame, but the chassis does not move. When the person leaves the camera view, the sound stops.
- This confirms follow commands reach the Pico, but the commanded linear speed is below the real robot's static-friction threshold.
- Follow forward defaults were raised while keeping rotation slow:
  - `BUDDYBOT_FOLLOW_HEIGHT_GAIN=0.006`
  - `BUDDYBOT_FOLLOW_TARGET_HEIGHT=0.72`
  - `BUDDYBOT_FOLLOW_MAX_LINEAR=0.30`
  - `BUDDYBOT_FOLLOW_MIN_LINEAR=0.22`
  - `BUDDYBOT_FOLLOW_LINEAR_ACCEL=0.30`
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD=0.22`
  - `BUDDYBOT_FOLLOW_HEIGHT_DEADZONE=16`
- Visible-forward creep now also has a close-range stop guard:
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD_MAX_HEIGHT=0.82`
- Goal: the robot should actually break static friction and move when the person is visible, but stop creeping once the bbox is very large/close.

Manual-like forward follow correction:
- User reported the follow command still felt too weak after the first stiction fix and asked for a forward force closer to manual control while keeping motion matched to camera FPS.
- Manual panel forward at 100% is about `0.40`, with backend cap `BUDDYBOT_MANUAL_LINEAR_LIMIT=0.52`.
- Follow forward defaults were raised to a manual-like but still camera-safe band:
  - `BUDDYBOT_FOLLOW_HEIGHT_GAIN=0.010`
  - `BUDDYBOT_FOLLOW_MAX_LINEAR=0.42`
  - `BUDDYBOT_FOLLOW_MIN_LINEAR=0.34`
  - `BUDDYBOT_FOLLOW_LINEAR_ACCEL=0.55`
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD=0.34`
- Follow rotation stays slow:
  - `BUDDYBOT_FOLLOW_MAX_ANGULAR=0.10`
  - `BUDDYBOT_FOLLOW_ANGULAR_ACCEL=0.12`
- BBox smoothing alpha was raised to `0.45` so the controller follows the latest 10fps camera / roughly 5Hz detector signal with less lag.
- Expected result: the robot should move forward decisively when the person is visible, without returning to the earlier fast spin behavior.

Closer stop-distance and slower turn correction:
- User reported forward speed now feels acceptable, but the robot stops while still around 2.3m away and needs to come closer to the user's front.
- The camera-height stop threshold was too conservative for the C920/MobileNet bbox geometry, so the follow target was moved closer:
  - `BUDDYBOT_FOLLOW_TARGET_HEIGHT=0.90`
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD_MAX_HEIGHT=0.94`
- Follow turn speed was reduced further because the camera stream cannot keep up with the chassis rotation:
  - `BUDDYBOT_FOLLOW_CENTER_GAIN=0.0008`
  - `BUDDYBOT_FOLLOW_MAX_ANGULAR=0.07`
  - `BUDDYBOT_FOLLOW_ANGULAR_ACCEL=0.08`
- Forward force remains unchanged from the manual-like tuning.

Near-front final follow tuning:
- User reported the new behavior is better, but follow still stops too far away and turn speed should be a little slower.
- Stop distance was moved much closer by requiring the person bbox to nearly fill the camera height before follow stops:
  - `BUDDYBOT_FOLLOW_TARGET_HEIGHT=0.98`
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD_MAX_HEIGHT=0.99`
- Turn response was reduced one more step:
  - `BUDDYBOT_FOLLOW_CENTER_GAIN=0.00065`
  - `BUDDYBOT_FOLLOW_MAX_ANGULAR=0.055`
  - `BUDDYBOT_FOLLOW_ANGULAR_ACCEL=0.06`
- Forward force stays unchanged because the user reported forward speed now feels acceptable.

Vision-bearing / LiDAR-safety follow split:
- User reported the robot now approaches about 1.5m in front, but still needs to come much closer and rotate slightly slower.
- The C920/MobileNet bbox height is saturated too early to be a reliable final stop distance. The follow profile now treats vision mainly as bearing/target confirmation, and lets the existing LiDAR avoidance layer handle the near-field safety boundary.
- Camera-height stop was moved past a full-frame box so it no longer stops at mid-distance:
  - `BUDDYBOT_FOLLOW_TARGET_HEIGHT=1.16`
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD_MAX_HEIGHT=1.10`
- Turn response was lowered again:
  - `BUDDYBOT_FOLLOW_CENTER_GAIN=0.00055`
  - `BUDDYBOT_FOLLOW_MAX_ANGULAR=0.045`
  - `BUDDYBOT_FOLLOW_ANGULAR_ACCEL=0.05`
- Forward speed and stiction floor remain unchanged.

Close anchor stop and target-lock correction:
- User pointed out that once bbox height saturates, a better close-distance cue is a reference/anchor line rather than height alone.
- Follow controller now uses near-field bbox geometry:
  - suppresses turning when bbox `area_ratio>=0.34` or `width_ratio>=0.50`
  - stops both forward and rotation when bbox `area_ratio>=0.56`, `width_ratio>=0.70`, or the top anchor reaches the top line with a large bbox
- This is intended to stop the robot in front of the user without rotating the camera away at close range.
- Detector now keeps a short target lock on the previous person:
  - prefers a detection near/overlapping the previous target
  - withholds far-away candidate people for about 2s instead of immediately switching to them
- This addresses the observed failure where the robot lost the original user during a turn and started following another person.
