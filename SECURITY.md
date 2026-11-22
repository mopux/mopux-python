# Security Policy

## Supported versions

Security fixes are released for the latest minor version.

| Version | Supported |
| --- | --- |
| 0.x (latest) | Yes |

## Reporting a vulnerability

Please do not open a public issue. Report it privately through GitHub's
"Report a vulnerability" button in the Security tab of this repository.

Include the affected version, a description of the issue and, if possible, steps
to reproduce it. You will get an answer within a few working days, and a fix and
an advisory will be published once the issue is confirmed.

Vulnerabilities in the Mopux service itself (not in this client) can be reported
the same way; they will be forwarded to the Mopux team.

## Handling tokens

- Treat API tokens like passwords: keep them out of version control and logs.
- The client never logs requests or tokens, and exception messages never contain
  the token. Exceptions expose the API response; a `ConnectionException` keeps the
  underlying HTTP client exception (`getPrevious()`), which may give access to the
  original request and its headers, so do not dump it into public logs.
