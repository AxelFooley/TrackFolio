# GitHub Actions CI/CD Setup

This document describes the automated CI/CD pipeline configured for TrackFolio.

## Overview

The workflow automatically builds and pushes Docker images to GitHub Container Registry (GHCR) whenever you push to `main` or `dev` branches.

## Workflow: `build-and-push.yml`

### Triggers
- **On Push**: Automatically runs and builds/pushes images when code is pushed to `main` or `dev` branches
- **On Pull Request**: Automatically runs linting and tests when PRs target `main` or `dev` (builds but does NOT push images)
- **Manual**: Can be manually triggered via Actions tab in GitHub

### What It Does

#### 1. **Setup Job**
- Determines the appropriate image tag based on branch:
  - `main` → tag: `latest`
  - `dev` → tag: `dev`
- Generates image names for backend and frontend
- Stores git short SHA for traceability

#### 2. **Lint Backend Job**
- Sets up Python 3.11 environment
- Installs all backend dependencies from `requirements.txt`
- Runs `flake8` linting (checks syntax, basic style)
- Runs `pytest` tests (if available)
- ✅ Must pass before building backend image

#### 3. **Lint Frontend Job**
- Sets up Node.js 18 environment
- Installs dependencies from `package.json`
- Runs `npm run lint` (ESLint)
- ✅ Must pass before building frontend image

#### 4. **Build Backend Image**
- Only runs if lint-backend job passes
- Uses Docker Buildx for multi-platform builds (amd64 + arm64)
- Builds image from `backend/Dockerfile`
- Tags images as:
  - `ghcr.io/AxelFooley/trackfolio-backend:latest` (for main)
  - `ghcr.io/AxelFooley/trackfolio-backend:dev` (for dev)
  - `ghcr.io/AxelFooley/trackfolio-backend:<short-sha>` (always)
- Pushes to GHCR
- Uses GitHub Actions cache for faster builds

#### 5. **Build Frontend Image**
- Only runs if lint-frontend job passes
- Uses Docker Buildx for multi-platform builds (amd64 + arm64)
- Builds image from `frontend/Dockerfile`
- Tags images as:
  - `ghcr.io/AxelFooley/trackfolio-frontend:latest` (for main)
  - `ghcr.io/AxelFooley/trackfolio-frontend:dev` (for dev)
  - `ghcr.io/AxelFooley/trackfolio-frontend:<short-sha>` (always)
- Pushes to GHCR
- Uses GitHub Actions cache for faster builds

#### 6. **Notify Job**
- Reports success or failure of the entire pipeline

### Pull Request Workflow

When you open a PR targeting `main` or `dev`:

1. ✅ Linting jobs run (flake8, pytest, eslint)
2. ✅ Build jobs run (creates Docker images)
3. ❌ **Images are NOT pushed to GHCR** (only for actual merges)
4. 📊 Workflow status is reported on the PR

This allows reviewers to see if the code passes quality checks before approving the merge.

### Image Tags Explained

Each push creates multiple tags for traceability:

**For main branch:**
```
ghcr.io/AxelFooley/trackfolio-backend:latest
ghcr.io/AxelFooley/trackfolio-backend:a1b2c3d
```

**For dev branch:**
```
ghcr.io/AxelFooley/trackfolio-backend:dev
ghcr.io/AxelFooley/trackfolio-backend:a1b2c3d
```

The short SHA (`a1b2c3d`) allows you to deploy specific commits if needed.

## Authentication

GHCR authentication is handled automatically:

- **Token Used**: `GITHUB_TOKEN` (automatically provided by GitHub Actions)
- **Permissions**: Automatically scoped to `write:packages` for your repository
- **No Setup Needed**: The workflow uses this token automatically
- **Image Access**: Images are private by default (only accessible to repository collaborators)

### Making Images Public (Optional)

If you want to make images public:

1. Go to your repository on GitHub
2. Click "Packages" tab
3. Click on the package (e.g., `trackfolio-backend`)
4. Click "Package settings" (gear icon)
5. Under "Danger Zone", select "Make public"

## Workflow Status

### View Workflow Runs
1. Go to your repository on GitHub
2. Click the "Actions" tab
3. Click "Build and Push Docker Images" to see all runs
4. Click a specific run to see details

