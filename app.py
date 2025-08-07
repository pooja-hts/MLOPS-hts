#!/usr/bin/env python3
"""
Streamlit UI for LangGraph Fixed Search Extraction
Provides an interactive interface for product extraction workflow
"""

import streamlit as st
import json
import os
import time
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
import plotly.express as px
import plotly.graph_objects as go
from langgraph_fixed_extractor import WorkflowManager, ExtractionState

# Page configuration
st.set_page_config(
    page_title="iProcure Product Extractor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    .step-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

class StreamlitWorkflowUI:
    """Streamlit UI for the LangGraph workflow"""
    
    def __init__(self):
        self.workflow_manager = WorkflowManager()
        self.session_state = st.session_state
        
        # Initialize session state
        if 'workflow_results' not in self.session_state:
            self.session_state.workflow_results = []
        if 'current_workflow' not in self.session_state:
            self.session_state.current_workflow = None
        if 'workflow_history' not in self.session_state:
            self.session_state.workflow_history = []
    
    def render_header(self):
        """Render the main header"""
        st.markdown('<h1 class="main-header">🔍 iProcure Product Extractor</h1>', unsafe_allow_html=True)
        st.markdown("### LangGraph-powered Product Information Extraction")
        st.markdown("---")
    
    def render_sidebar(self):
        """Render the sidebar with configuration options"""
        with st.sidebar:
            st.header("🔍 Product Search")
            
            # Search term input with better styling
            if 'search_term' not in st.session_state:
                st.session_state.search_term = "Safety Belts & Harness"
            
            search_term = st.text_input(
                "Enter Product Name",
                value=st.session_state.search_term,
                placeholder="e.g., Safety Belts & Harness, LED Floodlight, PVC Cable...",
                help="Enter the product name you want to search and extract information for"
            )
            
            # Update session state if search term changed
            if search_term != st.session_state.search_term:
                st.session_state.search_term = search_term
            
            # Search validation
            if search_term.strip():
                if len(search_term.strip()) < 3:
                    st.warning("⚠️ Search term should be at least 3 characters long")
                else:
                    st.success("✅ Search term is valid")
            else:
                st.error("❌ Please enter a search term")
            
            # Quick search suggestions
            st.markdown("**💡 Quick Search Suggestions:**")
            suggestions = [
                "Safety Belts & Harness",
                "Explosion-proof LED Floodlight", 
                "Glitz Premium Acrylic Emusion",
                "Latex Gloves QR 5-TSP13101",
                "Cordless Screwdriver"
            ]
            
            for suggestion in suggestions:
                if st.button(f"🔍 {suggestion}", key=f"suggest_{suggestion}", use_container_width=True):
                    st.session_state.search_term = suggestion
                    st.rerun()
            
            st.markdown("---")
            st.header("⚙️ Configuration")
            
            # Data folder
            data_folder = st.text_input(
                "Data Folder",
                value="data",
                help="Folder to save extracted data"
            )
            
            # Headless mode
            headless_mode = st.checkbox(
                "Headless Mode",
                value=True,
                help="Run browser in headless mode (faster, no GUI)"
            )
            
            # Download images
            download_images = st.checkbox(
                "Download Images",
                value=True,
                help="Download product images during extraction"
            )
            
            # Advanced options
            with st.expander("Advanced Options"):
                max_retries = st.slider("Max Retries", 1, 5, 3)
                timeout = st.slider("Timeout (seconds)", 10, 60, 30)
                
            st.markdown("---")
            
            # Quick actions
            st.header("🚀 Quick Actions")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Clear History", use_container_width=True):
                    self.session_state.workflow_results = []
                    self.session_state.workflow_history = []
                    st.rerun()
            
            with col2:
                if st.button("📊 Export Results", use_container_width=True):
                    self.export_results()
            
            st.markdown("---")
            st.header("📋 Search History")
            
            # Show recent searches
            if self.session_state.workflow_results:
                recent_searches = [result.get('search_term', 'Unknown') for result in self.session_state.workflow_results[-5:]]
                for i, search in enumerate(recent_searches):
                    if st.button(f"🔄 {search}", key=f"history_{i}", use_container_width=True):
                        st.session_state.search_term = search
                        st.rerun()
            else:
                st.info("No search history yet")
            
            st.markdown("---")
            st.header("💡 Search Tips")
            
            with st.expander("How to get better results"):
                st.markdown("""
                **🔍 Use specific product names:**
                - ✅ "Safety Belts & Harness"
                - ✅ "Explosion-proof LED Floodlight"
                - ❌ "safety equipment"
                
                **📋 Include brand names when possible:**
                - ✅ "3M Safety Belts"
                - ✅ "Philips LED Floodlight"
                
                **🔧 Use technical specifications:**
                - ✅ "1G PVC Modern Cable"
                - ✅ "Industrial Grade Safety Equipment"
                """)
            
            return {
                'search_term': search_term,
                'data_folder': data_folder,
                'headless_mode': headless_mode,
                'download_images': download_images,
                'max_retries': max_retries,
                'timeout': timeout
            }
    
    def render_main_content(self, config: Dict[str, Any]):
        """Render the main content area"""
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["🔍 Extraction", "📊 Results", "📈 Analytics", "📁 Files"])
        
        with tab1:
            self.render_extraction_tab(config)
        
        with tab2:
            self.render_results_tab()
        
        with tab3:
            self.render_analytics_tab()
        
        with tab4:
            self.render_files_tab()
    
    def render_extraction_tab(self, config: Dict[str, Any]):
        """Render the extraction tab"""
        st.header("🔍 Product Extraction")
        
        # Display current search term
        st.markdown(f"**Current Search:** `{config['search_term']}`")
        
        # Search and extract button with better styling
        st.markdown("---")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # Disable button if search term is invalid
            is_valid_search = len(config['search_term'].strip()) >= 3
            if st.button("🚀 Start Extraction", type="primary", use_container_width=True, disabled=not is_valid_search):
                self.run_extraction(config)
        
        with col2:
            if st.button("⏸️ Pause", use_container_width=True):
                st.info("Pause functionality coming soon...")
        
        with col3:
            if st.button("⏹️ Stop", use_container_width=True):
                st.info("Stop functionality coming soon...")
        
        # Search status indicator
        if self.session_state.current_workflow:
            st.markdown("---")
            self.render_search_status()
        
        st.markdown("---")
        
        # Current workflow status
        if self.session_state.current_workflow:
            self.render_workflow_status(self.session_state.current_workflow)
            
            # Quick product preview if extraction was successful
            if (self.session_state.current_workflow.get('status') == 'completed' and 
                self.session_state.current_workflow.get('product_data')):
                st.markdown("---")
                st.markdown("### 🎉 Extraction Complete! Quick Preview:")
                self.render_quick_preview(self.session_state.current_workflow['product_data'])
    
    def render_quick_preview(self, product_data: Dict[str, Any]):
        """Render a quick preview of extracted product data"""
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Show image if available (using same logic as render_product_image)
            image_path = self.get_product_image_path(product_data)
            if image_path:
                try:
                    st.image(image_path, caption="Product Image", width=150)
                except Exception as e:
                    st.error(f"Could not load image: {e}")
            else:
                st.info("📷 No image")
        
        with col2:
            # Show key information
            if product_data.get('title'):
                st.markdown(f"**Title:** {product_data['title']}")
            if product_data.get('brand'):
                st.markdown(f"**Brand:** {product_data['brand']}")
            if product_data.get('unspsc'):
                st.markdown(f"**UNSPSC:** {product_data['unspsc']}")
            if product_data.get('description'):
                desc = product_data['description']
                st.markdown(f"**Description:** {desc[:100]}{'...' if len(desc) > 100 else ''}")
            
            # Show a few key attributes
            attributes = product_data.get('attributes', {})
            if attributes:
                st.markdown("**Key Attributes:**")
                for key, value in list(attributes.items())[:3]:
                    if value:
                        st.markdown(f"• **{key.replace('_', ' ').title()}:** {value}")
    
    def render_search_status(self):
        """Render a simplified search status indicator"""
        workflow = self.session_state.current_workflow
        
        st.subheader("🔍 Search Status")
        
        # Status with color coding
        status = workflow.get('status', 'unknown')
        if status == 'completed':
            status_icon = "✅"
            status_color = "success"
        elif status == 'error':
            status_icon = "❌"
            status_color = "error"
        else:
            status_icon = "⏳"
            status_color = "warning"
        
        st.markdown(f'<p class="status-{status_color}">{status_icon} **Status:** {status.title()}</p>', unsafe_allow_html=True)
        
        # Current step
        current_step = workflow.get('current_step', 'Unknown')
        st.markdown(f"**Current Step:** {current_step}")
        
        # Progress bar for multi-step process
        steps = ['search', 'navigate', 'extract', 'save']
        current_step_index = 0
        
        if 'search' in current_step.lower():
            current_step_index = 0
        elif 'navigate' in current_step.lower() or 'product' in current_step.lower():
            current_step_index = 1
        elif 'extract' in current_step.lower():
            current_step_index = 2
        elif 'save' in current_step.lower():
            current_step_index = 3
        
        progress = (current_step_index + 1) / len(steps)
        st.progress(progress)
        
        # Step labels
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("🔍 **Search**")
        with col2:
            st.markdown("🎯 **Navigate**")
        with col3:
            st.markdown("📋 **Extract**")
        with col4:
            st.markdown("💾 **Save**")
        
        # Progress tracking
        if self.session_state.workflow_results:
            self.render_progress_tracking()
    
    def render_workflow_status(self, workflow_result: Dict[str, Any]):
        """Render current workflow status"""
        st.subheader("📋 Current Workflow Status")
        
        # Status indicators
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            status_color = "success" if workflow_result['status'] == 'completed' else "error" if workflow_result['status'] == 'error' else "warning"
            st.markdown(f'<div class="metric-card"><h4>Status</h4><p class="status-{status_color}">{workflow_result["status"].title()}</p></div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown(f'<div class="metric-card"><h4>Step</h4><p>{workflow_result.get("current_step", "Unknown")}</p></div>', unsafe_allow_html=True)
        
        with col3:
            success_rate = "✅" if workflow_result.get('extraction_success', False) else "❌"
            st.markdown(f'<div class="metric-card"><h4>Success</h4><p>{success_rate}</p></div>', unsafe_allow_html=True)
        
        with col4:
            timestamp = workflow_result.get('timestamp', 'Unknown')
            st.markdown(f'<div class="metric-card"><h4>Started</h4><p>{timestamp}</p></div>', unsafe_allow_html=True)
        
        # Detailed status
        if workflow_result.get('error_message'):
            st.error(f"❌ Error: {workflow_result['error_message']}")
        
        # Product information
        if workflow_result.get('product_data'):
            self.render_product_preview(workflow_result['product_data'])
        
        # Search results summary
        if workflow_result.get('search_results'):
            self.render_search_results_summary(workflow_result['search_results'])
    
    def render_product_preview(self, product_data: Dict[str, Any]):
        """Render a preview of extracted product data"""
        st.subheader("📦 Product Information")
        
        # Product Image Section
        self.render_product_image(product_data)
        
        # Product Details in tabs
        tab1, tab2, tab3 = st.tabs(["📋 Basic Info", "📝 Description", "🔧 Attributes"])
        
        with tab1:
            self.render_basic_info(product_data)
        
        with tab2:
            self.render_product_description(product_data)
        
        with tab3:
            self.render_product_attributes(product_data)
    
    def render_search_results_summary(self, search_results: Dict[str, Any]):
        """Render a summary of search results"""
        st.subheader("🔍 Search Results Summary")
        
        if isinstance(search_results, dict):
            # Show key information from search results
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Search Information**")
                if 'total_results' in search_results:
                    st.write(f"**Total Results:** {search_results['total_results']}")
                if 'search_url' in search_results:
                    st.write(f"**Search URL:** {search_results['search_url']}")
                if 'search_time' in search_results:
                    st.write(f"**Search Time:** {search_results['search_time']}")
            
            with col2:
                st.markdown("**Status**")
                if 'status' in search_results:
                    status = search_results['status']
                    if status == 'success':
                        st.success("✅ Search successful")
                    else:
                        st.error(f"❌ Search failed: {status}")
        
        elif isinstance(search_results, list):
            st.write(f"**Found {len(search_results)} results**")
            for i, result in enumerate(search_results[:3]):  # Show first 3 results
                with st.expander(f"Result {i+1}"):
                    st.json(result)
        else:
            st.write("**Search Results:**", search_results)
    
    def get_product_image_path(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Get the best available image path for a product"""
        # Check for image data in multiple locations
        image_url = product_data.get('image_url')
        image_path = product_data.get('image_path')
        
        # Check for downloaded image info
        image_downloaded = product_data.get('image_downloaded', {})
        if image_downloaded and isinstance(image_downloaded, dict):
            downloaded_path = image_downloaded.get('file_path')
            if downloaded_path and os.path.exists(downloaded_path):
                return downloaded_path
        
        # Check for file paths in product data
        file_paths = product_data.get('file_paths', {})
        if file_paths and isinstance(file_paths, dict):
            product_folder = file_paths.get('product_folder')
            if product_folder and os.path.exists(product_folder):
                # Look for image files in the product folder
                for file in os.listdir(product_folder):
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                        folder_image_path = os.path.join(product_folder, file)
                        if os.path.exists(folder_image_path):
                            return folder_image_path
        
        # Check direct image path
        if image_path and os.path.exists(image_path):
            return image_path
        
        # Return None if no image found
        return None
    
    def render_product_image(self, product_data: Dict[str, Any]):
        """Render product image if available"""
        st.markdown("### 🖼️ Product Image")
        
        # Get the best available image path
        image_path = self.get_product_image_path(product_data)
        image_url = product_data.get('image_url')
        image_data = product_data.get('image_data')
        
        if image_url:
            try:
                st.image(image_url, caption="Product Image", use_container_width=True)
                st.markdown(f"**Image URL:** {image_url}")
            except Exception as e:
                st.error(f"Could not load image from URL: {e}")
        
        elif image_path:
            try:
                st.image(image_path, caption="Product Image", use_container_width=True)
                st.markdown(f"**Image Path:** {image_path}")
            except Exception as e:
                st.error(f"Could not load image from path: {e}")
        
        elif image_data:
            try:
                st.image(image_data, caption="Product Image", use_container_width=True)
                st.markdown("**Image Source:** Embedded data")
            except Exception as e:
                st.error(f"Could not load embedded image: {e}")
        
        else:
            st.info("📷 No product image available")
            # Show a placeholder
            st.markdown("""
            <div style="text-align: center; padding: 2rem; background-color: #f0f0f0; border-radius: 0.5rem;">
                <h3>🖼️</h3>
                <p>No image available for this product</p>
            </div>
            """, unsafe_allow_html=True)
    
    def render_basic_info(self, product_data: Dict[str, Any]):
        """Render basic product information"""
        st.markdown("### 📋 Basic Information")
        
        # Create a nice layout for basic info
        col1, col2 = st.columns(2)
        
        with col1:
            basic_info = {
                'Title': product_data.get('title', 'N/A'),
                'Brand': product_data.get('brand', 'N/A'),
                'Supplier': product_data.get('supplier', 'N/A'),
                'SKU': product_data.get('sku', 'N/A'),
                'Model': product_data.get('model', 'N/A')
            }
            
            for key, value in basic_info.items():
                if value and value != 'N/A':
                    st.markdown(f"**{key}:** {value}")
                else:
                    st.markdown(f"**{key}:** <span style='color: #999;'>Not available</span>", unsafe_allow_html=True)
        
        with col2:
            # Show UNSPSC code first, then category
            unspsc_code = product_data.get('unspsc', 'N/A')
            if unspsc_code and unspsc_code != 'N/A':
                st.markdown(f"**UNSPSC Code:** {unspsc_code}")
            else:
                st.markdown("**UNSPSC Code:** <span style='color: #999;'>Not available</span>", unsafe_allow_html=True)
            
            # Category information
            category = product_data.get('category', 'N/A')
            if category and category != 'N/A':
                st.markdown(f"**Category:** {category}")
            else:
                st.markdown("**Category:** <span style='color: #999;'>Not available</span>", unsafe_allow_html=True)
            
            # Main category if different from category
            main_category = product_data.get('main_category', 'N/A')
            if main_category and main_category != 'N/A' and main_category != category:
                st.markdown(f"**Main Category:** {main_category}")
        
        # Extraction success indicators
        st.markdown("---")
        st.markdown("### ✅ Extraction Status")
        extraction_info = product_data.get('extraction_success', {})
        
        if extraction_info:
            col1, col2, col3 = st.columns(3)
            fields = list(extraction_info.keys())
            
            for i, field in enumerate(fields):
                success = extraction_info[field]
                status = "✅" if success else "❌"
                with [col1, col2, col3][i % 3]:
                    st.markdown(f"{status} **{field.title()}**")
        else:
            st.info("No extraction status information available")
    
    def render_product_description(self, product_data: Dict[str, Any]):
        """Render product description"""
        st.markdown("### 📝 Product Description")
        
        description = product_data.get('description', '')
        long_description = product_data.get('long_description', '')
        features = product_data.get('features', [])
        specifications = product_data.get('specifications', '')
        
        if description:
            st.markdown("**Short Description:**")
            st.write(description)
            st.markdown("---")
        
        if long_description:
            st.markdown("**Detailed Description:**")
            st.write(long_description)
            st.markdown("---")
        
        if features:
            st.markdown("**Key Features:**")
            if isinstance(features, list):
                for feature in features:
                    st.markdown(f"• {feature}")
            else:
                st.write(features)
            st.markdown("---")
        
        if specifications:
            st.markdown("**Technical Specifications:**")
            st.write(specifications)
            st.markdown("---")
        
        if not any([description, long_description, features, specifications]):
            st.info("📝 No description information available for this product")
    
    def render_product_attributes(self, product_data: Dict[str, Any]):
        """Render product attributes and key-value pairs"""
        st.markdown("### 🔧 Product Attributes")
        
        # Get attributes from different possible locations
        attributes = product_data.get('attributes', {})
        key_attributes = product_data.get('key_attributes', {})
        technical_specs = product_data.get('technical_specifications', {})
        product_specs = product_data.get('product_specifications', {})
        
        # Combine all attributes
        all_attributes = {}
        all_attributes.update(attributes)
        all_attributes.update(key_attributes)
        all_attributes.update(technical_specs)
        all_attributes.update(product_specs)
        
        if all_attributes:
            # Display attributes in a nice format
            for key, value in all_attributes.items():
                if value and str(value).strip():
                    # Skip invalid UNSPSC entries
                    if key == 'UNSPSC' and str(value).strip() == ':':
                        continue
                    
                    # Skip empty or invalid values
                    if str(value).strip() in ['', ':', 'N/A', 'Not available', 'None']:
                        continue
                    
                    # Clean up the key name
                    clean_key = key.replace('_', ' ').title()
                    
                    # Display with different styling based on value type
                    if isinstance(value, bool):
                        status = "✅ Yes" if value else "❌ No"
                        st.markdown(f"**{clean_key}:** {status}")
                    elif isinstance(value, (int, float)):
                        st.markdown(f"**{clean_key}:** `{value}`")
                    else:
                        st.markdown(f"**{clean_key}:** {value}")
                    
                    st.markdown("---")
        else:
            st.info("🔧 No attributes information available for this product")
        
        # Show raw data if available
        if st.checkbox("Show raw attribute data"):
            st.json(all_attributes)
    
    def render_progress_tracking(self):
        """Render progress tracking for workflows"""
        st.subheader("📈 Progress Tracking")
        
        # Create progress chart
        if len(self.session_state.workflow_results) > 1:
            df = pd.DataFrame(self.session_state.workflow_results)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            fig = px.line(df, x='timestamp', y='extraction_success', 
                         title='Extraction Success Over Time',
                         labels={'extraction_success': 'Success Rate', 'timestamp': 'Time'})
            st.plotly_chart(fig, use_container_width=True)
    
    def render_results_tab(self):
        """Render the results tab"""
        st.header("📊 Extraction Results")
        
        if not self.session_state.workflow_results:
            st.info("No extraction results yet. Start an extraction to see results here.")
            return
        
        # Results table
        results_df = pd.DataFrame(self.session_state.workflow_results)
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            if 'status' in results_df.columns:
                status_filter = st.selectbox("Filter by Status", ["All"] + list(results_df['status'].unique()))
            else:
                status_filter = "All"
        with col2:
            if 'extraction_success' in results_df.columns:
                success_filter = st.selectbox("Filter by Success", ["All", "Success", "Failed"])
            else:
                success_filter = "All"
        
        # Apply filters
        filtered_df = results_df.copy()
        if status_filter != "All" and 'status' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['status'] == status_filter]
        if success_filter != "All" and 'extraction_success' in filtered_df.columns:
            success_bool = success_filter == "Success"
            filtered_df = filtered_df[filtered_df['extraction_success'] == success_bool]
        
        # Display results - handle missing columns gracefully
        available_columns = ['search_term', 'status', 'current_step', 'extraction_success', 'timestamp']
        display_columns = [col for col in available_columns if col in filtered_df.columns]
        
        if display_columns:
            st.dataframe(filtered_df[display_columns], use_container_width=True)
        else:
            st.dataframe(filtered_df, use_container_width=True)
        
        # Detailed view with enhanced product display
        if st.checkbox("Show Detailed Results"):
            for i, result in enumerate(filtered_df.to_dict('records')):
                with st.expander(f"Result {i+1}: {result.get('search_term', 'Unknown')}"):
                    # Show product data if available
                    if result.get('product_data'):
                        st.markdown("### 📦 Product Details")
                        
                        # Product image
                        product_data = result['product_data']
                        image_path = self.get_product_image_path(product_data)
                        if image_path:
                            try:
                                st.image(image_path, caption="Product Image", width=200)
                            except Exception as e:
                                st.error(f"Could not load image: {e}")
                        elif product_data.get('image_url'):
                            try:
                                st.image(product_data['image_url'], caption="Product Image", width=200)
                            except Exception as e:
                                st.error(f"Could not load image: {e}")
                        
                        # Product title and basic info
                        if product_data.get('title'):
                            st.markdown(f"**Title:** {product_data['title']}")
                        if product_data.get('brand'):
                            st.markdown(f"**Brand:** {product_data['brand']}")
                        if product_data.get('unspsc'):
                            st.markdown(f"**UNSPSC Code:** {product_data['unspsc']}")
                        if product_data.get('description'):
                            st.markdown("**Description:**")
                            st.write(product_data['description'][:200] + "..." if len(product_data['description']) > 200 else product_data['description'])
                        
                        # Show key attributes
                        attributes = product_data.get('attributes', {})
                        if attributes:
                            st.markdown("**Key Attributes:**")
                            for key, value in list(attributes.items())[:5]:  # Show first 5 attributes
                                if value:
                                    st.markdown(f"• **{key.replace('_', ' ').title()}:** {value}")
                        
                        st.markdown("---")
                    
                    # Show full JSON data
                    st.markdown("### 📄 Raw Data")
                    st.json(result)
    
    def render_analytics_tab(self):
        """Render the analytics tab"""
        st.header("📈 Analytics Dashboard")
        
        if not self.session_state.workflow_results:
            st.info("No data available for analytics. Run some extractions first.")
            return
        
        df = pd.DataFrame(self.session_state.workflow_results)
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_extractions = len(df)
            st.metric("Total Extractions", total_extractions)
        
        with col2:
            if 'extraction_success' in df.columns:
                success_rate = (df['extraction_success'].sum() / len(df)) * 100
                st.metric("Success Rate", f"{success_rate:.1f}%")
            else:
                st.metric("Success Rate", "N/A")
        
        with col3:
            if 'duration' in df.columns:
                avg_duration = df['duration'].mean()
                st.metric("Avg Duration", f"{avg_duration:.1f}s")
            else:
                st.metric("Avg Duration", "N/A")
        
        with col4:
            if 'search_term' in df.columns:
                unique_products = df['search_term'].nunique()
                st.metric("Unique Products", unique_products)
            else:
                st.metric("Unique Products", "N/A")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Success rate by status
            if 'status' in df.columns and 'extraction_success' in df.columns:
                status_success = df.groupby('status')['extraction_success'].mean()
                fig1 = px.bar(x=status_success.index, y=status_success.values,
                             title='Success Rate by Status',
                             labels={'x': 'Status', 'y': 'Success Rate'})
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("Status and extraction_success data not available for chart")
        
        with col2:
            # Top searched products
            if 'search_term' in df.columns:
                product_counts = df['search_term'].value_counts().head(10)
                fig2 = px.bar(x=product_counts.values, y=product_counts.index, orientation='h',
                             title='Top Searched Products',
                             labels={'x': 'Count', 'y': 'Product'})
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Search term data not available for chart")
        
        # Product comparison section
        st.markdown("---")
        st.header("📊 Product Comparison")
        
        # Get products with extracted data
        products_with_data = []
        for result in self.session_state.workflow_results:
            if result.get('product_data'):
                products_with_data.append(result)
        
        if len(products_with_data) >= 2:
            # Allow user to select products for comparison
            product_options = [f"{p.get('search_term', 'Unknown')} - {p.get('product_data', {}).get('title', 'No title')}" 
                             for p in products_with_data]
            
            selected_products = st.multiselect(
                "Select products to compare (max 3):",
                product_options,
                max_selections=3
            )
            
            if selected_products:
                self.render_product_comparison(selected_products, products_with_data)
        else:
            st.info("Need at least 2 products with extracted data to enable comparison")
    
    def render_product_comparison(self, selected_products: List[str], products_with_data: List[Dict]):
        """Render a comparison table for selected products"""
        st.markdown("### 📋 Product Comparison Table")
        
        # Find the selected products
        selected_data = []
        for option in selected_products:
            for product in products_with_data:
                product_title = f"{product.get('search_term', 'Unknown')} - {product.get('product_data', {}).get('title', 'No title')}"
                if product_title == option:
                    selected_data.append(product)
                    break
        
        if not selected_data:
            st.error("No products found for comparison")
            return
        
        # Create comparison table
        comparison_data = {}
        fields = ['title', 'brand', 'supplier', 'category', 'sku', 'model', 'unspsc']
        
        for product in selected_data:
            product_name = product.get('search_term', 'Unknown')
            product_data = product.get('product_data', {})
            
            comparison_data[product_name] = {}
            for field in fields:
                comparison_data[product_name][field] = product_data.get(field, 'N/A')
        
        # Display comparison table
        if comparison_data:
            df_comparison = pd.DataFrame(comparison_data).T
            st.dataframe(df_comparison, use_container_width=True)
        
        # Show images side by side
        st.markdown("### 🖼️ Product Images")
        cols = st.columns(len(selected_data))
        
        for i, product in enumerate(selected_data):
            with cols[i]:
                product_data = product.get('product_data', {})
                product_name = product.get('search_term', 'Unknown')
                
                # Show image if available
                image_path = self.get_product_image_path(product_data)
                if image_path:
                    try:
                        st.image(image_path, caption=product_name, use_container_width=True)
                    except Exception as e:
                        st.error(f"Could not load image for {product_name}: {e}")
                elif product_data.get('image_url'):
                    try:
                        st.image(product_data['image_url'], caption=product_name, use_container_width=True)
                    except Exception as e:
                        st.error(f"Could not load image for {product_name}: {e}")
                else:
                    st.info(f"No image for {product_name}")
                
                # Show key attributes
                if product_data.get('attributes'):
                    st.markdown(f"**Key Attributes for {product_name}:**")
                    for key, value in list(product_data['attributes'].items())[:3]:
                        if value:
                            st.markdown(f"• **{key.replace('_', ' ').title()}:** {value}")
    
    def render_files_tab(self):
        """Render the files tab"""
        st.header("📁 Extracted Files")
        
        # Create tabs for different file views
        tab1, tab2 = st.tabs(["📂 File Browser", "🖼️ Product Gallery"])
        
        with tab1:
            self.render_file_browser()
        
        with tab2:
            self.render_product_gallery()
    
    def render_file_browser(self):
        """Render the file browser interface"""
        data_folder = "data"
        if not os.path.exists(data_folder):
            st.info(f"No data folder found at '{data_folder}'. Run extractions to create files.")
            return
        
        # List all product folders
        product_folders = [f for f in os.listdir(data_folder) if os.path.isdir(os.path.join(data_folder, f))]
        
        if not product_folders:
            st.info("No product folders found. Run extractions to create files.")
            return
        
        # File browser
        selected_folder = st.selectbox("Select Product Folder", product_folders)
        
        if selected_folder:
            folder_path = os.path.join(data_folder, selected_folder)
            files = os.listdir(folder_path)
            
            st.subheader(f"Files in: {selected_folder}")
            
            for file in files:
                file_path = os.path.join(folder_path, file)
                file_size = os.path.getsize(file_path)
                
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"📄 {file}")
                
                with col2:
                    st.write(f"{file_size:,} bytes")
                
                with col3:
                    if st.button(f"View {file}", key=f"view_{file}"):
                        self.view_file(file_path)
    
    def render_product_gallery(self):
        """Render a gallery of extracted product images"""
        st.markdown("### 🖼️ Product Image Gallery")
        
        data_folder = "data"
        if not os.path.exists(data_folder):
            st.info("No data folder found. Run extractions to see product images.")
            return
        
        # Find all image files
        image_files = []
        for root, dirs, files in os.walk(data_folder):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    image_files.append(os.path.join(root, file))
        
        if not image_files:
            st.info("No product images found. Run extractions with image download enabled to see images.")
            return
        
        # Display images in a grid
        st.markdown(f"Found **{len(image_files)}** product images")
        
        # Create a grid layout
        cols = st.columns(3)
        for i, image_path in enumerate(image_files):
            with cols[i % 3]:
                try:
                    # Get product name from folder
                    product_name = os.path.basename(os.path.dirname(image_path))
                    image_name = os.path.basename(image_path)
                    
                    st.image(image_path, caption=f"{product_name} - {image_name}", use_container_width=True)
                    
                    # Add download button
                    with open(image_path, "rb") as file:
                        st.download_button(
                            label=f"📥 Download {image_name}",
                            data=file.read(),
                            file_name=image_name,
                            mime="image/jpeg"
                        )
                    
                except Exception as e:
                    st.error(f"Could not load image: {e}")
    
    def view_file(self, file_path: str):
        """View file contents"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if file_path.endswith('.json'):
                # Pretty print JSON
                data = json.loads(content)
                st.json(data)
            else:
                # Display as text
                st.text(content)
        except Exception as e:
            st.error(f"Error reading file: {e}")
    
    def run_extraction(self, config: Dict[str, Any]):
        """Run the extraction workflow"""
        try:
            with st.spinner("Running extraction workflow..."):
                # Run workflow
                result = self.workflow_manager.run_workflow(
                    search_term=config['search_term'],
                    data_folder=config['data_folder']
                )
                
                # Handle error case
                if result.get('status') == 'error':
                    st.error(f"❌ Workflow failed: {result.get('error_message', 'Unknown error')}")
                    return
                
                # Store result with proper structure
                workflow_result = {
                    'search_term': config['search_term'],
                    'status': result.get('status', 'unknown'),
                    'current_step': result.get('current_step', 'unknown'),
                    'extraction_success': result.get('extraction_success', False),
                    'timestamp': result.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    'error_message': result.get('error_message'),
                    'product_data': result.get('product_data'),
                    'workflow_complete': result.get('workflow_complete', False)
                }
                
                self.session_state.current_workflow = workflow_result
                self.session_state.workflow_results.append(workflow_result)
                self.session_state.workflow_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'config': config,
                    'result': result
                })
                
                st.success("✅ Extraction completed!")
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Extraction failed: {e}")
    
    def export_results(self):
        """Export results to file"""
        if not self.session_state.workflow_results:
            st.warning("No results to export")
            return
        
        # Create export data
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'total_extractions': len(self.session_state.workflow_results),
            'results': self.session_state.workflow_results,
            'history': self.session_state.workflow_history
        }
        
        # Save to file
        export_file = f"extraction_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        # Provide download link
        with open(export_file, 'r', encoding='utf-8') as f:
            st.download_button(
                label="📥 Download Export",
                data=f.read(),
                file_name=export_file,
                mime="application/json"
            )

def main():
    """Main function to run the Streamlit app"""
    ui = StreamlitWorkflowUI()
    
    # Render the UI
    ui.render_header()
    
    # Get configuration from sidebar
    config = ui.render_sidebar()
    
    # Render main content
    ui.render_main_content(config)

if __name__ == "__main__":
    main() 