# BuddyBot 문서

## 개요

BuddyBot은 라즈베리 파이 5 + 라즈베리 파이 피코 기반 자율 주행 홈 어시스턴트 로봇입니다. 이 문서는 시스템의 아키텍처, 안전 정책, 통신 프로토콜, 개발 로드맵에 대한 포괄적인 정보를 제공합니다.

## 문서 구조

- **[architecture.md](architecture.md)**: 시스템 아키텍처 개요 및 설계 근거
- **[safety_policy.md](safety_policy.md)**: 안전 아키텍처 및 비상 절차
- **[uart_protocol.md](uart_protocol.md)**: Pi 5와 Pico 간 UART 통신 사양
- **[development_plan.md](development_plan.md)**: 구현 로드맵 및 마일스톤
- **[field_log.md](field_log.md)**: 날짜별 실기 디버깅 로그 및 다음 작업환경용 Codex 인수인계

## 빠른 시작

1. **하드웨어 설정**: LiDAR, 카메라, 모터 컨트롤러 연결
2. **소프트웨어 설치**: ROS 2 및 종속성을 위해 setup.sh 실행
3. **펌웨어 플래시**: 모터 제어를 위해 Pico에 펌웨어 업로드
4. **시스템 기동**: 적절한 순서로 ROS 2 노드 실행
5. **테스트**: 안전 시스템 및 기본 기능 검증

## 핵심 설계 원칙

- **Brain vs Spinal Cord**: 고수준 계획(Pi 5)과 저수준 제어(Pico) 분리
- **안전 우선**: 다중 중복 안전 메커니즘
- **모듈식 아키텍처**: 명확한 인터페이스를 가진 독립 서브시스템
- **명령 중재**: 안전한 다중 소스 제어를 위한 우선순위 기반 멀티플렉싱

## 저장소 레이아웃

```
BuddyBot/
├── firmware/           # Pico 마이크로컨트롤러 코드
├── software/           # ROS 2 워크스페이스
├── docs/              # 문서
└── tools/             # 개발 유틸리티
```

## 지원

특정 컴포넌트에 대한 질문은 관련 문서 섹션을 참조하거나 소프트웨어 디렉토리의 ROS 2 패키지 README를 확인하세요.
