# BuddyBot

`BuddyBot`은 실제 로봇 하드웨어 쪽 저장소입니다.

이 레포는 라즈베리파이 5와 라즈베리파이 Pico에서 돌아가는 실제 로봇 제어 스택을 담고 있습니다.

## 음성 명령 사용법

BuddyBot의 음성 명령은 Raspberry Pi 5의 `buddybot_voice` 노드가 처리합니다.
로봇 이동, 정지, 사용자 추종, 체크포인트 이동은 서버 AI를 거치지 않고 Pi에서 먼저 판별합니다.
특히 정지 명령은 서버 상태와 음성모드 상태에 관계없이 최우선으로 로컬 처리합니다.

### 최신 전체 명령어 빠른표

최신 전체 명령어 표는 이 섹션이 기준입니다. 더 자세한 운용 규칙과 디버깅 방법은 [docs/voice_commands.md](docs/voice_commands.md)를 참고하세요.

#### 음성모드 기본 규칙

- 발표 모드는 기본적으로 음성 명령이 꺼진 상태로 시작합니다. 패널에서 `음성모드 켜기`를 눌러야 `버디봇` 호출과 명령 처리가 시작됩니다.
- 권장 STT 모드는 `BUDDYBOT_STT_MODE=legacy_google`입니다. Pi local Whisper는 테스트용이며 발표 기본값으로 쓰지 않습니다.
- 로컬 로봇 명령은 Pi 5의 `buddybot_voice`가 먼저 판별합니다. 전진, 정지, 추종, 체크포인트 이동은 서버 LLM이 직접 실행하지 않습니다.
- 서버 연동 모드에서도 마이크 일반 대화는 `버디봇` 호출어가 있어야 서버로 전달됩니다. 호출어 없이 주변 대화를 엿듣고 답하지 않게 막아둔 상태입니다.
- 시연에서는 `전진/정지`보다 `앞으로/멈춰` 조합을 권장합니다. `정지`도 동작하지만 `전진`과 짧은 2음절이라 STT가 헷갈릴 수 있습니다.

#### 호출어

아래 호출어 뒤에 바로 명령을 붙여 말할 수 있습니다.

```text
버디봇
버디봇아
버디 봇
버디 봇아
바디봇
바디 봇
버디보
버디 보
버디보트
버디
buddybot
buddy bot
buddy
```

예:

```text
버디봇 앞으로
버디봇 일로와
버디봇 따라와
버디봇 오늘 날씨 알려줘
```

호출어만 말하면 `네`라고 응답하고 약 10초 동안 다음 명령을 기다립니다.

```text
사용자: 버디봇
버디봇: 네
사용자: 앞으로
```

#### 긴급 정지

아래 정지 명령은 호출어 없이도 최우선 처리합니다. 실제 시연에서는 `멈춰`를 가장 권장합니다.

```text
멈춰
멈춰줘
멈춰 줘
멈추세요
멈춰주세요
멈추어
멈춰라
멈춤
멈추
스톱
스탑
중지
취소
그만
그만해
세워
세워줘
정지
정지해
stop
halt
brake
cancel
```

정지 명령을 받으면 수동 이동, 사용자 추종, 체크포인트 이동을 끄고 zero velocity를 여러 번 발행합니다.

#### 이동 명령

| 기능 | 가능한 말 |
| --- | --- |
| 계속 전진 | `버디봇 앞으로`, `버디봇 앞으로 가`, `버디봇 전진`, `버디봇 전진해`, `버디봇 가자`, `버디봇 직진`, `forward`, `go ahead` |
| 전진 STT 보정 | `정진`, `전지`, `전짐`, `전 좀`으로 들리면 `전진`으로 보정 |
| 계속 전진 강조 | `버디봇 계속 전진`, `버디봇 계속 앞으로`, `버디봇 앞으로 계속`, `버디봇 앞으로 계속 가`, `버디봇 주행 시작`, `버디봇 계속 가`, `버디봇 쭉 가`, `버디봇 쭉 전진`, `버디봇 계속 직진` |
| 3초 전진 호출 | `버디봇 일로와`, `버디봇 일로 와`, `버디봇 일로와줘`, `버디봇 일루와`, `버디봇 이리와`, `버디봇 이리 와`, `버디봇 이리와줘`, `버디봇 여기로와`, `버디봇 이쪽으로와`, `버디봇 내쪽으로와`, `버디봇 나한테 와`, `버디봇 나에게 와`, `버디봇 앞으로 와`, `버디봇 가까이 와`, `come here`, `come to me` |
| 후진 | `버디봇 뒤로`, `버디봇 후진`, `backward`, `reverse`, `back` |
| 왼쪽 측면 이동 | `버디봇 왼쪽 이동`, `버디봇 왼쪽으로`, `버디봇 좌측 이동`, `버디봇 좌측으로`, `strafe left`, `slide left` |
| 오른쪽 측면 이동 | `버디봇 오른쪽 이동`, `버디봇 오른쪽으로`, `버디봇 우측 이동`, `버디봇 우측으로`, `strafe right`, `slide right` |
| 좌회전 | `버디봇 좌회전`, `버디봇 왼쪽 회전`, `turn left`, `rotate left` |
| 우회전 | `버디봇 우회전`, `버디봇 오른쪽 회전`, `turn right`, `rotate right` |

현재 기본 정책:

- `버디봇 앞으로`와 `버디봇 전진`은 정지 명령을 받을 때까지 계속 전진합니다.
- `버디봇 일로와`, `버디봇 이리와` 계열은 3초 동안만 전진합니다.
- 후진, 측면 이동, 회전, 대각선 이동은 기본 2.5초 이동 후 자동 정지합니다.
- 움직이는 중에는 `멈춰`라고 말하면 즉시 멈춥니다.

#### 홀로노믹 / 대각선 이동

