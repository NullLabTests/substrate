# Contributing to Substrate

## Code of Conduct

This project adheres to a standard of professional conduct. Harassment, intimidation, or discriminatory behavior will not be tolerated. All contributors and maintainers are expected to treat each other with respect.

## Getting Started

Clone the repository and install development dependencies:

```bash
git clone https://github.com/your-org/substrate.git
cd substrate
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

Verify installation:

```bash
python -m pytest tests/ -x --tb=short
```

## Development Workflow

1. **Create a branch**: `git checkout -b feature/your-feature-name`
2. **Make changes**: Write code, add tests, update documentation
3. **Run checks**: Ensure linting, type checking, and tests pass
4. **Commit**: Use conventional commit format: `type(scope): description`
   - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
   - Example: `feat(runtime): add configurable tick rate`
5. **Push and open a PR**: `git push -u origin your-branch`

## Coding Standards

### Python

- **Python version**: 3.11+
- **Formatter**: `ruff format` (line length: 100)
- **Linter**: `ruff check` — all rules enabled by default
- **Type checker**: `mypy --strict` on all source files
- **No `# type: ignore`** unless absolutely necessary and justified in comment

Run all checks:

```bash
ruff format --check .
ruff check .
mypy src/
```

### Naming

- `snake_case` for variables, functions, methods
- `PascalCase` for classes
- `UPPER_CASE` for constants
- Private methods prefixed with `_`
- Type annotations required on all function signatures

### Imports

Standard library → Third-party → Local. Groups separated by blank line. Use absolute imports.

## Testing Requirements

### Framework

- **Test runner**: `pytest`
- **Coverage**: Minimum 80% line coverage (source code only, not tests)
- **Coverage report**: `pytest --cov=src --cov-report=term-missing`

### Test Types

| Type | Location | Requirements |
|------|----------|-------------|
| Unit | `tests/unit/` | Mock all external dependencies |
| Integration | `tests/integration/` | Test components together with real backends |
| End-to-end | `tests/e2e/` | Full simulation run with verification |

### Test Patterns

- One test file per source module: `tests/unit/test_{module}.py`
- Use fixtures for common setup
- Parametrize tests for edge cases
- Tests must be deterministic (fixed seeds for random operations)

```python
# Example test structure
def test_specialization_index_computation():
    agent_roles = {"agent_1": "miner", "agent_2": "miner", "agent_3": "crafter"}
    result = compute_specialization_index(agent_roles)
    assert 0.0 <= result <= 1.0
    assert result == pytest.approx(0.636, rel=1e-3)
```

## Documentation Standards

- **Docstrings**: Google style for all public functions and classes
- **Architecture docs**: Update `ARCHITECTURE.md` for any architectural changes
- **Research docs**: Update `RESEARCH.md` when adding new metrics or modifying methodology
- **README**: Update if CLI or quickstart changes
- **Inline comments**: Use sparingly; prefer clear code over comments

### Docstring Example

```python
def compute_specialization_index(role_counts: dict[str, int]) -> float:
    """Compute the specialization index from role assignment counts.

    The specialization index is the normalized entropy of the role
    distribution. Values near 1 indicate high specialization; values
    near 0 indicate all agents share the same role.

    Args:
        role_counts: Mapping from role name to number of agents
                     assigned that role.

    Returns:
        Float in [0, 1] representing specialization level.
    """
```

## PR Review Process

1. **Open PR** against `main` branch with descriptive title and body
2. **CI must pass**: lint, type check, test, coverage
3. **Review requirements**:
   - At least one maintainer review required
   - All review comments must be addressed before merge
   - Changes should not decrease code coverage
4. **Merge**: Squash-merge with conventional commit message

### PR Template

```markdown
## Summary
Brief description of changes.

## Related Issue
Fixes #(issue)

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactoring
- [ ] Test

## Testing
Describe testing strategy and results.

## Checklist
- [ ] Tests pass
- [ ] Coverage maintained or improved
- [ ] Linting and type checks pass
- [ ] Documentation updated
```

## How to Report Issues

- **Bug reports**: Include Python version, OS, full traceback, and steps to reproduce
- **Feature requests**: Describe the use case, proposed behavior, and any relevant prior work
- **Research questions**: Open an issue with the `research` label
