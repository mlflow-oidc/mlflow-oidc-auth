# Contributing to mlflow-oidc-auth

Thank you for contributing.

## Before You Start

- Read the project documentation in docs/.
- Be respectful and follow the Code of Conduct in CODE_OF_CONDUCT.md.
- For security issues, do not open a public issue. Follow SECURITY.md.

## Development Setup

### Prerequisites

- Python 3.12
- Node.js 24+
- Yarn
- Git

### Quick Start

Run the full local dev environment:

```bash
./scripts/run-dev-server.sh
```

### Manual Setup

Backend:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev,test]"
```

Frontend:

```bash
cd web-react
yarn install
```

## Running Checks Locally

Backend tests:

```bash
pytest mlflow_oidc_auth/tests
```

Frontend tests:

```bash
cd web-react
yarn test
```

Type checking and linting:

```bash
cd web-react
npx tsc -b
yarn lint
```

Optional CI-like backend run:

```bash
tox -e py314
```

## Coding Standards

- Python formatting is enforced with Black.
- TypeScript/React formatting uses Prettier and linting uses ESLint.
- Keep changes focused and avoid unrelated refactors in the same PR.
- Add or update tests for behavior changes.

## Pull Request Guidelines

- Open a PR with a clear problem statement and scope.
- Include tests that cover your changes.
- Update docs when behavior or configuration changes.
- Keep PRs small and reviewable when possible.

## Commit Messages

This repository uses Conventional Commits.

Examples:

- feat(auth): add token refresh validation
- fix(ui): correct footer alignment on mobile
- docs: clarify oidc setup variables

## Legal

No Contributor License Agreement (CLA) and no DCO sign-off are currently required.

By submitting a contribution, you confirm that:

- You have the right to submit the contribution.
- You agree to license your contribution under the repository license.

If this policy changes, it will be announced in this file and in repository settings.
