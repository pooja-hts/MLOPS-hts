#!/usr/bin/env python3
"""
Google Cloud Storage Configuration
Updated via Streamlit UI - 2025-08-20 18:12:03
Cloud-First Architecture: Google Cloud Storage Only
"""

import os
from google.oauth2 import service_account
from google.cloud import storage

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# GCS Configuration - Always enabled for cloud-first mode
USE_GCS = True
GCS_BUCKET_NAME = "scraped-data-bucket-hts-big-traderz"
GCS_DATA_FOLDER = "data"

# GCP Credentials from environment variables
GCP_CREDENTIALS = {
    "type": os.getenv("type"),
    "project_id": os.getenv("project_id"),
    "private_key_id": os.getenv("private_key_id"),
    "private_key": os.getenv("private_key").replace('\\n', '\n') if os.getenv("private_key") else None,
    "client_email": os.getenv("client_email"),
    "client_id": os.getenv("client_id"),
    "auth_uri": os.getenv("auth_uri"),
    "token_uri": os.getenv("token_uri"),
    "auth_provider_x509_cert_url": os.getenv("auth_provider_x509_cert_url"),
    "client_x509_cert_url": os.getenv("client_x509_cert_url"),
    "universe_domain": os.getenv("universe_domain")
}

# Extraction Configuration
EXTRACTION_CONFIG = {
    "headless_mode": True,
    "delay_between_products": 3,
    "max_parallel_extractions": 3,
    "max_retries": 3,
    "confidence_threshold": 50.0,
    "cloud_first_mode": True
}

def get_gcs_client():
    """Get GCS client with explicit credentials"""
    try:
        # Create credentials from environment variables
        credentials = service_account.Credentials.from_service_account_info(GCP_CREDENTIALS)
        client = storage.Client(credentials=credentials, project=GCP_CREDENTIALS["project_id"])
        return client
    except Exception as e:
        print(f"Failed to create GCS client: {e}")
        return None

def validate_gcs_config():
    """Validate GCS configuration"""
    if USE_GCS:
        if GCS_BUCKET_NAME == "your-bucket-name":
            print("Please update GCS_BUCKET_NAME in gcs_config.py with your actual bucket name")
            return False
        
        # Check if all required credentials are present
        required_fields = ["type", "project_id", "private_key", "client_email"]
        missing_fields = [field for field in required_fields if not GCP_CREDENTIALS.get(field)]
        
        if missing_fields:
            print(f"Missing required GCP credentials: {missing_fields}")
            print("Please check your .env file contains all required fields")
            return False
        
        try:
            client = get_gcs_client()
            if client is None:
                return False
                
            bucket = client.bucket(GCS_BUCKET_NAME)
            if not bucket.exists():
                print(f"GCS bucket '{GCS_BUCKET_NAME}' does not exist!")
                print("Please create the bucket or update GCS_BUCKET_NAME.")
                return False
            print(f"GCS bucket '{GCS_BUCKET_NAME}' is accessible")
            return True
        except Exception as e:
            print(f"GCS validation failed: {e}")
            return False
    return True

def print_setup_instructions():
    """Print GCS setup instructions"""
    print("GCP Credentials loaded from environment variables:")
    for key, value in GCP_CREDENTIALS.items():
        if key == "private_key":
            print(f"  {key}: {'***' if value else 'NOT SET'}")
        else:
            print(f"  {key}: {value or 'NOT SET'}")
