+++
title = "gVisor Just Joined the CNCF: What It Is, Why It Exists, and How We Used It"
date = 2026-10-20
draft = false
summary = "Google has donated gVisor — its userspace kernel for sandboxing containers — to the CNCF. Here's what gVisor actually is, how its Sentry/Gofer/runsc architecture gives you a real security boundary around a container, what it's good for, and how we wired runsc into containerd as a RuntimeClass to sandbox untrusted, multi-tenant workloads."
tags = ["gvisor", "kubernetes", "security", "containers", "cncf"]
showTableOfContents = true
+++

On **October 2, 2026**, Google announced it is donating **gVisor** — the project, its name, and its trademarks — to the Cloud Native Computing Foundation. The CNCF application was accepted on September 28, 2026, and gVisor is moving into the CNCF Sandbox, with its CI shifting to GitHub Actions/Buildkite and maintainership opening up beyond Google. It's the same path Kubernetes took, which Google also seeded.

gVisor has been open source under Apache 2.0 since 2018 and quietly runs a lot of serious infrastructure (it's the sandbox behind Google Cloud Run and GKE Sandbox). The CNCF move is a good excuse to explain what it is, why it exists, and — the useful part — how we actually used it.

## The problem gVisor solves: containers aren't a security boundary

The uncomfortable truth about containers: **a container is not a strong security boundary.** Every container on a host shares the **same Linux kernel**. Namespaces and cgroups isolate *what a process can see and use*, but every container still makes syscalls directly against that one shared kernel. The kernel's syscall surface is enormous — hundreds of calls, many with a long history of privilege-escalation and container-escape CVEs.

So if you run **untrusted or multi-tenant workloads** — customer-supplied code, CI jobs from pull requests, AI-generated code, anything you didn't write — a single kernel vulnerability can mean one tenant breaking out of its container and reaching the host or its neighbours. Namespaces don't stop that; they weren't designed to.

The classic fix is a VM per workload (strong isolation, heavy cost). gVisor is the middle path: **much of a VM's isolation, closer to a container's speed and density.**

## What gVisor actually is: a userspace kernel

gVisor puts a **second kernel, written in Go, in userspace, between the container and the host kernel.** The container never talks to the host kernel directly. Instead:

```text
   Container process
        │  makes a syscall
        ▼
   gVisor  ── Sentry (a userspace "guest kernel")
        │     implements the syscall itself
        ▼
   Host Linux kernel  ── sees only a tiny, tightly-filtered set of syscalls
```

Two components do the work:

- **Sentry** — the heart of gVisor. It's a userspace application kernel that **intercepts the container's syscalls and implements them itself** — the filesystem, networking, signals, memory, process model. The container thinks it's talking to Linux; it's actually talking to Sentry. Sentry itself runs heavily sandboxed (seccomp-filtered) so even *it* can only make a small, locked-down set of real host syscalls.
- **Gofer** — a separate host process that brokers filesystem access. Sentry can't just open host files; it goes through the Gofer over a narrow protocol, so filesystem access is mediated and constrained.

The effect: the container's ~300-syscall attack surface against the host kernel collapses to a tiny, filtered set that Sentry is allowed to make. A kernel exploit in the container now has to first get through Sentry — a far smaller, defensively-written target — before it ever reaches the real kernel.

## runsc: it looks just like a normal container runtime

The thing that makes gVisor *usable* is that it speaks **OCI**, the same runtime standard as runc. gVisor's runtime binary is **`runsc`** ("run sandboxed container"), a drop-in OCI runtime. containerd and Docker already know how to call an OCI runtime, so adopting gVisor is mostly a matter of pointing them at `runsc` instead of (or alongside) `runc`.

That's the key practical point: **you don't rewrite your workloads.** The same OCI image runs under `runsc`; it just runs inside the Sentry sandbox instead of directly on the host kernel.

## What it's good for (and what it costs)

**Good fit:**

- **Multi-tenant platforms** — running many customers' workloads on shared nodes where a container escape would be a cross-tenant breach.
- **Untrusted code execution** — CI from forked PRs, user-submitted code, AI-agent-generated code, plugin/extension sandboxes, online code runners.
- **Defense-in-depth for sensitive workloads** — an extra boundary even for code you mostly trust.

**The trade-offs — be honest about them:**

- **Syscall-heavy and I/O-heavy workloads pay a tax.** Because Sentry intercepts and re-implements syscalls, workloads that do a lot of them (heavy filesystem I/O, lots of small network ops) see measurable overhead. CPU-bound work is barely affected; syscall-bound work can be.
- **Not 100% Linux-compatible.** Sentry implements a large majority of the Linux syscall surface, but not all of it, and some edge-case behaviours differ. Most apps run unmodified; some that poke at obscure kernel features won't.
- **No GPU/host-device passthrough by default**, and some low-level features (certain `/proc` entries, niche syscalls) aren't available. Test your actual workload.

The right mental model: **you spend some performance and some compatibility to buy a real isolation boundary.** For untrusted multi-tenant workloads, that's a trade you happily make; for a trusted, latency-critical database, it usually isn't.

## How we used it: sandboxing untrusted workloads via a containerd RuntimeClass

Our use case was the textbook one: running **workloads we didn't fully trust on shared, multi-tenant nodes**, where a container escape would cross a tenant boundary. Namespaces alone weren't an acceptable boundary for that, and a full VM per workload was too heavy for the density we needed. gVisor was the fit.

### 1. Install the runtime on the nodes

`runsc` and the containerd shim get installed on each node that will run sandboxed workloads (we scoped this to a dedicated node pool rather than every node, so only untrusted workloads pay the overhead).

```bash
# gVisor ships runsc + the containerd shim (containerd-shim-runsc-v1).
# Installed onto the node and placed on PATH.
runsc --version
```

### 2. Register gVisor as a containerd runtime

containerd is told about a second runtime handler named `runsc`, alongside the default `runc`:

```toml
# /etc/containerd/config.toml
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runsc]
  runtime_type = "io.containerd.runsc.v1"
```

```bash
sudo systemctl restart containerd
```

### 3. Expose it to Kubernetes as a RuntimeClass

Kubernetes' **RuntimeClass** is exactly the abstraction for "this pod should use a different runtime." We created one that maps to the `runsc` handler:

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: gvisor
handler: runsc            # matches the containerd runtime name above
```

### 4. Opt the untrusted workloads into the sandbox

Now sandboxing a workload is one line in the pod spec — `runtimeClassName: gvisor`. Everything else about the pod is unchanged:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: untrusted-job
  namespace: tenant-workloads
spec:
  runtimeClassName: gvisor      # run this pod inside the gVisor sandbox
  nodeSelector:
    workload: sandboxed         # land on the dedicated runsc node pool
  containers:
    - name: job
      image: registry.example.com/tenant/job:1.2.0
      securityContext:          # defense in depth: gVisor AND a tight securityContext
        runAsNonRoot: true
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities: { drop: ["ALL"] }
```

Trusted platform workloads kept running under the default `runc` (no overhead); only the untrusted, multi-tenant pods got `runtimeClassName: gvisor`. That selectivity matters — you pay gVisor's cost only where you're buying isolation.

### 5. Verify the sandbox is real

The useful sanity check: a pod running under gVisor sees **Sentry's kernel**, not the host kernel. `dmesg` and the kernel version give it away:

```bash
# In a normal (runc) pod: the host's real kernel version.
# In a gVisor pod: a gVisor/Sentry identity string instead.
kubectl exec -it untrusted-job -n tenant-workloads -- uname -a
# ... gVisor ...

kubectl exec -it untrusted-job -n tenant-workloads -- dmesg | head
# Starting gVisor...
```

If `uname`/`dmesg` report gVisor rather than the node's kernel, the workload is genuinely running against Sentry — the isolation boundary is in place.

## How it fits with the rest of your hardening

gVisor isn't a replacement for the usual [Kubernetes hardening](/posts/kubernetes-securitycontext-kyverno/) — it's another layer under it. We still applied a restricted `securityContext`, dropped all capabilities, and enforced network default-deny with NetworkPolicy on those pods. gVisor adds the kernel-isolation layer that `securityContext` can't provide: even if the workload is malicious and finds a kernel bug, it's attacking Sentry, not the host. Defense in depth — the pod is locked down *and* the kernel surface it can reach is tiny.

## Why the CNCF move matters

gVisor was already production-grade, but it was a Google-run project. Moving it to the CNCF — neutral governance, non-Google maintainers, community CI — is what makes it safe to bet on long-term as *infrastructure*, the same way Kubernetes became safe to bet on after Google handed it to the CNCF. For anyone running untrusted or multi-tenant workloads on Kubernetes, gVisor just became a more durable choice for the hardest part of container security: making the container an actual boundary.

## Takeaways

- **Containers share the host kernel; that's not a security boundary.** For untrusted or multi-tenant workloads, a kernel bug is a cross-tenant breach waiting to happen.
- **gVisor is a userspace kernel (Sentry) that intercepts a container's syscalls**, shrinking the host-kernel attack surface to a tiny filtered set — VM-like isolation at closer-to-container cost.
- **`runsc` is a drop-in OCI runtime**, so adoption is plumbing (containerd runtime + Kubernetes RuntimeClass), not a rewrite — flip it on per-pod with `runtimeClassName: gvisor`.
- **Use it selectively** on the workloads that need isolation; mind the syscall/I/O overhead and the compatibility edges.
- **It's a layer, not a replacement** — pair it with securityContext and NetworkPolicy for real defense in depth.
- **Now a CNCF project**, gVisor has the neutral governance that makes it a durable long-term bet.

---

*Written shortly after the October 2026 CNCF donation announcement. Commands and manifests are illustrative — pin versions and test your actual workloads under `runsc` before relying on it.*
