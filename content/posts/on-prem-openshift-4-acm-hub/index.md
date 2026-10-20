+++
title = "On-Prem OpenShift, Part 4: Turning SNO into an ACM Hub and Deploying Managed Clusters"
date = 2026-10-20
draft = false
summary = "The final step: install Advanced Cluster Management on the Single Node OpenShift cluster from the on-prem mirror, turn it into a hub, and use it to provision and manage new OpenShift clusters — all disconnected. One node becomes the control point for a fleet."
tags = ["openshift", "acm", "multicluster", "gitops", "on-prem"]
showTableOfContents = true
+++

This is Part 4 — the finale — of a four-part series on building OpenShift on-prem:

1. [A Quay mirror registry in a Docker host-network container](/posts/on-prem-openshift-1-quay-registry/)
2. [Bringing up the cluster node with KVM/libvirt](/posts/on-prem-openshift-2-kvm-vm/)
3. [Installing Single Node OpenShift from the private registry](/posts/on-prem-openshift-3-sno-install/)
4. **Turning SNO into an ACM hub and deploying managed clusters** (this post)

We ended [Part 3](/posts/on-prem-openshift-3-sno-install/) with a healthy, disconnected Single Node OpenShift cluster. On its own it's just one cluster. The reason to build it carefully is this part: make it the **hub** that provisions and governs every *other* cluster, without ever reaching the internet.

## What ACM gives you

Red Hat Advanced Cluster Management (ACM) turns one cluster into a control plane for many. The pieces that matter here:

- **MultiClusterHub** — the hub itself, installed by the ACM operator.
- **The multicluster engine (MCE)** — the component that actually *creates* clusters (via Hive / the Assisted Installer running on the hub).
- **Managed clusters** — every cluster the hub provisions or imports, governed centrally.

Because we mirrored both `advanced-cluster-management` and `multicluster-engine` back in [Part 1](/posts/on-prem-openshift-1-quay-registry/), the operator can install fully from the on-prem registry.

## Installing ACM from the mirror

First, make the cluster resolve operators from the mirror, not the internet. `oc-mirror` (Part 1) emitted a `CatalogSource` and an `ImageDigestMirrorSet`/`ICSP` — apply them:

```bash
# Point the cluster's operator catalog at the mirror, and mirror image pulls.
oc apply -f oc-mirror-workspace/results-*/catalogSource.yaml
oc apply -f oc-mirror-workspace/results-*/imageContentSourcePolicy.yaml
oc get catalogsource -n openshift-marketplace
```

Then install the ACM operator and create the hub:

```yaml
# Subscribe to the ACM operator from the mirrored catalog.
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: advanced-cluster-management
  namespace: open-cluster-management
spec:
  channel: release-2.x
  name: advanced-cluster-management
  source: redhat-operator-index          # the mirrored CatalogSource
  sourceNamespace: openshift-marketplace
---
# Create the hub.
apiVersion: operator.open-cluster-management.io/v1
kind: MultiClusterHub
metadata:
  name: multiclusterhub
  namespace: open-cluster-management
spec: {}
```

```bash
oc get multiclusterhub -n open-cluster-management -w
# Wait for Status: Running — on SNO this takes a while and needs the RAM from Part 2.
```

This is where the Part 2 sizing pays off: the hub components (search, observability, the console plugins, MCE) are heavy, and a hub squeezed onto an under-provisioned SNO will crash-loop. 32 GB RAM is the floor.

## Teaching the hub to install clusters disconnected

A hub that provisions clusters needs the same disconnected plumbing we did by hand in Part 3 — but now declared as resources the hub reuses for every cluster it builds:

- A **mirror registry ConfigMap / `ImageContentSourcePolicy`** so managed clusters pull from Quay.
- A **ClusterImageSet** pointing at the mirrored release.
- The **pull secret** and **mirror CA** as secrets the install templates reference.

```yaml
# The release image managed clusters will install — from the mirror.
apiVersion: hive.openshift.io/v1
kind: ClusterImageSet
metadata:
  name: img4.16.x-x86-64
spec:
  releaseImage: registry.lab.example.com:8443/ocp4/openshift4:4.16.x
```

## Deploying a managed cluster

With the hub ready, provisioning a new cluster is declarative. For on-prem bare-metal/VM targets, that's the Assisted Installer path driven by hub CRs — an `AgentClusterInstall`, a `ClusterDeployment`, an `InfraEnv` (which generates a discovery ISO), and the mirror config. The short version:

```yaml
# InfraEnv generates a discovery ISO for the new cluster's node(s),
# pre-loaded with the mirror registry + CA so the node pulls locally.
apiVersion: agent-install.openshift.io/v1beta1
kind: InfraEnv
metadata:
  name: edge-cluster-01
  namespace: edge-cluster-01
spec:
  clusterRef:
    name: edge-cluster-01
    namespace: edge-cluster-01
  pullSecretRef:
    name: mirror-pull-secret
  sshAuthorizedKey: '<SSH PUBLIC KEY>'
```

The flow mirrors Parts 2–3, but the *hub* does the work:

1. Apply the cluster CRs to the hub.
2. The hub's Assisted Service generates a discovery ISO (with mirror + CA baked in).
3. Boot the new target node (another KVM VM, or bare metal) from that ISO — exactly like [Part 2](/posts/on-prem-openshift-2-kvm-vm/).
4. The node registers back to the hub, which drives the install from the mirror — exactly like [Part 3](/posts/on-prem-openshift-3-sno-install/), but automated.
5. The finished cluster shows up as a **managed cluster**.

```bash
oc get managedclusters
# NAME              HUB ACCEPTED   AVAILABLE   ...
# local-cluster     true           True        (the hub itself)
# edge-cluster-01   true           True        (provisioned from the hub)
```

## Why this architecture is the point

Everything compounds: the mirror registry (Part 1) is the single source of images for the hub *and* every cluster the hub builds. The KVM pattern (Part 2) is how every node — hub or managed — comes up. The disconnected install settings (Part 3) are no longer hand-entered; the hub templates them into every provision. One Single Node OpenShift box, built deliberately, becomes the control point for a whole disconnected fleet.

That's the full arc of this series: from an empty mirror host to a self-contained, air-gapped OpenShift platform that can grow itself — no internet required at any step.

## What "done" looks like for Part 4

- `oc get multiclusterhub` → `Running`.
- `oc get managedclusters` → the hub (`local-cluster`) plus at least one provisioned cluster, both `AVAILABLE=True`.
- The managed cluster's images all resolve to the mirror.
- You can apply policies/applications from the hub and watch them land on the managed cluster.

---

*Notes from real on-prem OpenShift / ACM work. Names, versions, and secrets are placeholders — adapt to your environment and never commit real credentials.*
