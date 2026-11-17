# Laboratory review IAM

Local Keycloak 26.8.1 for the lab-summary OIDC flow. It is not the workload realm in `infra/iam-lab` and it is not production identity.

From the repository root:

```powershell
services\ai-service\.venv\Scripts\python.exe infra\lab-review-iam\prepare.py --up
```

The command writes the realm, binding file, and generated passwords under `C:\Temp\lab-review-iam\run`. Those files stay outside Git. The provider listens on `http://127.0.0.1:18294`. HTTP on that loopback address is a laboratory exception and is not acceptable in production. Keycloak 26.8.1 marks its login cookies `Secure` and SameSite=None even on this HTTP listener. A browser accepts those cookies for `127.0.0.1`; another hostname over HTTP does not.

The AI service then needs `LAB_REVIEW_IAM_ENABLED=true`, the issuer `http://127.0.0.1:18294/realms/lab-review-iam`, the matching discovery and JWKS URLs, client `lab-review-web`, redirect `http://127.0.0.1:18293/lab-review-iam/callback`, `LAB_REVIEW_IAM_ALLOW_HTTP_LOOPBACK=true`, and the generated bindings and session database paths. Do not enable `HUMAN_REVIEW_DEVELOPMENT_AUTH_ENABLED` at the same time.

Users in the generated realm: `reviewer-a`, `auditor-a`, `admin-a`, and `reviewer-b`. Their passwords are in `user-passwords.json`.