| 기능 | 가능한 말 |
| --- | --- |
| 왼쪽 앞으로 | `버디봇 왼쪽 앞으로`, `버디봇 좌측 앞으로`, `버디봇 왼쪽 앞`, `버디봇 좌측 앞`, `버디봇 왼쪽 대각선 전진`, `버디봇 좌측 대각선 전진`, `forward left`, `diagonal forward left` |
| 오른쪽 앞으로 | `버디봇 오른쪽 앞으로`, `버디봇 우측 앞으로`, `버디봇 오른쪽 앞`, `버디봇 우측 앞`, `버디봇 오른쪽 대각선 전진`, `버디봇 우측 대각선 전진`, `forward right`, `diagonal forward right` |
| 왼쪽 뒤로 | `버디봇 왼쪽 뒤로`, `버디봇 좌측 뒤로`, `버디봇 왼쪽 뒤`, `버디봇 좌측 뒤`, `버디봇 왼쪽 대각선 후진`, `버디봇 좌측 대각선 후진`, `backward left`, `diagonal backward left` |
| 오른쪽 뒤로 | `버디봇 오른쪽 뒤로`, `버디봇 우측 뒤로`, `버디봇 오른쪽 뒤`, `버디봇 우측 뒤`, `버디봇 오른쪽 대각선 후진`, `버디봇 우측 대각선 후진`, `backward right`, `diagonal backward right` |

#### 사용자 추종

사용자 추종은 Pi 5 로컬 비전/제어 노드가 처리합니다. 서버 AI가 모터를 직접 움직이지 않습니다.

추종 시작:

```text
버디봇 따라와
버디봇 따라와줘
버디봇 나 따라와
버디봇 나 따라와줘
버디봇 사람 따라와
버디봇 사람 따라와줘
버디봇 사용자 추종
버디봇 사용자 추종 시작
버디봇 사용자 추종 켜
버디봇 사용자 추종 켜줘
버디봇 사용자 조정
버디봇 사용자 조종
버디봇 사용자 추정
버디봇 추종
버디봇 추종 시작
버디봇 추종 시작해
버디봇 추종 켜
버디봇 추종 켜줘
버디봇 추종해
버디봇 따라오기 시작
버디봇 쫓아와
follow
track user
follow me
```

추종 정지:

```text
버디봇 추종 정지
버디봇 추종 중지
버디봇 추종 종료
버디봇 추종 꺼
버디봇 추종 끄기
버디봇 사용자 추종 정지
버디봇 사용자 추종 중지
버디봇 따라오지 마
버디봇 따라오지마
버디봇 그만 따라와
버디봇 따라오기 중지
follow stop
unfollow
stop following
```

추종 중에도 `멈춰`는 추종을 끄고 즉시 정지합니다.

#### 체크포인트 / 목적지 이동

아래 명령은 waypoint 요청으로 처리합니다. waypoint 파일과 내비게이션 노드가 준비되어 있어야 실제 이동합니다.

| 목적지 | 가능한 말 |
| --- | --- |
| 주방 | `버디봇 주방`, `버디봇 주방 이동`, `버디봇 주방으로 가`, `버디봇 부엌`, `버디봇 부엌으로 가`, `kitchen` |
| 거실 | `버디봇 거실`, `버디봇 거실 이동`, `버디봇 거실로 가`, `living room`, `livingroom` |
| 충전 위치 | `버디봇 충전`, `버디봇 충전소`, `버디봇 충전소로 가`, `버디봇 도킹`, `charge`, `charger`, `charging` |

이동 중 `멈춰`는 내비게이션 요청을 취소합니다.

#### 상태 확인

```text
버디봇 상태
버디봇 지금 상태
status
state
```

#### 서버 AI 질문

패널에서 서버 연동 모드를 켠 뒤 사용할 수 있습니다. 로봇 이동 명령은 Pi 로컬에서 먼저 처리되고, 나머지 질문만 BuddyBot-ai 서버로 전달됩니다.

```text
버디봇 오늘 날씨 알려줘
버디봇 서울 날씨 알려줘
버디봇 지금 몇 시야
버디봇 너는 누구야
버디봇 네 기능 설명해줘
버디봇 사용자 추종 설명해줘
버디봇 미니맵 설명해줘
버디봇 안전 구조 설명해줘
버디봇 갈비찜 레시피 알려줘
버디봇 코딩이 뭐야
버디봇 메모해줘 내일 배터리 충전
```

서버 AI 답변은 기본적으로 짧은 한국어 응답을 목표로 합니다. 실제 모터 제어는 서버 답변에서 직접 실행하지 않습니다.

#### 시연 추천 문장

```text
버디봇
버디봇 앞으로
멈춰
버디봇 일로와
버디봇 따라와
멈춰
버디봇 오늘 날씨 알려줘
버디봇 미니맵 설명해줘
```

시연 중 `버디봇 전진`이 `버디봇 정지`로 들리면 `버디봇 앞으로`를 사용하세요. `멈춰`는 `전진`과 발음 차이가 커서 정지 명령으로 가장 안정적입니다.

### 1. 음성모드 켜기

1. Pi에서 발표 모드를 실행합니다.

```bash
cd ~/BuddyBot
BUDDYBOT_FORCE_LIDAR_START=1 bash scripts/start_presentation_mode.sh mapping
```

2. 브라우저에서 BuddyBot 패널을 엽니다.

```text
http://PI_IP:8090
```

3. 패널 상단에서 음성모드를 켭니다.

- `로컬 명령`: 서버가 없어도 이동, 정지, 추종, 체크포인트 명령을 사용합니다.
- `서버컴 연동`: 로봇 명령은 Pi에서 로컬 처리하고, 나머지 질문은 BuddyBot-ai 서버로 보냅니다.
- 기본 서버 주소: `http://100.115.246.76:8000`
- 정상적으로 켜지면 Pi 스피커에서 `음성 모드 켜짐` 확인 응답이 나옵니다.

### 2. 버디봇 부르는 방법

두 가지 방식 모두 지원합니다.

한 번에 말하기:

```text
버디봇 전진
버디봇 따라와
버디봇 오늘 날씨 알려줘
```

먼저 부르고 다음 명령 말하기:

```text
사용자: 버디봇
버디봇: 네.
사용자: 전진
```

`버디봇`이라고 부른 뒤 약 10초 동안은 다시 웨이크워드를 말하지 않아도 됩니다.

지원하는 웨이크워드:

```text
버디봇
버디봇아
버디
buddybot
buddy
```

### 3. 긴급 정지

