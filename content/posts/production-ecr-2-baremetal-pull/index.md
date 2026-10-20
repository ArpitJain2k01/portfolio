+++
title = "Production-Grade ECR with Terraform, Part 2: Pulling from a Bare-Metal Cluster"
date = 2026-10-20
draft = false
summary = "A bare-metal Kubernetes cluster has no EC2 instance role to lean on, and you don't want static AWS keys living in it. Here's how it authenticates to ECR with IAM Roles Anywhere — turning an X.509 certificate into short-lived STS credentials, into an ECR token, into an auto-refreshed imagePullSecret — and pulls through the Docker Hub cache, with no long-lived credentials anywhere."
tags = ["aws", "ecr", "kubernetes", "iam", "on-prem"]
showTableOfContents = true
+++

This is Part 2 of a two-part series on production ECR:

1. [Building the registry with Terraform](/posts/production-ecr-1-terraform/)
2. **Pulling from a bare-metal Kubernetes cluster** (this post)

In [Part 1](/posts/production-ecr-1-terraform/) we built a hardened ECR — repositories, lifecycle, scanning, a Docker Hub pull-through cache, and least-privilege IAM including an **IAM Roles Anywhere** trust anchor for the cluster. This post is the other side of that hinge: how a Kubernetes cluster that doesn't run on AWS actually authenticates and pulls, without a single long-lived credential.

## The problem: no instance role, no static keys

On EKS or EC2, pulling from ECR is almost free — the node's IAM instance role grants it, and the kubelet's ECR credential provider handles the token automatically. A bare-metal cluster has none of that:

- There is **no EC2 instance role** attached to the nodes.
- You **must not** drop a long-lived AWS access key into the cluster — it's a static, exfiltratable credential that never rotates, exactly what Part 1's IAM design avoided.
- ECR authorization tokens are **short-lived (12 hours)** — so even once you can get one, something has to keep refreshing it.

So the real task is a credential *chain* that starts from something the cluster legitimately holds (an X.509 certificate) and ends in a Kubernetes `imagePullSecret` that's always fresh.

## The credential chain

```text
cluster X.509 cert  (trusted by the Roles Anywhere Trust Anchor from Part 1)
        │  aws_signing_helper
        ▼
short-lived STS credentials  (assume the ECR pull role, ~1 hour)
        │  aws ecr get-login-password
        ▼
ECR authorization token  (12-hour docker credential)
        │  kubectl create secret docker-registry
        ▼
imagePullSecret  (what the kubelet uses to pull)
```

Nothing in that chain is long-lived or stored. The certificate proves identity; everything downstream is minted on demand and expires on its own.

## Step 1 — certificate to STS credentials

AWS ships `aws_signing_helper` (the IAM Roles Anywhere credential helper). Given the cluster's certificate, private key, and the Trust Anchor / Profile / Role ARNs from Part 1, it returns temporary STS credentials:

```bash
aws_signing_helper credential-process \
  --certificate   /etc/aws/cluster.crt \
  --private-key    /etc/aws/cluster.key \
  --trust-anchor-arn arn:aws:rolesanywhere:…:trust-anchor/… \
  --profile-arn      arn:aws:rolesanywhere:…:profile/… \
  --role-arn         arn:aws:iam::<acct>:role/ecr-pull
```

The private key stays on the host (or better, in a TPM/HSM the helper can reference) and never leaves it. The output is a short-lived credential set — exactly the kind of ephemeral access the whole design is built around.

## Step 2 — STS credentials to an ECR token to a pull secret

With those temporary credentials, `aws ecr get-login-password` returns the 12-hour ECR authorization token, which becomes a standard Docker registry secret:

