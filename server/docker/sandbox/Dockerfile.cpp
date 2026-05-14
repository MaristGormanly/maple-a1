FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        git \
        libgtest-dev \
        ninja-build \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*
