+++
title = "Experience"
description = "Career path of Arpit Jain — roles, responsibilities, and what I learned at each step."
layout = "simple"
showTableOfContents = true
+++

My path so far as a Platform / DevOps engineer — the problems I owned at each role, the technology I worked with, and what each step taught me.

## Nava

**Platform Engineer / DevOps Engineer**
April 2026 – Present · Bengaluru, India

Building and operating production platform infrastructure across AWS and bare-metal Kubernetes, with a strong focus on automation and security.

**What I do here**

- Design and run production-grade, multi-account AWS infrastructure (Dev → Staging → Pre-Prod → Prod) in Terraform — EKS, EC2, Lambda, ECR, ACM PCA, SNS, SQS, IAM, VPC, S3 — with reusable modules and approval-gated GitHub Actions pipelines for plan, apply, and controlled destroy.
- Architect and operate vanilla Kubernetes clusters for high-performance workloads, integrating Cilium/eBPF, Ceph, Mayastor, KubeVirt, SR-IOV, and MetalLB.
- Built a Go-based DNS management platform integrating PowerDNS and Akamai DNS, with request-level metering and billing visibility.
- Run GitOps delivery with ArgoCD and GitHub Actions, using blue/green and canary rollout strategies.
- Led infrastructure security hardening (OpenSCAP, OVAL, Kyverno, Kubescape, kube-bench) — taking CIS Level 2 server compliance from 51% to 85%+ and Kubernetes security compliance from 40% to 80%.

**What I learned**

- How to design cloud infrastructure that stays reviewable and reversible — modules, saved plans, approval gates — rather than clever one-offs.
- That security compliance is a measurable engineering target you can move with the right tooling and discipline, not a box-ticking exercise.
- Building real Go tooling for the platform, not just scripts — turning operational problems into maintainable services.

## Jio Platforms Limited

**SRE / DevOps Engineer**
October 2023 – April 2026 · Mumbai, India

Operated telco-grade OpenShift at scale in highly restricted, air-gapped environments — where reliability and automation are non-negotiable.

**What I did here**

- Ran production OpenShift (OCP) clusters in disconnected environments — private registries, OIDC authentication, custom Operator Hub workflows, and platform-level configuration.
- Optimized CPU- and network-intensive DPDK-based telco applications with CPU pinning, topology-aware scheduling, and SR-IOV/OVS networking for low-latency, high-throughput workloads.
- Engineered Tekton-based CI/CD pipelines to automate OpenShift cluster provisioning and validation, including custom Ignition-based ISO images for automated server bring-up and pre-deployment checks.
- Implemented centralized multi-cluster lifecycle management with OpenShift Advanced Cluster Management (ACM) across on-premises environments.
- Diagnosed and resolved complex production issues spanning application, Kubernetes/OpenShift, Linux kernel, networking, and distributed storage layers.

**What I learned**

- How to operate infrastructure where you can't just `pull` from the internet — air-gapped discipline, private supply chains, and everything-as-automation.
- Deep, layered troubleshooting across the full stack — from the Linux kernel and NIC up through the cluster and the application.
- What "production reliability" really means at telco scale, across 500+ nodes, where downtime is measured in impact.

## Education

**Indian Institute of Technology (IIT), Palakkad**
B.Tech, Civil Engineering · 2019 – 2023 · CGPA 8.33 / 10

Where I built the engineering fundamentals and the habit of learning hard things from first principles — the foundation I later turned toward infrastructure and systems.

---

Want the detail? The full [CV](/cv/) lists the projects and the complete technical stack. For what I'm learning right now, see the [blog](/posts/).