정지는 가장 중요한 안전 명령입니다. 아래 단어는 `버디봇`을 먼저 부르지 않아도 즉시 처리합니다.

```text
멈춰
멈춰줘
멈추세요
멈춰주세요
정지
정지해
스톱
스탑
중지
취소
그만
그만해
세워
세워줘
stop
halt
brake
cancel
```

예:

```text
사용자: 버디봇 전진
사용자: 멈춰
```

정지 명령을 받으면 Pi가 먼저 아래 작업을 수행한 뒤 음성으로 응답합니다.

1. 수동 이동 명령 해제
2. 사용자 추종 해제
3. 체크포인트 이동 취소
4. zero velocity 반복 발행
5. `정지.` 로컬 음성 응답

모터가 움직이는 중에는 `정지`보다 발음이 뚜렷한 `멈춰` 사용을 권장합니다.

### 4. 이동 명령

#### 전진

아래 명령은 정지 명령을 받을 때까지 계속 전진합니다.

```text
버디봇 전진
버디봇 앞으로
버디봇 앞으로 가
버디봇 가자
버디봇 직진
```

명시적으로 지속 전진을 말해도 동일하게 동작합니다.

```text
버디봇 계속 전진
버디봇 계속 앞으로
버디봇 앞으로 계속 가
버디봇 주행 시작
버디봇 계속 가
버디봇 쭉 가
버디봇 쭉 전진
버디봇 계속 직진
```

기본 설정에서 지속 전진은 시간 제한 없이 유지됩니다. 반드시 `멈춰`, 패널 정지 버튼, 안전 차단 또는 프로세스 종료로 멈춥니다.

#### 짧은 이동

후진, 측면 이동, 대각선 이동, 회전은 기본적으로 약 2.5초간 움직인 뒤 자동 정지합니다.

| 목적 | 명령 예시 |
| --- | --- |
| 후진 | `버디봇 후진`, `버디봇 뒤로` |
| 왼쪽 측면 이동 | `버디봇 왼쪽 이동`, `버디봇 왼쪽으로`, `버디봇 좌측 이동` |
| 오른쪽 측면 이동 | `버디봇 오른쪽 이동`, `버디봇 오른쪽으로`, `버디봇 우측 이동` |
| 왼쪽 앞 대각선 | `버디봇 왼쪽 앞으로`, `버디봇 왼쪽 앞`, `버디봇 좌측 대각선 전진` |
| 오른쪽 앞 대각선 | `버디봇 오른쪽 앞으로`, `버디봇 오른쪽 앞`, `버디봇 우측 대각선 전진` |
| 왼쪽 뒤 대각선 | `버디봇 왼쪽 뒤로`, `버디봇 왼쪽 뒤`, `버디봇 좌측 대각선 후진` |
| 오른쪽 뒤 대각선 | `버디봇 오른쪽 뒤로`, `버디봇 오른쪽 뒤`, `버디봇 우측 대각선 후진` |
| 좌회전 | `버디봇 좌회전`, `버디봇 왼쪽 회전` |
| 우회전 | `버디봇 우회전`, `버디봇 오른쪽 회전` |

급하게 멈춰야 할 때는 동작 시간이 끝나기를 기다리지 말고 `멈춰`라고 말합니다.

### 5. 사용자 추종

사용자 추종은 카메라 기반 로컬 기능입니다. 서버 AI가 모터를 직접 제어하지 않습니다.

추종 시작:

```text
버디봇 따라와
버디봇 추종
버디봇 사용자 추종
버디봇 추종 시작
버디봇 추종 켜
```

추종 중지:

```text
버디봇 추종 중지
버디봇 따라오지마
버디봇 추종 꺼
```

추종 중에도 `멈춰`라고 말하면 추종을 해제하고 즉시 정지합니다.

로컬 제어 흐름:

```text
카메라
→ 사람 감지
→ follow_controller
→ /cmd_vel_follow
→ command_mux
→ safety
→ pico_bridge
→ Pico
→ 모터
```

### 6. 체크포인트 이동

아래 목적지 명령은 로컬 waypoint 요청으로 처리합니다.

| 목적지 | 명령 예시 |
| --- | --- |
| 주방 | `버디봇 주방 이동`, `버디봇 주방`, `버디봇 부엌으로 가` |
| 거실 | `버디봇 거실 이동`, `버디봇 거실로 가` |
| 충전 위치 | `버디봇 충전`, `버디봇 충전소로 가`, `버디봇 도킹` |

체크포인트 이동을 사용하려면 해당 waypoint가 저장되어 있고 내비게이션 노드가 실행 중이어야 합니다.
이동 중 `멈춰`라고 말하면 내비게이션 요청도 취소합니다.

### 7. 상태 확인

```text
버디봇 상태
버디봇 지금 상태
```

로봇은 현재 이동, 추종 또는 내비게이션 상태를 짧게 응답합니다.

### 8. 서버 AI 질문

패널에서 `서버컴 연동`을 선택하면 로컬 명령으로 분류되지 않은 말은 BuddyBot-ai 서버로 전달합니다.

예:

```text
버디봇 오늘 날씨 알려줘
버디봇 지금 몇 시야
버디봇 너는 누구야
버디봇 사용자 추종 기능 설명해줘
버디봇 LiDAR 미니맵 설명해줘
버디봇 안전 구조 설명해줘
```

역할 분리:

```text
Pi 5 로컬 처리
- 웨이크워드
- 이동
- 긴급 정지
- 사용자 추종
- 체크포인트 이동
- 짧은 시스템 응답

BuddyBot-ai 서버 처리
- 날씨
- 시간
- 자기소개
- 기능 설명
- 일반 대화
- AI 답변용 Edge TTS
```

LLM 답변이 직접 모터 명령으로 연결되지는 않습니다.

### 9. 음성 출력 우선순위

짧은 시스템 응답과 긴급 정지는 Pi에서 출력합니다.

```text
1. 사전 녹음 WAV/MP3
2. 설정된 경우 Piper
3. espeak-ng fallback
```

AI 대화 답변은 서버의 Edge TTS를 사용하고, Pi에서 `mpg123`로 재생합니다.

