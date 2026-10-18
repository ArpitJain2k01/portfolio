+++
title = "CV"
description = "Curriculum vitae — Arpit Jain, Platform / DevOps Engineer."
layout = "simple"
showTableOfContents = true
+++

**Platform Engineer · Hybrid Cloud & AI Infrastructure · Kubernetes · Terraform · Go**
Bengaluru, Karnataka, India · [arpit2k01jain@gmail.com](mailto:arpit2k01jain@gmail.com)

{{< button href="/arpit-jain-cv.pdf" target="_blank" download="arpit-jain-cv.pdf" >}}
Download PDF
{{< /button >}}

## Summary

DevOps and Platform engineer with **3+ years** of experience working on production infrastructure across AWS, Kubernetes, OpenShift, and bare-metal environments. Experienced in infrastructure automation with Terraform, GitOps with ArgoCD, CI/CD, and Go-based tooling. Worked on high-performance networking and workloads using DPDK, SR-IOV, and Cilium; distributed storage with Ceph and Mayastor; and multi-cluster management with OpenShift ACM. Hands-on experience in infrastructure security and compliance using OpenSCAP, OVAL, Kubescape, kube-bench, and Kyverno — including improving CIS Level 2 server compliance from 35% to 85%+.

## Technical skills

- **Cloud & Infrastructure:** AWS (EKS, EC2, Lambda, ECR, IAM, VPC, S3, SNS, SQS, ACM PCA), Kubernetes, OpenShift/OCP, OpenShift ACM, KubeVirt
- **IaC & Automation:** Terraform, Ansible, Helm, GitHub Actions, Tekton, ArgoCD
- **Networking & Storage:** SR-IOV, Cilium, BGP, MetalLB, Traefik, Ceph, OpenEBS Mayastor, load balancing, service mesh
- **Security & Compliance:** IAM, RBAC, CIS Level 2, OpenSCAP, OVAL, Trivy, Kubescape, kube-bench, Kyverno, Pod Security Standards, Wazuh
- **Observability:** Prometheus, Grafana, VictoriaMetrics, OpenTelemetry, CloudWatch, Loki
- **Programming & Systems:** Go, Python, Bash/Shell, Linux, Linux kernel tuning, OS patching & upgrades

## Experience

### Nava — Platform / DevOps Engineer
**April 2026 – Present · Bengaluru, India**

- **Cloud infrastructure & IaC:** Designed and implemented production-grade, multi-account AWS infrastructure across Dev, Staging, Pre-Production, and Production using Terraform — covering EKS, EC2, Lambda, ECR, ACM PCA, SNS, SQS, IAM, VPC, and S3. Built reusable modules, secure cross-account access using IAM Roles Anywhere and Trust Anchors, and GitHub Actions workflows for automated plan, approval-gated apply, and controlled destroy.
- **Platform engineering & Kubernetes:** Architected and operated production-grade vanilla Kubernetes clusters for high-performance workloads, integrating Cilium/eBPF, Ceph, Mayastor, KubeVirt, SR-IOV, and MetalLB for advanced networking, distributed storage, virtualization, and workload connectivity.
- **DNS platform engineering:** Engineered a scalable Go-based DNS management platform integrating PowerDNS and Akamai DNS, automating DNS operations while providing request-level metering and billing visibility for enterprise-scale zones.
- **GitOps & release automation:** Implemented GitOps-based deployment workflows using ArgoCD and GitHub Actions, with controlled rollout strategies including blue/green and canary deployments.
- **Security & compliance:** Led infrastructure security hardening using OpenSCAP, OVAL, Kyverno, Kubescape, and kube-bench, improving CIS Level 2 server compliance from 51% to 85%+ and Kubernetes security compliance from 40% to 80%.
- **Observability & reliability:** Built custom node security audit tooling to track vulnerability remediation and compliance deltas, and implemented full-stack observability using the OpenTelemetry ecosystem for metrics, logs, and traces.

### Jio Platforms Limited — SRE / DevOps Engineer
**October 2023 – April 2026 · Mumbai, India**

- **Private cloud & air-gapped infrastructure:** Operated production-grade OpenShift (OCP) clusters in highly restricted, disconnected environments — managing private container registries, OIDC authentication, custom Operator Hub workflows, and platform-level configuration.
- **High-performance networking & workloads:** Optimized CPU- and network-intensive DPDK-based telco applications using CPU pinning, topology-aware scheduling, and SR-IOV/OVS networking for low-latency, high-throughput workloads.
- **Cluster provisioning & automation:** Engineered Tekton-based CI/CD pipelines to automate OpenShift cluster provisioning and infrastructure validation, including custom Ignition-based ISO images for automated server connectivity and pre-deployment checks.
- **Multi-cluster management:** Implemented centralized cluster lifecycle and operational management using OpenShift Advanced Cluster Management (ACM) across multiple on-premises environments.
- **Production reliability & troubleshooting:** Diagnosed and resolved complex production issues across application, Kubernetes/OpenShift, Linux kernel, networking, and distributed storage layers.

## Key projects

### Production-grade multi-account AWS infrastructure
_Terraform · AWS · GitHub Actions_

- Multi-account AWS infrastructure across Dev, Staging, Pre-Production, and Production with GitHub as the single source of truth.
- Reusable, modular Terraform components for EKS, EC2, Lambda, ECR, ACM PCA, SNS, SQS, and IAM to standardize provisioning.
- Secure cross-account access with AWS IAM Roles Anywhere, Trust Anchors, and role-based authentication, reducing long-lived credentials.
- GitHub Actions CI/CD for automated formatting, validation, plan, approval-gated apply, and controlled destroy.

### Production-grade telco cloud platform on bare metal
_OpenShift · ACM · Kubernetes · CI/CD_

- Designed and deployed an air-gapped telco cloud platform on bare metal from the ground up: private container registry, private DNS, OpenShift ACM, Operator Hub, organizational certificates, and platform services.
- Built a single-node OpenShift ACM management cluster and used it to provision and manage production clusters across **500+ bare-metal nodes**.
- Automated SR-IOV, Network Attachment Definitions (NADs), MetalLB, telemetry, and cluster networking for high-performance telco workloads.
- Engineered an end-to-end CI/CD pipeline to pre-validate connectivity, provision clusters, run post-deployment configuration, deploy operators/apps, and execute platform validation automatically.

### Infrastructure security & compliance automation platform
_OpenSCAP · OVAL · Trivy · Kubescape · kube-bench · Kyverno_

- Built a multi-node security audit platform with a TUI to orchestrate concurrent deep scans using OpenSCAP, OVAL, and custom tooling.
- Automated collection and analysis of CVE findings (severity, status, affected/installed/fixed versions) into consolidated reports.
- Used it to identify, track, and remediate vulnerabilities and configuration gaps, raising CIS Server Level 2 compliance to 85%+.
- Implemented Kubernetes security assessments and policy enforcement with Kubescape, kube-bench, and Kyverno; integrated Trivy into CI/CD for container and dependency scanning before image build/publish.

### Automated certificate lifecycle & monitoring
_Kubernetes · cert-manager · Prometheus · Grafana_

- End-to-end certificate lifecycle management for Kubernetes, service, database, and platform TLS certificates — automating provisioning, renewal, and rotation.
- Centralized expiry monitoring with proactive alerts, preventing certificate-related outages.
- Automated renewal/rotation with cert-manager, with no manual intervention or downtime.

## Education

**Indian Institute of Technology (IIT), Palakkad** — B.Tech, Civil Engineering
2019 – 2023 · CGPA 8.33 / 10
