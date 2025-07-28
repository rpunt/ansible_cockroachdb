FROM python:3.12-alpine

# Environment variables to prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Install dependencies
RUN apk add --no-cache \
    gcc \
    python3-dev \
    postgresql-dev \
    openssh \
    sudo \
    curl \
    ca-certificates \
    wget \
    unzip \
    tar \
    gzip \
    musl-dev \
    linux-headers

# Install Python packages
RUN pip install --no-cache-dir ansible pytest pytest-mock pytest-ansible psycopg2-binary

# Set up SSH for testing
RUN mkdir /var/run/sshd
RUN echo 'root:password' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN echo 'PermitUserEnvironment yes' >> /etc/ssh/sshd_config

# Configure sudo for ansible user
RUN echo "ALL ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/nopasswd

# Create working directory
WORKDIR /collection

# Copy test runner script
COPY docker/test_runner.sh /test_runner.sh
RUN chmod +x /test_runner.sh

# Expose SSH port
EXPOSE 22

# Default command to run SSH server
CMD ["/usr/sbin/sshd", "-D"]
