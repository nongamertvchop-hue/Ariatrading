# Bodyguard(Aria) — Webaria UI security notes (v0.03.0)

These are client-side hygiene rules for Webaria pages. The browser is untrusted.

## Do
- Treat all API JSON as untrusted data; do not `eval` it
- Keep paper-trading state local; never send it to unknown hosts
- Prefer `textContent` over `innerHTML` when rendering API strings
- Poll market endpoints at modest intervals (already used by Advisor)

## Do not
- Store API keys in `localStorage` / `sessionStorage`
- Embed secrets in frontend bundles
- Accept `javascript:` URLs or arbitrary HTML from the network
- Build admin panels on the public static site without separate auth

## Recommended meta (optional per page)
```html
<meta http-equiv="Referrer-Policy" content="no-referrer">
<meta http-equiv="X-Content-Type-Options" content="nosniff">
```

Server already sends stronger headers via Bodyguard on API responses.
