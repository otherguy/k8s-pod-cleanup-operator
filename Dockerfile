# syntax = docker/dockerfile:1.2

# Start with Python base image
FROM python:3.12.2

# Maintainer
LABEL maintainer="Alexander Graf <hi@otherguy.io"

# Required to prevent warnings
ARG DEBIAN_FRONTEND=noninteractive
ARG DEBCONF_NONINTERACTIVE_SEEN=true

# Change workdir
WORKDIR /app/
RUN useradd -u 65532 -ms /bin/bash service && chown -R service /app
USER 65532:65532

# Copy dependencies
COPY --chown=service requirements.txt .

# Install requirements
RUN pip3 install -r requirements.txt --progress-bar off

# Copy app
COPY --chown=service . .

# Build arguments
ARG VCS_REF=main
ARG BUILD_DATE=""
ARG VERSION="${VCS_REF}"

# http://label-schema.org/rc1/

LABEL org.label-schema.schema-version '1.0'
LABEL org.label-schema.name           'k8s-pod-cleanup-operator'
LABEL org.label-schema.description    'A Kubernetes Operator to clean up expired pods in any desired non-running state.'
LABEL org.label-schema.vcs-url        'https://github.com/otherguy/k8s-pod-cleanup-operator'
LABEL org.label-schema.version        '${VERSION}'
LABEL org.label-schema.build-date     '${BUILD_DATE}'
LABEL org.label-schema.vcs-ref        '${VCS_REF}'

# Expose environment variables to app
ENV VCS_REF="${VCS_REF}"
ENV BUILD_DATE="${BUILD_DATE}"
ENV VERSION="${VERSION}"

# Configure app
ENV PYTHONUNBUFFERED="1"

# Entrypoint
ENTRYPOINT [ "python3", "/app/cleaner.py" ]

# Empty CMD
CMD [""]
