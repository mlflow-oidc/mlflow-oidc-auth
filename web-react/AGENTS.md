# AGENTS.md — frontend (`web-react/`)

Extends the [root AGENTS.md](../AGENTS.md). Applies to everything under `web-react/`.

## Commands

```bash
yarn dev        # Vite dev server
yarn test       # Vitest
yarn lint       # ESLint
yarn build      # outputs into ../mlflow_oidc_auth/ui/ — build artifact, never edited by hand
```

## Layout

| Concern | Location |
|---|---|
| Route table | `src/App.tsx` (admin routes via `ProtectedLayoutRoute isAdminRequired`) |
| Feature folders | `src/features/<feature>/` with co-located `components/`, `hooks/`, `services/` |
| Shared hooks | `src/core/hooks/use-*.ts` |
| API clients | `src/core/services/` (`http.ts` is the shared fetch wrapper) |
| Global state | `src/core/context/` |
| Runtime config | fetched from `/oidc/ui/config.json` at startup |

## Conventions

- Files `kebab-case.tsx` / `kebab-case.ts`; components `PascalCase`; hooks `useCamelCase` in
  files named `use-*.ts`.
- Tests co-located as `*.test.tsx`, using Testing Library. A new component ships with its test.
- TypeScript strict. No `any` in new code.
- Tailwind for styling; no new CSS frameworks.

## Rules

1. **The UI is not a security boundary.** Hiding a button is not authorization — the server
   decides. Never rely on client-side gating for access control.
2. **Disable what the server will reject.** If an action will fail server-side (insufficient
   permission, an externally-managed record), disable the control and explain why. A rejected
   save is a support ticket.
3. **Never render server data as HTML** without `dompurify`.
4. **Do not put tokens in `localStorage`.** Auth is cookie-based by design.
5. Auth errors: a 401 on a subresource fetch must not be turned into a redirect — the SPA
   handles it. Only top-level navigations redirect.
