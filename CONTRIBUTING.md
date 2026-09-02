# Contributing to LORL-9.1

## Getting Started

```bash
git clone https://github.com/ceyptoslim/LORL-9.1.git
cd LORL-9.1
pip install -e ".[test]"
pytest tests/ -v
```

All tests must pass before submitting a PR.

## CLA — Required Before First Contribution

All contributors must sign the [Contributor License Agreement (CLA)](./CLA.md)
before their pull requests can be merged. This is **automatically enforced** by
a GitHub Action that checks every PR.

### How to Sign

1. Read the [CLA document](./CLA.md)
2. Add your GitHub username to `CLA_SIGNERS.md` in your PR:

```markdown
| @your-github-username | Individual | 2026-09-02 | v1.0 |
```

3. Commit this change as part of your PR

The CLA check will automatically verify your signature and update the PR status.
For questions about the CLA, contact frolifeproductions@gmail.com.

## Branch Convention

| Branch | Purpose |
|--------|---------|
| `main` | Stable releases only |
| `feature/*` | Feature branches |

## Commit Convention

```
feat: add OPA treaty enforcement
fix: resolve event ledger hash chain gap
test: add governed executor integration tests
docs: update README badge
```

## Pull Request Requirements

- [ ] CLA signed (add username to `CLA_SIGNERS.md`)
- [ ] All existing tests pass (`pytest tests/ -v`)
- [ ] New functionality has tests
- [ ] `ruff check lorl/ tests/` passes with no errors
- [ ] No secrets or credentials in code
- [ ] PR description explains what changed and why

## Code Style

- Python 3.12+
- `ruff` for linting
- Type hints on all public functions
- Docstrings on all public classes and methods
