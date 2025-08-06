#!/usr/bin/env python3
"""
Advanced LangGraph Agentic Product Extractor
Enhanced version with parallel processing, better error handling, sophisticated agent interactions, and Google Cloud Storage support
"""

import json
import os
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Union
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import pandas as pd
import openpyxl
from google.cloud import storage
from google.api_core import exceptions as gcs_exceptions
import tempfile
import io
import sys

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field, validator
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

from iprocure_product_list_extractor import iProcureProductListExtractor
from fixed_search_extraction import FixedSearchExtractor

# Set up logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True  # <-- important to override any existing settings
)
logger = logging.getLogger(__name__)

class ProductState(str, Enum):
    """States in the product extraction workflow"""
    INITIALIZED = "initialized"
    PRODUCT_LIST_LOADED = "product_list_loaded"
    FOLDERS_CREATED = "folders_created"
    EXTRACTION_STARTED = "extraction_started"
    EXTRACTION_IN_PROGRESS = "extraction_in_progress"
    EXTRACTION_COMPLETED = "extraction_completed"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    FAILED = "failed"
    RETRYING = "retrying"



@dataclass
class ProductData:
    """Enhanced product data structure"""
    name: str
    url: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    price: Optional[str] = None
    sku: Optional[str] = None
    brand: Optional[str] = None
    supplier: Optional[str] = None
    image_url: Optional[str] = None
    image_downloaded: Optional[Dict[str, Any]] = None
    key_attributes: Optional[Dict[str, Any]] = None
    unspsc_code: Optional[str] = None
    main_category: Optional[str] = None
    sub_category: Optional[str] = None
    # iProcure specific fields
    type: Optional[str] = None
    selector: Optional[str] = None
    source: Optional[str] = None
    index: Optional[int] = None
    # Workflow fields
    retry_count: int = 0
    max_retries: int = 3
    last_attempt: Optional[str] = None

@dataclass
class ExtractionResult:
    """Enhanced result of a single product extraction"""
    product_name: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    folder_path: Optional[str] = None
    extraction_time: Optional[float] = None
    retry_count: int = 0
    confidence_score: Optional[float] = None
    validation_status: Optional[str] = None

@dataclass
class WorkflowMetrics:
    """Metrics for tracking workflow performance"""
    total_products: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    retried_extractions: int = 0
    total_extraction_time: float = 0.0
    average_extraction_time: float = 0.0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    success_rate: float = 0.0

class WorkflowState(TypedDict):
    """Enhanced state for the LangGraph workflow with Google Cloud Storage support"""
    current_state: ProductState
    products: List[ProductData]
    extraction_results: List[ExtractionResult]
    current_product_index: int
    data_folder: str
    headless_mode: bool
    delay_between_products: int
    max_parallel_extractions: int
    metrics: WorkflowMetrics
    messages: List[Any]
    error: Optional[str]
    retry_queue: List[ProductData]
    validation_queue: List[ExtractionResult]
    config: Dict[str, Any]
    # Google Cloud Storage configuration
    gcs_bucket_name: str
    gcs_client: Optional[storage.Client]
    use_gcs: bool
    gcs_manager: Optional["GCSManager"]  # Use string forward reference

