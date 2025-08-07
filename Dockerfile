FROM python:3.12

# Expose Cloud Run expected port
EXPOSE 8080

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Run Streamlit on Cloud Run expected port
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
