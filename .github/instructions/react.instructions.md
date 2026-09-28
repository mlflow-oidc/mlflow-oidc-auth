---
applyTo: 'web-react/**/*.{ts,tsx,js,jsx,css,scss}'
description: React/TypeScript conventions — see AGENTS.md for the full set
---

Frontend conventions for this repository live in [`AGENTS.md`](../../AGENTS.md) and
[`web-react/AGENTS.md`](../../web-react/AGENTS.md). Read those; this file only exists so Copilot
applies them to the frontend.

The short version:

- Function components with hooks. Props typed explicitly; no `any` in new code.
- Files `kebab-case.tsx`; components `PascalCase`; hooks `useCamelCase` in `use-*.ts`.
- Tests co-located as `*.test.tsx` using Testing Library. A new component ships with its test.
- Side effects inside `useEffect`, with cleanup returned for subscriptions and timers.
- **The UI is not a security boundary.** Hiding a control is not authorization — the server
  decides. Disable what the server would reject, and say why.
