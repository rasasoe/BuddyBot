# BuddyBot Codex Resume Workflow

이 문서는 **다른 노트북 / 다른 Codex 세션 / 다음날 재시작** 때 매번 상황을 다시 길게 설명하지 않도록 만드는 운영 문서입니다.

목표:
- 새 작업환경에서도 5분 안에 현재 상태를 복원
- Codex에게 같은 배경 설명을 반복하지 않기
- Pi5 실기 로그와 레포 상태를 한 번에 맞추기

## 1. 새 작업환경에서 가장 먼저 할 일

로컬 레포 준비:

```bash
git clone https://github.com/rasasoe/BuddyBot.git
cd BuddyBot
git pull origin main
git rev-parse --short HEAD
```

Codex에게 작업을 넘길 때는 아래 3개를 먼저 읽게 하면 됩니다.

1. `AI_HANDOFF.md`
2. `docs/field_log.md` 최신 날짜 항목
3. `docs/CODEX_RESUME_WORKFLOW.md`

특히 Pico 주행 문제라면 아래를 추가로 먼저 확인해야 합니다.

- `AI_HANDOFF.md`의 `Latest Motion Fix Direction`
- 현재 기준은 `전체 방향은 맞고, 남은 것은 좌측 편향 미세조정`이다.
- `78a7db3`는 큰 방향성을 다시 맞춘 기준선이고, 그 다음 단계들에서 우측 편향이 좌측 미세편향으로 이동한 상태다.
- 따라서 새 작업환경에서는 바퀴 각도/좌우 이름/기본 직식 자체를 다시 뒤집지 말고 시작한다.

## 2. Pi5에서 상태 맞추기

Pi5 쪽 최신 코드 반영:

```bash
cd ~/BuddyBot
git pull origin main
cd ~/BuddyBot/software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

다른 작업환경에서 바로 실기 테스트까지 가려면, 이어서 아래를 수행합니다.

```bash
cd ~/BuddyBot
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/config.py :config.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/pins.py :pins.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/kinematics.py :kinematics.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/motor_driver.py :motor_driver.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/encoder.py :encoder.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/main.py :main.py
mpremote connect /dev/ttyACM0 reset
cd ~/BuddyBot/software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

Pico 펌웨어 파일도 최근 변경이 있으면 다시 올립니다.

최소 재배포 기준:
- `firmware/pico_motor_controller/main.py`
- `firmware/pico_motor_controller/config.py`
- `firmware/pico_motor_controller/motor_driver.py`
- `firmware/pico_motor_controller/pins.py`
- `firmware/pico_motor_controller/kinematics.py`
- `firmware/pico_motor_controller/encoder.py`

## 3. Codex에 붙여넣을 추천 프롬프트

아래 템플릿을 그대로 복사해서 새 세션 첫 메시지로 쓰면 됩니다.

```text
BuddyBot 디버깅 이어서 해줘.

먼저 이 순서로 읽고 시작해:
1. AI_HANDOFF.md
2. docs/field_log.md 최신 날짜 항목
3. docs/CODEX_RESUME_WORKFLOW.md

제약:
- destructive git 명령 금지
- 기존 사용자 변경사항 revert 금지
- 필요하면 코드 수정 후 문서까지 같이 갱신
- 가능하면 한 터미널 기준으로 디버깅 가능한 명령어 우선

현재 내가 보는 장비는 Raspberry Pi 5 (pi@pi-desktop) 실기 장비고,
로컬 레포는 BuddyBot main 기준이다.

먼저 현재 상태를 요약하고, 바로 다음 확인 명령어부터 제시해줘.
```

## 4. 세션 끝나기 전 꼭 남길 것

작업 종료 전에 아래를 항상 반영합니다.

1. `docs/field_log.md`
   - 오늘 날짜
   - 기준 커밋
   - 재현 증상
   - 확인된 원인 후보
   - 성공/실패한 테스트
   - 다음에 볼 우선순위
2. 필요하면 `AI_HANDOFF.md`
   - 전체 상태 요약이 바뀌었을 때만 갱신
   - Pico 주행 기준선이 바뀌었거나, "방향은 유지하고 미세조정만 남았다" 같은 작업 원칙이 생기면 반드시 반영
3. 관련 컴포넌트 README
   - 하드웨어나 실행 절차가 바뀌었을 때만 갱신

## 5. Pi5 실기에서 자주 쓰는 재현 명령

시연용 presentation profile:

```bash
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

더 보수적인 저부하 카메라 프로파일:

```bash
cd ~/BuddyBot
BUDDYBOT_CAMERA_WIDTH=160 \
BUDDYBOT_CAMERA_HEIGHT=120 \
BUDDYBOT_CAMERA_FPS=5.0 \
BUDDYBOT_CAMERA_PUBLISH_RATE=2.0 \
BUDDYBOT_CAMERA_START_DELAY=10 \
BUDDYBOT_LIDAR_SETTLE_DELAY=10 \
bash scripts/start_presentation_mode.sh mapping
```

## 6. Pi5 실기에서 자주 쓰는 모니터링 명령

전원 / USB:

```bash
sudo dmesg -w | grep -Ei 'under-voltage|usb .*disconnect|usb .*reset|uvcvideo|cdc_acm'
```

주요 런타임 로그:

```bash
tail -n 80 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/pico_bridge.log
tail -n 80 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/camera.log
tail -n 80 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/detector.log
tail -n 80 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/follow_controller.log
```

ROS 토픽 확인:

```bash
source /opt/ros/jazzy/setup.bash
source ~/BuddyBot/software/pi5/ros2_ws/install/setup.bash
ros2 topic echo /cmd_vel_final
ros2 topic echo /buddybot/pico_status
ros2 topic echo --qos-reliability best_effort /camera/image_raw
```

## 7. 다음 작업자가 빠르게 판단해야 할 축

새 세션에서는 문제를 아래 축으로 먼저 나눕니다.

1. 전원/USB 안정성
   - `under-voltage`
   - USB disconnect/reset
2. Pico 연결/estop
   - `/buddybot/pico_status`
   - `pico_bridge.log`
3. 카메라 publish
   - `camera_node`는 살아 있는데 `/camera/image_raw`가 실제 뜨는지
   - 이미지는 `BEST_EFFORT`라서 토픽 확인도 같은 QoS로 할 것
4. detector/follow 연결
   - `/vision/person_bbox` QoS mismatch 여부
5. 실제 주행 방향
   - 전진이 회전으로 보이면 Pico 모터 polarity / wheel mapping부터 확인
   - 다만 현재 기준선에서는 "전체 방향"을 다시 뒤집지 말고, 남아 있는 편향이 공통 좌/우 어느 쪽인지부터 본다

## 8. 이상적인 운영 습관

- 새 노트북에서 작업 시작 전: `git pull`
- 실기 전: Pi5도 `git pull`
- 실기 후: `docs/field_log.md` 갱신
- 작업 종료 전: `git commit` + `git push`

이 습관만 지키면 "어느 노트북에서 무엇을 했는지 모르겠다"는 문제가 크게 줄어듭니다.
