# Set the default port (can be overridden)
ARG PORT=443

# Use the Cypress browsers base image
FROM cypress/browsers:latest

# Install Python 3
RUN apt-get update && apt-get install -y python3 python3-pip

# Set up the Python environment
RUN echo $(python3 -m site --user_base)

# Copy requirements file
COPY req.txt .

# Update PATH for local bin
ENV PATH="/home/root/.local/bin:${PATH}"

# Install Python packages
RUN pip install --no-cache-dir -r req.txt --break-system-packages

# Install required packages
RUN apt-get update && \
    apt-get install -y \
    unzip \
    wget \
    firefox \
    && apt-get clean
    
RUN apt-get install -y firefox

# Install GeckoDriver
RUN GECKODRIVER_VERSION=v0.30.0 && \
    wget https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz && \
    tar -xvzf geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz && \
    mv geckodriver /usr/local/bin/ && \
    chmod +x /usr/local/bin/geckodriver && \
    rm geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz

# Add GeckoDriver to PATH
ENV PATH="/usr/local/bin:${PATH}"

# Set the display port to avoid errors
ENV DISPLAY=:99

# Copy the rest of the application code
COPY . .

# Command to run your application
CMD python3 main.py $PORT
