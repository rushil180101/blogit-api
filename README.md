# Blog posting and management REST API

REST APIs for managing blog posts and users.

## Tech stack
- Programming language: Python
- Framework: FastAPI
- Database: Postgres (via Neon)
- Media files storage: AWS S3
- API deployment: Google Cloud (Cloud run, Cloud build, Artifact registry)
- Docker

## Deployed the API service on Google cloud
- Cloud run (run.googleapis.com): For running the containers
- Cloud build (cloudbuild.googleapis.com): For building docker images in the cloud
- Artifact registry (artifactregistry.googleapis.com): For storing docker images
