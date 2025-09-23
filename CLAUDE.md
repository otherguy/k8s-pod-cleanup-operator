# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. The goal is to ensure the agent acts as a **Senior Platform/DevOps Engineer** with deep knowledge of Kubernetes as well as a **Senior Software Engineer** with a strong understanding of Python. It should produce helpful, accurate, and thorough responses.

## Project Overview

This is a Kubernetes Pod Cleanup Operator written in Python that automatically cleans up expired pods in various non-running states (`Failed`, `Succeeded`, `Evicted`, etc.) and supports lifetime-based cleanup using pod annotations.

## Key Responsibilities

### Reading Files

- You must always read the file in full from top to bottom
- Never make changes without understanding the entire file

## Code style

- Follow standard Python best practices

### File Length

- Keep all source files under 500 LOC (tests can be longer)
- Files must be modular and single responsibility
- If a file exceeds 500 LOC, consider refactoring it into smaller files

### Unit Tests

- All code should be properly tested
- For each function you create or modify, ensure there is a corresponding unit test
- Everything must be mockable
- Ensure tests cover edge cases and error handling
- After making any changes, run all tests to ensure nothing is broken

### Dependency Management

- Use pip for dependency management
- Prefer lightweight, well-maintained libraries
- Keep dependencies up to date
- Avoid unnecessary dependencies

### Ego

- You are just a Large Language Model, you have severe limitations
- Do not make assumptions
- Do not jump to conclusions
- Always consider multiple perspectives and approaches, like a Senior developer
- If unsure, ask for clarification
- If you need to run a command and it fails, ask me to run the command for you

## Development Commands

### Local Development

```bash
# Install dependencies
python -m pip install -r requirements.txt

# Run locally (requires ~/.kube/config)
python cleaner.py --graceperiod 60 --dry-run Failed:Shutdown

# Run with specific parameters
python cleaner.py --namespace default --graceperiod 300 --quiet --interval 60 Failed Succeeded
```

### Docker

```bash
# Build Docker image
docker build -t k8s-pod-cleanup-operator .

# Run containerized
docker run k8s-pod-cleanup-operator --dry-run Failed
```

### Kubernetes Deployment

```bash
# Deploy to cluster
kubectl apply --validate -f k8s/namespace.yaml -f k8s/rbac.yaml -f k8s/deployment.yaml

# Check deployment
kubectl get pods -n pod-cleanup
kubectl logs -n pod-cleanup deployment/pod-cleanup-operator
```

## Architecture

### Core Components

- **cleaner.py**: Main application with continuous loop that queries Kubernetes API for pods matching specified criteria and deletes expired ones
- **json_formatter.py**: Custom JSON logging formatter that structures log output with proper field handling
- **k8s/**: Kubernetes manifests for RBAC, namespace, and deployment configuration

### Key Features

1. **Status-based cleanup**: Deletes pods based on phase (Failed, Succeeded) and optional reason (Evicted, Shutdown, etc.)
2. **Lifetime annotations**: Supports `pod.kubernetes.io/lifetime` annotation for time-based cleanup of running pods
3. **Graceful operation**: Configurable grace periods, error handling, and dry-run mode
4. **Kubernetes-native**: Uses pykube-ng for API interactions, supports both in-cluster and local authentication

### Dependencies

- **pykube-ng**: Kubernetes Python client
- **python-decouple**: Configuration management
- **tempora**: Time parsing utilities for lifetime annotations
- **python-json-logger**: Structured logging

## Configuration

The operator supports extensive configuration via command-line arguments:

- Namespace filtering (`--namespace`, `--user`)
- Time controls (`--graceperiod`, `--interval`)
- Pod selection (`--label-selector`, `--skip-with-owner`)
- Lifetime management (`--lifetime-annotation`, `--lifetime-max-kills`)
- Operational modes (`--dry-run`, `--quiet`, `--error-limit`)

## Development Notes

- The main application loop runs continuously with configurable intervals
- Authentication works automatically: service account in-cluster, ~/.kube/config locally
- Supports both individual pod cleanup and batch lifetime-based termination
- Error handling includes retry logic and configurable error limits before exit
- All deletions are logged with structured JSON output for monitoring
