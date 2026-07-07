# Self-Hosted Core setup

Self-Hosted Core runs one Organization per instance. The first owner creates that Organization from
the login portal. After that, the portal no longer offers organization creation; new users either
sign in, request access for owner approval, or accept an invitation.

## Environment checklist

Start from `.env.example` and review these values before exposing the instance:

```bash
REFLE_EDITION=core
REFLE_DEPLOYMENT_MODE=self_hosted_core
REFLE_SECRET_KEY=change-me-to-a-long-random-value
REFLE_DATABASE_URL=postgresql+asyncpg://...
REFLE_REDIS_URL=redis://...
REFLE_CORS_ORIGINS=http://localhost:3000
REFLE_S3_ENDPOINT_URL=http://localhost:9000
REFLE_S3_ACCESS_KEY=...
REFLE_S3_SECRET_KEY=...
REFLE_S3_BUCKET=refle-evidence
```

Optional but recommended:

```bash
REFLE_SMTP_HOST=...
REFLE_SMTP_FROM=notifications@example.com
# or
RESEND_API_KEY=...

REFLE_AI_PROVIDER=local
REFLE_AI_LOCAL_BASE_URL=http://localhost:11434/v1
REFLE_AI_LOCAL_MODEL=llama3.1
```

Cloud AI providers can also be used:

```bash
REFLE_AI_PROVIDER=gemini
GEMINI_API_KEY=...

# or
REFLE_AI_PROVIDER=openai
OPENAI_API_KEY=...
```

## First run

```bash
cp .env.example .env
make install
make up
make migrate
make seed
make api
make web
```

Open `http://localhost:3000`. The onboarding screen shows configured and pending settings from
`GET /setup/status`. Create the first Organization and owner account there.

## User management

Owners manage application users from the dashboard gear:

- **Create users** directly with Owner, User, or Auditor roles.
- **Create invitations** for pending invite acceptance.
- **Approve or reject access requests** submitted from the login portal.

Application users are separate from compliance Persons. A user account is for signing in to Refle;
a Person record is for compliance workflows such as onboarding, training, access reviews, and
offboarding.