```text
Pi 마이크
→ 로컬 명령 여부 판별
→ 일반 질문이면 BuddyBot-ai /chat
→ BuddyBot-ai /tts
→ Edge TTS MP3
→ Pi mpg123 재생
```

Pi에 필요한 패키지:

```bash
sudo apt update
sudo apt install -y flac mpg123
```

사전 녹음 음성 파일 이름은 `software/pi5/ros2_ws/src/buddybot_voice/assets/system_sounds/README.md`에서 확인합니다.

### 10. 오인식 안전 처리

이동과 정지가 함께 인식되면 정지를 우선합니다.

```text
전진 정지
앞으로 멈춰
정지 전진
```

부정문 또는 설명 요청은 이동 명령으로 실행하지 않습니다.

```text
버디봇 전진하지 마
버디봇 움직이지 마
버디봇 전진하는 방법 설명해줘
```

### 11. 현재 STT 방식

현재 기본 STT는 발표 안정성을 위해 기존 Google Web Speech 경로입니다.
Pi 5의 `faster-whisper tiny`는 ROS 발표 모드에서 LiDAR, 카메라, 패널, 모터 브리지와 함께 돌 때 20~30초 이상 지연될 수 있어 기본값에서 제외했습니다.
Whisper 서버/로컬 STT는 연구 및 비교 테스트용 옵션으로 남겨 둡니다.

발표 모드 시작 시 음성모드는 기본적으로 꺼져 있습니다. 패널에서 `음성모드 켜기`를 눌러야 웨이크워드와 일반 명령을 처리합니다. 음성모드가 꺼져 있어도 안전을 위해 Pi 로컬 `멈춰` 감지만 유지합니다.

```text
기본 발표 모드
→ BUDDYBOT_STT_MODE=legacy_google
→ Google Web Speech로 웨이크워드와 명령 문장 인식
→ Pi 로컬 명령 분기
→ 로봇 제어 또는 서버 AI 대화

로컬 Whisper 테스트 모드
→ BUDDYBOT_STT_MODE=local_whisper
→ Pi faster-whisper tiny만 사용
→ 발표 기본값으로 쓰지 않음

하이브리드 Whisper 테스트 모드
→ BUDDYBOT_STT_MODE=hybrid_whisper
→ BuddyBot-ai /stt 서버 Whisper 우선
→ Pi faster-whisper tiny fallback
→ Google Web Speech fallback
→ 발표 기본값으로 쓰지 않음
```

`버디봇 전진`처럼 웨이크워드와 명령을 한 번에 말하면 Pi가 STT 결과를 로컬 명령 allowlist로 먼저 분류합니다.
`멈춰`, `정지`, `스톱`, `그만`은 서버 AI 판단보다 먼저 로컬 정지로 처리합니다.
Whisper 테스트 모드에서는 `버디 봇`, `버디 봇아`, `바디봇`, `버디보`, `버디보트`, `buddy bot`도 웨이크워드로 정규화합니다.

기본 발표 모드는 별도 환경변수 없이 실행하면 됩니다.

```bash
BUDDYBOT_FORCE_LIDAR_START=1 \
bash scripts/start_presentation_mode.sh mapping
```

Whisper 모드를 실험하려면 명시적으로 켭니다.

```bash
BUDDYBOT_STT_MODE=local_whisper BUDDYBOT_FORCE_LIDAR_START=1 bash scripts/start_presentation_mode.sh mapping
BUDDYBOT_STT_MODE=hybrid_whisper BUDDYBOT_FORCE_LIDAR_START=1 bash scripts/start_presentation_mode.sh mapping
```

`voice.log`에는 STT 모드, 사용 backend, 처리 시간, raw 텍스트, 웨이크워드 매칭, 분리된 명령, 로컬 intent가 기록됩니다.

```text
BUDDYBOT_STT_MODE=legacy_google
BUDDYBOT_VOICE_RECOGNITION_BACKEND=google
BUDDYBOT_VOICE_SERVER_STT_ENABLED=0
BUDDYBOT_VOICE_SERVER_STT_TIMEOUT_SEC=4.0
BUDDYBOT_VOICE_SERVER_STT_COOLDOWN_SEC=10.0
BUDDYBOT_VOICE_LOCAL_WHISPER_ENABLED=0
BUDDYBOT_VOICE_LOCAL_WHISPER_MODEL=tiny
BUDDYBOT_VOICE_LOCAL_WHISPER_DEVICE=cpu
BUDDYBOT_VOICE_LOCAL_WHISPER_COMPUTE_TYPE=int8
BUDDYBOT_VOICE_GOOGLE_FALLBACK_ENABLED=1
BUDDYBOT_VOICE_WAKE_AUDIO_FALLBACK_ENABLED=0
BUDDYBOT_VOICE_WAKE_AUDIO_FALLBACK_MIN_SEC=0.35
BUDDYBOT_VOICE_WAKE_AUDIO_FALLBACK_MAX_SEC=1.60
BUDDYBOT_VOICE_RECOGNITION_LANGUAGE=ko-KR
BUDDYBOT_VOICE_GOOGLE_TIMEOUT_SEC=1.8
```

Whisper 테스트 모드를 쓰려면 Pi에서 한 번만 설치하고 tiny 모델을 미리 내려받습니다.

```bash
cd ~/BuddyBot
bash scripts/setup_pi5_whisper.sh
```

### 12. 추천 시연 순서

```text
버디봇
→ 네.

전진
→ 계속 전진

멈춰
→ 즉시 정지

버디봇 따라와
→ 사용자 추종 시작

멈춰
→ 추종 해제 및 즉시 정지

버디봇 오늘 날씨 알려줘
→ 서버 AI 답변과 Edge TTS 재생
```

### 13. 음성 디버깅

음성 응답이 없거나 인식이 느리면 Pi에서 아래 로그를 확인합니다.

```bash
tail -n 160 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/voice.log
```

ROS 토픽으로 마이크 없이 로컬 분기를 시험할 수도 있습니다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/BuddyBot/software/pi5/ros2_ws/install/setup.bash

