+++
title = "On-Prem OpenShift, Part 3: Installing Single Node OpenShift from a Private Registry"
date = 2026-10-20
draft = false
summary = "The payoff of the first two parts: a disconnected Single Node OpenShift install that pulls every image from the on-prem Quay mirror. Here's the install-config that points the installer at the mirror, the trust and imageContentSources plumbing, and how I drive the install to a healthy cluster."
tags = ["openshift", "sno", "disconnected", "installer", "on-prem"]
showTableOfContents = true
+++

This is Part 3 of a four-part series on building OpenShift on-prem:

1. [A Quay mirror registry in a Docker host-network container](/posts/on-prem-openshift-1-quay-registry/)
2. [Bringing up the cluster node with KVM/libvirt](/posts/on-prem-openshift-2-kvm-vm/)
3. **Installing Single Node OpenShift from the private registry** (this post)
4. [Turning SNO into an ACM hub and deploying managed clusters](/posts/on-prem-openshift-4-acm-hub/)

We have a populated mirror registry ([Part 1](/posts/on-prem-openshift-1-quay-registry/)) and a correctly-sized, correctly-networked VM ([Part 2](/posts/on-prem-openshift-2-kvm-vm/)). Now we install Single Node OpenShift onto that VM, with every image coming from the mirror and nothing from the internet.

## What makes a disconnected install different

A normal install pulls from `quay.io` and `registry.redhat.io`. A disconnected install has to be told three extra things, all in the `install-config.yaml`:

1. **A pull secret** that authenticates to the *mirror*, not the internet.
2. **`additionalTrustBundle`** — the mirror's CA (from Part 1), so the cluster trusts the registry's TLS.
3. **`imageContentSources`** — the mapping that rewrites every upstream image reference to its mirror equivalent, so the cluster resolves images locally.

Miss any one and the install stalls on image pulls. Together they make the cluster believe the mirror *is* the source of truth.

## The install-config

For SNO specifically, the topology is one control-plane replica and zero workers — the single node is both:

```yaml
apiVersion: v1
baseDomain: lab.example.com
metadata:
  name: sno
controlPlane:
  name: master
  replicas: 1          # SNO: exactly one control-plane node
compute:
  - name: worker
    replicas: 0        # SNO: no separate workers; the master runs workloads
networking:
  networkType: OVNKubernetes
  clusterNetwork:
    - cidr: 10.128.0.0/14
      hostPrefix: 23
  serviceNetwork:
    - 172.30.0.0/16
platform:
  none: {}             # bare-metal/none platform (the KVM VM looks like bare metal)
bootstrapInPlace:
  installationDisk: /dev/vda   # SNO bootstraps in place on this disk
pullSecret: '<MERGED PULL SECRET THAT INCLUDES THE MIRROR CREDENTIALS>'
sshKey: '<YOUR SSH PUBLIC KEY>'
additionalTrustBundle: |
  -----BEGIN CERTIFICATE-----
  <THE QUAY MIRROR ROOT CA FROM PART 1>
  -----END CERTIFICATE-----
imageContentSources:
  - mirrors:
      - registry.lab.example.com:8443/ocp4/openshift4
    source: quay.io/openshift-release-dev/ocp-release
  - mirrors:
      - registry.lab.example.com:8443/ocp4/openshift4
    source: quay.io/openshift-release-dev/ocp-v4.0-art-dev
```

Three fields do the disconnection:

- **`platform: none`** — the installer doesn't try to talk to a cloud or a BMC; the KVM VM is treated like a generic bare-metal node.
- **`bootstrapInPlace.installationDisk`** — SNO's trick: there's no separate bootstrap node, so it bootstraps on the install disk itself (`/dev/vda`, the virtio disk from Part 2).
- **`imageContentSources`** — pasted straight from the `oc adm release mirror` output in Part 1. This is what rewrites `quay.io/...` pulls to `registry.lab.example.com:8443/...`.

## Generating the ISO and installing

With the config in place, the installer produces the single-node ISO — the discovery ISO that Part 2's VM boots from:

```bash
# Keep a copy of install-config.yaml; the installer consumes (deletes) it.
openshift-install --dir=./sno create single-node-ignition-config

# Embed the ignition into a bootable RHCOS ISO using coreos-installer.
coreos-installer iso ignition embed \
  -i ./sno/bootstrap-in-place-for-live-iso.ign \
  -o ./sno/sno-discovery.iso \
  rhcos-live.x86_64.iso
```

That `sno-discovery.iso` is exactly what [Part 2's `virt-install`](/posts/on-prem-openshift-2-kvm-vm/) booted the VM from. Boot it, and the node:

1. Comes up in the live RHCOS environment.
2. Reads the embedded ignition, which contains the mirror CA, the pull secret, and the `imageContentSources`.
3. Pulls the release payload **from the mirror**, writes RHCOS to `/dev/vda`, and reboots into the installed node.
4. Bootstraps the control plane in place and brings up the cluster operators.

> If you drive this through the **Assisted Installer** instead of `openshift-install` directly, the same three disconnected settings are entered in the UI/API (mirror registry, trust bundle, and the release source) and it generates the equivalent ISO. The Assisted Installer is the smoother path for repeatable on-prem SNO, which matters once ACM is doing it for you (Part 4).

## Watching the install

```bash
# Follow the bootstrap/install progress.
openshift-install --dir=./sno wait-for install-complete --log-level=info

# Once it prints the kubeadmin password and console URL:
export KUBECONFIG=./sno/auth/kubeconfig
oc get clusterversion
oc get nodes
oc get co            # all cluster operators should go Available=True
```

The tell that the mirror plumbing worked: `oc get clusterversion` shows the image pulled from `registry.lab.example.com:8443`, and no operator is stuck `Progressing` on an image pull. If one is, it's almost always a missing `imageContentSources` entry or an untrusted CA — the same two issues from Part 1, now surfacing at cluster scale.

## What "done" looks like for Part 3

- `oc get clusterversion` → `Available: True`, version pinned to the mirrored release.
- `oc get nodes` → one node, `Ready`, role `control-plane,master,worker`.
- `oc get co` → every cluster operator `Available=True`, `Degraded=False`.
- Every image reference in `oc get pods -A -o yaml` resolves to the mirror, not `quay.io`.

That's a fully functional, disconnected Single Node OpenShift cluster, installed entirely from on-prem artifacts. On its own it already runs workloads — but the reason we built it is to make it a control point for *other* clusters.

Next: [Part 4 — turning this SNO into an ACM hub and deploying managed clusters from it](/posts/on-prem-openshift-4-acm-hub/).

---

*Notes from real on-prem OpenShift work. CIDRs, disks, domains, and secrets are placeholders — adapt to your environment and never commit a real pull secret or private key.*
