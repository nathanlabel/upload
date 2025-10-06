# Bug: Missing `create_ssh_client` helper

## Summary
The automated test-suite imports a public `create_ssh_client` helper from `upload.py`, but the function was removed when the `SSHConfig` class was introduced. Importing the module therefore raises `ImportError`, preventing the test-suite (and any external callers) from running.

## Steps to Reproduce
1. Install the dependencies listed in `requirements.txt`.
2. Run `pytest` from the repository root.

## Expected Result
Pytest should collect and execute the tests.

## Actual Result
Pytest aborts during collection with `ImportError: cannot import name 'create_ssh_client' from 'upload'`.

## Impact
* The automated tests fail before executing any assertions.
* Downstream scripts that still import `create_ssh_client` crash immediately, breaking backwards compatibility.

## Fix
Reintroduce the helper that creates, configures, and connects a `paramiko.SSHClient`, and have `SSHConfig` reuse it so that functionality stays in sync.