ros2 topic pub --once /voice/text std_msgs/msg/String "{data: '버디봇 전진'}"
ros2 topic pub --once /voice/text std_msgs/msg/String "{data: '멈춰'}"
ros2 topic echo /voice/command_status
ros2 topic echo /cmd_vel_manual
ros2 topic echo /follow/enabled
```

## 다음 세션 바로 시작

다른 로컬 환경 / 다른 노트북 / 다음 Codex 세션에서 바로 이어서 테스트하려면, 맨 먼저 아래 문서 3개를 이 순서대로 봅니다.

1. `AI_HANDOFF.md`
2. `docs/field_log.md` 최신 날짜 항목
3. `docs/CODEX_RESUME_WORKFLOW.md`

현재 Pico 주행 기준은 아래 흐름으로 이해하면 됩니다.

- `78a7db3`
  - legacy standalone 구조를 모듈화 코드에 다시 맞춘 기준선
  - 전진/후진의 큰 방향성은 이 시점부터 맞기 시작했음
  - 다만 공통으로 오른쪽으로 도는 편향이 남아 있었음
- `ba4186b` 이후
  - 엔코더 부호 쪽까지 같이 맞추면서, 기존 오른쪽 편향이 반대편으로 넘어가
  - 지금은 전진/후진 모두 `조금씩 왼쪽으로 도는` 상태로 남아 있음
- 현재 결론
  - 전체 방향은 더 이상 다시 뒤집지 않는다
  - 다음 작업은 `왼쪽으로 도는 미세 편향`만 줄이는 것이다

즉, 다음 작업환경에서는 `78a7db3` 계열의 전체 방향성 + 그다음 커밋들까지 포함된 현재 기준을 그대로 받고, 작은 steering bias만 조정해야 합니다.

## 다른 환경에서 바로 테스트

Pi에서는 ROS를 올리기 전에 먼저 최신 코드를 받고 Pico를 재배포합니다.

```bash
cd ~/BuddyBot
git pull origin main
git rev-parse --short HEAD
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/config.py :config.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/pins.py :pins.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/kinematics.py :kinematics.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/motor_driver.py :motor_driver.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/encoder.py :encoder.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/main.py :main.py
mpremote connect /dev/ttyACM0 reset
```

그다음 바로 실행:

```bash
cd ~/BuddyBot/software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

바로 확인할 테스트:

- `forward`
- `backward`
- `rotate_left`
- `rotate_right`
- `stop`

현재 기대 상태:

- 전진/후진의 큰 방향은 맞음
- 남은 증상은 `forward`와 `backward`에서 공통으로 조금씩 왼쪽으로 도는 것
- 따라서 다음 조정도 그 편향만 다뤄야 함

포함 기능:
- ROS 2 기반 로봇 스택
- Pi5 <-> Pico 시리얼 브리지
- 수동 조작
- 카메라 기반 사용자 추종
- LiDAR 기반 회피구동
- LiDAR / waypoint navigation
- Pi5 로컬 웹 UI
- Pico 펌웨어

## 역할 분리

- 서버컴: `BuddyBot-ai`
- 라즈베리파이 5: `BuddyBot`
- 라즈베리파이 Pico: `firmware/pico_motor_controller`

## 최신 현장 로그 / 다음 환경 인수인계

최근 Pi5 실기 디버깅 기록과 다음 작업환경용 Codex 인수인계 문서는 아래를 먼저 보시면 됩니다.

- 팀원이 다른 AI에게 바로 넘길 때: `AI_HANDOFF.md`
- `docs/field_log.md`
- `docs/CODEX_RESUME_WORKFLOW.md`
- `docs/bringup.md`

특히 새 작업환경에서 mapping panel, LiDAR, camera bring-up을 다시 볼 때는 `docs/field_log.md`의 최신 날짜 항목부터 읽는 것을 권장합니다.

## Pico 주행 기준선

Pi5 실기에서 Pico 주행 방향을 다시 건드리기 전에 아래 기준을 먼저 읽고 그대로 유지해야 합니다.

- `AI_HANDOFF.md`의 `Latest Motion Fix Direction`
- `docs/field_log.md`의 최신 날짜 항목
- `docs/CODEX_RESUME_WORKFLOW.md`

현재 합의된 기준은 이렇습니다.

- 전진/후진의 큰 방향성은 이제 맞춰진 상태다.
- 남은 증상은 `forward`와 `backward`에서 공통으로 조금씩 왼쪽으로 도는 미세 편향이다.
- 따라서 다음 작업은 `전체 방향`을 다시 뒤집는 작업이 아니라, 현재 기준을 유지한 채 좌우 편향만 조금씩 바로잡는 작업이어야 한다.

현재 Pico 기준선:

- `pins.py`
  - `left = m0`
  - `right = m1`
  - `back = m2`
- `kinematics.py`
  - `left = vx + 0.5 * vy + w`
  - `right = -vx + 0.5 * vy + w`
  - `back = -vy + w`
- `motor_driver.py`
  - `+speed -> in1=0, in2=1`
  - `-speed -> in1=1, in2=0`

주의:

- 위 기준은 실기에서 전진/후진의 전체 방향성을 맞춘 기준선이다.
- 다음 작업환경에서는 이 기준을 바꾸지 말고, 좌우 편향만 미세 조정할 것.
- 실기 중 `mpremote`는 ROS 실행 전에만 사용할 것.

## 지금 바로 가능한 운용 모드

### 1. 오프라인 Standalone Mode

서버컴 없이 Pi5와 Pico만으로 시연/테스트하는 모드입니다.

가능한 것:
- Pi5 로컬 웹 UI 접속
- 수동 조작
- 추종 상태 전환
- LiDAR 기반 안전 우회
- 체크포인트 저장 / 이동
- 브라우저 음성 입력 / 음성 응답
- 맵 클릭으로 좌표 확인
- 현재 위치 기준 체크포인트 저장

### 2. Assistant Mode

서버컴과 연결해서 쓰는 상위 모드입니다.

가능한 것:
- BuddyBot-ai로 채팅 전달
- AI 비서 기능
- 날씨 / 시간 / 메모리 / 상위 자연어 명령
- 웹앱/패널에서 추종 / waypoint / voice 명령 연동

## 주요 패키지

