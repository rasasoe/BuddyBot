# buddybot_voice

BuddyBot의 음성 인터페이스 패키지.

## 노드

- **voice_interface**: 웨이크 워드 감지 및 명령 인식

## 목적

자연어 상호 작용 제공:
- 웨이크 워드 감지
- 음성 인식
- 명령 파싱 및 실행
- 긴급 정지 우선 처리
- 로컬 로봇 제어와 서버 AI 대화 분리
- Pi 로컬 시스템 음성과 서버 Edge TTS 분리

## 사용자 가이드

전체 음성 명령 목록, 패널 설정, 추천 시연 순서, 디버깅 방법은 저장소 루트의 `README.md`에 있는 `음성 명령 사용법` 섹션을 참고합니다.

## 로컬 명령 처리 흐름

```text
Pi 마이크 또는 /voice/text
→ Pi faster-whisper tiny wake-word 확인
→ 정지 명령 최우선 검사
→ 이동 / 추종 / waypoint 로컬 명령 검사
→ /cmd_vel_manual, /follow/enabled, /nav/waypoint_goal
→ command_mux
→ safety
→ pico_bridge
→ Pico
```

서버 AI가 모터 명령을 직접 발행하지는 않습니다.

## STT 우선순위

기본 backend는 `hybrid`입니다.

```text
대기 중:
Pi faster-whisper tiny로 웨이크워드 감지
→ 흔한 오인식 별칭 정규화
→ 로컬 로봇 명령이면 서버 왕복 없이 즉시 처리

웨이크워드 이후 명령:
Pi faster-whisper tiny 로컬 명령 우선
→ BuddyBot-ai /stt 서버 Whisper
→ 선택적 Google Web Speech fallback

주행 중:
Pi faster-whisper tiny로 긴급 정지 우선 검사
→ 서버 Whisper
→ 선택적 Google Web Speech fallback
```

서버 `/stt`가 실패하면 일정 시간 cooldown을 적용해 네트워크 실패로 마이크 루프가 계속 지연되지 않게 합니다.
`voice.log`의 `stt_observation` 줄에는 Pi tiny의 raw 텍스트, 정규화 결과, 웨이크워드 별칭, 분리된 명령, 로컬 intent가 기록됩니다.

Pi 설치 및 tiny 모델 사전 다운로드:

```bash
cd ~/BuddyBot
bash scripts/setup_pi5_whisper.sh
```

## 서버 대화 처리 흐름

패널에서 서버컴 연동을 켠 상태에서 로컬 명령으로 분류되지 않은 말만 BuddyBot-ai로 전달합니다.

```text
Pi 마이크
→ buddybot_voice
→ BuddyBot-ai /chat
→ BuddyBot-ai /tts
→ Edge TTS MP3
→ Pi mpg123 재생
```

## 주요 ROS 토픽

| 토픽 | 방향 | 용도 |
| --- | --- | --- |
| `/voice/text` | subscribe | 인식된 텍스트 입력 또는 개발용 테스트 입력 |
| `/voice/response` | publish / subscribe | 음성 및 텍스트 응답 |
| `/voice/command_status` | publish | 패널에 표시할 음성 상태 |
| `/voice/enabled` | subscribe | 음성 명령 모드 ON/OFF |
| `/voice/assistant_enabled` | subscribe | 서버컴 연동 ON/OFF |
| `/voice/server_url` | subscribe | BuddyBot-ai URL 갱신 |
| `/voice/manual_override` | subscribe | 패널 수동조작 우선권 알림 |
| `/cmd_vel_manual` | publish | 로컬 이동 명령 |
| `/follow/enabled` | publish | 사용자 추종 ON/OFF |
| `/nav/waypoint_goal` | publish | 체크포인트 이동 요청 |
| `/nav/cancel` | publish | 내비게이션 취소 |

## 기본 정책

- `버디봇 전진`: 정지 명령을 받을 때까지 지속 전진
- `후진`, 측면 이동, 대각선 이동, 회전: 기본 2.5초 동작 후 자동 정지
- `멈춰`, `정지`, `스톱`, `그만`: 웨이크워드 없이 최우선 정지
- 정지 처리 순서: 이동 해제, 추종 해제, 내비게이션 취소, zero velocity 발행, 음성 응답
- 부정문과 설명 요청은 이동 명령으로 실행하지 않음
- 서버가 꺼져 있어도 로컬 로봇 명령은 계속 처리
- Pi tiny 모델이 준비되어 있으면 서버와 인터넷이 모두 끊겨도 기본 음성 제어 가능

## 음성 출력 우선순위

로컬 시스템 응답:

```text
사전 녹음 WAV/MP3
→ Piper, 설정된 경우
→ espeak-ng
```

AI 답변:

```text
BuddyBot-ai Edge TTS
→ Pi 로컬 fallback
```

사전 녹음 파일 이름은 `assets/system_sounds/README.md`를 참고합니다.
