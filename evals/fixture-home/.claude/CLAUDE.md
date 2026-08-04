# Global Instructions

## Project Structure

```
src/
  components/
  hooks/
  utils/
tests/
docs/
```

## Tech Stack

React 18, TypeScript 5.4, Vite, Vitest, Tailwind CSS. Package manager is npm.

## Build and Test

- Dev server: `npm run dev`
- Build: `npm run build`
- Test: `npm test`

## Coding Principles

- Write clean code.
- Handle errors properly.
- Add tests.
- Keep functions short.

## Response Language

Respond in Korean unless the user requests another language.

## No-Deploy Rule

Never push directly to the `main` branch. Always go through a PR.

## Generated Files

Never edit files under `src/generated/` directly — they're regenerated from the schema.

## E2E Tests

E2E runs on the in-house `qa-runner`, not the default Playwright runner. The test DB
must be up via `docker compose up qa-db` before running.