- `buddybot_base`: Pi5 <-> Pico 시리얼 브리지
- `buddybot_system`: command mux, mode manager, safety supervisor, lidar avoidance
- `buddybot_vision`: 사용자 추종 및 비전 제어
- `buddybot_nav`: waypoint manager, navigation
- `buddybot_voice`: BuddyBot 오프라인 wake-word / command router, 필요 시 AI bridge
- `buddybot_panel`: Pi5 로컬 웹 UI

## 하드웨어 기준

- Raspberry Pi 5
- Raspberry Pi Pico
- 3륜 옴니 / Kiwi drive 베이스
- LiDAR
- 카메라
- Pi5 <-> Pico USB 시리얼 연결

## 핀 매핑 기준

- Motor 0: `GP2 / GP0 / GP1 / GP3 / GP14`
- Motor 1: `GP8 / GP6 / GP7 / GP9 / GP15`
- Motor 2: `GP12 / GP10 / GP11 / GP13 / GP16`

상세 문서:
- `docs/pin_mapping.md`

## Pi5 권장 환경

- Ubuntu 24.04
- ROS 2 Jazzy
- `python3-serial`

## Pi5 설치

```bash
git clone https://github.com/rasasoe/BuddyBot.git
cd BuddyBot
bash scripts/setup_pi5.sh
```

위 스크립트가 자동으로 해주는 것:
- apt 의존성 설치
- ROS 패키지 의존성 설치
- 누락된 `resource` / `__init__.py` 점검 및 보정
- `colcon build --symlink-install`

## 제일 쉬운 오프라인 시연 시작

Pi5에서 아래 두 줄이면 시작입니다.

```bash
cd ~/BuddyBot
bash scripts/start_offline_demo.sh
```

Run the full Pi5 stack with preflight checks in one command:

```bash
cd ~/BuddyBot
bash scripts/start_all_pi5.sh
```

Run the full Pi5 stack without the camera pipeline:

```bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=1 bash scripts/start_all_pi5.sh
```

## 발표/시연 안정화 모드

실기에서 카메라, LiDAR, Pico를 동시에 붙였을 때 USB 전력/재연결 이슈가 남아 있으면 아래 모드를 우선 사용합니다.

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
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

이 모드는 아래를 기본으로 적용합니다.
- preflight 재시작 churn 최소화
- microphone listener 비활성화
- Pi speaker 출력 비활성화
- 카메라 저해상도, 저FPS, MJPG, 작은 버퍼 유지
- detector 주기를 낮춰 CPU/USB 부담 완화
- 종료 시 자동으로 `/tmp/buddybot-debug-*` 번들을 남겨서 바로 디버깅 가능

더 줄여야 하면 아래 값을 같이 줍니다.

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

최신 로그 번들은 이렇게 확인합니다.

```bash
BUNDLE_DIR="$(ls -dt /tmp/buddybot-debug-* | grep -v '\.tar\.gz$' | head -n 1)"
echo "$BUNDLE_DIR"
tail -n 120 "$BUNDLE_DIR/command_mux.tail.log"
tail -n 120 "$BUNDLE_DIR/pico_bridge.tail.log"
tail -n 120 "$BUNDLE_DIR/camera.tail.log"
grep -n "Undervoltage\\|USB disconnect\\|error -71" "$BUNDLE_DIR/system_snapshot.log" | tail -n 40
```

## Pi5 startup guide

Recommended clean rebuild after pulling new changes:

```bash
cd ~/BuddyBot
git pull
cd ~/BuddyBot/software/pi5/ros2_ws
rm -rf build install log
colcon build --symlink-install
source install/setup.bash
```

여러 노트북 / 다음날 / 새 Codex 세션에서 바로 이어갈 때는 아래 문서를 같이 봅니다.

```text
AI_HANDOFF.md
docs/field_log.md
docs/CODEX_RESUME_WORKFLOW.md
```

Recommended full offline start on Pi5:

```bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=0 BUDDYBOT_DISABLE_PICO=0 bash scripts/start_all_pi5.sh
```

What this does:
- Forces local ROS discovery for Pi5 offline mode
- Clears any `ROS_DISCOVERY_SERVER` setting used for server-PC or Tailscale workflows
- Probes Pico, LiDAR, camera, and microphone
- Runs `check_all_devices.sh`
- Resets ROS discovery again after preflight so stale `/scan` or `/camera/image_raw` topics do not fool the main launcher
- Reuses the exact device paths found during preflight for the real launch
- Forces the main launch to start LiDAR again after preflight instead of trusting stale graph state
- Starts the actual offline demo stack

If you only want a quick hardware check first:

```bash
cd ~/BuddyBot
bash scripts/check_all_devices.sh
```

If LiDAR and Pico should be skipped temporarily during debugging:

```bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=1 BUDDYBOT_DISABLE_PICO=1 bash scripts/start_all_pi5.sh
```

If camera is unstable but LiDAR and Pico should still run:

```bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=1 bash scripts/start_all_pi5.sh
```

## Real map waypoint workflow

To save waypoints from a real LiDAR map instead of the synthetic waypoint view:

```bash
cd ~/BuddyBot
bash scripts/start_mapping_panel.sh
```

Or start the same flow through the all-in-one launcher:

```bash
cd ~/BuddyBot
bash scripts/start_all_pi5.sh mapping
```

If LiDAR auto-start is unstable, start real-map mode with a detached LiDAR boot first:

```bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=1 BUDDYBOT_DISABLE_PICO=1 bash scripts/start_mapping_real_lidar.sh
```

Recommended real-map startup sequence on Pi5:

```bash
cd ~/BuddyBot
git pull
cd ~/BuddyBot/software/pi5/ros2_ws
rm -rf build install log
colcon build --symlink-install
source install/setup.bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=1 BUDDYBOT_DISABLE_PICO=1 bash scripts/start_mapping_real_lidar.sh
```

One-terminal real-map startup with automatic stale-process cleanup:

```bash
cd ~/BuddyBot
git pull
cd ~/BuddyBot/software/pi5/ros2_ws
rm -rf build install log
colcon build --symlink-install
source install/setup.bash
cd ~/BuddyBot
bash scripts/start_mapping_one_terminal.sh
```

