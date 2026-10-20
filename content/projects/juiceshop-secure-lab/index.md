+++
title = "Secure Lab: OWASP Juice Shop + Wazuh on AWS"
date = 2026-06-01
draft = false
summary = "A fully automated, security-first lab that stands up OWASP Juice Shop behind a WAF, monitored by a Wazuh SIEM, reachable only through a WireGuard VPN — entirely Terraform-driven, with a verifier that gates deployment on end-to-end log delivery."
stack = "Terraform · AWS · K3s · ModSecurity WAF · WireGuard · Wazuh SIEM · DevSecOps"
repo = "https://github.com/ArpitJain2k01/juiceshop"
showTableOfContents = true
+++

A fully automated, **security-first lab** that stands up [OWASP Juice Shop](https://owasp.org/www-project-juice-shop/) — the deliberately vulnerable web app — behind a Web Application Firewall, monitored by a SIEM, and reachable only through a VPN. The whole environment is Terraform-driven and reproducible: supply credentials and variables, and it comes up with a single documented command.

It ties the **application-security** side (a vulnerable app + WAF) to the **platform** side (Terraform, K3s, VPN, SIEM, and a DevSecOps pipeline) — security as a verifiable, reproducible system rather than a checklist.

## What it demonstrates

- **Application** — OWASP Juice Shop on single-node **K3s**, exposed only as an internal ClusterIP (no public app endpoint).
- **WAF** — a **ModSecurity + OWASP Core Rule Set** reverse proxy in front of the app: an allowed request passes (200), malicious requests are deterministically blocked (403), and there's no direct-origin bypass.
- **VPN-only access** — a **WireGuard** gateway is the single public entry point; the app and the SIEM have no public IPs at all.
- **SIEM** — **Wazuh** (manager + indexer + dashboard) on a dedicated VM, with an agent on the app host shipping WAF/ingress and application logs, persisted on a dedicated EBS volume.
- **Deployment verifier** — each run sends a unique marker through the WAF and confirms it landed in Wazuh via the Indexer API, with bounded timeouts and a non-zero exit on failure; the deployment is **gated** on that end-to-end log-delivery proof.
- **Cloud security** — least-privilege security groups (SG references, no `0.0.0.0/0` inbound) and IAM, no public workloads, encrypted EBS volumes, IMDSv2, and VPC flow logs; Terraform state and secrets kept out of git.
- **CI/CD** — Terraform validation, **Trivy** (IaC + filesystem), **Gitleaks** (secret scanning), and the verifier, with the deploy job gated on all checks behind protected branches.

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

Design goal: no public workloads, every request mediated by the WAF, every security-relevant event landing in the SIEM — and a pipeline that refuses to call a deploy successful until it has *proven* that log path works end to end.

## One-command deployment

The entire stack — VPC and networking, the WireGuard VPN gateway, the K3s app node with Juice Shop behind the ModSecurity WAF, and the separate Wazuh SIEM VM with its agent — comes up from **a single command**. You set your inputs once (`terraform.tfvars`) and run:

```bash
make deploy    # provisions everything, then runs the verifier (deploy FAILS if log delivery fails)
make verify    # re-run the log-delivery verifier with a fresh unique marker
make destroy   # tear down every lab resource
```

`make deploy` runs `terraform apply` to build all the infrastructure, then **automatically runs the verifier** — so one command both *builds* the environment and *proves* its security pipeline works, with no manual wiring, console clicking, or post-install steps. There's no snowflake setup: every machine is configured declaratively through Terraform and cloud-init, so the lab comes up identically every time and tears down cleanly with `make destroy` (the main hourly cost is the NAT gateway).

`make verify` requires the WireGuard tunnel to be up, because the WAF and the Wazuh indexer are private — they're reached only over the VPN. Terraform state lives in an encrypted, versioned S3 bucket with public access blocked.

## The verifier — why "it deployed" isn't enough

The piece I'm most happy with is the **verifier**. A green `terraform apply` only proves resources exist, not that the security pipeline actually *works*. So on every deploy the verifier:

1. Sends a request carrying a **unique marker** through the WAF.
2. Polls the **Wazuh Indexer API** until that exact marker shows up as an indexed event — with a bounded timeout.
3. **Exits non-zero** if the marker never arrives, which **fails the deploy**.

That turns "the SIEM is probably receiving logs" into a provable, gated invariant: a deploy isn't successful unless a real request was observed, blocked/allowed correctly, and surfaced in the SIEM end to end.

## CI/CD

GitHub Actions runs Terraform validation, Trivy and Gitleaks scans, and the verifier on pull requests; `main` is protected so changes land only through PRs with passing checks. The gated deploy job runs on a **self-hosted runner on the VPN** (so it can reach the private WAF/indexer), applies Terraform, and gates on the verifier. Secrets (`*.tfvars`, `*.tfstate`, keys, `.env`) are git-ignored, with Gitleaks as a CI backstop.

## Evidence

The repo includes redacted proof in [`evidence/`](https://github.com/ArpitJain2k01/juiceshop/blob/main/evidence/EVIDENCE.md): VPN-only access, the WAF allowing a legitimate request (200) and blocking attacks (403), and a fresh Wazuh event demonstrating end-to-end log delivery — plus the raw verifier output.

## Security practices that make it solid

The lab is built around secure-by-default principles end to end:

- **Zero public attack surface** — the application and the SIEM have **no public IPs**. The only internet-facing endpoint is a WireGuard VPN gateway, so there's nothing to scan, brute-force, or exploit from the open internet.
- **Defense in depth** — a request has to pass the VPN, then the ModSecurity + OWASP CRS WAF, before it ever reaches the app, which itself is an internal ClusterIP. Multiple independent layers, each a real control.
- **Least privilege everywhere** — security groups use SG-to-SG references with **no `0.0.0.0/0` inbound**, and each host's IAM instance role carries only the permissions it actually needs.
- **Verifiable security, not assumed** — the pipeline *proves* the WAF blocks attacks and the SIEM receives events on every deploy, rather than trusting that it's configured correctly.
- **Secrets and state kept safe** — Terraform state lives in an encrypted, versioned S3 bucket with public access blocked; secrets are git-ignored and **Gitleaks** runs in CI as a backstop so nothing sensitive can slip into the repo.
- **Hardened cloud baseline** — **encrypted EBS volumes**, **IMDSv2** enforced (closing the SSRF-to-credentials path), and **VPC flow logs** for network visibility.
- **Shift-left security in CI** — **Trivy** scans IaC and the filesystem and **Gitleaks** scans for secrets on every pull request, with `main` protected so changes only land through reviewed PRs that pass all checks.
- **One command, whole stack, every time** — the entire environment (network, VPN, WAF, app, and SIEM) deploys from a single `make deploy` and tears down with `make destroy`. It's fully Terraform- and cloud-init-driven, so there are no manual steps or snowflake configuration — the secure baseline is reproduced identically on every run.

Together these make the lab a compact, working model of how to run an exposed application *safely*: nothing public, every layer enforced, and the security posture continuously proven rather than presumed.
