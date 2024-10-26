#!/bin/bash

# 检测 Debian 系统（如 Ubuntu）
if grep -qEi "(debian|ubuntu)" /etc/*release; then
    apt-get update -yq --fix-missing && \
    DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends \
    pkg-config \
    wget \
    cmake \
    curl \
    git \
    vim \
    build-essential \
    libgl1-mesa-glx \
    portaudio19-dev \
    libnss3 \
    libxcomposite1 \
    libxrender1 \
    libxrandr2 \
    libqt5webkit5-dev \
    libxdamage1 \
    libxtst6 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
# 检测 CentOS 系统
elif grep -qEi "(centos|fedora|rhel)" /etc/*release; then
    yum update -y && \
    yum install -y \
    pkgconfig \
    wget \
    cmake \
    curl \
    git \
    vim-enhanced \
    gcc \
    gcc-c++ \
    mesa-libGL \
    portaudio \
    nss \
    libXcomposite \
    libXrender \
    libXrandr \
    qt5-qtwebkit-devel \
    libXdamage \
    libXtst && \
    yum clean all
else
    echo "Unsupported OS"
    exit 1
fi
