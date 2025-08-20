#!/usr/bin/env python3
"""
Google Cloud Storage Configuration
Updated via Streamlit UI - 2025-07-30 14:57:18
Cloud-First Architecture: Google Cloud Storage Only
updating for test
"""

# GCS Configuration - Always enabled for cloud-first mode
USE_GCS = True
GCS_BUCKET_NAME = "scraped-data-bucket-hts-big-traderz"
GCS_DATA_FOLDER = "data"

# Extraction Configuration
EXTRACTION_CONFIG = {
    "headless_mode": True,
    "delay_between_products": 3,
    "max_parallel_extractions": 3,
    "max_retries": 3,
    "confidence_threshold": 50.0,
    "cloud_first_mode": True
}

def validate_gcs_config():
    """Validate GCS configuration"""
    if USE_GCS:
        if GCS_BUCKET_NAME == "scraped-data-bucket-hts":
            print("Please update GCS_BUCKET_NAME in gcs_config.py with your actual bucket name")
            return False
        
        try:
            from google.cloud import storage
            client = storage.Client()
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
    pass