What this one-terminal command does:
- Kills stale `sllidar_ros2` and `slam_toolbox` processes left from previous runs
- Resets ROS discovery
- Reuses the detected Pico, LiDAR, and camera device paths
- Forces LiDAR to be started again for the real mapping run
- Starts the full mapping stack in the foreground so `Ctrl+C` stops everything together

Notes:
- Your LiDAR driver must already be publishing `/scan`
- When SLAM is healthy, the panel changes from `Map: synthetic` to `Map: ROS OccupancyGrid`
- Click a map cell, type a waypoint name, then use `Save clicked point`
- If `/scan` is missing, start your LiDAR driver first; otherwise SLAM cannot create `/map`
- If you use a server PC, Tailscale, or a ROS discovery server in other workflows, the offline Pi5 launch scripts now clear those settings on purpose so Pi5 local nodes can discover each other directly

## Pi5 local hotspot mode

Hotspot mode is disabled by default to avoid accidental AP-mode switching during normal development.
You must explicitly opt in with `BUDDYBOT_ALLOW_HOTSPOT=1` before running the hotspot scripts.
The saved hotspot profile is also created with `autoconnect no`, so reboot does not switch `wlan0` back into AP mode.

You do not need Tailscale, VPS, or internet for local control if Pi5 opens its own Wi-Fi AP.

One-time setup:

```bash
cd ~/BuddyBot
BUDDYBOT_ALLOW_HOTSPOT=1 bash scripts/setup_pi5_hotspot.sh
```

Start hotspot:

```bash
cd ~/BuddyBot
BUDDYBOT_ALLOW_HOTSPOT=1 bash scripts/start_pi5_hotspot.sh

Remove an existing hotspot profile and stop reboot-time fallback:

```bash
bash scripts/disable_pi5_hotspot.sh
```
```

Default values:
- SSID: `BuddyBot-Local`
- Password: `BuddyBot1234!`
- Panel URL: `http://192.168.50.1:8090`

## Startup behavior summary

`bash scripts/start_offline_demo.sh`
- Starts the Pi5 local panel backend
- Starts Pico bridge, system mux/safety nodes, camera, detector, follow controller, and waypoint manager
- Tries to auto-start an `sllidar_ros2` driver if that package is installed and a likely serial port exists
- Keeps running in the foreground until you press `Ctrl+C`

`bash scripts/start_all_pi5.sh`
- Resets ROS discovery first
- Probes attached Pi5 devices
- Runs `check_all_devices.sh` as a preflight check
- Starts the offline demo stack in one step

`bash scripts/start_mapping_panel.sh`
- Starts everything from the offline demo
- Adds SLAM toolbox for live map generation
- Tries to auto-start `sllidar_ros2` the same way
- If `/scan` is still missing, the panel stays on `Map: synthetic`

`bash scripts/start_all_pi5.sh mapping`
- Runs the same preflight flow
- Starts the mapping panel stack in one step

## Quick device check

Before a demo, you can verify Pico, LiDAR, camera, and microphone with one command:

```bash
cd ~/BuddyBot
bash scripts/check_all_devices.sh
```

This script:
- Detects Pico, LiDAR, and camera using stable `/dev/serial/by-id` and `/dev/v4l/by-id` paths when available
- Starts each device path one-by-one in a short runtime check
- Reports whether `/buddybot/pico_status`, `/scan`, and `/camera/image_raw` appear
- Shows recent logs for the failing device immediately
- Starts the camera in a conservative USB profile by default: `320x240`, `15fps`, `10Hz` publish
- You can override that profile with `BUDDYBOT_CAMERA_WIDTH`, `BUDDYBOT_CAMERA_HEIGHT`, `BUDDYBOT_CAMERA_FPS`, and `BUDDYBOT_CAMERA_PUBLISH_RATE`

## Manual drive behavior

- Manual drive buttons are latched
- Press `Forward`, `Backward`, `Turn Left`, or `Turn Right` once and the robot keeps moving
- Press `Stop` to clear the command and publish zero velocity
- The panel status shows `Manual drive: latched` while a drive command is active

## Development vs hotspot mode

- For daily development, stay on your normal Wi-Fi or hotspot and use `http://PI5_IP:8090`
- Pi5 hotspot mode is optional and mainly for demos where you want the phone to connect directly to the robot
- When Pi5 switches `wlan0` into hotspot/AP mode, it will usually stop using the previous Wi-Fi connection

접속 주소:
- Pi5 자체 브라우저: `http://127.0.0.1:8090`
- 같은 와이파이 휴대폰: `http://PI5_IP:8090`

## Pico 준비

먼저 Pico에 MicroPython UF2를 설치합니다.

그 다음 `firmware/pico_motor_controller/` 안의 파일들을 Pico 루트에 복사합니다.

필수 파일:
- `main.py`
- `config.py`
- `pins.py`
- `motor_driver.py`
- `encoder.py`
- `kinematics.py`
- `pid.py`
- `watchdog.py`
- `safety.py`
- `state.py`
- `uart_protocol.py`

중요:
- Pico 루트에 `main.py`가 있어야 전원 인가 시 자동 실행됩니다.

## 수동으로 실행하고 싶을 때

Pi5에서 아래 순서로 실행하면 됩니다.

### 1. Pico bridge 실행

```bash
ros2 run buddybot_base pico_bridge_node
```

### 2. 시스템 노드 실행

```bash
ros2 run buddybot_system command_mux_node
ros2 run buddybot_system mode_manager_node
ros2 run buddybot_system safety_supervisor_node
ros2 run buddybot_system lidar_avoidance_node
```

### 3. 추종 노드 실행

```bash
ros2 run buddybot_vision follow_controller_node
```

### 4. waypoint manager 실행

```bash
ros2 run buddybot_nav waypoint_manager_node
```

### 5. Pi5 로컬 패널 실행

```bash
ros2 run buddybot_panel panel_server
```

## Pi5 로컬 패널에서 되는 것

