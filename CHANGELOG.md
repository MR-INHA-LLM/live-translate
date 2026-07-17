# Changelog

이 프로젝트의 모든 주목할 변경을 기록한다. 형식은 [Keep a Changelog](https://keepachangelog.com),
버전 규칙은 [Semantic Versioning](https://semver.org)을 따른다.

## [Unreleased]

### ✨ Features
- **web/console**: 고객 화면을 태블릿 규격(580px)으로 키우고 본문 폰트를 확대해 데모에서 "실제 고객 기기" 느낌을 강화. 빈 스테이지 위에 부양하도록 우측 패널만 배경 분리.
- **web/console**: 고객 화면에 입력창 추가 — 외국인 고객이 자기 언어로 입력하면 역방향 세션으로 운영자 언어로 번역돼 작업대에 수신된다(양방향 대화 데모).

### ♻️ Refactor
- **web/console**: 3분할 콘솔에서 전체를 카드로 띄우던 처리를 걷어내고 풀 레이아웃으로 복귀. 부양 효과는 고객 화면 한 곳에만 남겨 시선을 집중.

---
**배포 노트**: nginx 이미지 재빌드 필요(`docker compose build nginx && docker compose up -d nginx`). 마이그레이션·env 변경 없음.
