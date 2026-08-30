# Global Instructions

## 프로젝트 구조

```
src/
  components/
  hooks/
  utils/
tests/
docs/
```

## 기술 스택

React 18, TypeScript 5.4, Vite, Vitest, Tailwind CSS. 패키지 매니저는 npm.

## 빌드와 테스트

- 개발 서버: `npm run dev`
- 빌드: `npm run build`
- 테스트: `npm test`

## 코딩 원칙

- 깨끗한 코드를 작성할 것.
- 에러를 적절히 처리할 것.
- 테스트를 추가할 것.
- 함수는 짧게 유지할 것.

## 응답 언어

사용자가 다른 언어를 요청하지 않는 한 한국어로 답한다.

## 배포 금지 규칙

`main` 브랜치에 직접 푸시하지 않는다. 반드시 PR을 거친다.

## 생성 파일

`src/generated/` 아래 파일은 절대 직접 수정하지 않는다 — 스키마에서 재생성된다.

## E2E 테스트

E2E는 기본 Playwright 러너가 아니라 사내 `qa-runner`로 돌린다. 실행 전에
`docker compose up qa-db`로 테스트 DB가 떠 있어야 한다.
