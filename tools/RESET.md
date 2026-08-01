# Resetting the testbed

Every test tier assumes it starts from a known base commit. This repository is a throwaway, so
the reset is a force-push of that commit over `main`.

## The base commit

The base SHA is recorded by whoever set the run up; it is the commit `main` pointed at before any
agent touched the repository. Capture it before a run:

```bash
git ls-remote https://github.com/EmileK33/factory-testbed refs/heads/main
```

## Resetting

Branch protection on `main` blocks a force-push while it is enabled, so the reset is:

```bash
gh api -X DELETE repos/EmileK33/factory-testbed/branches/main/protection
git push --force origin <base-sha>:main
gh api -X PUT repos/EmileK33/factory-testbed/branches/main/protection --input tools/protection.json
```

## Confirming the reset actually reset

A reset that is not verified is discovered to be broken halfway through a benchmark repetition.
Confirm the remote tip is the base SHA, and confirm a fresh clone's tree matches it:

```bash
git ls-remote https://github.com/EmileK33/factory-testbed refs/heads/main
git clone --depth 1 https://github.com/EmileK33/factory-testbed /tmp/reset-check
git -C /tmp/reset-check rev-parse HEAD
```

Compare the two SHAs directly. Do not read "the push succeeded" as "the tree is at base": a
force-push to a protected branch fails with an exit code that is easy to lose on the left of a
pipe.

## Leftovers

Delete the branches and PRs a run created, and close its issues, so the next run's Preflight sees
a clean graph:

```bash
gh pr list -R EmileK33/factory-testbed --state open --json number --jq '.[].number'
gh api repos/EmileK33/factory-testbed/git/refs/heads --jq '.[].ref'
```
