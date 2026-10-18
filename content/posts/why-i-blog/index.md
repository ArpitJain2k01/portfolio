+++
title = "Why I'm Building a Learning Log in Public"
date = 2026-10-18
draft = false
summary = "Starting a public engineering journal: what I'll write about, why writing it down makes me learn faster, and why showing the work beats listing it on a resume."
tags = ["meta", "career"]
showTableOfContents = true
+++

This site is my engineering notebook, in public.

I spend most of my week deep in Kubernetes, AWS, Terraform, and the security glue that holds platforms together. A lot of that work never leaves a terminal or a pull request. This blog is where I write it down — not as polished tutorials, but as honest notes on what I tried, what broke, and what I understood by the end.

## Why in public

Three reasons.

**Writing forces understanding.** It's easy to feel like you understand something after it works. Explaining it in plain words is a much harder test — and it's where I find the gaps in my own mental model. If I can't write the "why," I didn't really get it.

**It compounds.** A note I write today is something future-me can search in six months when the same error message shows up again. Over a year, that becomes a personal reference built from real problems I actually solved.

**It shows the work.** A resume says "Kubernetes, Terraform, CI/CD." A post about debugging a fail-closed admission policy, or hardening a workload's `securityContext` without breaking it, *shows* the depth behind those words. For anyone evaluating me — a recruiter, a hiring manager, a future teammate — that's far more useful than a bullet list.

## What to expect here

- **Hands-on labs** — things I ran myself, with the commands and the output, not copied from docs.
- **Production patterns** — the design decisions behind real infrastructure, and the trade-offs I'd defend.
- **Deep dives** — the occasional "I went down a rabbit hole and here's what's at the bottom."
- **Mistakes** — the ones worth remembering, written down so I don't repeat them.

The topics will cluster around what I work on: Kubernetes and platform engineering, AWS, Terraform and IaC, GitOps, observability, and infrastructure security.

## The standard I'm holding myself to

Everything here aims to be correct and reproducible. If I show a command, I ran it. If I show a result, that's what I saw. Where I'm uncertain, I'll say so. A learning log is only useful if it's honest about the edges of what I know.

That's the whole idea. Next post, we get our hands dirty.
