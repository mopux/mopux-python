# Releasing

A `vX.Y.Z` tag starts the release: GitHub Actions builds the package and publishes it to PyPI with trusted publishing (OIDC, no tokens), then creates the GitHub release.

## Steps

1. Update the version in `pyproject.toml` and `src/mopux/_version.py`, then run `uv lock`.
2. Move the `Unreleased` notes of `CHANGELOG.md` under `## X.Y.Z - YYYY-MM-DD`.
3. Check locally: `uv run ruff check src tests scripts && uv run mypy src && uv run pytest`.
4. Commit (`chore: versión X.Y.Z`), tag and push the branch and the tag:
   ```sh
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push --atomic origin main vX.Y.Z
   ```
5. The `release` workflow checks that the tag matches the package version, runs the checks, builds, publishes to PyPI (environment `pypi`) and creates the GitHub release.
6. Check https://pypi.org/project/mopux/.

## If something fails

- **Tag and version differ:** the workflow stops before publishing. Fix the version, delete the tag locally and on origin, and tag again.
- **PyPI rejects the upload:** check the trusted publisher on PyPI: `mopux/mopux-python`, workflow `release.yml`, environment `pypi`.
- **Re-run:** `gh run rerun <run-id> --failed -R mopux/mopux-python`.
