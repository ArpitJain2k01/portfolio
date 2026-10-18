+++
title = "Hardening Kubernetes Workloads with securityContext and Kyverno"
date = 2026-10-17
draft = false
summary = "A practical walk through pod and container securityContext — the settings worth enforcing, why each one matters — and how Kyverno turns them from a guideline into fail-closed policy without breaking your workloads."
tags = ["kubernetes", "security", "kyverno"]
showTableOfContents = true
+++

A `securityContext` is a threat boundary, not a checkbox. By default a container runs with far more power than it needs: as root, able to escalate privileges, with a writable root filesystem and a pile of Linux capabilities it will never use. Tightening that boundary is one of the highest-value, lowest-effort things you can do to a cluster.

This post covers two halves: **what to set** on a workload, and **how to enforce it** so a future deployment can't quietly skip it.

## The settings that matter

Here's a hardened pod spec. Every line earns its place.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  template:
    spec:
      securityContext:              # pod level
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 3000
        fsGroup: 2000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: api
          image: registry.example.com/api:1.4.2   # pinned, never :latest
          securityContext:          # container level
            allowPrivilegeEscalation: false
            privileged: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 512Mi }
```

Why each one:

- **`runAsNonRoot: true` + `runAsUser`** — if the process is compromised, it isn't root inside the container. Combined with the other settings, a container breakout has far less to work with.
- **`allowPrivilegeEscalation: false`** — blocks `setuid` binaries and similar tricks from gaining more privileges than the parent process. This is the single most important container-level flag.
- **`readOnlyRootFilesystem: true`** — an attacker can't drop a binary or modify the app on disk. Anything that needs to write gets an explicit `emptyDir` mount, so writable paths are a deliberate, visible decision.
- **`capabilities.drop: ["ALL"]`** — most apps need zero Linux capabilities. Drop everything, then add back only what's genuinely required (usually nothing). `NET_BIND_SERVICE` is the common exception for binding ports < 1024 — and even that you can avoid by listening on a high port.
- **`seccompProfile: RuntimeDefault`** — restricts the syscalls the container can make to the runtime's sane default set. Cheap, broadly compatible, and closes a large attack surface.
- **Pinned image tags + resource limits** — `:latest` makes rollouts non-reproducible and defeats rollback; missing limits let one workload starve a node.

## The problem with "just set it"

You can hand every team this YAML. Some will apply it. Some will copy an old manifest that doesn't have it. Someone, under deadline pressure, will comment out `readOnlyRootFilesystem` to make an app start and never put it back. Six months later half the cluster is hardened and half isn't, and nobody knows which half.

Guidelines decay. **Policy doesn't.** That's where an admission controller comes in.

## Enforcing it with Kyverno

[Kyverno](https://kyverno.io/) is a policy engine that runs as a Kubernetes admission controller. It evaluates every create/update against your rules *before* the object is persisted. Written in YAML — no new language to learn.

Here's a policy that requires `allowPrivilegeEscalation: false` on every container:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privilege-escalation
spec:
  validationFailureAction: Enforce   # Audit first, then flip to Enforce
  background: true
  rules:
    - name: deny-privilege-escalation
      match:
        any:
          - resources:
              kinds: ["Pod"]
      validate:
        message: "allowPrivilegeEscalation must be set to false"
        pattern:
          spec:
            containers:
              - securityContext:
                  allowPrivilegeEscalation: false
```

The important field is `validationFailureAction`:

- **`Audit`** — violations are recorded in a policy report, but the object is still admitted. Nothing breaks.
- **`Enforce`** — violations are rejected at admission. The bad deployment never lands.

## The rollout order that saves you

The mistake I see most often is flipping straight to `Enforce` on a running cluster. You will instantly block pod restarts for every workload that doesn't already comply — including things you didn't write, like vendor charts and operators. A node drain at 2am then can't reschedule those pods, and now you have an outage caused by your security policy.

The safe sequence:

1. **Deploy every policy as `Audit` first.** Nothing is blocked.
2. **Read the policy reports.** `kubectl get policyreport -A` shows exactly which workloads violate which rule.

   ```bash
   kubectl get policyreport -A
   kubectl get clusterpolicyreport
   ```
3. **Fix your own workloads** to comply, and **add scoped exclusions** for the ones you can't change yet (vendor images, operators with legitimate needs). Exclusions are explicit and reviewable — not a blanket "off."
4. **Only then flip to `Enforce`,** policy by policy, watching for rejections.

This is the difference between a hardening project that lands and one that gets rolled back after it causes an incident. Audit-first is not optional.

## What to enforce first

If you're starting from zero, this is a high-value baseline — most map directly to Kubernetes Pod Security Standards and common CIS controls:

| Control | Setting |
|---|---|
| No privileged containers | `privileged: false` |
| No privilege escalation | `allowPrivilegeEscalation: false` |
| Run as non-root | `runAsNonRoot: true` |
| Drop all capabilities | `capabilities.drop: ["ALL"]` |
| Read-only root filesystem | `readOnlyRootFilesystem: true` |
| Seccomp profile set | `seccompProfile.type: RuntimeDefault` |
| Resource limits present | `resources.limits` |
| No `:latest` image tag | pinned tags only |

Ship them all as `Audit`, clean up the reports, then enforce. The ones most likely to block real workloads are the read-only root filesystem and the probe requirements — tackle those with the most care.

## Takeaways

- A `securityContext` is a real threat boundary. Set `runAsNonRoot`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem`, `drop: ["ALL"]`, and a seccomp profile as your default, not your exception.
- A guideline that depends on humans remembering it will rot. An admission policy enforces it on every single deployment, forever.
- **Always roll out policy as Audit first.** Flipping straight to Enforce on a live cluster is how a security change becomes an outage.

That last point is the one I'd tattoo on a wall. The policies are easy; the rollout discipline is what keeps you employed.
