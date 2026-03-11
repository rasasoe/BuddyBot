# Selective Merge Plan: BuddyBot-main narrative + codex hardware patch

이 문서는 `codex/update-buddybot-for-real-hardware-compatibility` 브랜치를
**main 전체 대체가 아닌 하드웨어 호환 패치셋**으로 병합하기 위한 계획입니다.

## Phase 1 — File-by-file merge plan

### A) Direct-take candidates (hardware-specific, low narrative risk)
아래 파일은 codex 패치 버전을 우선 채택 가능:
- `docs/bringup.md`
- `docs/pin_mapping.md`
- `firmware/pico_motor_controller/main.py`
- `firmware/pico_motor_controller/pins.py`
- `firmware/pico_motor_controller/watchdog.py`
- `tools/usb_serial_test.py`

### B) Manual-merge candidates (high narrative / behavior impact)
아래 파일은 라인 단위 수동 병합 필수:
- `README.md`
- `docs/architecture.md`
- `firmware/pico_motor_controller/uart_protocol.py`
- `software/pi5/ros2_ws/src/buddybot_base/buddybot_base/pico_bridge_node.py`
- `software/pi5/ros2_ws/src/buddybot_system/buddybot_system/command_mux_node.py`

### C) Cleanup / non-functional noise
주요 소스 병합 판단과 분리해서 정리:
- nested workspace duplication (`software/pi5/ros2_ws/ros2_ws/...`)
- `__pycache__/`
- `.pyc`

## Phase 2 — Safe direct replacements only

### Applied as safe hardware patch
- 기존 실배선 핀맵 강제 (`pins.py`)
- monotonic watchdog (`watchdog.py`)
- Pico practical entrypoint (`main.py`)
- bring-up / pin mapping docs 추가 유지
- USB serial bring-up tool 유지 (`tools/usb_serial_test.py`)

### Manual-merge preserved (not blindly overwritten)
- README, architecture narrative는 **main의 설명력**(프로젝트/설계 근거) 유지 +
  codex의 하드웨어 제약(실배선, USB serial, bring-up 링크)만 추가
- `pico_bridge_node.py`는 `/dev/ttyACM0` 기본값과 안전 파싱 보강 유지
- `command_mux_node.py`는 소스 키 mismatch 오류 수정/안전 우선순위만 채택
- `uart_protocol.py`는 malformed-safe 및 line-based USB serial 계약 유지

## Documentation restoration requirements (must preserve)
- 프로젝트 개요/가치 제안
- Brain vs Spinal Cord rationale
- LiDAR vs Vision 책임 분리 설명
- command mux 존재 이유
- Pico safety layer 역할
- 발표/포트폴리오용 저장소 구조와 로드맵 설명

## Final merge policy statement
- BuddyBot-main = narrative/documentation base
- codex branch = hardware compatibility patch source
- 결과물은 selective merge이며, 전체 overwrite 금지