```bash
TOKEN=$(aws ecr get-login-password --region ap-south-1)

kubectl create secret docker-registry ecr-creds \
  --docker-server="<acct>.dkr.ecr.ap-south-1.amazonaws.com" \
  --docker-username=AWS \
  --docker-password="$TOKEN" \
  --namespace app \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Step 3 — keep it fresh with a CronJob

Because the ECR token expires every 12 hours, a one-shot secret rots. A small in-cluster **CronJob** re-runs the chain on a schedule (say every 6 hours) and rewrites the `imagePullSecret`, so the kubelet always has a valid credential:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ecr-credential-refresh
  namespace: app
spec:
  schedule: "0 */6 * * *"          # refresh well before the 12h expiry
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: ecr-refresher   # RBAC: may write the one secret
          restartPolicy: OnFailure
          containers:
            - name: refresh
              image: <acct>.dkr.ecr.ap-south-1.amazonaws.com/tools/ecr-login:1.0
              command: ["/bin/sh", "-c"]
              args:
                - |
                  TOKEN=$(aws ecr get-login-password --region ap-south-1)
                  kubectl create secret docker-registry ecr-creds \
                    --docker-server="$ECR_REGISTRY" \
                    --docker-username=AWS --docker-password="$TOKEN" \
                    --dry-run=client -o yaml | kubectl apply -f -
```

The refresher's own AWS auth comes from `aws_signing_helper` wired as a `credential_process` in its AWS config — so even the refresher holds no static key. Its Kubernetes RBAC is scoped to writing exactly one secret in one namespace, nothing more.

Then workloads just reference the secret — or, cleaner, attach it to the namespace's default service account so every pod inherits it:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: default
  namespace: app
imagePullSecrets:
  - name: ecr-creds
```

## Pulling through the cache

Now the pull-through cache from Part 1 pays off. A workload references a Docker Hub image *through* ECR, and the cluster never touches Docker Hub directly:

```yaml
# Instead of  image: nginx:1.27
image: <acct>.dkr.ecr.ap-south-1.amazonaws.com/dockerhub/library/nginx:1.27
```

On the first pull, ECR fetches `nginx:1.27` from Docker Hub (using the Secrets Manager credential from Part 1), caches it, and serves it to the node. Every subsequent pull — across every node — is served from ECR. The bare-metal cluster is now immune to Docker Hub rate limits and upstream outages, and every image it runs, public or private, is one that ECR has scanned.

## Trusting the endpoint

ECR's endpoints use public, well-known TLS, so there's no custom CA to install for the registry itself (unlike the on-prem Quay case). What the cluster *does* need:

- **Outbound reachability** to the ECR, STS, and Roles Anywhere endpoints in your region (and the Secrets Manager/ECR path for the first cache fill).
- **Correct clock** — certificate and STS signature validation are time-sensitive; a skewed node clock produces confusing `SignatureDoesNotMatch` / expired-credential errors. Run NTP.

## Why this design holds up

Walk back through what's *not* in the cluster: no AWS access key, no secret-access-key, no long-lived token. The only durable thing is an X.509 certificate whose matching private key never leaves the host, backing a role that can do exactly one thing — pull from specific ECR repositories. Every credential downstream of that cert is short-lived and self-expiring, and the refresher keeps the pull secret current automatically. Compromising a node yields, at worst, read access to the images you were already going to run — and only until the short-lived credentials expire.

That's the whole arc of the series: in [Part 1](/posts/production-ecr-1-terraform/) Terraform builds a hardened, cached, least-privilege registry; here, a cluster with no native AWS identity consumes it safely, with nothing static to steal.

## What "done" looks like for Part 2

- `aws_signing_helper` returns valid STS credentials from the cluster certificate.
- The `ecr-credential-refresh` CronJob writes/updates the `ecr-creds` `imagePullSecret` on schedule.
- A pod referencing `<acct>.dkr.ecr…/dockerhub/library/nginx` pulls successfully, and ECR shows the image cached after the first pull.
- `kubectl get secret ecr-creds` is always valid; grep the cluster — there is no static AWS key anywhere.

---

*Notes from real production AWS/Terraform/Kubernetes work. Account IDs, ARNs, regions, paths, and secrets are placeholders — adapt to your environment and never commit real credentials or private keys.*
