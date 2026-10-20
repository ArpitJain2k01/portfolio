+++
title = "End-to-End Kubernetes Hardening: securityContext, NetworkPolicy, RBAC, and Policy-as-Code with Kyverno"
date = 2026-10-17
draft = false
summary = "A complete, production-tested walkthrough of hardening Kubernetes clusters: pod/container securityContext, service-account token hygiene, least-privilege RBAC, image provenance, network default-deny, and enforcing all of it as fail-closed policy with Kyverno — plus the audit-first rollout discipline that keeps it from causing an outage. Grounded in work that moved CIS and Kubernetes security compliance from the ~40% range to 80%+."
tags = ["kubernetes", "security", "kyverno", "networkpolicy", "rbac", "cis", "devsecops"]
showTableOfContents = true
+++

Most Kubernetes clusters ship wide open. A default pod runs as root, can escalate privileges, has a writable root filesystem, carries Linux capabilities it will never use, auto-mounts a service-account token it doesn't need, sits on a flat network where it can reach every other pod, and pulls images from anywhere on the internet. Each of those is a rung an attacker climbs after the first foothold.

Hardening is about removing those rungs — systematically, measurably, and in a way that **stays** removed. This post is the end-to-end version: every layer worth hardening, why it matters, the concrete config, how to enforce it as policy with [Kyverno](https://kyverno.io/), and — the part that actually determines success — the rollout discipline that lets you do all of this on a *running* cluster without causing an outage.

It's drawn from real cluster-hardening work that moved CIS Level 2 server compliance from the ~35–50% range to 85%+ and Kubernetes security compliance from ~40% to 80%, across clusters running real production workloads and third-party operators.

## The model: defend in layers, enforce at admission

Think of it as two axes.

**The layers** (what you harden):

1. **Workload security context** — how much power a container has over its own host and kernel.
2. **Service-account token hygiene** — whether a pod carries a credential to the Kubernetes API it never uses.
3. **RBAC** — what identities can do to the cluster.
4. **Image provenance** — where images are allowed to come from, and whether they're pinned.
5. **Network reachability** — which pods can talk to which.
6. **Scheduling & availability** — probes, resource limits, and anti-affinity that keep hardening from becoming fragility.

**The enforcement** (how it stays done): an admission controller — Kyverno — that evaluates every create/update *before* it's persisted. A guideline rots the moment someone copies an old manifest under deadline pressure. A policy doesn't.

The rest of this post walks each layer, then the Kyverno enforcement and the rollout plan that ties it together.

## Layer 1 — Workload security context

The `securityContext` is the single highest-value, lowest-effort boundary. Here's a fully hardened pod; every line earns its place.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  template:
    spec:
      automountServiceAccountToken: false   # Layer 2 — see below
      securityContext:                        # pod level
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 3000
        fsGroup: 2000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: api
          image: registry.example.com/api:1.4.2   # pinned, never :latest
          securityContext:                    # container level
            allowPrivilegeEscalation: false
            privileged: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 512Mi }
          livenessProbe:
            httpGet: { path: /healthz, port: 8080 }
          readinessProbe:
            httpGet: { path: /readyz, port: 8080 }
