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

`tools/protection.json` sets `allow_force_pushes: true`, so the reset needs **no** protection
change — measured on this repository with protection enabled, `enforce_admins: true` and the
`gates` check required:

```bash
git push --force origin <base-sha>:main
```

```
 + 1ee7e21...3d9858f 3d9858f -> main (forced update)      exit 0
```

Do not take protection down to do this. Deleting and re-adding it opens a window in which a
failed step leaves `main` unprotected, and the window is unnecessary.

Note the asymmetry, because it is easy to read one result as the other: an **ordinary** push to
`main` *is* refused while the required check has not passed on the pushed commit —

```
 ! [remote rejected] main -> main (protected branch hook declined)
```

— while a **force**-push is permitted by `allow_force_pushes`. Only the force-push is the reset
path. And `git push … | tail` will report the failure as a success, because `$?` after a pipe is
`tail`'s status; run the push so its own exit code is visible.

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

Close the PRs a run left open, delete its branches, and close its issues, so the next run's
Preflight sees a clean graph. These commands **do** the deletion — the listing forms are the first
line of each pipeline, and running only those changes nothing:

```bash
# close every open PR and delete its head branch
for n in $(gh pr list -R EmileK33/factory-testbed --state open --json number --jq '.[].number'); do
  gh pr close "$n" -R EmileK33/factory-testbed --delete-branch
done

# delete any branch the loop above missed (a branch with no PR)
for ref in $(gh api repos/EmileK33/factory-testbed/git/refs/heads --jq '.[].ref'); do
  case "$ref" in refs/heads/main) continue;; esac
  gh api -X DELETE "repos/EmileK33/factory-testbed/git/$ref"
done

# close every open issue
for n in $(gh issue list -R EmileK33/factory-testbed --state open --json number --jq '.[].number'); do
  gh issue close "$n" -R EmileK33/factory-testbed
done
```

Then confirm, rather than assuming the loops ran:

```bash
gh pr list -R EmileK33/factory-testbed --state open --json number --jq 'length'
gh issue list -R EmileK33/factory-testbed --state open --json number --jq 'length'
gh api repos/EmileK33/factory-testbed/git/refs/heads --jq '[.[].ref] | length'
```
