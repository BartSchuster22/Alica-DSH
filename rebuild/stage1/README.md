# Stage 1: read-only qualification — deployment BLOCKED

This package implements the first Stage 1 host gate of `alica-dsh-rebuild/v1` (PROJECT-ALICA ADR-0020/0021). It is **not** a candidate runtime, a revised installer, a new release manifest or Stage 1 acceptance.

## Run

```sh
python3 rebuild/stage1/qualify_host.py --sudo
python3 -m unittest discover -s rebuild/stage1 -p 'test_*.py' -v
```

`--sudo` adds `sudo -n` to read-only Docker calls only. Omit when Docker access is already available. The collector uses Python stdlib, observes `/etc/os-release`, `/proc`, filesystem capacity and Docker inventory. Stdout is JSON. Exit **0** means the retained platform envelope matched; exit **3** means it did not. Neither exit authorizes deployment. It does not install dependencies, pull images, start/stop containers, execute in containers, inspect secret values or modify the host.

The policy is the inherited Debian 13/amd64/systemd, Docker >=28.4.0 <29, Compose >=2.39.4 <3, 4 vCPU, 8 GiB physical RAM and 100 GiB free-disk candidate envelope. No environment variable disables these checks. Headroom for existing workloads and measured candidate resource ceilings require a separate placement assessment even if this policy passes. Swap does not substitute for physical RAM.

Only selected ownership/image labels, mount paths, environment **names**, ports, resource limits and health status are exported. Docker environment values and health logs are omitted. Metadata can still identify infrastructure: keep live inventories in private PROJECT-ALICA, not this public distribution repository. The unit-test host fixture is synthetic and never counted as live acceptance.

## Observed result, 2026-09-09

Both inspected hosts failed the retained envelope:

- The requested target fails the OS, Docker, physical-RAM and free-disk gates.
- The engineering host also fails the Compose range.

Exact host identities, versions, resource readings, observation times and private paths are retained in PROJECT-ALICA evidence rather than published here.

All existing services/resources remain protected. Additional unlabeled runtime/database resources have characteristics matching UNIFY combined-runtime acceptance code; their live operational owner/disposal authorization is **not established**. No pruning or removal performed. Missing old temporary fixture paths are contrary evidence, not permission to delete running resources.

## Remaining work and decision

Provide a separate conforming candidate target, or explicitly authorize a revised OS/runtime/resource qualification effort. A budget/new machine and any destructive resize/reinstall are not implicitly authorized by Stage 1. Do not downgrade shared production Docker or weaken the policy to turn red into green.

Then complete ownership closure, candidate source/API compatibility, one-runtime manifest/artifact builds, fresh secrets/volumes/networks, isolated start/stop/restart tests and predecessor-preservation checks. No stub or old multi-runtime image set is installed as a substitute.

Source-image observation narrowed the Hermes discrepancy: the Dockerfile's immutable base registry metadata binds an amd64 manifest and config with revision label `b8b17b8cee50b85adb7fba6ea332dc06731b86f4`. The inherited D6 source list uses `9e54eee44f1cbbe62247a36546e51ff8940373c6`. The inspected SLSA statement resolves base dependencies but does not establish the source Git material. **Neither labels nor this registry lookup prove native API compatibility or complete source provenance.** That gate remains open.

Rollback for this package is a source-commit revert/removal of the isolated worktree. There are no deployed candidate resources to tear down. Never use blanket Docker cleanup as rollback.
