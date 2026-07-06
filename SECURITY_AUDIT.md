# Security Audit Notes

Last run locally:

```powershell
.\venv\Scripts\python.exe -m pip install pip-audit
.\venv\Scripts\python.exe -m pip_audit
```

Result:

```text
Name Version ID             Fix Versions
nltk 3.9.4   PYSEC-2026-597
```

The advisory feed did not list a fixed version. The app only uses NLTK data through local summarization helpers and does not expose NLTK parsing as a separate unauthenticated service. Keep NLTK pinned via the installed environment, rerun `pip-audit` before deployment, and upgrade as soon as the advisory publishes a fixed release.

Other hardening added in Phase 4:

- Email/password auth with salted PBKDF2-HMAC-SHA256 hashes.
- HTTP-only session cookie and separate CSRF cookie/header for write requests.
- Per-user ownership checks for lecture, chat, quiz, flashcard, mind-map, script, and export endpoints.
- Server-side file type and size validation.
- Basic auth and AI-generation rate limiting.
- Security headers and production HTTPS assumptions.
- No transcript bodies in application info logs.
