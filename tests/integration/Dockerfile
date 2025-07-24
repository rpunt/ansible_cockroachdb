FROM ubuntu:22.04

# Set non-interactive mode to avoid hanging on tzdata configuration
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-pip \
    build-essential \
    apt-transport-https \
    ca-certificates \
    gnupg \
    openssh-server \
    openssh-client \
    lsb-release \
    sudo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up SSH
RUN mkdir /var/run/sshd
RUN echo 'root:root' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Configure sudo without password
RUN echo 'root ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/root
RUN chmod 0440 /etc/sudoers.d/root

# Install Python packages
RUN pip3 install ansible pytest

# Expose SSH port
EXPOSE 22

# Start SSH server
CMD ["/usr/sbin/sshd", "-D"]
