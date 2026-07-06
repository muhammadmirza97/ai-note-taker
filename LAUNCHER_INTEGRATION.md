When building this app, make it launcher-friendly: read the port from `PORT` (fallback to a sensible local default), bind only to `127.0.0.1`/localhost, and print a clear ready line to stdout such as `Ready on http://localhost:{port}` once serving. If a run command needs a port flag, make it work with a `{port}` placeholder too. End your final report with this filled JSON registration block for my Windows Project Launcher:
```json
{"name":"App Name","folder":"C:/path/to/app","setup":[],"run":"command here","wants_browser":true,"port":"auto"}
```
