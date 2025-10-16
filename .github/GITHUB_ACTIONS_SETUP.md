# GitHub Actions CI/CD Setup

This document describes the automated CI/CD pipeline configured for TrackFolio.

## Overview

The workflow automatically builds and pushes Docker images to GitHub Container Registry (GHCR) whenever you push to `main` or `dev` branches.

## Workflow: `build-and-push.yml`

### Triggers
- Automatically runs when code is pushed to `main` or `dev` branches
- Can be manually triggered via Actions tab in GitHub

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

## Next Steps

1. **Push to main or dev branch** to trigger the first build
2. **Go to Actions tab** to monitor the build
3. **Check GHCR** (Packages tab) to see your images
4. **Pull and test locally** if desired
5. **Update docker-compose.yml** to use GHCR images for remote deployments

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

### Build on Pull Requests

Add to the `on:` section:

```yaml
on:
  pull_request:
    branches:
      - main
      - dev
```

This will lint and build PRs but won't push images.
