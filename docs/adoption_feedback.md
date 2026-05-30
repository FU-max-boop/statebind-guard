# Adoption And Feedback

StateBind Guard needs real workflow pressure, not only local examples. The most useful feedback is specific and small.

## Report Adoption

Open an adoption report when you try StateBind Guard in a repository, even if you decide not to keep it.

Include:

- repository or workflow type
- setup path used
- whether you adopted, removed, or are still evaluating
- friction, false positives, or missing integrations
- whether it caught or clarified a real handoff issue

## Report Failure Cases

Open a failure-case issue for sanitized examples where a resumed agent could act on the wrong object.

Useful cases include:

- wrong file
- wrong test
- wrong commit or SHA
- wrong PR or issue
- stale artifact
- wrong branch
- wrong working directory
- risky command

## What Not To Share

Do not post private code, secrets, customer data, proprietary traces, local machine paths, or unreleased research material. Reduce examples to the smallest visible handles and expected StateBind repair.

## Good Feedback Shape

```text
Failure type: wrong test
Visible handles: pytest tests/test_api.py::test_stream, make test
Bad handoff: rerun the previous test
Expected binding: failing_test -> pytest tests/test_api.py::test_stream
Impact: resumed agent ran the broad suite and missed the focused regression
```

