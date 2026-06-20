# @refle/sdk

Typed TypeScript client surface for the refle API, **generated from the API's OpenAPI
schema** — the API (`services/api`) is the single source of truth.

Regenerate after changing API endpoints:

```bash
make openapi
```

This exports `openapi.json` from the FastAPI app and runs `openapi-typescript` to produce
`schema.d.ts`. Both are committed so consumers don't need a running API to typecheck.
