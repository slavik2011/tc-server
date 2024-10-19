# Set the default port (can be overridden)
ARG PORT=443

# Use the Cypress browsers base image
FROM cypress/browsers:latest

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

# Add the Mozilla PGP key and repository for Firefox
RUN curl -fsSL https://mozilla.debian.net/archive-key.gpg | gpg --dearmor -o /usr/share/keyrings/mozilla-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/mozilla-archive-keyring.gpg] http://mozilla.debian.net/ stable main" > /etc/apt/sources.list.d/mozilla.list && \
    apt-get update && \
    apt-get install -y firefox && \
    apt-get clean

# Install GeckoDriver
RUN GECKODRIVER_VERSION=`wget -qO- https://api.github.com/repos/mozilla/geckodriver/releases/latest | grep -Po '"tag_name": "\K[^"]*'` && \
    wget https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz && \
    tar -xvzf geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz && \
    mv geckodriver /usr/local/bin/ && \
    chmod +x /usr/local/bin/geckodriver && \
    rm geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz

# Copy requirements file
COPY req.txt .

# Update PATH for local bin
ENV PATH="/home/root/.local/bin:${PATH}"

# Install Python packages
RUN pip install --no-cache-dir -r req.txt --break-system-packages

# Set the display port to avoid errors
ENV DISPLAY=:99

# Copy the rest of the application code
COPY . .

# Command to run your application
CMD python3 main.py $PORT
