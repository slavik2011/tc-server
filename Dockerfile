# Set the default port (can be overridden)
ARG PORT=443

# Use the Cypress browsers base image
FROM cypress/browsers:latest
FROM instrumentisto/geckodriver:latest

RUN apk add --no-cache firefox-esr

# Install Geckodriver
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
RUN apk add --no-cache --virtual .build-deps wget \
    && GECKODRIVER_VERSION=$(wget -qO- https://api.github.com/repos/mozilla/geckodriver/releases/latest \
    | grep "tag_name" | sed -E 's/.*"([^"]+)".*/\1/') \
    && wget -qO /tmp/geckodriver.tar.gz \
    "https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz" \
    && tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin/ \
    && rm /tmp/geckodriver.tar.gz \
    && apk del .build-deps

# Copy requirements file
COPY req.txt .

# Update PATH for local bin
ENV PATH="/home/root/.local/bin:${PATH}"

# Install Python packages
RUN pip install --no-cache-dir -r req.txt

# Set the display port to avoid errors
ENV DISPLAY=:99

# Copy the rest of the application code
COPY . .

# Command to run your application
CMD python3 main.py $PORT