```

Why each one:

- **`runAsNonRoot: true` + `runAsUser`** — if the process is compromised, it isn't root inside the container, so a breakout has far less to work with.
- **`allowPrivilegeEscalation: false`** — blocks `setuid` binaries and similar tricks from gaining more privilege than the parent. The single most important container-level flag.
- **`privileged: false`** — a privileged container is effectively root on the node. There is almost never a legitimate reason for an application workload to be privileged.
- **`readOnlyRootFilesystem: true`** — an attacker can't drop a binary or modify the app on disk. Anything that needs to write gets an explicit `emptyDir` mount, so writable paths are a deliberate, visible decision.
- **`capabilities.drop: ["ALL"]`** — most apps need zero Linux capabilities. Drop everything, then add back only what's genuinely required (usually nothing). `NET_BIND_SERVICE` is the common exception for binding ports < 1024 — and even that you can avoid by listening on a high port.
- **`seccompProfile: RuntimeDefault`** — restricts syscalls to the runtime's sane default set. Cheap, broadly compatible, and closes a large attack surface.
- **No host namespaces / hostPath** — not shown above because the answer is simply *don't*: `hostNetwork`, `hostPID`, `hostIPC`, and `hostPath` volumes all punch holes in the container boundary. Reserve them for genuine node-level agents, never application workloads.

These map almost one-to-one onto the Kubernetes **Pod Security Standards** `restricted` profile and the CIS Kubernetes Benchmark — which is why hardening here moves a compliance score directly.

## Layer 2 — Service-account token hygiene

Every pod, by default, gets a mounted token for the `default` service account. Most workloads never call the Kubernetes API — so that token is pure attack surface: steal it, and you can talk to the API as that service account.

The fix is to stop mounting it unless it's needed:

```yaml
# On the pod spec (or the ServiceAccount) for anything that doesn't call the API:
automountServiceAccountToken: false
```

In practice this has a nuance worth knowing: you can set it on the **ServiceAccount** *and* on the **pod**, and the pod-level setting wins. A clean pattern is to default the service account to `false` and only opt specific pods back in to `true` when they genuinely use the API (controllers, operators, anything with a client-go client). Workloads that just serve traffic get no token at all.

This was one of the higher-churn parts of real hardening work — many components mount the token by habit, not need — but it's also one of the clearest wins: a stolen token for a pod that has no API permissions is worthless.

## Layer 3 — Least-privilege RBAC

Hardening the pod is wasted if its service account is cluster-admin. Two rules carry most of the value:

- **No wildcards.** A Role or ClusterRole with `verbs: ["*"]`, `resources: ["*"]`, or `apiGroups: ["*"]` is a blank cheque. Enumerate exactly the verbs and resources a component needs.
- **Namespace-scope by default.** Prefer `Role`/`RoleBinding` (namespaced) over `ClusterRole`/`ClusterRoleBinding`. A component that only operates in its own namespace should not have cluster-wide reach.

Two frequent, high-impact findings:
- **Shared "god" service accounts.** Several components binding to one over-privileged SA (e.g. a shared `cloud-controller` with `* / * / *`) means a compromise of the least-important one grants the union of everyone's permissions. Give each component its own SA with only its own rights.
- **Secret read access.** Roles that can `get`/`list` secrets cluster-wide are a prime exfiltration path. Scope secret access to the specific namespaces and names that need it.

Decommissioning wildcards is delicate — you can break a controller that silently relied on broad access — so it's exactly the kind of change you make in **audit** first (below) and validate against real behaviour before enforcing.

## Layer 4 — Image provenance

Two cheap, high-value controls:

- **Allowlist registries.** Only pull from registries you trust (your mirror/registry, Red Hat, etc.). This blocks a typo-squatted or attacker-controlled public image from ever running, and in a disconnected environment it enforces that everything comes from the internal mirror.
- **Ban the `:latest` tag.** `:latest` makes rollouts non-reproducible, defeats rollback, and means two nodes can run different code under the same tag. Require pinned, immutable tags (ideally digests).

## Layer 5 — Network reachability: default-deny

A hardened pod still sits on a flat network by default — **any pod can talk to any other pod**, so a single compromised container can reach your database, scrape internal services, or exfiltrate data laterally. `securityContext` locks down the *inside* of a pod; NetworkPolicy locks down what it can *reach*. You need both.

The foundational move is **default-deny per namespace**, then explicitly allow only what each app needs. Deny ingress *and* egress:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: app
spec:
  podSelector: {}                 # all pods in the namespace
  policyTypes: ["Ingress", "Egress"]   # no rules below ⇒ all ingress + egress denied
```

Then open exactly what's required — the database accepts traffic only from the API, on one port:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: db-allow-from-api
  namespace: app
spec:
  podSelector:
    matchLabels: { app: postgres }
  policyTypes: ["Ingress"]
  ingress:
    - from:
        - podSelector:
            matchLabels: { app: api }
      ports:
        - { protocol: TCP, port: 5432 }
```

Two things people get wrong:

- **Egress is where exfiltration lives.** A default-deny *ingress* policy still lets a compromised pod call out to a C2 server or copy data out. Denying egress (and allowing only the specific destinations an app needs) is what actually closes that path.
- **DNS is the first thing you'll break.** The moment you deny egress, pods can't resolve names until you explicitly allow UDP/TCP **53** to the cluster DNS. Allow it in the same change, or everything "mysteriously" fails:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: app
spec:
  podSelector: {}
  policyTypes: ["Egress"]
  egress:
    - to:
        - namespaceSelector:
            matchLabels: { kubernetes.io/metadata.name: kube-system }
      ports:
        - { protocol: UDP, port: 53 }
        - { protocol: TCP, port: 53 }
```

> One environment-specific caveat from real rollouts: a cluster-wide default-deny has to account for your CNI's own traffic and node/pod CIDRs — porting a working policy between clusters verbatim will break if the node CIDRs differ. Validate per cluster.

## Layer 6 — Availability controls (so hardening doesn't become fragility)

Hardening and reliability pull in the same direction if you let them:

- **Liveness & readiness probes** — required so the platform can tell a wedged pod from a healthy one. (Caveat: enforce these carefully — a probe policy flipped to Enforce can block pod restarts for anything that lacks probes, including vendor workloads. More on that below.)
- **Resource requests & limits** — stop one workload from starving a node; also a scheduling-fairness and DoS-containment control.
- **Multiple replicas + topology spread / anti-affinity** — so a single node loss doesn't take a service down. Hardening a single-replica app is polishing a single point of failure.

## Turning it all into policy with Kyverno

