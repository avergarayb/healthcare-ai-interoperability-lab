# Healthcare showcase v1

Local catalog for the five clinical demonstrations. It does not add an agent, a permit, or a deployment.

## Surface

`GET /showcase` and `GET /showcase/demo-001` through `GET /showcase/demo-005` return HTML on Mini HIS. `POST /ward/showcase/episode` opens one new synthetic episode for `MHS-PAT-001` when the caller is the clinician session and presents the CSRF token. An auditor receives a redirect and no episode.

## Availability

The page probes only loopback health URLs. A non-loopback URL is not available. DEMO-002 stays «Perfil aislado» until its own local health URL answers. The other four stay «No disponible» until the dependencies named in [the guide](../demos/healthcare-showcase-001.md) answer. The word READY is not a status on this page.

## Limits

The catalog does not run operating-system commands, does not delete rows, and does not mark a step complete without a stored order, correlation, result, proposal, task, episode, or documentation state. The ward session is not OIDC. Decision: [ADR-112](../adr/ADR-112-healthcare-showcase-001.md).
