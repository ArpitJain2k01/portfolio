+++
title = "On-Prem OpenShift, Part 1: A Quay Mirror Registry in a Docker Host-Network Container"
date = 2026-10-20
draft = false
summary = "Building a disconnected OpenShift install starts with one thing: a local image registry. Here's how I stand up Quay on a Docker container with host networking, mirror the OpenShift release and operators into it, and wire up the trust and pull-secret plumbing the installer needs."
tags = ["openshift", "quay", "disconnected", "docker", "on-prem"]
showTableOfContents = true
+++

This is Part 1 of a four-part series on building an OpenShift cluster on-prem, from an empty box to a multi-cluster fleet:

1. **A Quay mirror registry in a Docker host-network container** (this post)
2. [Bringing up the cluster node with KVM/libvirt](/posts/on-prem-openshift-2-kvm-vm/)
3. [Installing Single Node OpenShift from the private registry](/posts/on-prem-openshift-3-sno-install/)
4. [Turning SNO into an ACM hub and deploying managed clusters](/posts/on-prem-openshift-4-acm-hub/)

## Why a local registry comes first

A disconnected (air-gapped) OpenShift install has no path to `quay.io` or `registry.redhat.io`. Every image the cluster needs — the release payload, every operator, the CLI tools — has to come from a registry *you* control inside the network boundary. So before there is a cluster, there has to be a registry, and it has to be populated.

That ordering matters: the registry is a hard dependency of the install, not a day-2 add-on. Get it wrong and the installer fails on the first image pull with a `x509` or `manifest unknown` error that sends people down the wrong rabbit hole.

## Why host networking

I run the registry as a container, but with `--network host` rather than bridge networking + port mapping. Three reasons:

- **The registry must be reachable at a stable, routable address** that the cluster nodes (and later, the installer host) can hit — not a NAT'd container IP that only exists on the Docker bridge.
- **TLS cert SANs** are tied to a hostname/IP. Host networking lets me bind the registry to the host's real interface, so the certificate I issue for `registry.lab.example.com` actually matches what clients connect to.
- It sidesteps a layer of port-forwarding translation that only makes debugging `curl` failures harder in a disconnected environment.

The trade-off is that the registry owns its port on the host directly (8443 here), so nothing else can use it — which is fine for a dedicated mirror host.

## Standing up Quay

Red Hat ships `mirror-registry`, a small Quay distribution purpose-built for exactly this: a single-container Quay backed by a local Postgres, meant to serve as a disconnected mirror. It's the least fiddly way to get a production-grade registry (Quay) rather than the bare `docker/distribution` registry.

```bash
# On the mirror host (a RHEL box with Docker/Podman and plenty of disk).
# Download mirror-registry, then install it bound to the host's address.
./mirror-registry install \
  --quayHostname registry.lab.example.com \
  --quayRoot /opt/quay \
  --initUser   admin \
  --initPassword 'REDACTED'
```

`mirror-registry` generates a self-signed CA and server certificate for `--quayHostname` and brings up the Quay + Postgres containers. If you're running the registry as a plain container yourself instead, the equivalent is a `docker run` with host networking, a persistent volume for the image data, and your own TLS cert mounted in:

```bash
docker run -d --name quay --network host \
  -v /opt/quay/storage:/datastorage:Z \
  -v /opt/quay/tls:/tls:Z \
  -e QUAY_HOSTNAME=registry.lab.example.com:8443 \
  quay.io/projectquay/quay:stable
```

The key detail with `--network host`: there is no `-p 8443:8443`. The container binds the host's `:8443` directly. Confirm it:

```bash
ss -ltnp | grep 8443
curl -I https://registry.lab.example.com:8443/health/instance --cacert /opt/quay/quay-rootCA/rootCA.pem
```

## Trusting the registry's CA

Because the cert is self-signed (or signed by your internal CA), every client that talks to the registry — the installer host, and later every cluster node — must trust that CA. On the mirror host and the installer host:

```bash
sudo cp /opt/quay/quay-rootCA/rootCA.pem \
  /etc/pki/ca-trust/source/anchors/quay-registry.crt
sudo update-ca-trust extract
```

Skip this and the first `podman login` or `oc` pull dies with `x509: certificate signed by unknown authority`. The same CA gets injected into the cluster later via the install-config `additionalTrustBundle` (Part 3) — this is the single most common disconnected-install snag, so it's worth getting right up front.

## Mirroring the content

An empty registry doesn't help. Two things have to land in it: the **OpenShift release payload** and the **operators** you intend to run (including, for this series, Advanced Cluster Management).

First, log in to both the upstream (with your Red Hat pull secret) and your local registry, and build a combined pull secret:

```bash
# Authenticate podman to the local mirror.
podman login registry.lab.example.com:8443 -u admin -p 'REDACTED'

# Merge the Red Hat pull secret + local creds into one file the mirror tools use.
# (pull-secret.json comes from console.redhat.com; the local entry is added to it.)
```

**Mirror the release payload** with `oc adm release mirror`. This copies the exact release images for a pinned version into your registry and prints the `imageContentSources` block you'll paste into the install config:

```bash
oc adm release mirror \
  --from=quay.io/openshift-release-dev/ocp-release:4.16.x-x86_64 \
  --to=registry.lab.example.com:8443/ocp4/openshift4 \
  --to-release-image=registry.lab.example.com:8443/ocp4/openshift4:4.16.x \
  --registry-config=pull-secret-merged.json
```

**Mirror the operators** with `oc-mirror`, driven by an `ImageSetConfiguration` that names the catalog and the specific operators — here, ACM (`advanced-cluster-management`) and its dependency, the multicluster engine:

```yaml
# imageset-config.yaml
kind: ImageSetConfiguration
apiVersion: mirror.openshift.io/v1alpha2
mirror:
  platform:
    channels:
      - name: stable-4.16
        type: ocp
  operators:
    - catalog: registry.redhat.io/redhat/redhat-operator-index:v4.16
      packages:
        - name: advanced-cluster-management
        - name: multicluster-engine
  additionalImages:
    - name: registry.redhat.io/ubi9/ubi:latest
```

```bash
oc-mirror --config imageset-config.yaml docker://registry.lab.example.com:8443
```

`oc-mirror` is the one to prefer for anything beyond the bare release: it tracks what it has already mirrored, handles operator dependency graphs, and emits the `ImageContentSourcePolicy`/`IDMS` and `CatalogSource` manifests you apply to the cluster so it resolves operators from your mirror instead of the internet.

## What "done" looks like for Part 1

Before moving on, I verify the registry can actually serve what the installer will ask for:

```bash
# The release image is resolvable from the mirror.
oc adm release info registry.lab.example.com:8443/ocp4/openshift4:4.16.x \
  --registry-config=pull-secret-merged.json

# The operator catalog landed.
curl -s https://registry.lab.example.com:8443/v2/_catalog --cacert rootCA.pem | jq .
```

When both of those return real data over TLS the clients trust, the registry is ready. The cluster doesn't exist yet — but everything it will need to pull now lives inside the network, which is the whole point of a disconnected install.

Next up: [Part 2 — bringing up the cluster node as a KVM virtual machine](/posts/on-prem-openshift-2-kvm-vm/), the box that SNO will actually install onto.

---

*Notes from real on-prem OpenShift work. Hostnames, versions, and credentials here are placeholders — adapt them to your environment and never commit a real pull secret.*
