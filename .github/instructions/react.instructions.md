```instructions
---
applyTo: 'web-react/**/*.{ts,tsx,js,jsx,css,scss}'
description: React (TypeScript) coding conventions and guidelines
---

# React Coding Conventions

## Components and Props

- Use function components with hooks; keep components focused and prefer composition over prop drilling.
- Type props with explicit interfaces; avoid `any` and prefer discriminated unions for variants.
- Memoize only when needed (`React.memo`, `useMemo`, `useCallback`) and keep dependency arrays accurate.

## State, Effects, and Data

- Keep state minimal and derived when possible; use `useReducer` for multi-step state machines.
- Prefer the `async`/`await` pattern with `fetch` plus `AbortController` for cancellable requests.
- Handle loading/error/empty states explicitly and surface actionable messages in the UI.

## Routing and Navigation

- Use `react-router` loaders/actions sparingly; colocate route-level data fetching with the route component.
- Keep navigation accessible with semantic links and buttons; avoid div-based click targets.

## Templates and Markup

- Keep JSX expressions simple; extract helpers for complex conditionals or mapping logic.
- Use `key` that is stable and unique for lists; prefer `trackBy`-style identifiers over array indices.
- Sanitize any dynamic HTML with `DOMPurify` before using `dangerouslySetInnerHTML`.

## Styling

- Prefer Tailwind utility classes first; keep custom CSS/SCSS minimal and scoped to components.
- Keep className strings readable (group related utilities) and factor repeated patterns into small helpers.
- Avoid global selectors; when necessary, isolate with :global blocks and document why.

## Testing

- Write tests with Vitest and Testing Library; assert via `screen` queries and user-centric interactions (`userEvent`).
- Use accessible queries (`getByRole`, `getByLabelText`) over brittle CSS selectors; avoid snapshot-only tests for behavior.
- Mock network boundaries deterministically; keep tests isolated and free of real timers when not required.

## General Quality

- Enforce strict TypeScript settings; prefer `readonly` props and never ignore type errors with `// @ts-ignore`.
- Avoid inline anonymous functions in hot paths when they cause unnecessary renders; measure before optimizing.
- Keep side effects inside `useEffect` and return cleanup functions for subscriptions or timers.
```
