# Linux portable ledger v1

## Status

Laboratory contract for the demonstration ledger. It does not change permit, reservation, budget, audit, or migration rules.

## Owner lock

| Platform | Lock | Released by |
| --- | --- | --- |
| Windows (`os.name == "nt"`) | `msvcrt.locking` of one byte, non-blocking | closing the descriptor, or process death |
| Linux (`os.name == "posix"` with `fcntl.flock`) | `LOCK_EX \| LOCK_NB`, plus an in-process `(st_dev, st_ino)` registry | closing the descriptor, or process death |
| Anything else | none; construction fails before creating a file | not applicable |

The sidecar remains `processing.owner`. A second coordinator cannot open the ledger while the lock is held. The SQLite row, not the lock, remembers `held` and `consumed`.

## SQLite

- `journal_mode=WAL`
- `synchronous=FULL` on initialize and on every write connection
- `busy_timeout=100`
- `BEGIN IMMEDIATE` for writes
- `foreign_keys=ON` and `trusted_schema=OFF`

`NORMAL` and `OFF` are not used. A checkpoint is not required before a backup: the backup API copies a consistent snapshot into a new file and does not copy a live `-wal`.

## Storage

The demonstration store is `/var/lab/ledger/<profile>` on the profile's named volume. Peru uses `platform-pe-data`. Spain uses `platform-es-data`. NFS and the other network filesystems named by the runner are rejected. The two profiles do not share a database, a permit, or a review file.

## Provider

`live_egress_enabled` stays false. `request_real_provider_send` stays closed. A key present in the environment does not change either check. The demonstration transport is an intercepted client, and the container probe must fail to connect to the provider.

## Repeated consume

`consume_remote_reservation` still requires one updated `held` row. A second call does not change that row and does not release it. `require` has always mapped the reason `replay_denied` to `ExecutionError("internal_failure")` because that reason is not in the execution-error set. The evaluation API returns `replay_denied`. This increment does not change either response.

## Procedure

Build and start with `infra/platform-001/up.ps1`. Run one profile with `run-e2e.ps1` or `run-e2e.sh`. Read it after a restart with `recover.ps1` or `recover.sh`. Copy the backup with `backup.ps1` or `backup.sh`. Stop with `down.ps1`, which does not delete volumes. A Linux host uses the shell scripts. This is one coordinator per ledger file, not a distributed production deployment.

## References

- [ADR-107](../adr/ADR-107-linux-portable-ledger.md)
