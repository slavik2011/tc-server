# Use an official Python image as a base
FROM python:3.10-slim

# Set environment variables
ENV PATH /home/root/.local/bin:${PATH}

# Copy requirements file
COPY req.txt .

# Update system and install dependencies
RUN apt update && \
    apt install -y python3-pip && \
    apt install -y --no-install-recommends gcc && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r req.txt && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code
COPY . .

# Set the command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]
