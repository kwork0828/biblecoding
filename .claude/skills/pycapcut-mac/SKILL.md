---
name: pycapcut-mac
description: pycapcut(pyCapCut)으로 CapCut 드래프트를 생성할 때 반드시 참조하는 함정 목록. 드래프트가 캡컷 목록에 안 뜸, 0:00 길이, 미디어 누락(빨간 화면), 자막 위치 이상, ASR 동시 호출 segfault, 한국어 자막 청크가 어색함 등의 문제를 다룬다. "캡컷 드래프트", "pycapcut", "draft_content", "draft_info", "자막 트랙", "점프컷 드래프트" 작업 시 자동 적용.
---

# pycapcut-mac: CapCut 드래프트 생성 함정 레퍼런스

> 이 문서는 edit-auto 저장소용으로 작성한 레퍼런스다. 공개된 동명 스킬을 찾지 못해
> pycapcut 0.0.3 소스 + CapCut Mac 커뮤니티 사례를 기반으로 정리했다.
> **"(검증 필요)" 표시 항목은 실제 캡컷 재생으로 확인되기 전까지 가설이다.**

## 0. 대원칙

- 빌드 성공 ≠ 검증. **캡컷에서 드래프트를 열고 끝까지 재생**해야 검증이다.
- 새 함정을 발견하면 이 파일 하단 "발견 로그"에 날짜와 함께 추가한다.

## 1. 드래프트 폴더 위치

| OS | 경로 |
|---|---|
| macOS | `~/Movies/CapCut/User Data/Projects/com.lveditor.draft` |
| Windows | `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft` |

폴더가 없으면 캡컷을 설치하고 **한 번 실행 + 빈 프로젝트 1개 생성**해야 생긴다.
`capcut_agent.env.find_draft_root()`가 이 규칙을 구현한다.

## 2. draft_info.json vs draft_content.json

- pycapcut은 `draft_content.json`만 쓴다.
- CapCut Mac 최신 버전은 `draft_info.json`을 읽는다 (검증 필요: 버전별 차이).
- 대응: **같은 내용을 두 파일에 모두 저장**한다 (`draft.save_draft()`).

## 3. draft_meta_info.json (tm_duration 등)

pycapcut이 복사하는 템플릿은 값이 비어 있다. 그대로 두면 목록에서 0:00으로 표시되거나 썸네일/열기가 이상해진다.
반드시 채울 필드:

- `tm_duration`: 타임라인 총 길이 (**마이크로초**)
- `draft_name`, `draft_fold_path`(드래프트 폴더 절대경로), `draft_root_path`(상위 루트)
- `draft_id`: 드래프트마다 **새 UUID** (템플릿 값 재사용 시 충돌)
- `tm_draft_create`, `tm_draft_modified`: 현재 시각 (마이크로초)

## 4. 샌드박스 (Mac)

- 캡컷이 접근 못 하는 경로(다운로드 임시폴더, 외장 드라이브 일부 등)의 미디어는 "미디어 없음"으로 뜬다 (검증 필요: 설치 경로별 차이).
- 대응: **원본 영상을 드래프트 폴더 안 `materials/`로 복사한 뒤 그 경로로 material 생성**.

## 5. 타임라인 규칙

- 모든 시간은 **마이크로초 정수**. `pycapcut.trange(start_us, dur_us)`.
- 주 비디오 트랙 첫 세그먼트는 **0에서 시작**해야 한다 (아니면 캡컷이 강제 정렬).
- 세그먼트끼리 겹치면 안 된다. 컷 누적 시 반올림 오차로 1µs 겹침이 생기지 않도록 target 시작은 직전 세그먼트의 `start + duration`을 그대로 쓴다.
- `source_timerange.end`가 소재 길이를 넘으면 `ValueError` → 마지막 구간은 소재 길이로 clamp.
- 캡컷이 열려 있는 상태에서 덮어쓰면 캡컷이 자기 메모리 상태로 되덮을 수 있다 → **캡컷 종료 후 생성, 또는 새 이름으로 생성**.

## 6. 자막 (3단 이후)

- `ClipSettings(transform_y=...)`: 단위는 **캔버스 높이의 절반**, **양수 = 위**. 하단 자막은 `-0.75 ~ -0.8` 근처.
- 한국어 단어별 자막은 조사/의존명사가 따로 떨어지면 어색하다.
  **의존명사 청크 규칙**: `것, 수, 데, 줄, 때, 적, 뿐, 만큼, 대로, 듯` 등은 앞 단어에 붙여 한 청크로.
- 자막 결정은 **전체 대본(script)을 먼저 추출한 뒤** 문장 단위로 한다. 단어 단위로 바로 결정하지 않는다.

## 7. ASR (whisper)

- mlx-whisper / faster-whisper 모두 동시 호출 시 numba 쪽에서 segfault 가능 → **`asyncio.Lock`으로 직렬화**.
- 캐시 키는 **파일 content hash** (mtime은 업로드마다 바뀌어 매번 miss).
- 트랙 선택: Mac arm64 → mlx-whisper, 그 외 → faster-whisper.

## 8. Windows 전용

- pycapcut의 자동 export(MP4)는 Windows에서만 동작한다. Mac/Linux는 드래프트 생성까지만.
- 일부 CapCut Windows 버전은 draft_content.json을 암호화한다 (검증 필요). 그 경우 드래프트 신규 생성은 되지만 기존 드래프트 템플릿 로드는 실패할 수 있다.

## 발견 로그

- 2026-09-26: 초기 작성. 항목 2, 4, 8의 "검증 필요"는 사용자 캡컷 재생 결과로 확정할 것.
