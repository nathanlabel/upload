# Bug: Remote directory existence check fails without sudo password

## Summary
`create_remote_directory` validates the target directory by running `sudo -S ls <remote_dir>`, but it never feeds the sudo password to the command. As a result the check always fails on hosts that require authentication, even when the user has sudo privileges.

## Steps to Reproduce
1. Connect to a host where `sudo` prompts for a password.
2. Call `create_remote_directory(ssh_client, '/tmp/example', 'correct-password')`.

## Expected Result
The function should detect that the directory exists (exit status 0) without prompting for input, or proceed to create it if missing.

## Actual Result
The check command exits with a non-zero status because sudo does not receive the password, forcing the code to recreate the directory every time and emitting warnings.

## Impact
* Superfluous warnings about missing directories.
* Unnecessary attempts to recreate existing directories, which may confuse logs or fail for non-empty paths.

## Fix
Pipe the password into the check command (for example, `echo <password> | sudo -S test -d <remote_dir>`) so it can execute without interactive prompts. Sanitize logging so the password is never written to the logs.
