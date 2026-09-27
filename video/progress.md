# progress.md

## 사전 점검 (2026-09-27)
- 실행 환경: 클라우드 컨테이너(Linux). 사용자 확인으로 biblecoding을 대상 앱으로 확정.
- 앱인토스 설정 파일 없음 → 앱인토스 관련 내용은 [확인 필요]로 처리.
- 설치: pycapcut 0.0.3, edge-tts, pillow, pymediainfo, ffmpeg(apt), 한글 폰트 Noto CJK(apt).
- 스킬 파일 `.claude/skills/pycapcut-mac/SKILL.md` 내려받음 (76줄).
- **edge-tts 실패**: 인증서 문제는 CA 번들 지정으로 해결했지만, 이후 WebSocket 연결이 403으로 거부됨. 프록시 문서에 "WebSocket 업그레이드 미지원, 우회하지 말 것"이라고 명시됨. 3회 시도 후 중단.

## STEP 1 완료 — 작업 기록 수집
- 결과: `video/research.md`
- 요약: 문서는 SPEC.md 1개, 커밋 2개(9/21, 9분 간격). SPEC 1단계(뼈대 + Dexie + 읽기 모드 + SM-2)만 완료. 막힌 문제 4건을 코드 주석에서 확인(새벽 4시 경계, bulkPut, HashRouter, 저작권). 프롬프트 원문, 배포, 앱인토스, 캡처는 기록 없음 → [확인 필요] 6건.

## STEP 2 완료 — 시리즈 기획
- 결과: `video/series_plan.md`
- 요약: 전 5편 (EP01 명세서 / EP02 첫 화면 / EP03 데이터 / EP04 SM-2 복습 / EP05 검증·배포). 앱인토스 EP06은 기록이 확인되면 추가. 프롬프트는 원문 기록이 없어 "시청자용 따라 치기 프롬프트"로 표기. [확인 필요] 6건.

## STEP 3 완료 — EP01 대본
- 결과: `video/ep01/script.json`, `video/ep01/need_capture.md`
- 요약: 18장면, 내레이션 78문장(1,920자, 모든 문장 40자 이내). 15초 안에 "이 편이 끝나면 갖게 되는 것" 장면(s02) 배치. prompt 장면 2개(min 3초), code 장면 1개(SPEC.md 13~22줄 실물), 마지막은 EP02 예고. 캡처가 없어서 screen 장면(s04)은 설명 슬라이드로 대체.

## STEP 4 부분 완료 — 렌더러 + EP01 렌더링 (음성 제외)
- 결과: `video/tools/render.py`, `ep01/ep01_preview_silent.mp4`(5분 52초, 18장면), `ep01.srt`, `thumbnail.png`, `upload.txt`, 캡컷 드래프트 `ep01/capcut/EP01_bible`(클라우드 경로, git 제외)
- 막힌 것: edge-tts(WebSocket 차단) → `--tts silent` 무음 미리보기로 대체. **최종 ep01.mp4(음성 포함)는 미생성.**
- 폰트: 맑은 고딕·Consolas 없음 → Noto Sans CJK KR / DejaVu Sans Mono로 대체 (qa.md 기록)

## STEP 5 완료 — 자동 점검 + 수정 (재렌더링 1회)
- 결과: `ep01/qa.md`
- 요약: 문제 6건 수정(내레이션-실제 불일치 1, 자막 줄바꿈 1, 레이아웃 2, 캡컷 오류 1, 캐시 1). 2회차 프레임 점검에서 잘림·겹침·오타·비밀정보 없음.

## STEP 6 — 보고 후 대기
