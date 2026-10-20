+++
title = "Projects"
description = "Selected projects by Arpit Jain — platform, security, and infrastructure work."
layout = "simple"
showTableOfContents = false
+++

A few projects worth calling out. For the production platform and infrastructure work I do day to day, see [Experience](/experience/) and the [blog](/posts/).

## Secure Lab: OWASP Juice Shop + Wazuh on AWS

_Terraform · AWS · K3s · ModSecurity WAF · WireGuard · Wazuh SIEM · DevSecOps_

A fully automated, security-first lab that stands up [OWASP Juice Shop](https://owasp.org/www-project-juice-shop/) — the deliberately vulnerable web app — behind a Web Application Firewall, monitored by a SIEM, and reachable only through a VPN. The whole environment is Terraform-driven and reproducible: supply credentials and variables, and it comes up with a single documented command.

**What it demonstrates:**

- **Application** — OWASP Juice Shop on single-node **K3s**, exposed only as an internal ClusterIP (no public app endpoint).
- **WAF** — a **ModSecurity + OWASP Core Rule Set** reverse proxy in front of the app: allowed requests pass (200), malicious ones are blocked (403), and the origin can't be bypassed directly.
- **VPN-only access** — a **WireGuard** gateway is the single public entry point; the app and the SIEM have no public IPs at all.
- **SIEM** — **Wazuh** (manager + indexer + dashboard) on a dedicated VM, with an agent on the app host shipping WAF/ingress and application logs to a persistent store.
- **Deployment verifier** — each run sends a unique marker through the WAF and confirms it landed in Wazuh via the Indexer API; the deployment is gated on that end-to-end log-delivery proof, with bounded timeouts and a non-zero exit on failure.
- **Cloud security** — least-privilege security groups and IAM, no public workloads, encrypted EBS volumes, IMDSv2, and VPC flow logs; Terraform state and secrets kept out of git.
- **CI/CD** — Terraform validation, **Trivy** (IaC + filesystem), **Gitleaks** (secret scanning), and the verifier, with a deploy job gated on all checks behind protected branches.

It ties the application-security side (a vulnerable app + WAF) to the platform side (Terraform, K3s, VPN, SIEM, and a DevSecOps pipeline) — security as a verifiable, reproducible system rather than a checklist.

**[View on GitHub →](https://github.com/ArpitJain2k01/juiceshop)**
