# Security Policy

StateBind Guard is a public alpha for coding-agent handoff validation. It is not
a sandbox, permission system, or secret scanner.

## Supported Versions

The `main` branch is the supported development line until the first tagged
release.

## Reporting A Problem

Please open a GitHub issue for ordinary bugs. For a sensitive report, avoid
posting secrets, private logs, or proprietary handoff traces in public issues.

## Safety Boundary

StateBind Guard can reject unsafe handoff shape, such as vague handles or
missing evidence. It cannot prove that a command is safe to run, that a patch is
correct, or that a repository contains no secrets.

Before using a generated handoff in production:

1. Verify bound files, commands, commits, PRs, and artifacts against live state.
2. Remove private paths, credentials, and customer data.
3. Treat low-confidence bindings as blockers unless a human or trusted runtime
   verifies them.
