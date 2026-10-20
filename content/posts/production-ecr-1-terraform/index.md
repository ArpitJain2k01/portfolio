+++
title = "Production-Grade ECR with Terraform, Part 1: Building the Registry"
date = 2026-10-20
draft = false
summary = "A real, production ECR setup built entirely with Terraform: reusable repository modules, lifecycle policies, scan-on-push, a Docker Hub pull-through cache, and least-privilege IAM — including credential-less access with IAM Roles Anywhere — all delivered through an approval-gated GitHub Actions pipeline."
tags = ["aws", "ecr", "terraform", "iam", "cicd"]
showTableOfContents = true
+++

This is Part 1 of a two-part series on running Amazon ECR in production and consuming it from clusters that aren't on AWS:

1. **Building the registry with Terraform** (this post)
2. [Using ECR from a bare-metal Kubernetes cluster](/posts/production-ecr-2-baremetal-pull/)

Amazon ECR is easy to click together in the console and hard to run *well*: reproducibly, least-privilege, with image hygiene and a cache in front of upstream registries. This post is the Terraform build-out of an ECR that holds up in production — every piece codified, reviewed, and shipped through CI.

## What "production-grade" actually means for a registry

A registry you can defend in an audit has, at minimum:

- **Reproducible repositories** — created from a module, not by hand, so every repo has the same encryption, tag policy, and scanning.
- **Image hygiene** — lifecycle policies that expire old/untagged images so storage and attack surface don't grow forever.
- **Vulnerability scanning** — scan-on-push, so a known-vulnerable image is flagged the moment it lands.
- **A pull-through cache** — so pulls of public images (Docker Hub, etc.) are cached in your account, surviving upstream rate limits and outages.
- **Least-privilege access** — tightly scoped IAM for who can push, who can pull, and (critically) credential-less access for workloads that can't hold long-lived keys.
- **Delivered by CI** — plan on PR, approval-gated apply, controlled destroy. No one `terraform apply`-ing from a laptop.

Let's build each.

## A reusable repository module

The core is a module that stamps out identical, hardened repositories. Callers just pass names and knobs.

```hcl
# modules/ecr/main.tf
resource "aws_ecr_repository" "this" {
  for_each             = toset(var.repository_names)
  name                 = each.value
  image_tag_mutability = var.tag_mutability          # "IMMUTABLE" for release repos

  image_scanning_configuration {
    scan_on_push = true                               # flag CVEs at push time
  }

  encryption_configuration {
    encryption_type = "KMS"                           # encrypt at rest with a CMK
    kms_key         = var.kms_key_arn
  }

  tags = var.tags
}
```

Two defaults worth defending:

- **`IMMUTABLE` tags for release repositories.** A mutable `:v1.4.2` can be overwritten, so two nodes can run different code under the same tag and rollback is a lie. Immutability makes a tag a permanent, auditable pointer. (Cache repositories stay mutable — more below.)
- **KMS encryption with a customer-managed key**, not just the AWS-managed default, so key access is itself an IAM-controlled boundary.

## Lifecycle policies — image hygiene

Without a lifecycle policy, every image ever pushed lives forever. That's cost, and it's a growing pile of old, vulnerable images. The policy below keeps the last N tagged images and expires untagged ones quickly:

```hcl
resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the last 20 tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 20
        }
        action = { type = "expire" }
      }
    ]
  })
}
```

## Scan-on-push

Scanning is enabled per repository above (`scan_on_push = true`), and you can also set it registry-wide so no repository can opt out:

```hcl
resource "aws_ecr_registry_scanning_configuration" "this" {
  scan_type = "BASIC"
  rule {
    scan_frequency = "SCAN_ON_PUSH"
    repository_filter {
      filter      = "*"
      filter_type = "WILDCARD"
    }
  }
}
```

