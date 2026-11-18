# ADR-107 — Portable ledger lock for the Linux demonstration

## Status

Accepted for this laboratory increment. It does not authorize a Hetzner deployment, a public staging environment, a live model call, or a replacement of SQLite by PostgreSQL, Redis, or Kafka.

## Context

TASK-C02 closed the durable ledger to Windows. `SQLiteExecutionLedger` rejected every other `os.name` before opening a file, and the owner sidecar used `msvcrt.locking`. That lock is a kernel byte lock. It is released when the file descriptor closes or the process dies. It is not a SQLite limitation. WAL, `busy_timeout`, and `BEGIN IMMEDIATE` were already in the ledger.

PLATFORM-001 therefore kept LangGraph on the Windows host. Federation, the AI service, and Keycloak already ran in Linux containers. ADR-105 records that earlier shape and leaves a later increment free to adapt the lock.

## Decision

1. Windows keeps `msvcrt.locking` with `LK_NBLCK`. Linux uses non-blocking exclusive `fcntl.flock` on the same sidecar. An in-process registry of `(st_dev, st_ino)` rejects a second open in the same process when `flock` does not. Any other `os.name` still fails before a file is created. A POSIX process that cannot import `fcntl` fails the same way.
2. The reservation contract is unchanged. One row is inserted as `held`. A second evaluation is `replay_denied`. `consume` moves `held` to `consumed` and requires one updated row. A failure after the hold leaves the row held. Restart does not release it. A budget outside the deployment minimum and the permit ceiling inserts nothing.
3. Each write sets `PRAGMA synchronous=FULL`. `journal_mode` stays `WAL`. `busy_timeout` stays 100 milliseconds. Writes stay `BEGIN IMMEDIATE`. Durability is not weakened for speed.
4. The demonstration ledger lives on the named volumes `platform-pe-data` and `platform-es-data`, mounted at `/var/lab`. Peru and Spain do not share that directory. A network filesystem, including NFS, is rejected. A Windows bind mount is not the portability store.
5. Each AI container runs its own LangGraph. The runner refuses to start unless `PLATFORM_IN_CONTAINER=true`, `os.name` is `posix`, and `/.dockerenv` exists. The model policy still refuses a real send. An API key in the environment does not open that policy. The container probe still requires the provider socket to fail.
6. A backup uses SQLite's backup API and is restored only into an isolated directory. It is not copied over the live ledger or over historical evidence.

## Consequences

The owner lock still admits one coordinator process. A second process is blocked while the owner is alive. After the owner closes or dies, the durable row is what prevents a second consumption. Uncoordinated writers that bypass the owner lock remain outside this guarantee. `NET_ADMIN` and deletion of the default route remain a laboratory control, not the proof that a provider call is impossible.

A second direct `consume` still raises `ExecutionError("internal_failure")`. That mapping predates this increment: `replay_denied` is not an execution-error reason. The row stays `consumed`, and a later evaluation returns `replay_denied`. The execution commands are in the platform demonstration guide.

This increment does not deploy the stack. Docker Desktop is the verification host.

## References

- [linux-001-portable-ledger-v1](../contracts/linux-001-portable-ledger-v1.md)
- [ADR-105](ADR-105-platform-001-local-demonstration.md)
- [platform-001](../demos/platform-001.md)