Everything above is a *guideline* until something enforces it on every deployment. [Kyverno](https://kyverno.io/) is a policy engine that runs as a Kubernetes admission controller, evaluating every create/update against your rules before the object is persisted — authored in YAML, no new language.

A **validate** policy rejects (or audits) non-compliant resources. Example — require `allowPrivilegeEscalation: false` on every container:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privilege-escalation
spec:
  validationFailureAction: Audit     # Audit first; flip to Enforce later
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

A **generate** policy *creates* resources — e.g. drop a default-deny NetworkPolicy into every new namespace so none ever ships wide open:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-deny
spec:
  rules:
    - name: default-deny-per-namespace
      match:
        any:
          - resources:
              kinds: ["Namespace"]
      generate:
        apiVersion: networking.k8s.io/v1
        kind: NetworkPolicy
        name: default-deny
        namespace: "{{request.object.metadata.name}}"
        synchronize: true
        data:
          spec:
            podSelector: {}
            policyTypes: ["Ingress", "Egress"]
```

### A baseline policy set

A practical starting set — each one maps to a layer above and to Pod Security Standards / CIS controls:

| Policy | Control | Layer |
|---|---|---|
| disallow-privileged-containers | no privileged pods | 1 |
| disallow-privilege-escalation | `allowPrivilegeEscalation: false` | 1 |
| require-run-as-non-root | `runAsNonRoot: true` | 1 |
| require-drop-all-capabilities | `capabilities.drop: ["ALL"]` | 1 |
| require-ro-rootfs | `readOnlyRootFilesystem: true` | 1 |
| require-seccomp-profile | `seccompProfile: RuntimeDefault` | 1 |
| disallow-host-namespaces | no `hostNetwork`/`hostPID`/`hostIPC` | 1 |
| disallow-host-path | no `hostPath` volumes | 1 |
| disallow-sa-token-automount | `automountServiceAccountToken: false` | 2 |
| restrict-wildcard-rbac | no `*` verbs/resources | 3 |
| restrict-image-registries | allowlisted registries only | 4 |
| disallow-latest-tag | pinned tags only | 4 |
| require-default-deny-netpol | default-deny per namespace | 5 |
| require-pod-probes | liveness + readiness present | 6 |
| require-resource-limits | requests + limits present | 6 |

That's ~15 policies; a mature set runs closer to 18–20 with finer-grained variants. Together they take a cluster from "default-open" to Pod-Security-`restricted`-equivalent, enforced on every admission.

## The rollout order that saves you

This is the part that decides whether a hardening project lands or gets rolled back after it causes an incident.

The mistake: flipping straight to `Enforce` on a running cluster. You will instantly block pod restarts for every workload that doesn't already comply — **including things you didn't write**, like vendor charts, operators, and CNI components. A node drain at 2am then can't reschedule those pods, and your security policy just caused an outage.

The safe sequence, per policy:

1. **Deploy every policy as `Audit` first.** Nothing is blocked; violations are recorded.
2. **Read the policy reports** to see exactly what violates what:

   ```bash
   kubectl get policyreport -A
   kubectl get clusterpolicyreport
   ```
3. **Fix your own workloads** to comply.
4. **Add scoped, documented exclusions** for the things you legitimately can't change yet — vendor images, operators that genuinely need a capability, system components. Exclusions are explicit and reviewable, matched narrowly (by namespace or name prefix), never a blanket "off."
5. **Flip to `Enforce` one policy at a time**, watching for rejections, starting with the safest (e.g. `disallow-privileged-containers`) and leaving the riskiest for last.

The two policies most likely to cause pain, from experience:

- **`readOnlyRootFilesystem`** — many apps write to disk without declaring an `emptyDir`; expect to add volumes.
- **`require-pod-probes`** — flipping this to Enforce can block restarts for anything lacking probes (often third-party pods). Keep it in **Audit**, add probes to the charts you own, and only then enforce. In real rollouts this one stayed Audit the longest.

Keep a couple of policies permanently in Audit if enforcing them would block legitimate platform behaviour (e.g. auditing secrets-as-env-vars while you migrate workloads to mounted secret volumes) — Audit still gives you the visibility and the compliance signal without the blast radius.

## Measuring it

Hardening you can't measure is hard to defend in a review or an audit. Point `kube-bench` (CIS Kubernetes Benchmark) and a scanner like `kubescape` or `Trivy` at the cluster before and after, and track the delta. Pair it with Kyverno's own policy reports for live, per-workload compliance. "We moved Kubernetes security compliance from ~40% to 80%" is a sentence that only exists because the before/after was measured — and it's the sentence that makes the work legible to everyone above you.

## Takeaways

- **Harden in layers, not as a single setting.** Workload `securityContext`, service-account token hygiene, least-privilege RBAC, image provenance, network default-deny, and availability controls each remove a different rung an attacker climbs.
- **`securityContext` hardens the inside of a pod; NetworkPolicy controls what it can reach.** Deny ingress *and* egress by default, allow only what's needed, and never forget the DNS egress rule.
- **A guideline rots; a policy doesn't.** Kyverno enforces every control on every admission, and `generate` policies make the secure default (like default-deny) automatic for new namespaces.
- **Always roll out Audit-first, one policy at a time, with scoped exclusions.** Flipping straight to Enforce — or dropping a default-deny-egress onto a live namespace — is how a security change becomes an outage.
- **Measure the before/after** with kube-bench / kubescape / Trivy and Kyverno reports, so the hardening is defensible and the progress is visible.

The policies are the easy part. The rollout discipline — and the measurement that proves it worked — is what makes cluster hardening something you ship to production instead of something you revert on Monday.