Pair this with a scanner in CI (Trivy against the image before it's even pushed), so vulnerabilities are caught *before* publication, and ECR's scan is the backstop that keeps watching after.

## The pull-through cache — surviving Docker Hub

This is the piece most teams skip and later regret. A **pull-through cache rule** makes ECR a transparent, caching proxy for an upstream registry (Docker Hub, Quay, registry.k8s.io, GHCR, …). The first pull of `nginx` fetches from upstream and caches it in your account; every pull after is served from ECR — immune to Docker Hub rate limits and upstream outages, and scannable like any other ECR image.

```hcl
# The upstream credential lives in Secrets Manager, never in code.
resource "aws_ecr_pull_through_cache_rule" "dockerhub" {
  ecr_repository_prefix = "dockerhub"
  upstream_registry_url = "registry-1.docker.io"
  credential_arn        = aws_secretsmanager_secret.dockerhub.arn
}

resource "aws_secretsmanager_secret" "dockerhub" {
  # ECR requires this exact name prefix for pull-through credentials.
  name = "ecr-pullthroughcache/dockerhub"
}
```

A real-world detail that costs people a day: **ECR pull-through credential secrets must use the AWS-managed `aws/secretsmanager` key** — ECR does not support a customer-managed CMK on these secrets. Trying to force a CMK fails closed. Cached repositories are also created `MUTABLE` (upstream tags like `latest` move), which is the one place mutability is correct.

After this, a workload pulls Docker Hub's nginx as:

```text
<acct>.dkr.ecr.<region>.amazonaws.com/dockerhub/library/nginx:latest
```

…and ECR caches it on first pull. (Official Docker Hub images live under `/library/`.)

## IAM — least privilege, and credential-less access

Access splits into three roles, each scoped tightly:

- **Push** (CI): `ecr:GetAuthorizationToken` + `BatchCheckLayerAvailability` + `PutImage` + `Upload*` — scoped to the specific repository ARNs it publishes.
- **Pull** (workloads): `GetAuthorizationToken` + `BatchGetImage` + `GetDownloadUrlForLayer` — read-only, scoped to what they consume.
- **Registry management** (Terraform): the create/lifecycle/policy actions, used only by the pipeline.

The interesting part is **how a non-AWS workload authenticates**. A bare-metal Kubernetes cluster has no EC2 instance role to lean on, and you do not want long-lived access keys sitting in it. The answer is **IAM Roles Anywhere**: the cluster presents an X.509 certificate from a trusted CA (a **Trust Anchor**) and exchanges it for short-lived STS credentials scoped to the ECR pull role.

```hcl
resource "aws_rolesanywhere_trust_anchor" "cluster" {
  name    = "baremetal-cluster"
  enabled = true
  source {
    source_type = "CERTIFICATE_BUNDLE"
    source_data {
      x509_certificate_data = file(var.cluster_ca_pem)   # your cluster's CA
    }
  }
}

resource "aws_rolesanywhere_profile" "ecr_pull" {
  name      = "ecr-pull"
  role_arns = [aws_iam_role.ecr_pull.arn]                # the read-only pull role
  enabled   = true
}
```

This is the hinge between the two posts: Part 2 is entirely about the cluster side of this — turning that certificate into a working `imagePullSecret`, with no static credentials anywhere.

## Delivered by CI, not by hand

None of this is `apply`-ed from a laptop. A GitHub Actions pipeline runs the Terraform with a clean separation of plan and apply:

- **On PR:** `terraform fmt -check`, `validate`, and `plan` — the plan is posted for review. A security scan (Checkov/Trivy) and `terraform test` run here too.
- **On merge to `main`:** an **approval-gated apply** — the real credential (via OIDC to AWS, no stored keys) is only exposed to the trusted apply job on `main`, never to PR builds from forks.
- **Destroy** is a separate, deliberate, controlled workflow — never automatic.

```yaml
# Simplified: PR plans are safe; only trusted main applies with real creds.
jobs:
  plan:
    if: github.event_name == 'pull_request'
    steps:
      - run: terraform init -backend=false
      - run: terraform validate
      - run: terraform plan -no-color      # posted to the PR; no apply
  apply:
    if: github.ref == 'refs/heads/main'
    environment: production                # requires manual approval
    permissions: { id-token: write }       # OIDC to AWS — no long-lived keys
    steps:
      - run: terraform apply -auto-approve
```

The principle: a pull request can *propose* an infrastructure change and show its plan, but it can never *make* one. Only a reviewed merge to `main`, through an approval gate, with short-lived OIDC credentials, can apply.

## What "done" looks like for Part 1

- `terraform apply` creates every repository from the module with KMS encryption, immutability (for release repos), lifecycle policies, and scan-on-push.
- A pull-through cache rule proxies Docker Hub, backed by a Secrets Manager credential on the AWS-managed key.
- Three least-privilege IAM roles exist (push, pull, manage), and a Roles Anywhere trust anchor + profile are ready for the cluster.
- The whole thing plans on PR and applies only through an approval-gated, OIDC-authenticated pipeline on `main`.
- A first smoke pull of `dockerhub/library/nginx` through the cache succeeds and caches the image.

The registry now exists, is hardened, and is reproducible. The question Part 2 answers: how does a Kubernetes cluster that lives on bare metal — with no EC2 instance role — actually *pull* from it, securely and without static credentials?

Next: [Part 2 — using ECR from a bare-metal Kubernetes cluster](/posts/production-ecr-2-baremetal-pull/).

---

*Notes from real production AWS/Terraform work. Account IDs, ARNs, regions, and secrets are placeholders — adapt to your environment and never commit real credentials or private keys.*