class GCSManager:
    """Helper class for Google Cloud Storage operations"""
    
    def __init__(self, bucket_name: str, client: Optional[storage.Client] = None):
        self.bucket_name = bucket_name
        self.client = client or storage.Client()
        self.bucket = None
        self.logger = logging.getLogger(__name__)
        self._initialize_bucket()
    
    def _initialize_bucket(self):
        """Initialize and verify bucket access"""
        try:
            self.bucket = self.client.bucket(self.bucket_name)
            # Test bucket access
            self.bucket.exists()
            self.logger.info(f"✅ Connected to GCS bucket: {self.bucket_name}")
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to GCS bucket '{self.bucket_name}': {e}")
            raise
    
    def upload_file(self, local_file_path: str, gcs_file_path: str) -> bool:
        """Upload a file to GCS"""
        try:
            blob = self.bucket.blob(gcs_file_path)
            blob.upload_from_filename(local_file_path)
            self.logger.info(f"✅ Uploaded {local_file_path} to gs://{self.bucket_name}/{gcs_file_path}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to upload {local_file_path}: {e}")
            return False
    
    def upload_from_string(self, content: str, gcs_file_path: str, content_type: str = 'application/json') -> bool:
        """Upload string content to GCS"""
        try:
            blob = self.bucket.blob(gcs_file_path)
            blob.upload_from_string(content, content_type=content_type)
            self.logger.info(f"✅ Uploaded content to gs://{self.bucket_name}/{gcs_file_path}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to upload content to {gcs_file_path}: {e}")
            return False
    
    def upload_dataframe_as_excel(self, df: pd.DataFrame, gcs_file_path: str, sheet_name: str = 'Sheet1') -> bool:
        """Upload pandas DataFrame as Excel file to GCS"""
        try:
            self.logger.info(f"🔄 Starting Excel upload to GCS: {gcs_file_path}")
            self.logger.info(f"📊 DataFrame shape: {df.shape}")
            
            # Create Excel file in memory
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            excel_buffer.seek(0)
            
            self.logger.info(f"💾 Excel file created in memory, size: {len(excel_buffer.getvalue())} bytes")
            
            # Upload to GCS
            blob = self.bucket.blob(gcs_file_path)
            blob.upload_from_file(excel_buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.logger.info(f"✅ Uploaded Excel file to gs://{self.bucket_name}/{gcs_file_path}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to upload Excel file to {gcs_file_path}: {e}")
            self.logger.error(f"❌ Exception type: {type(e).__name__}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return False
    
    def create_folder(self, folder_path: str) -> bool:
        """Create a 'folder' in GCS (actually just a marker object)"""
        try:
            # GCS doesn't have real folders, but we can create a marker
            if not folder_path.endswith('/'):
                folder_path += '/'
            
            blob = self.bucket.blob(folder_path)
            blob.upload_from_string('', content_type='application/x-directory')
            self.logger.info(f"✅ Created folder marker: gs://{self.bucket_name}/{folder_path}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to create folder {folder_path}: {e}")
            return False
    
    def list_blobs(self, prefix: str = None) -> List[str]:
        """List blobs in the bucket with optional prefix"""
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            self.logger.error(f"❌ Failed to list blobs: {e}")
            return []

class ProductListAgent:
    """Enhanced agent responsible for loading and managing product lists"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.llm = ChatOpenAI(temperature=0) if os.getenv("OPENAI_API_KEY") else None
    
    def load_existing_products(self, json_file_path: str) -> List[ProductData]:
        """Load product list from existing JSON file with enhanced parsing"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures
            products_data = []
            if isinstance(data, list):
                products_data = data
            elif isinstance(data, dict) and 'products' in data:
                products_data = data['products']
            elif isinstance(data, dict) and 'data' in data:
                products_data = data['data']
            else:
                self.logger.error(f"Unexpected JSON structure in {json_file_path}")
                return []
            
            # Convert to ProductData objects
            products = []
            for product in products_data:
                if isinstance(product, dict):
                    # Create ProductData with only valid fields
                    product_data = ProductData(
                        name=product.get('name', 'Unknown Product')
                    )
                    
                    # Add optional fields if they exist
                    optional_fields = [
                        'url', 'category', 'description', 'price', 'sku', 'brand', 
                        'supplier', 'image_url', 'unspsc_code', 'main_category', 
                        'sub_category', 'type', 'selector', 'source', 'index'
                    ]
                    
                    for field in optional_fields:
                        if field in product:
                            setattr(product_data, field, product[field])
                    
                    products.append(product_data)
                    
                elif isinstance(product, str):
                    products.append(ProductData(name=product))
            
            # Sort by name for consistent ordering
            products.sort(key=lambda x: x.name)
            
            return products
                
        except Exception as e:
            self.logger.error(f"Error loading JSON file {json_file_path}: {e}")
            return []
    

    
    def extract_from_iprocure(self, url: str = "https://iprocure.ai/pages/productpages") -> List[ProductData]:
        """Extract product list from iProcure website with enhanced processing"""
        try:
            self.logger.info("Extracting product list from iProcure...")
            extractor = iProcureProductListExtractor(headless=True, debug=True)
            raw_products = extractor.extract_with_selenium(url)
            
            if not raw_products:
                self.logger.error("No products found from iProcure!")
                return []
            
            # Convert to ProductData objects
            products = []
            for product in raw_products:
                if isinstance(product, dict):
                    # Create ProductData with only valid fields
                    product_data = ProductData(
                        name=product.get('name', 'Unknown Product')
                    )
                    
                    # Add optional fields if they exist
                    optional_fields = [
                        'url', 'category', 'description', 'price', 'sku', 'brand', 
                        'supplier', 'image_url', 'unspsc_code', 'main_category', 
                        'sub_category', 'type', 'selector', 'source', 'index'
                    ]
                    
                    for field in optional_fields:
                        if field in product:
                            setattr(product_data, field, product[field])
                    
                    products.append(product_data)
                    
                elif isinstance(product, str):
                    products.append(ProductData(name=product))
            
            # Sort by name for consistent ordering
            products.sort(key=lambda x: x.name)
            
            self.logger.info(f"Found {len(products)} products from iProcure")
            return products
            
        except Exception as e:
            self.logger.error(f"Error extracting from iProcure: {e}")
            return []

class FolderManagerAgent:
    """Enhanced agent responsible for managing product folders in GCS or local storage"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_product_folders(self, products: List[ProductData], data_folder: str = "data", 
                             gcs_manager: Optional[GCSManager] = None) -> List[str]:
        """Create folders for each product in GCS or local storage"""
        folder_paths = []
        
        for product in products:
            # Clean folder name (remove special characters)
            folder_name = "".join(c for c in product.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if gcs_manager:
                # Create GCS folder path
                folder_path = f"{data_folder}/{folder_name}"
                if gcs_manager.create_folder(folder_path):
                    self.logger.info(f"Created GCS folder: gs://{gcs_manager.bucket_name}/{folder_path}")
                folder_paths.append(folder_path)
            else:
                # Create local folder
                folder_path = os.path.join(data_folder, folder_name)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                    self.logger.info(f"Created local folder: {folder_path}")
                folder_paths.append(folder_path)
        
        return folder_paths

class ProductExtractionAgent:
    """Enhanced agent responsible for extracting individual product details"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_single_product(self, product: ProductData, data_folder: str = "data", headless: bool = True,
                             gcs_manager: Optional["GCSManager"] = None) -> ExtractionResult:
        """Extract details for a single product with enhanced error handling and cloud-first approach"""
        extractor = None
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting extraction for: {product.name}")
            
            # Initialize the fixed search extractor
            extractor = FixedSearchExtractor(headless=headless, download_images=True)
            
            # Create folder path
            folder_name = "".join(c for c in product.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            if gcs_manager:
                folder_path = f"{data_folder}/{folder_name}"
            else:
                folder_path = os.path.join(data_folder, folder_name)
            
            # Run the complete workflow for this product
            self.logger.info(f"Running complete workflow for: {product.name}")
            result = extractor.run_complete_workflow(product.name)
            
            extraction_time = time.time() - start_time
            
            if result:
                # Create clean data without extraction_success
                clean_data = result.copy()
                if 'extraction_success' in clean_data:
                    del clean_data['extraction_success']
                
                if gcs_manager:
                    # Cloud-first mode: Save only to GCS, no local files
                    self.logger.info(f"☁️ Cloud-first mode: Saving product data to GCS only...")
                    json_content = json.dumps(clean_data, indent=2, ensure_ascii=False)
                    gcs_file_path = f"{folder_path}/product_details.json"
                    
                    if gcs_manager.upload_from_string(json_content, gcs_file_path):
                        self.logger.info(f"✅ Saved product details to GCS: gs://{gcs_manager.bucket_name}/{gcs_file_path}")
                    
                    # Handle image upload to GCS (no local storage)
                    if result.get('image_downloaded'):
                        image_info = result['image_downloaded']
                        local_image_path = image_info['filename']
                        if os.path.exists(local_image_path):
                            image_filename = os.path.basename(local_image_path)
                            gcs_image_path = f"{folder_path}/{image_filename}"
                            
                            if gcs_manager.upload_file(local_image_path, gcs_image_path):
                                self.logger.info(f"✅ Uploaded image to GCS: gs://{gcs_manager.bucket_name}/{gcs_image_path}")
                                # Update the filename in the result to reflect GCS path
                                clean_data['image_downloaded']['filename'] = f"gs://{gcs_manager.bucket_name}/{gcs_image_path}"
                                # Clean up local file immediately (cloud-first mode)
                                try:
                                    os.remove(local_image_path)
                                    self.logger.info(f"🗑️ Removed temporary local image: {local_image_path}")
                                except Exception as e:
                                    self.logger.warning(f"Could not remove temporary image: {e}")
                    
                    self.logger.info(f"🌩️ Cloud-first mode: All data saved to GCS, no local files created")
                else:
                    # Local mode: Save locally (create folder if needed)
                    self.logger.info(f"💾 Local mode: Saving product data locally...")
                    if not os.path.exists(folder_path):
                        os.makedirs(folder_path)
                    
                    json_path = os.path.join(folder_path, "product_details.json")
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(clean_data, f, indent=2, ensure_ascii=False)
                    self.logger.info(f"✅ Saved product details to: {json_path}")
                    
                    # Move downloaded image to product folder if it exists
                    if result.get('image_downloaded'):
                        image_info = result['image_downloaded']
                        old_image_path = image_info['filename']
                        if os.path.exists(old_image_path):
                            new_image_path = os.path.join(folder_path, os.path.basename(old_image_path))
                            os.rename(old_image_path, new_image_path)
                            self.logger.info(f"✅ Moved image to: {new_image_path}")
                            # Update the filename in the result
                            clean_data['image_downloaded']['filename'] = new_image_path
                
                # Calculate confidence score
                confidence_score = self._calculate_confidence_score(result)
                
                return ExtractionResult(
                    product_name=product.name,
                    success=True,
                    result=clean_data,  # Use clean data without extraction_success
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    folder_path=folder_path,
                    extraction_time=extraction_time,
                    retry_count=product.retry_count,
                    confidence_score=confidence_score,
                    validation_status="pending"
                )
            else:
                self.logger.warning(f"❌ No details found for: {product.name}")
                return ExtractionResult(
                    product_name=product.name,
                    success=False,
                    error_message="No details found",
                    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    extraction_time=time.time() - start_time,
                    retry_count=product.retry_count
                )
                
        except Exception as e:
            self.logger.error(f"❌ Error extracting details for {product.name}: {e}")
            return ExtractionResult(
                product_name=product.name,
                success=False,
                error_message=str(e),
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                extraction_time=time.time() - start_time,
                retry_count=product.retry_count
            )
        finally:
            if extractor:
                extractor.close()
    
    def _calculate_confidence_score(self, result: Dict[str, Any]) -> float:
        """Calculate confidence score based on extracted data quality"""
        score = 0.0
        total_fields = 0
        
        # Check for key fields
        key_fields = ['title', 'sku', 'brand', 'supplier', 'description', 'key_attributes']
        for field in key_fields:
            total_fields += 1
            if result.get(field):
                if field == 'key_attributes' and isinstance(result[field], dict) and len(result[field]) > 0:
                    score += 1.0
                elif field != 'key_attributes' and result[field]:
                    score += 1.0
        
        # Bonus for image
        if result.get('image_downloaded'):
            score += 0.5
            total_fields += 0.5
        
        return (score / total_fields) * 100 if total_fields > 0 else 0.0

class ValidationAgent:
    """Agent responsible for validating extraction results"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_extraction_result(self, result: ExtractionResult) -> ExtractionResult:
        """Validate the quality of an extraction result"""
        if not result.success:
            result.validation_status = "failed"
            return result
        
        # Basic validation checks
        validation_issues = []
        
        if not result.result:
            validation_issues.append("No result data")
        
        if result.confidence_score and result.confidence_score < 50:
            validation_issues.append(f"Low confidence score: {result.confidence_score}")
        
        if result.extraction_time and result.extraction_time > 60:
            validation_issues.append(f"Slow extraction time: {result.extraction_time:.2f}s")
        
        # Check for required fields
        if result.result:
            required_fields = ['title']
            for field in required_fields:
                if not result.result.get(field):
                    validation_issues.append(f"Missing required field: {field}")
        
        if validation_issues:
            result.validation_status = "issues"
            result.error_message = "; ".join(validation_issues)
        else:
            result.validation_status = "validated"
        
        return result

class WorkflowCoordinator:
    """Enhanced coordinator for the LangGraph workflow"""
    
    def __init__(self):
        self.product_list_agent = ProductListAgent()
        self.folder_manager_agent = FolderManagerAgent()
        self.product_extraction_agent = ProductExtractionAgent()
        self.validation_agent = ValidationAgent()
        self.logger = logging.getLogger(__name__)
    
    def initialize_workflow(self, state: WorkflowState) -> WorkflowState:
        """Initialize the workflow state with enhanced configuration and GCS setup"""
        self.logger.info("Initializing enhanced workflow with GCS support...")
        
        # Initialize GCS if enabled
        if state["use_gcs"] and state["gcs_bucket_name"]:
            try:
                gcs_manager = GCSManager(state["gcs_bucket_name"])
                state["gcs_manager"] = gcs_manager
                self.logger.info(f"✅ GCS initialized for bucket: {state['gcs_bucket_name']}")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize GCS: {e}")
                state["error"] = f"GCS initialization failed: {e}"
                state["current_state"] = ProductState.FAILED
                return state
        else:
            state["gcs_manager"] = None
            self.logger.info("Using local file storage")
        
        state["current_state"] = ProductState.INITIALIZED
        state["metrics"].start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        state["messages"].append(SystemMessage(content="Enhanced workflow initialized with parallel processing, validation, and storage support"))
        return state
    
    def load_product_list(self, state: WorkflowState) -> WorkflowState:
        """Load or extract product list with priority assessment"""
        self.logger.info("Loading product list with priority assessment...")
        
        # Check for existing product list
        json_files = [
            "iprocure_product_list_20250723_121423.json",
            "iprocure_product_list_20250723_121423.txt",
            "iprocure_product_list_20250723_121423.csv"
        ]
        
        products = []
        
        # Try to load existing product list
        for json_file in json_files:
            if os.path.exists(json_file):
                self.logger.info(f"Found existing product list: {json_file}")
                products = self.product_list_agent.load_existing_products(json_file)
                if products:
                    self.logger.info(f"Loaded {len(products)} products from {json_file}")
                    break
        
        # If no existing list, extract from iProcure
        if not products:
            self.logger.info("No existing product list found. Extracting from iProcure...")
            products = self.product_list_agent.extract_from_iprocure()
            
            if not products:
                state["error"] = "No products found from iProcure!"
                state["current_state"] = ProductState.FAILED
                return state
        
        state["products"] = products
        state["metrics"].total_products = len(products)
        state["current_state"] = ProductState.PRODUCT_LIST_LOADED
        state["messages"].append(AIMessage(content=f"Loaded {len(products)} products"))
        
        return state
    
    def create_folders(self, state: WorkflowState) -> WorkflowState:
        """Create folders for products with priority-based organization in GCS or local storage"""
        if state.get("use_gcs", False):
            self.logger.info("Creating priority-based product folders in GCS...")
        else:
            self.logger.info("Creating priority-based product folders locally...")
            # Ensure local data folder exists
            if not os.path.exists(state["data_folder"]):
                os.makedirs(state["data_folder"])
        
        # Get GCS manager safely
        gcs_manager = state.get("gcs_manager") if state.get("use_gcs", False) else None
        
        folder_paths = self.folder_manager_agent.create_product_folders(
            state["products"], 
            state["data_folder"],
            gcs_manager
        )
        
        state["current_state"] = ProductState.FOLDERS_CREATED
        
        if state.get("use_gcs", False) and gcs_manager:
            state["messages"].append(AIMessage(content=f"Created {len(folder_paths)} priority-organized product folders in GCS bucket: {state['gcs_bucket_name']}"))
        else:
            state["messages"].append(AIMessage(content=f"Created {len(folder_paths)} priority-organized product folders locally"))
        
        return state
    
    def start_extraction(self, state: WorkflowState) -> WorkflowState:
        """Start the extraction process with parallel processing"""
        self.logger.info(f"Starting parallel extraction for {len(state['products'])} products...")
        
        state["current_state"] = ProductState.EXTRACTION_STARTED
        state["current_product_index"] = 0
        state["extraction_results"] = []
        state["retry_queue"] = []
        state["validation_queue"] = []
        
        state["messages"].append(AIMessage(content=f"Started parallel extraction for {len(state['products'])} products (Max parallel: {state['max_parallel_extractions']})"))
        
        return state
    
    def extract_products_parallel(self, state: WorkflowState) -> WorkflowState:
        """Extract products in parallel batches"""
        if state["current_product_index"] >= len(state["products"]):
            # All products processed
            state["current_state"] = ProductState.EXTRACTION_COMPLETED
            state["messages"].append(AIMessage(content="All products processed"))
            return state
        
        # Get next batch of products
        batch_size = min(state["max_parallel_extractions"], len(state["products"]) - state["current_product_index"])
        batch_products = state["products"][state["current_product_index"]:state["current_product_index"] + batch_size]
        
        self.logger.info(f"Processing batch {state['current_product_index']//batch_size + 1}: {len(batch_products)} products")
        
        # Process batch in parallel
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            future_to_product = {
                executor.submit(
                    self.product_extraction_agent.extract_single_product,
                    product,
                    state["data_folder"],
                    state["headless_mode"],
                    state.get("gcs_manager") if state.get("use_gcs", False) else None
                ): product for product in batch_products
            }
            
            for future in as_completed(future_to_product):
                product = future_to_product[future]
                try:
                    result = future.result()
                    state["extraction_results"].append(result)
                    
                    if result.success:
                        state["metrics"].successful_extractions += 1
                        self.logger.info(f"✅ Successfully extracted: {product.name}")
                    else:
                        state["metrics"].failed_extractions += 1
                        self.logger.warning(f"❌ Failed to extract: {product.name}")
                        
                        # Add to retry queue if retries remaining
                        if product.retry_count < product.max_retries:
                            product.retry_count += 1
                            product.last_attempt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            state["retry_queue"].append(product)
                    
                    # Add to validation queue
                    state["validation_queue"].append(result)
                    
                except Exception as e:
                    self.logger.error(f"❌ Error in parallel extraction for {product.name}: {e}")
                    state["metrics"].failed_extractions += 1
        
        state["current_product_index"] += batch_size
        
        # Add delay between batches
        if state["current_product_index"] < len(state["products"]):
            self.logger.info(f"Waiting {state['delay_between_products']} seconds before next batch...")
            time.sleep(state["delay_between_products"])
        
        state["current_state"] = ProductState.EXTRACTION_IN_PROGRESS
        state["messages"].append(AIMessage(content=f"Processed batch: {len(batch_products)} products"))
        
        return state
    
    def process_retry_queue(self, state: WorkflowState) -> WorkflowState:
        """Process products that need retrying"""
        if not state["retry_queue"]:
            return state
        
        self.logger.info(f"Processing retry queue: {len(state['retry_queue'])} products")
        state["current_state"] = ProductState.RETRYING
        
        retry_products = state["retry_queue"].copy()
        state["retry_queue"] = []
        
        for product in retry_products:
            self.logger.info(f"Retrying extraction for: {product.name} (Attempt {product.retry_count})")
            
            result = self.product_extraction_agent.extract_single_product(
                product,
                state["data_folder"],
                state["headless_mode"],
                state.get("gcs_manager") if state.get("use_gcs", False) else None
            )
            
            # Update the result in extraction_results
            for i, existing_result in enumerate(state["extraction_results"]):
                if existing_result.product_name == product.name:
                    state["extraction_results"][i] = result
                    break
            
            if result.success:
                state["metrics"].successful_extractions += 1
                state["metrics"].retried_extractions += 1
                self.logger.info(f"✅ Retry successful for: {product.name}")
            else:
                state["metrics"].failed_extractions += 1
                self.logger.warning(f"❌ Retry failed for: {product.name}")
        
        state["messages"].append(AIMessage(content=f"Processed retry queue: {len(retry_products)} products"))
        
        return state
    
    def start_validation(self, state: WorkflowState) -> WorkflowState:
        """Start validation of extraction results"""
        self.logger.info("Starting validation of extraction results...")
        state["current_state"] = ProductState.VALIDATION_STARTED
        
        # Validate all results
        for i, result in enumerate(state["extraction_results"]):
            validated_result = self.validation_agent.validate_extraction_result(result)
            state["extraction_results"][i] = validated_result
        
        state["current_state"] = ProductState.VALIDATION_COMPLETED
        state["messages"].append(AIMessage(content=f"Validated {len(state['extraction_results'])} extraction results"))
        
        return state
    
    def save_summary(self, state: WorkflowState) -> WorkflowState:
        """Save enhanced extraction summary with metrics and cloud-first Excel export"""
        state["metrics"].end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculate final metrics
        if state["metrics"].total_products > 0:
            state["metrics"].success_rate = (state["metrics"].successful_extractions / state["metrics"].total_products) * 100
        
        # Calculate average extraction time
        successful_results = [r for r in state["extraction_results"] if r.success and r.extraction_time]
        if successful_results:
            total_time = sum(r.extraction_time for r in successful_results)
            state["metrics"].average_extraction_time = total_time / len(successful_results)
        
        # Save all product data to Excel (cloud-first)
        self._save_to_excel(state["extraction_results"], state.get("gcs_manager"))
        
        # Create summary data
        summary = {
            'extraction_summary': {
                'total_products': state["metrics"].total_products,
                'successful_extractions': state["metrics"].successful_extractions,
                'failed_extractions': state["metrics"].failed_extractions,
                'retried_extractions': state["metrics"].retried_extractions,
                'success_rate': f"{state['metrics'].success_rate:.1f}%",
                'average_extraction_time': f"{state['metrics'].average_extraction_time:.2f}s",
                'start_time': state["metrics"].start_time,
                'end_time': state["metrics"].end_time
            },
            'detailed_results': [result.__dict__ for result in state["extraction_results"]],
            'validation_summary': self._get_validation_summary(state["extraction_results"])
        }
        
        # Save summary - cloud-first mode
        summary_filename = f"langgraph_advanced_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        gcs_manager = state.get("gcs_manager")
        
        if gcs_manager:
            # Cloud-first mode: Save summary to GCS only
            self.logger.info(f"☁️ Cloud-first mode: Saving summary to GCS only...")
            summary_content = json.dumps(summary, indent=2, ensure_ascii=False, default=str)
            if gcs_manager.upload_from_string(summary_content, summary_filename):
                self.logger.info(f"✅ Summary saved to GCS: gs://{gcs_manager.bucket_name}/{summary_filename}")
                self.logger.info(f"🌩️ Cloud-first mode: No local summary file created")
                state["messages"].append(AIMessage(content=f"Enhanced summary saved to GCS: {summary_filename}"))
            else:
                self.logger.error(f"❌ Failed to save summary to GCS")
                state["messages"].append(AIMessage(content=f"❌ Failed to save summary to GCS"))
        else:
            # Local mode: Save summary locally
            self.logger.info(f"💾 Local mode: Saving summary locally...")
            with open(summary_filename, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"✅ Summary saved locally: {summary_filename}")
            state["messages"].append(AIMessage(content=f"Enhanced summary saved to: {summary_filename}"))
        
        return state
    
    def _save_to_excel(self, extraction_results: List[ExtractionResult], gcs_manager: Optional["GCSManager"] = None) -> None:
        """Save all extraction results to Excel - GCS only when enabled, local when disabled"""
        try:
            self.logger.info(f"🔄 Starting Excel export process...")
            self.logger.info(f"📊 Processing {len(extraction_results)} extraction results")
            self.logger.info(f"☁️ GCS Manager available: {gcs_manager is not None}")
            
            excel_data = []
            
            for result in extraction_results:
                if result.success and result.result:
                    # Extract data from result, excluding extraction_success
                    product_data = result.result.copy()
                    
                    # Remove extraction_success if it exists (should already be removed)
                    if 'extraction_success' in product_data:
                        del product_data['extraction_success']
                    
                    # Flatten the data structure for Excel
                    excel_row = {
                        'product_name': result.product_name,
                        'extraction_timestamp': result.timestamp,
                        'url': product_data.get('url', ''),
                        'title': product_data.get('title', ''),
                        'brand': product_data.get('brand', ''),
                        'supplier': product_data.get('supplier', ''),
                        'category': product_data.get('category', ''),
                        'sku': product_data.get('sku', ''),
                        'model': product_data.get('model', ''),
                        'description': product_data.get('description', ''),
                        'unspsc': product_data.get('unspsc', ''),
                        'main_category': product_data.get('main_category', ''),
                    }
                    
                    # Handle key_attributes - convert dict to string
                    if 'key_attributes' in product_data and isinstance(product_data['key_attributes'], dict):
                        for key, value in product_data['key_attributes'].items():
                            excel_row[f'attribute_{key}'] = str(value)
                    
                    # Handle technical_specifications - convert dict to string  
                    if 'technical_specifications' in product_data and isinstance(product_data['technical_specifications'], dict):
                        for key, value in product_data['technical_specifications'].items():
                            excel_row[f'spec_{key}'] = str(value)
                    
                    # Handle image_downloaded info
                    if 'image_downloaded' in product_data and isinstance(product_data['image_downloaded'], dict):
                        image_info = product_data['image_downloaded']
                        excel_row['image_filename'] = image_info.get('filename', '')
                        excel_row['image_url'] = image_info.get('url', '')
                        excel_row['image_size_bytes'] = image_info.get('size_bytes', '')
                    
                    # Handle alternative_descriptions
                    if 'alternative_descriptions' in product_data and isinstance(product_data['alternative_descriptions'], list):
                        excel_row['alternative_descriptions'] = '; '.join(product_data['alternative_descriptions'])
                    
                    # Add extraction metadata
                    excel_row['extraction_time_seconds'] = result.extraction_time
                    excel_row['confidence_score'] = result.confidence_score
                    excel_row['validation_status'] = result.validation_status
                    excel_row['retry_count'] = result.retry_count
                    
                    excel_data.append(excel_row)
                else:
                    # Add failed extractions with basic info
                    excel_row = {
                        'product_name': result.product_name,
                        'extraction_timestamp': result.timestamp,
                        'error_message': result.error_message,
                        'extraction_time_seconds': result.extraction_time,
                        'retry_count': result.retry_count,
                        'validation_status': 'failed'
                    }
                    excel_data.append(excel_row)
            
            self.logger.info(f"📋 Prepared {len(excel_data)} rows for Excel export")
            
            if excel_data:
                # Create DataFrame
                df = pd.DataFrame(excel_data)
                excel_filename = f"product_extraction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                
                self.logger.info(f"📄 Excel filename: {excel_filename}")
                
                if gcs_manager:
                    # Cloud-first mode: Save only to GCS
                    self.logger.info(f"☁️ Cloud-first mode: Saving Excel file to GCS only...")
                    if gcs_manager.upload_dataframe_as_excel(df, excel_filename, 'Product_Data'):
                        self.logger.info(f"✅ Saved all product data to GCS Excel: gs://{gcs_manager.bucket_name}/{excel_filename}")
                        self.logger.info(f"✅ Total rows saved: {len(excel_data)}")
                        self.logger.info(f"🌩️ Cloud-first mode: No local Excel file created")
                    else:
                        self.logger.error(f"❌ Failed to upload Excel to GCS")
                else:
                    # Local mode: Save locally only
                    self.logger.info(f"💾 Local mode: Saving Excel file locally...")
                    df.to_excel(excel_filename, index=False, sheet_name='Product_Data')
                    self.logger.info(f"✅ Saved all product data to Excel: {excel_filename}")
                    self.logger.info(f"✅ Total rows saved: {len(excel_data)}")
            else:
                self.logger.warning("No data to save to Excel - all extractions failed")
                
        except Exception as e:
            self.logger.error(f"Error saving to Excel: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")

    def _get_validation_summary(self, results: List[ExtractionResult]) -> Dict[str, int]:
        """Get summary of validation results"""
        summary = {}
        for result in results:
            status = result.validation_status or "unknown"
            summary[status] = summary.get(status, 0) + 1
        return summary
    
    def should_continue_extraction(self, state: WorkflowState) -> str:
        """Determine next step in the workflow"""
        if state["current_product_index"] >= len(state["products"]):
            if state["retry_queue"]:
                return "retry"
            return "validate"
        return "continue"
    
    def handle_error(self, state: WorkflowState) -> WorkflowState:
        """Handle workflow errors with enhanced logging"""
        state["current_state"] = ProductState.FAILED
        error_msg = f"Workflow failed: {state.get('error', 'Unknown error')}"
        state["messages"].append(AIMessage(content=error_msg))
        self.logger.error(error_msg)
        return state

def create_advanced_workflow() -> StateGraph:
    """Create the enhanced LangGraph workflow"""
    
    # Initialize coordinator
    coordinator = WorkflowCoordinator()
    
    # Create the workflow graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("initialize", coordinator.initialize_workflow)
    workflow.add_node("load_products", coordinator.load_product_list)
    workflow.add_node("create_folders", coordinator.create_folders)
    workflow.add_node("start_extraction", coordinator.start_extraction)
    workflow.add_node("extract_parallel", coordinator.extract_products_parallel)
    workflow.add_node("process_retries", coordinator.process_retry_queue)
    workflow.add_node("start_validation", coordinator.start_validation)
    workflow.add_node("save_summary", coordinator.save_summary)
    workflow.add_node("handle_error", coordinator.handle_error)
    
    # Add edges
    workflow.add_edge("initialize", "load_products")
    workflow.add_edge("load_products", "create_folders")
    workflow.add_edge("create_folders", "start_extraction")
    workflow.add_edge("start_extraction", "extract_parallel")
    
    # Conditional edge for extraction loop
    workflow.add_conditional_edges(
        "extract_parallel",
        coordinator.should_continue_extraction,
        {
            "continue": "extract_parallel",
            "retry": "process_retries",
            "validate": "start_validation"
        }
    )
    
    # Add edges for retry and validation flow
    workflow.add_edge("process_retries", "start_validation")
    workflow.add_edge("start_validation", "save_summary")
    
    # Error handling
    workflow.add_edge("handle_error", END)
    workflow.add_edge("save_summary", END)
    
    # Set entry point
    workflow.set_entry_point("initialize")
    
    return workflow

def main():
    """Main function to run the enhanced LangGraph workflow with cloud-first GCS support"""
    print("="*70)
    print("ADVANCED LANGGRAPH AGENTIC PRODUCT EXTRACTOR")
    print("Enhanced with parallel processing, validation, retry logic, and Cloud-First GCS")
    print("="*70)
    
    # Import configuration
    try:
        from gcs_config import USE_GCS, GCS_BUCKET_NAME, GCS_DATA_FOLDER, EXTRACTION_CONFIG, validate_gcs_config
    except ImportError:
        print("Error: gcs_config.py not found!")
        print("Please ensure gcs_config.py exists and is properly configured.")
        return
    
    # Validate GCS configuration
    if not validate_gcs_config():
        print("GCS configuration validation failed. Please fix the issues above.")
        return
    
    if USE_GCS:
        print(f"Cloud Storage: gs://{GCS_BUCKET_NAME}")
        print("Cloud-First Mode Enabled")
        print("- All data will be saved directly to GCS")
        print("- No local files will be created")
        print("- Individual JSON files: saved to GCS")
        print("- Excel consolidated file: saved to GCS")
        print("- Summary reports: saved to GCS")
        print("GCS configuration validated successfully")
    else:
        print("Local Storage Mode")
        print("- All data will be saved locally")
    print("="*70)
    
    # Create initial state with enhanced configuration
    initial_state = WorkflowState(
        current_state=ProductState.INITIALIZED,
        products=[],
        extraction_results=[],
        current_product_index=0,
        data_folder=GCS_DATA_FOLDER if USE_GCS else "data",
        headless_mode=EXTRACTION_CONFIG.get("headless_mode", True),
        delay_between_products=EXTRACTION_CONFIG.get("delay_between_products", 3),
        max_parallel_extractions=EXTRACTION_CONFIG.get("max_parallel_extractions", 3),
        metrics=WorkflowMetrics(),
        messages=[],
        error=None,
        retry_queue=[],
        validation_queue=[],
        config={
            "enable_parallel_processing": True,
            "enable_validation": True,
            "enable_retry_logic": True,
            "max_retries": EXTRACTION_CONFIG.get("max_retries", 3),
            "confidence_threshold": EXTRACTION_CONFIG.get("confidence_threshold", 50.0),
            "export_to_excel": True,
            "cloud_first_mode": USE_GCS
        },
        # Google Cloud Storage configuration
        gcs_bucket_name=GCS_BUCKET_NAME,
        gcs_client=None,  # Will be initialized in workflow
        use_gcs=USE_GCS,
        gcs_manager=None  # Will be initialized in workflow
    )
    
    # Create and compile workflow
    workflow = create_advanced_workflow()
    app = workflow.compile()
    
    # Run the workflow
    try:
        result = app.invoke(initial_state)
        
        # Print enhanced final summary
        print(f"\n{'='*70}")
        if USE_GCS:
            print("ENHANCED EXTRACTION COMPLETE - ALL DATA SAVED TO GOOGLE CLOUD STORAGE")
        else:
            print("ENHANCED EXTRACTION COMPLETE - DATA SAVED LOCALLY")
        print(f"{'='*70}")
        print(f"Total products processed: {result['metrics'].total_products}")
        print(f"Successful extractions: {result['metrics'].successful_extractions}")
        print(f"Failed extractions: {result['metrics'].failed_extractions}")
        print(f"Retried extractions: {result['metrics'].retried_extractions}")
        print(f"Success rate: {result['metrics'].success_rate:.1f}%")
        print(f"Average extraction time: {result['metrics'].average_extraction_time:.2f}s")
        print(f"Total extraction time: {result['metrics'].total_extraction_time:.2f}s")
        print(f"{'='*70}")
        
        if USE_GCS:
            print("All product data has been saved to Google Cloud Storage:")
            print(f"   Excel file: gs://{GCS_BUCKET_NAME}/product_extraction_results_*.xlsx")
            print(f"   Individual JSON files: gs://{GCS_BUCKET_NAME}/{GCS_DATA_FOLDER}/[product-name]/product_details.json")
            print(f"   Product images: gs://{GCS_BUCKET_NAME}/{GCS_DATA_FOLDER}/[product-name]/[image-file]")
            print(f"   Summary report: gs://{GCS_BUCKET_NAME}/langgraph_advanced_summary_*.json")
            print("   (excluding extraction_success field for cleaner data)")
            print(f"\nCloud Console: https://console.cloud.google.com/storage/browser/{GCS_BUCKET_NAME}")
            print("Cloud-First Mode: No local files were created")
        else:
            print("All product data has been saved locally:")
            print("   Excel file: ./product_extraction_results_*.xlsx")
            print("   Individual JSON files: ./data/[product-name]/product_details.json")
            print("   Summary report: ./langgraph_advanced_summary_*.json")
        print(f"{'='*70}")

        # Show validation summary
        validation_summary = result.get('validation_summary', {})
        if validation_summary:
            print("\nValidation Summary:")
            for status, count in validation_summary.items():
                print(f"  {status}: {count} results")
        
        # Show failed products if any
        if result['metrics'].failed_extractions > 0:
            print("\nFailed products:")
            for extraction_result in result['extraction_results']:
                if not extraction_result.success:
                    print(f"  - {extraction_result.product_name}: {extraction_result.error_message}")
        
        # Show workflow messages
        print("\nWorkflow Messages:")
        for message in result['messages']:
            if hasattr(message, 'content'):
                print(f"  - {message.content}")
        
    except Exception as e:
        logger.error(f"Enhanced workflow execution failed: {e}")
        print(f"❌ Enhanced workflow failed: {e}")

if __name__ == "__main__":
    main() 