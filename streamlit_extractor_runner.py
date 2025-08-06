#!/usr/bin/env python3
"""
Background runner for the Streamlit Product Extractor
Handles the actual execution of the extraction process with real-time updates
"""

import subprocess
import threading
import time
import os
import json
import logging
import queue
from datetime import datetime
from typing import Dict, Any, Optional
import streamlit as st

class ExtractionRunner:
    """Handles running the extraction process in the background"""
    
    def __init__(self):
        self.process = None
        self.log_queue = queue.Queue()
        self.stats = {
            'products_found': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'success_rate': 0.0,
            'current_status': 'Ready'
        }
        self.is_running = False
        self.start_time = None
    
    def start_extraction(self) -> bool:
        """Start the extraction process"""
        try:
            if self.is_running:
                return False
            
            self.is_running = True
            self.start_time = datetime.now()
            self.stats['current_status'] = 'Initializing...'
            
            # Start the extraction in a separate thread
            extraction_thread = threading.Thread(target=self._run_extraction)
            extraction_thread.daemon = True
            extraction_thread.start()
            
            return True
        except Exception as e:
            self.log_queue.put({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'level': 'ERROR',
                'message': f'Failed to start extraction: {e}'
            })
            self.is_running = False
            return False
    
    def _run_extraction(self):
        """Run the actual extraction process"""
        try:
            # Import and run the extractor
            import sys
            import io
            import contextlib
            
            # Capture stdout and stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            
            # Create custom log handler
            log_capture = io.StringIO()
            
            # Configure logging to capture messages
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(log_capture)
                ]
            )
            
            # Update status
            self.stats['current_status'] = 'Loading extractor...'
            self._add_log('INFO', 'Starting advanced product extraction...')
            
            # Import the extractor module
            try:
                from langgraph_advanced_extractor import main as run_extractor
                self.stats['current_status'] = 'Running extraction...'
                self._add_log('INFO', 'Extractor loaded successfully')
                
                # Run the extraction
                run_extractor()
                
                self.stats['current_status'] = 'Completed successfully'
                self._add_log('INFO', 'Extraction completed successfully!')
                
            except ImportError as e:
                self._add_log('ERROR', f'Failed to import extractor: {e}')
                self.stats['current_status'] = 'Import failed'
            except Exception as e:
                self._add_log('ERROR', f'Extraction failed: {e}')
                self.stats['current_status'] = 'Failed'
            
        except Exception as e:
            self._add_log('ERROR', f'Runner error: {e}')
            self.stats['current_status'] = 'Error'
        finally:
            self.is_running = False
    
    def _add_log(self, level: str, message: str):
        """Add a log entry to the queue"""
        self.log_queue.put({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'level': level,
            'message': message
        })
    
    def get_logs(self) -> list:
        """Get all pending logs"""
        logs = []
        while not self.log_queue.empty():
            try:
                logs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        return logs
    
    def stop_extraction(self):
        """Stop the extraction process"""
        if self.process:
            self.process.terminate()
        self.is_running = False
        self.stats['current_status'] = 'Stopped by user'
        self._add_log('WARNING', 'Extraction stopped by user')
    
    def update_stats_from_files(self):
        """Update statistics by checking result files - handles both local and cloud-first modes"""
        try:
            # Check if we're in cloud-first mode
            try:
                from gcs_config import USE_GCS, EXTRACTION_CONFIG
                cloud_first_mode = USE_GCS and EXTRACTION_CONFIG.get("cloud_first_mode", False)
            except ImportError:
                cloud_first_mode = False
            
            if cloud_first_mode:
                # In cloud-first mode, we don't have local files to check
                # Stats will be updated through other means (logs, etc.)
                self._add_log('INFO', '🌩️ Cloud-first mode: Stats tracking via GCS (local files not available)')
                return
            
            # Local mode: Check for Excel files
            excel_files = [f for f in os.listdir('.') if f.startswith('product_extraction_results_') and f.endswith('.xlsx')]
            if excel_files:
                # Get the most recent file
                latest_file = max(excel_files, key=os.path.getmtime)
                try:
                    import pandas as pd
                    df = pd.read_excel(latest_file)
                    
                    total_products = len(df)
                    successful = len(df[df['validation_status'] != 'failed'])
                    failed = total_products - successful
                    success_rate = (successful / total_products * 100) if total_products > 0 else 0
                    
                    self.stats.update({
                        'products_found': total_products,
                        'successful_extractions': successful,
                        'failed_extractions': failed,
                        'success_rate': success_rate
                    })
                    self._add_log('INFO', f'📊 Updated stats from local Excel file: {total_products} products')
                except Exception as e:
                    self._add_log('WARNING', f'Could not read Excel file: {e}')
            
            # Check for summary JSON files
            json_files = [f for f in os.listdir('.') if f.startswith('langgraph_advanced_summary_') and f.endswith('.json')]
            if json_files:
                latest_json = max(json_files, key=os.path.getmtime)
                try:
                    with open(latest_json, 'r') as f:
                        summary = json.load(f)
                    
                    if 'extraction_summary' in summary:
                        summary_data = summary['extraction_summary']
                        self.stats.update({
                            'products_found': summary_data.get('total_products', 0),
                            'successful_extractions': summary_data.get('successful_extractions', 0),
                            'failed_extractions': summary_data.get('failed_extractions', 0),
                            'success_rate': float(summary_data.get('success_rate', '0%').replace('%', ''))
                        })
                        self._add_log('INFO', f'📋 Updated stats from local summary file')
                except Exception as e:
                    self._add_log('WARNING', f'Could not read summary file: {e}')
                    
        except Exception as e:
            self._add_log('ERROR', f'Error updating stats: {e}')

# Global runner instance
if 'extractor_runner' not in st.session_state:
    st.session_state.extractor_runner = ExtractionRunner() 