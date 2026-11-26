# Agent Guide — `colab-playground` (Draw Studio)

## Source of Truth & Release Pipeline

- **Canonical Repo**: Private GitHub repository `M1nt-Ch0c0/colab-playground` (`main` branch).
- **Production Runtime**: Managed by **Dokploy** (`https://ops.m1ntch0c0.com`, project `Draw Studio`, app `colab-playground`, service `colab-playground-87tmi6`) on `dogcloud-mg-cpa`, mounting `/var/lib/colab-playground:/data`.
- **Standard Release Flow (Scheme B · Tag Trigger)**:
  1. Edit code in this Git repository and run unit tests (`tests/test_backend_v21.py`, `tests/test_comfy_mode.py`, `tests/test_workflows.py`) + JS check (`node --check` on `ui._JS`).
  2. Merge to `main`, create a semantic version tag (`git tag v3.0.0 && git push origin v3.0.0`), or trigger `workflow_dispatch` manually.
  3. GitHub Actions (`.github/workflows/build-and-deploy.yml`) automatically runs tests, builds the Docker image (with `ffmpeg`), pushes to `asia-east1-docker.pkg.dev/cpa-platform-e9b3/cpa-images/colab-playground:<tag>-<sha>` + `:latest`, and triggers Dokploy deployment. Ordinary `git push` to branches does **not** deploy production.

## Guardrails for All Agents

1. **NEVER develop or build directly on the VPS**: Do NOT edit `/opt/colab-playground` (deprecated legacy copy) or `/tmp/*` on `dogcloud-mg-cpa`, do NOT run local `docker build` on the VPS, and do NOT bypass Dokploy with `docker service update` unless the user explicitly asks for an emergency hotfix.
2. **Never commit or print secrets**: `secret.env`, `colab_token.json`, `hf_token.txt`, `proxy_custom.txt`, and cloud credentials live only in `/var/lib/colab-playground` or GitHub Secrets.
3. **Host GCP SA is read-only for Artifact Registry**: Pushing images to `asia-east1-docker.pkg.dev` is performed exclusively by GitHub Actions (`GCP_AR_SA_KEY`).
