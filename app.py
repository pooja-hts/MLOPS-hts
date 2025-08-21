#!/usr/bin/env python3
"""
Streamlit UI for LangGraph Advanced Product Extractor
Cloud-First Architecture - Google Cloud Storage Only
No local file handling - Pure GCS integration
"""

import streamlit as st
import os
import json
import time
import threading
import subprocess
import sys
from datetime import datetime
import pandas as pd
import logging
from io import StringIO
import queue
import tempfile

# Import the extraction runner
from streamlit_extractor_runner import ExtractionRunner

# Configure page
st.set_page_config(
    page_title="Product Extractor Pro",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .status-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 0.75rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .status-error {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 0.75rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .status-warning {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 0.75rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
    .stMetric {
        background: #f8f9fa;
        padding: 0.5rem;
        border-radius: 5px;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'extractor_runner' not in st.session_state:
    st.session_state.extractor_runner = ExtractionRunner()
if 'extraction_logs' not in st.session_state:
    st.session_state.extraction_logs = []

# Header
st.markdown("""
<div class="main-header">
    <h1 style="color: white; margin: 0;">🔍 Product Extractor Pro</h1>
    <p style="color: #f0f0f0; margin: 0;">Cloud-First Product Extraction - Google Cloud Storage Only</p>
</div>
""", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration")

# GCS Configuration Section
st.sidebar.subheader("🌩️ Google Cloud Storage")

bucket_name = st.sidebar.text_input(
    "GCS Bucket Name", 
    value="scraped-data-bucket-hts-big-traderz", 
    help="Enter your GCS bucket name (without gs:// prefix)"
)
data_folder = st.sidebar.text_input(
    "Data Folder", 
    value="data", 
    help="Folder name within the bucket for organizing data"
)

# GCS Authentication Status
st.sidebar.subheader("🔐 Authentication Status")
try:
    from google.cloud import storage
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    if bucket.exists():
        st.sidebar.markdown('<div class="status-success">✅ GCS Connected</div>', unsafe_allow_html=True)
        gcs_status = "connected"
    else:
        st.sidebar.markdown('<div class="status-error">❌ Bucket not found</div>', unsafe_allow_html=True)
        gcs_status = "bucket_not_found"
except Exception as e:
    st.sidebar.markdown('<div class="status-error">❌ Authentication Failed</div>', unsafe_allow_html=True)
    st.sidebar.error(f"Error: {str(e)[:100]}...")
    gcs_status = "auth_failed"

# Cloud-first notice
st.sidebar.info("🌩️ **Cloud-First Architecture**: All data saved directly to Google Cloud Storage. No local files created.")

# Extraction Configuration
st.sidebar.subheader("🔧 Extraction Settings")

headless_mode = st.sidebar.checkbox("Headless Mode", value=True, help="Run browser in headless mode")
delay_between_products = st.sidebar.slider("Delay Between Products (seconds)", 1, 10, 3)
max_parallel_extractions = st.sidebar.slider("Max Parallel Extractions", 1, 5, 3)
max_retries = st.sidebar.slider("Max Retries", 1, 5, 3)
confidence_threshold = st.sidebar.slider("Confidence Threshold", 0.0, 100.0, 50.0)

# Advanced Options
st.sidebar.subheader("🔬 Advanced Options")
download_images = st.sidebar.checkbox("Download Product Images", value=True)
st.sidebar.info("📁 All data automatically saved to GCS (JSON, Excel, Images)")

# Function to update GCS config
def update_gcs_config():
    """Update the GCS configuration file for cloud-first mode"""
    config_content = f'''#!/usr/bin/env python3
"""
Google Cloud Storage Configuration
Updated via Streamlit UI - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Cloud-First Architecture: Google Cloud Storage Only
"""

# GCS Configuration - Always enabled for cloud-first mode
USE_GCS = True
GCS_BUCKET_NAME = "{bucket_name}"
GCS_DATA_FOLDER = "{data_folder}"

# Extraction Configuration
EXTRACTION_CONFIG = {{
    "headless_mode": {headless_mode},
    "delay_between_products": {delay_between_products},
    "max_parallel_extractions": {max_parallel_extractions},
    "max_retries": {max_retries},
    "confidence_threshold": {confidence_threshold},
    "cloud_first_mode": True
}}

def validate_gcs_config():
    """Validate GCS configuration"""
    if USE_GCS:
        if GCS_BUCKET_NAME == "your-bucket-name":
            print("Please update GCS_BUCKET_NAME in gcs_config.py with your actual bucket name")
            return False
        
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(GCS_BUCKET_NAME)
            if not bucket.exists():
                print(f"GCS bucket '{{GCS_BUCKET_NAME}}' does not exist!")
                print("Please create the bucket or update GCS_BUCKET_NAME.")
                return False
            print(f"GCS bucket '{{GCS_BUCKET_NAME}}' is accessible")
            return True
        except Exception as e:
            print(f"GCS validation failed: {{e}}")
            return False
    return True

def print_setup_instructions():
    """Print GCS setup instructions"""
    pass
'''
    
    with open('gcs_config.py', 'w', encoding='utf-8') as f:
        f.write(config_content)

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("🚀 Extraction Control")
    
    # Get current extraction status
    runner = st.session_state.extractor_runner
    is_running = runner.is_running
    
    # Status display
    if is_running:
        st.markdown(f'<div class="status-warning">⏳ {runner.stats["current_status"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-success">✅ Ready to start cloud extraction</div>', unsafe_allow_html=True)
    
    # Control buttons
    col_start, col_stop, col_clear = st.columns(3)
    
    with col_start:
        if st.button("🚀 Start Cloud Extraction", disabled=is_running):
            if gcs_status != "connected":
                st.error("❌ Please fix GCS configuration before starting extraction")
            else:
                # Update configuration
                update_gcs_config()
                st.success("✅ Starting cloud extraction...")
                
                # Start the extraction
                if runner.start_extraction():
                    st.session_state.extraction_logs = []
                    st.rerun()
                else:
                    st.error("❌ Failed to start extraction")
    
    with col_stop:
        if st.button("⏹️ Stop Extraction", disabled=not is_running):
            runner.stop_extraction()
            st.warning("⏹️ Extraction stopped")
            st.rerun()
    
    with col_clear:
        if st.button("🗑️ Clear Logs"):
            st.session_state.extraction_logs = []
            st.rerun()

with col2:
    st.header("📊 Quick Stats")
    
    # Display current configuration summary
    st.markdown(f"""
    <div class="metric-card">
        <h4>Cloud Configuration</h4>
        <ul>
            <li><strong>Storage:</strong> Google Cloud Storage</li>
            <li><strong>Bucket:</strong> {bucket_name}</li>
            <li><strong>Data Folder:</strong> {data_folder}</li>
            <li><strong>Parallel Jobs:</strong> {max_parallel_extractions}</li>
            <li><strong>Retry Limit:</strong> {max_retries}</li>
            <li><strong>Confidence:</strong> {confidence_threshold}%</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Progress tracking with real data
st.header("📈 Extraction Progress")

# Update stats and get new logs
runner.update_stats_from_files()
new_logs = runner.get_logs()
st.session_state.extraction_logs.extend(new_logs)

# Display metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Products Found", runner.stats['products_found'])
with col2:
    st.metric("Successfully Extracted", runner.stats['successful_extractions'])
with col3:
    st.metric("Failed Extractions", runner.stats['failed_extractions'])
with col4:
    st.metric("Success Rate", f"{runner.stats['success_rate']:.1f}%")

# Progress bar
if runner.stats['products_found'] > 0:
    progress = runner.stats['successful_extractions'] / runner.stats['products_found']
    st.progress(progress, f"Progress: {progress*100:.1f}%")

# Real-time logs section
st.header("📝 Real-time Logs")

log_container = st.container()
with log_container:
    if st.session_state.extraction_logs:
        # Display logs in reverse order (newest first)
        for log_entry in reversed(st.session_state.extraction_logs[-20:]):  # Show last 20 logs
            timestamp = log_entry.get('timestamp', '')
            level = log_entry.get('level', 'INFO')
            message = log_entry.get('message', '')
            
            if level == 'ERROR':
                st.error(f"[{timestamp}] {message}")
            elif level == 'WARNING':
                st.warning(f"[{timestamp}] {message}")
            else:
                st.info(f"[{timestamp}] {message}")
    else:
        st.info("No logs yet. Start an extraction to see real-time progress.")

# Results section - GCS Only
st.header("☁️ Cloud Storage Results")

if gcs_status == "connected":
    st.subheader("🗂️ GCS Bucket Browser")
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        blobs = list(bucket.list_blobs(max_results=100))
        if blobs:
            # Filter and organize blobs
            excel_blobs = [b for b in blobs if b.name.endswith('.xlsx')]
            json_blobs = [b for b in blobs if b.name.endswith('.json') and not b.name.endswith('product_details.json')]
            image_blobs = [b for b in blobs if b.name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
            product_json_blobs = [b for b in blobs if b.name.endswith('product_details.json')]
            
            # Create tabs for different file types
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Excel Reports", "📋 Summaries", "🖼️ Images", "📄 Product JSONs", "📁 All Files"])
            
            with tab1:
                if excel_blobs:
                    st.write("**Excel Extraction Results**")
                    for blob in sorted(excel_blobs, key=lambda x: x.updated, reverse=True)[:10]:
                        col1, col2, col3 = st.columns([3, 2, 2])
                        with col1:
                            st.text(f"📄 {blob.name}")
                        with col2:
                            st.text(f"🕒 {blob.updated.strftime('%Y-%m-%d %H:%M:%S')}")
                            st.text(f"📏 {blob.size / 1024:.1f} KB")
                        with col3:
                            st.link_button("View in GCS", f"https://console.cloud.google.com/storage/browser/_details/{bucket_name}/{blob.name}")
                else:
                    st.info("No Excel files found yet. Start an extraction to generate reports.")
            
            with tab2:
                if json_blobs:
                    st.write("**Extraction Summary Reports**")
                    for blob in sorted(json_blobs, key=lambda x: x.updated, reverse=True)[:5]:
                        col1, col2, col3 = st.columns([3, 2, 2])
                        with col1:
                            st.text(f"📋 {blob.name}")
                        with col2:
                            st.text(f"🕒 {blob.updated.strftime('%Y-%m-%d %H:%M:%S')}")
                        with col3:
                            st.link_button("View in GCS", f"https://console.cloud.google.com/storage/browser/_details/{bucket_name}/{blob.name}")
                else:
                    st.info("No summary files found yet.")
            
            with tab3:
                if image_blobs:
                    st.write("**Product Images**")
                    for blob in sorted(image_blobs, key=lambda x: x.updated, reverse=True)[:20]:
                        col1, col2, col3 = st.columns([3, 2, 2])
                        with col1:
                            st.text(f"🖼️ {blob.name}")
                        with col2:
                            st.text(f"📏 {blob.size / 1024:.1f} KB")
                        with col3:
                            st.link_button("View Image", f"https://console.cloud.google.com/storage/browser/_details/{bucket_name}/{blob.name}")
                else:
                    st.info("No images found yet.")
            
            with tab4:
                if product_json_blobs:
                    st.write("**Individual Product Data**")
                    for blob in sorted(product_json_blobs, key=lambda x: x.updated, reverse=True)[:20]:
                        col1, col2, col3 = st.columns([3, 2, 2])
                        with col1:
                            product_folder = '/'.join(blob.name.split('/')[:-1])
                            st.text(f"📄 {product_folder}")
                        with col2:
                            st.text(f"🕒 {blob.updated.strftime('%Y-%m-%d %H:%M:%S')}")
                        with col3:
                            st.link_button("View JSON", f"https://console.cloud.google.com/storage/browser/_details/{bucket_name}/{blob.name}")
                else:
                    st.info("No product JSON files found yet.")
            
            with tab5:
                st.write("**Complete Bucket Contents**")
                df_blobs = pd.DataFrame([
                    {
                        'Name': blob.name,
                        'Size': f"{blob.size / 1024:.1f} KB" if blob.size else "0 KB",
                        'Updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S') if blob.updated else 'Unknown',
                        'Type': blob.content_type or 'Unknown'
                    }
                    for blob in sorted(blobs, key=lambda x: x.updated or datetime.min, reverse=True)
                ])
                st.dataframe(df_blobs, use_container_width=True)
                
                # Bucket statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Files", len(blobs))
                with col2:
                    st.metric("Excel Reports", len(excel_blobs))
                with col3:
                    st.metric("Product Images", len(image_blobs))
                with col4:
                    st.metric("Product JSONs", len(product_json_blobs))
        else:
            st.info("🌟 Bucket is empty. Start an extraction to see results here!")
            
        # Direct GCS links
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.link_button("🌐 Open GCS Console", f"https://console.cloud.google.com/storage/browser/{bucket_name}")
        with col2:
            st.link_button("📊 Cloud Storage Dashboard", "https://console.cloud.google.com/storage/")
            
    except Exception as e:
        st.error(f"❌ Error accessing GCS bucket: {e}")
        st.info("Please check your authentication and bucket configuration.")

else:
    st.error("❌ Google Cloud Storage not connected")
    st.info("Please configure GCS authentication in the sidebar to view results.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    🔍 Product Extractor Pro | Cloud-First Architecture | Google Cloud Storage Only<br/>
    <small>Built with Streamlit & LangGraph | No local file storage</small>
</div>
""", unsafe_allow_html=True)

# Auto-refresh for real-time updates when extraction is running
if is_running:
    time.sleep(3)  # Refresh every 3 seconds

    st.rerun() 
