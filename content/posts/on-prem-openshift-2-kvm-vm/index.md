+++
title = "On-Prem OpenShift, Part 2: Bringing Up the Cluster Node with KVM/libvirt"
date = 2026-10-20
draft = false
summary = "Single Node OpenShift needs a machine to land on. Here's how I provision that node as a KVM/libvirt virtual machine — sizing it correctly, giving it a bridged network and a stable MAC/IP, and booting it from the SNO discovery ISO."
tags = ["openshift", "kvm", "libvirt", "virtualization", "on-prem"]
showTableOfContents = true
+++

This is Part 2 of a four-part series on building OpenShift on-prem:

1. [A Quay mirror registry in a Docker host-network container](/posts/on-prem-openshift-1-quay-registry/)
2. **Bringing up the cluster node with KVM/libvirt** (this post)
3. [Installing Single Node OpenShift from the private registry](/posts/on-prem-openshift-3-sno-install/)
4. [Turning SNO into an ACM hub and deploying managed clusters](/posts/on-prem-openshift-4-acm-hub/)

With the mirror registry from [Part 1](/posts/on-prem-openshift-1-quay-registry/) populated, the next thing SNO needs is a machine to install onto. In a lab or a compact on-prem footprint, that machine is a KVM virtual machine rather than bare metal — same install flow, far faster to iterate.

## Sizing the VM

Single Node OpenShift collapses the control plane and the worker onto one node, so that node carries everything: etcd, the API server, the ingress router, the registry, and your workloads. It needs real resources — SNO is not a "runs on a laptop" footprint.

The minimums I provision for a usable SNO that will later become an ACM hub:

| Resource | Value | Why |
|---|---|---|
| vCPU | 16 | Control plane + ACM/MCE operators are CPU-hungry |
| RAM | 32 GB | etcd + API + ACM hub components; 32 GB is the floor for a hub |
| Disk | 150 GB+ | Release images, operator images, etcd, and managed-cluster manifests |
| Firmware | UEFI | OpenShift expects UEFI boot on modern installs |

Under-provisioning here is the quiet killer: the install "succeeds" but the node thrashes, operators crash-loop on memory pressure, and ACM never goes healthy. Give it the headroom.

## Networking: bridged, with a stable address

The VM must be reachable at a predictable IP from the installer host and must be able to reach the mirror registry. I use a **bridged** network (not libvirt's default NAT), so the VM sits on the same L2 as the registry and gets a routable address.

```bash
# A bridge (br0) over the host's physical NIC so VMs are first-class on the LAN.
sudo nmcli connection add type bridge ifname br0 con-name br0
sudo nmcli connection add type bridge-slave ifname eno1 master br0
sudo nmcli connection up br0
```

Two things about the address:

- **Pin the MAC**, so a DHCP reservation (or static assignment) always gives the node the same IP across reboots. SNO's node identity, certificates, and the API/ingress DNS all assume a stable address.
- **DNS must resolve two names** to that IP before install: `api.<cluster>.<base-domain>` and `*.apps.<cluster>.<base-domain>`. For SNO these both point at the single node. I set these up on the on-prem DNS (or `/etc/hosts` on the installer host for a pure lab).

## Creating the VM

With the discovery ISO in hand (that comes from the install flow in [Part 3](/posts/on-prem-openshift-3-sno-install/) — the Assisted Installer or `openshift-install` generates it), `virt-install` defines the VM and boots it from that ISO:

```bash
sudo virt-install \
  --name sno-node \
  --vcpus 16 \
  --memory 32768 \
  --disk path=/var/lib/libvirt/images/sno-node.qcow2,size=150,bus=virtio \
  --network bridge=br0,model=virtio,mac=52:54:00:ab:cd:01 \
  --boot uefi \
  --cdrom /var/lib/libvirt/images/sno-discovery.iso \
  --os-variant rhel9.4 \
  --graphics vnc \
  --noautoconsole
```

A few choices worth calling out:

- **`virtio` for disk and NIC** — paravirtualized drivers; markedly better I/O and network throughput than emulated hardware, which matters because SNO is pulling gigabytes of images from the mirror during install.
- **`--boot uefi`** — matches OpenShift's expectations; mismatched firmware is a frustrating "node never PXE/ISO boots" failure.
- **A fixed `mac=`** — the other half of the stable-address story from above.
- **`qcow2`** — thin-provisioned so the 150 GB only fills as the install writes.

## Booting and watching it come up

Boot the VM and watch it over VNC (or serial console). The discovery ISO brings the node up into a live environment that registers itself with the installer and begins pulling the release payload — from the mirror registry, not the internet.

```bash
sudo virsh start sno-node
sudo virsh console sno-node        # or connect VNC
sudo virsh dumpxml sno-node | grep -i 'mac address'   # confirm the pinned MAC
```

At this point the VM is a blank, correctly-sized, correctly-networked node booted into discovery, able to reach the mirror. It is *not* OpenShift yet — it's the hardware (virtual) that OpenShift is about to be installed onto.

## What "done" looks like for Part 2

- `virsh list` shows `sno-node` running.
- The node has its pinned MAC and the expected IP (`arp`/DHCP lease confirms it).
- From the node's discovery environment, the mirror registry is reachable over TLS (the CA from Part 1 is baked into the discovery ISO via the install config).
- DNS for `api.` and `*.apps.` resolves to the node.

With the node up and the registry reachable, we can run the actual install. Next: [Part 3 — installing Single Node OpenShift from the private registry](/posts/on-prem-openshift-3-sno-install/).

---

*Notes from real on-prem OpenShift work. Interfaces, MACs, and names are placeholders — adapt to your environment.*
