+++
title = "Secure Lab: OWASP Juice Shop + Wazuh on AWS"
date = 2026-06-01
draft = false
summary = "An automated, security-first AWS lab that deploys OWASP Juice Shop behind a ModSecurity WAF, monitors it with a Wazuh SIEM, and restricts all access to a WireGuard VPN. The environment is fully Terraform-driven and includes a verification step that gates every deployment on proven end-to-end log delivery."
stack = "Terraform · AWS · K3s · ModSecurity WAF · WireGuard · Wazuh SIEM · DevSecOps"
repo = "https://github.com/ArpitJain2k01/juiceshop"
showTableOfContents = true
+++

## Overview

This project is an automated, security-first AWS environment that deploys [OWASP Juice Shop](https://owasp.org/www-project-juice-shop/) — an intentionally vulnerable web application — behind a Web Application Firewall, places it under continuous SIEM monitoring, and restricts all access to a private VPN. The entire environment is defined in Terraform and provisioned reproducibly from a single command.

The project connects the application-security domain (a vulnerable application protected by a WAF) with the platform domain (Terraform, Kubernetes, VPN, SIEM, and a DevSecOps pipeline), presenting security as a verifiable, reproducible system rather than a static configuration.

## Key capabilities

- **Application** — OWASP Juice Shop runs on single-node **K3s** and is exposed only as an internal ClusterIP, with no public application endpoint.
- **Web Application Firewall** — a **ModSecurity + OWASP Core Rule Set** reverse proxy fronts the application: legitimate requests are served (HTTP 200), malicious requests are deterministically blocked (HTTP 403), and the origin cannot be reached directly.
- **VPN-only access** — a **WireGuard** gateway is the sole public entry point; the application and SIEM hosts have no public IP addresses.
- **SIEM** — **Wazuh** (manager, indexer, and dashboard) runs on a dedicated host, with an agent on the application host forwarding WAF, ingress, and application logs to persistent storage.
- **Deployment verification** — each deployment sends a unique marker through the WAF and confirms its arrival in Wazuh through the Indexer API, using bounded timeouts and a non-zero exit on failure, so the deployment is gated on proven end-to-end log delivery.
- **Cloud security** — least-privilege security groups (security-group references, no `0.0.0.0/0` ingress) and IAM roles, no public workloads, encrypted EBS volumes, enforced IMDSv2, and VPC flow logs; Terraform state and secrets are excluded from version control.
- **CI/CD** — Terraform validation, **Trivy** (infrastructure-as-code and filesystem scanning), **Gitleaks** (secret detection), and the deployment verifier, with the deploy stage gated on all checks behind protected branches.

## Architecture

```text
Evaluator ──WireGuard (UDP 51820, allowlisted IP)──▶ WG gateway (only public IP)
                                                          │ private routing
                 ┌────────────────────────────────────────┼─────────────────────┐
                 ▼                                          ▼
        App VM (private)                            Wazuh VM (private)
        K3s: WAF (NodePort) ──▶ Juice Shop          manager + indexer + dashboard
             │ ModSecurity + CRS  (ClusterIP)        agent events ──▶ indexed, searchable
             └ Wazuh agent ───────── logs ──────────▶
```

The architecture enforces a consistent set of principles: no publicly exposed workloads, every request mediated by the WAF, and every security-relevant event delivered to the SIEM — with a pipeline that treats a deployment as successful only once that log-delivery path has been verified end to end.

## Single-command deployment

The complete stack — VPC and networking, the WireGuard VPN gateway, the K3s application node running Juice Shop behind the ModSecurity WAF, and the dedicated Wazuh SIEM host and agent — is provisioned from a single command. Inputs are configured once in `terraform.tfvars`, after which the lifecycle is managed through three targets:

```bash
make deploy    # provisions the full environment, then runs the verifier
make verify    # re-runs the log-delivery verifier with a fresh unique marker
make destroy   # tears down all resources
```

`make deploy` applies the Terraform configuration to build the infrastructure and then runs the verifier automatically, so a single command both provisions the environment and confirms that its security pipeline functions correctly — with no manual configuration or post-deployment steps. Every host is configured declaratively through Terraform and cloud-init, which ensures the environment is reproduced identically on each run and removed cleanly with `make destroy`.

Because the WAF and the Wazuh indexer are private, `make verify` requires an active WireGuard tunnel to reach them. Terraform state is stored in an encrypted, versioned S3 bucket with public access blocked.

## Deployment verification

A successful `terraform apply` confirms only that resources exist, not that the security controls operate as intended. To close that gap, the verifier runs on every deployment and:

1. Sends a request carrying a **unique marker** through the WAF.
2. Polls the **Wazuh Indexer API** until the marker appears as an indexed event, within a bounded timeout.
3. Exits with a non-zero status, failing the deployment, if the marker is not observed.

This converts an assumption — that the SIEM is receiving logs — into a verified, gated invariant: a deployment is considered successful only when a real request has been processed, correctly allowed or blocked, and surfaced in the SIEM end to end.

## CI/CD pipeline

GitHub Actions runs Terraform validation, Trivy and Gitleaks scans, and the verifier on every pull request. The `main` branch is protected, so changes merge only through pull requests with passing checks. The gated deploy stage runs on a self-hosted runner connected to the VPN — enabling it to reach the private WAF and indexer — applies the Terraform configuration, and gates on the verifier. Sensitive files (`*.tfvars`, `*.tfstate`, keys, and `.env`) are excluded from version control, with Gitleaks providing a secondary safeguard in CI.

## Evidence

The repository includes redacted verification artifacts in [`evidence/`](https://github.com/ArpitJain2k01/juiceshop/blob/main/evidence/EVIDENCE.md): confirmation of VPN-only access, the WAF allowing a legitimate request (HTTP 200) and blocking attacks (HTTP 403), a Wazuh event demonstrating end-to-end log delivery, and the raw verifier output.

## Security principles applied

The environment is built on secure-by-default principles throughout:

- **Minimal public attack surface** — the application and SIEM have no public IP addresses. The only internet-facing endpoint is the WireGuard VPN gateway, leaving no public service to scan or exploit.
- **Defense in depth** — a request must traverse the VPN and then the ModSecurity + OWASP CRS WAF before reaching the application, which is itself an internal ClusterIP. Each layer is an independent, enforced control.
- **Least privilege** — security groups use security-group references with no `0.0.0.0/0` ingress, and each host's IAM role grants only the permissions it requires.
- **Verified rather than assumed security** — the pipeline confirms on every deployment that the WAF blocks attacks and the SIEM receives events, rather than relying on configuration alone.
- **Protected secrets and state** — Terraform state is stored in an encrypted, versioned S3 bucket with public access blocked; secrets are excluded from version control, with Gitleaks enforcing this in CI.
- **Hardened cloud baseline** — encrypted EBS volumes, enforced IMDSv2 (mitigating SSRF-to-credential exposure), and VPC flow logs for network visibility.
- **Shift-left security** — Trivy and Gitleaks scan infrastructure, filesystem, and secrets on every pull request, with protected branches ensuring changes merge only after passing all checks.
- **Reproducible provisioning** — the complete environment deploys and is destroyed through a single command, defined entirely in Terraform and cloud-init, so the secure baseline is reproduced identically on every run.

Collectively, these controls make the project a concise, working model for operating an exposed application securely: no public workloads, enforced controls at every layer, and a security posture that is continuously verified rather than assumed.
