# Container for running orchestrator_hardened.py
# Build:  docker build -t battlecode-orch .
# Run it with run_contained.sh, which sets the safety flags.

FROM python:3.12-slim

ENV ORCH_IN_CONTAINER=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# git is used by the orchestrator for local commits. Add other system
# packages your bots or cambc need here (e.g. a JDK or Rust toolchain).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install claude-agent-sdk

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Non-root user with a throwaway home: no ~/.ssh, no ~/.aws, nothing personal.
RUN useradd --create-home --uid 1000 agent
USER agent
WORKDIR /work

# The project folder is mounted at /work at run time (see run_contained.sh).
CMD ["python", "orchestrator_hardened.py"]