### Workflow Badges (Optional)

You can add a status badge to your README:

```markdown
[![Build and Push Docker Images](https://github.com/AxelFooley/TrackFolio/actions/workflows/build-and-push.yml/badge.svg)](https://github.com/AxelFooley/TrackFolio/actions/workflows/build-and-push.yml)
```

## Using the Built Images

### Pull Images Locally

```bash
# Latest backend image
docker pull ghcr.io/AxelFooley/trackfolio-backend:latest

# Dev backend image
docker pull ghcr.io/AxelFooley/trackfolio-backend:dev

# Specific commit
docker pull ghcr.io/AxelFooley/trackfolio-backend:a1b2c3d
```

### Login to GHCR

```bash
# Create a PAT (Personal Access Token) with read:packages scope
# Then login with:
echo $TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

### Update docker-compose.yml

To use GHCR images in docker-compose:

```yaml
services:
  backend:
    image: ghcr.io/AxelFooley/trackfolio-backend:latest
    # rest of config...

  frontend:
    image: ghcr.io/AxelFooley/trackfolio-frontend:latest
    # rest of config...
```

## Troubleshooting

### Build Fails Due to Linting

1. **Backend linting errors**: Run locally to fix:
   ```bash
   docker compose exec backend flake8 app/
   ```

2. **Frontend linting errors**: Run locally to fix:
   ```bash
   docker compose exec frontend npm run lint
   ```

### Build Fails Due to Tests

1. **Backend tests**: Run locally:
   ```bash
   docker compose exec backend pytest tests/ -v
   ```

2. **Frontend tests**: Run locally:
   ```bash
   docker compose exec frontend npm test
   ```

### Slow Builds

- First build is slow (builds cache)
- Subsequent builds are faster due to GitHub Actions cache
- Multi-platform builds (amd64 + arm64) take ~5-10 minutes
- Standard amd64-only builds take ~2-3 minutes

## Security Considerations

- ✅ `GITHUB_TOKEN` is automatically rotated after each workflow run
- ✅ Images are private by default
- ✅ Only linted code is built
- ✅ Only tested code is pushed
- ✅ Container registry requires GitHub authentication

## Typical Workflow

1. **Create a feature branch** from `dev`
2. **Push to your feature branch** - no workflow runs
3. **Create a Pull Request** targeting `dev`
   - Linting and tests run on your PR
   - Reviewers see if code passes quality checks
4. **After PR approval**, merge into `dev`
   - Workflow runs and pushes image with `dev` tag
   - `ghcr.io/AxelFooley/trackfolio-backend:dev` is updated
5. **Create PR from `dev` to `main`** when ready for release
   - Same linting and test checks
6. **Merge into `main`**
   - Workflow runs and pushes image with `latest` tag
   - `ghcr.io/AxelFooley/trackfolio-backend:latest` is updated

## Next Steps

1. **Go to Actions tab** to see your workflow
2. **Create a test PR** to see the workflow in action
3. **Merge a PR** to trigger the build and push
4. **Check Packages tab** to see your built images in GHCR
5. **Pull and test images locally** if desired
6. **Update docker-compose.yml** to use GHCR images for remote deployments

## Advanced Customization

### Build Only for amd64 (Faster)

Edit `.github/workflows/build-and-push.yml` and change:

```yaml
platforms: linux/amd64
```

This reduces build time from ~5-10 min to ~2-3 min.

### Skip Linting

Not recommended, but you can remove the `needs: [setup, lint-*]` dependency if needed.

### Add Slack/Discord Notifications

Add a notification step after the notify job to send alerts to your preferred platform.

### Limit Builds to Specific Paths (Optional)

To only build when specific files change (e.g., backend OR frontend, not dependencies):

```yaml
on:
  push:
    branches:
      - main
      - dev
    paths:
      - 'backend/**'
      - 'frontend/**'
      - '.github/workflows/build-and-push.yml'
  pull_request:
    branches:
      - main
      - dev
    paths:
      - 'backend/**'
      - 'frontend/**'
```

This prevents unnecessary builds when only documentation or other unrelated files change.
