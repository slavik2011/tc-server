# Set the default port (can be overridden)
ARG PORT=443

# Use the Cypress browsers base image
FROM cypress/browsers:latest
FROM apache/airflow:2.1.4
USER root
# Install required packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    unzip \
    wget \
    xvfb \
    curl \
    gnupg2 \
    && apt-get clean

RUN apt-get update                             \
 && apt-get install -y --no-install-recommends \
    ca-certificates curl firefox-esr           \
 && rm -fr /var/lib/apt/lists/*                \
 && curl -L https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz | tar xz -C /usr/local/bin \
 && apt-get purge -y ca-certificates curl

# Copy requirements file
COPY req.txt .

# Update PATH for local bin
ENV PATH="/home/root/.local/bin:${PATH}"

RUN pip install PyXDG --break-system-packages

# Install Python packages
RUN pip install --no-cache-dir -r req.txt --break-system-packages

# Set the display port to avoid errors
ENV DISPLAY=:99

# Copy the rest of the application code
COPY . .

USER airflow

# Command to run your application
CMD python3 main.py $PORT