- 수동 조작
- 추종 시작 / 중지
- 실시간 맵 토픽이 있으면 OccupancyGrid 기반 미니맵 표시
- 맵이 없으면 체크포인트 기반 합성 미니맵 표시
- 맵 클릭으로 좌표 채우기
- 현재 위치 기준 체크포인트 저장
- 체크포인트 선택 이동
- 로컬 텍스트 명령
- 브라우저 음성 입력
- command mux 상태를 통해 회피/안전 상태 간접 확인

## 회피구동 동작 방식

- 사용자 추종은 카메라 기반 제어를 사용합니다.
- 장애물 회피는 LiDAR `/scan` 기반으로 동작합니다.
- `lidar_avoidance_node`가 전방 장애물을 감지하면 `/cmd_vel_safety_override`를 발행합니다.
- `command_mux_node`는 이 안전 override를 follow/nav/manual보다 높은 우선순위로 반영합니다.
- 가까운 장애물은 정지 또는 후진+회전, 여유가 있는 장애물은 제자리 회전 우회로 처리합니다.

즉:
- 사람 추종: 카메라
- 장애물 회피: LiDAR
- 최종 주행 출력: command mux

## 미니맵 / 체크포인트 동작 방식

### 실시간 맵이 있는 경우

- `/map` 토픽을 읽어 미니맵 표시
- `/amcl_pose` 또는 `/odom` 기준 현재 위치 표시
- 미니맵 클릭으로 좌표 입력
- 현재 위치를 이름만 넣고 바로 체크포인트로 저장 가능

### 실시간 맵이 없는 경우

- `waypoints.yaml` 기준으로 합성 미니맵 생성
- 저장된 체크포인트 좌표를 기준으로 빠른 시연 가능

## 체크포인트 파일

기준 파일:

- `software/pi5/ros2_ws/src/buddybot_nav/config/waypoints.yaml`

이 파일은 아래에서 함께 사용합니다.
- navigation
- waypoint manager
- Pi5 로컬 패널
- 서버측 체크포인트 기능

## Assistant Mode 연결

서버컴이 있을 때만 아래를 추가 실행합니다.

```bash
ros2 run buddybot_voice voice_interface --ros-args -p buddybot_ai_url:=http://SERVER_PC_IP:8000
```

그리고 Pi5 로컬 패널에서 Assistant Mode를 켜면 됩니다.

## 자주 나오는 빌드 에러와 해결

### 1. `can't copy 'resource/buddybot_nav': doesn't exist`

원인:
- `buddybot_nav`는 `ament_python` 패키지이고 `resource/buddybot_nav` 마커 파일이 필요합니다.
- 이 파일이 빠진 예전 커밋을 받은 경우 발생할 수 있습니다.

해결:
```bash
cd ~/BuddyBot
git pull
bash scripts/setup_pi5.sh
```

### 2. `buddybot_voice ... doesn't contain an '__init__.py' file`

원인:
- 예전 커밋의 `buddybot_voice`는 파이썬 패키지 폴더가 빠져 있어서 발생할 수 있습니다.

해결:
```bash
cd ~/BuddyBot
git pull
bash scripts/setup_pi5.sh
```

### 3. 이전 빌드 캐시 때문에 계속 이상한 에러가 날 때

아래처럼 워크스페이스 빌드 산출물만 지우고 다시 빌드합니다.

```bash
cd ~/BuddyBot/software/pi5/ros2_ws
rm -rf build install log
colcon build
source install/setup.bash
```

### 4. 패키지 설치 후에도 ROS가 명령을 못 찾을 때

빌드 후 반드시 아래를 다시 실행합니다.

```bash
cd ~/BuddyBot/software/pi5/ros2_ws
source install/setup.bash
```

그래도 `ros2 run buddybot_panel panel_server` 에서 `No executable found`가 나오면:

```bash
cd ~/BuddyBot
git pull
cd ~/BuddyBot/software/pi5/ros2_ws
rm -rf build install log
cd ~/BuddyBot
bash scripts/setup_pi5.sh
```

### 5. 설치가 자꾸 꼬일 때 전체 점검만 먼저 하고 싶다면

```bash
cd ~/BuddyBot
bash scripts/doctor_pi5.sh
```

자동 수정까지 하고 싶다면:

```bash
cd ~/BuddyBot
bash scripts/doctor_pi5.sh --fix
```

## 팀원 역할 분리

### 서버컴 담당

`BuddyBot-ai` 설치 및 실행

### Pi5 담당

이 `BuddyBot` 설치 및 ROS2 bringup

### Pico 담당

MicroPython 설치 후 `firmware/pico_motor_controller` 업로드

## 오프라인 시연 인계 포인트

팀원에게는 아래처럼 전달하면 됩니다.

1. `BuddyBot`만 받아도 오프라인 모드 시연 가능
2. Pi5에서 `bash scripts/setup_pi5.sh` 한 번 실행
3. `bash scripts/start_offline_demo.sh`로 바로 데모 시작
4. 휴대폰으로 Pi5 패널 접속 가능
5. 수동 조작, 체크포인트 저장/이동, 맵 확인, LiDAR 회피 시연은 서버 없이 가능
6. 서버컴이 붙으면 AI 비서 기능만 추가됨

## 중요한 현실적 주의사항

이 레포는 설치와 소프트웨어 연동, UI 시연을 시작하기에 충분합니다.

하지만 실제 로봇 완성은 아래 하드웨어 검증이 필요합니다.
- 모터 방향 보정
- Kiwi drive 운동학 검증
- 전진 / 후진 / 좌 / 우 / 회전 보정
- 오도메트리 검증
- 추종 튜닝
- 네비게이션 튜닝
- LiDAR 회피 파라미터 튜닝

즉:
- 오프라인 시연 / 기능 테스트는 가능
- 최종 실주행 완성도는 하드웨어 캘리브레이션이 남아 있음

## 같이 보면 좋은 파일

- `README.md`
- `docs/TEAM_SETUP_PI5_AND_PICO.md`
- `docs/pin_mapping.md`
- `docs/bringup.md`

## 폴더 구조

```text
BuddyBot/
  docs/
  firmware/
    pico_motor_controller/
  software/
    pi5/ros2_ws/src/
      buddybot_base/
      buddybot_system/
      buddybot_vision/
      buddybot_nav/
      buddybot_voice/
      buddybot_panel/
      buddybot_msgs/
  README.md
```
