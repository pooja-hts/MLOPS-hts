#!/usr/bin/env python3
"""
LangGraph Workflow for Fixed Search Extraction
Provides a structured workflow for product extraction with state management
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from fixed_search_extraction import FixedSearchExtractor

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ExtractionState(TypedDict):
    """State for the extraction workflow"""
    search_term: str
    status: str
    current_step: str
    error_message: Optional[str]
    search_results: Optional[Dict]
    product_url: Optional[str]
    product_data: Optional[Dict]
    extraction_success: bool
    workflow_complete: bool
    timestamp: str
    data_folder: str

class SearchAgent:
    """Agent responsible for searching products"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def search_products(self, state: ExtractionState) -> ExtractionState:
        """Search for products using the search term"""
        try:
            self.logger.info(f"Starting search for: {state['search_term']}")
            
            # Initialize extractor
            extractor = FixedSearchExtractor(headless=True, download_images=False)
            
            # Test search URL
            search_results = extractor.test_search_url(state['search_term'])
            
            if 'error' in search_results:
                state['status'] = 'error'
                state['error_message'] = f"Search failed: {search_results['error']}"
                state['current_step'] = 'search_failed'
                return state
            
            state['search_results'] = search_results
            state['status'] = 'search_completed'
            state['current_step'] = 'search_success'
            
            self.logger.info(f"Search completed successfully")
            extractor.close()
            
            return state
            
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            state['status'] = 'error'
            state['error_message'] = str(e)
            state['current_step'] = 'search_failed'
            return state

class ProductNavigationAgent:
    """Agent responsible for finding and navigating to product pages"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def find_and_navigate_product(self, state: ExtractionState) -> ExtractionState:
        """Find and navigate to a product page"""
        try:
            self.logger.info(f"Finding product for: {state['search_term']}")
            
            # Initialize extractor
            extractor = FixedSearchExtractor(headless=True, download_images=False)
            
            # Find and click product
            product_url = extractor.find_and_click_product(state['search_term'])
            
            if product_url:
                state['product_url'] = product_url
                state['status'] = 'navigation_completed'
                state['current_step'] = 'product_found'
                self.logger.info(f"Product found: {product_url}")
            else:
                # Fallback: extract from search results
                self.logger.info("No product URL found, extracting from search results")
                basic_info = extractor._extract_basic_info_from_search_results(state['search_term'])
                if basic_info:
                    state['product_data'] = basic_info
                    state['status'] = 'extraction_completed'
                    state['current_step'] = 'basic_extraction'
                    state['extraction_success'] = True
                else:
                    state['status'] = 'error'
                    state['error_message'] = "Could not find product or extract basic info"
                    state['current_step'] = 'navigation_failed'
            
            extractor.close()
            return state
            
        except Exception as e:
            self.logger.error(f"Navigation error: {e}")
            state['status'] = 'error'
            state['error_message'] = str(e)
            state['current_step'] = 'navigation_failed'
            return state

class ProductExtractionAgent:
    """Agent responsible for extracting detailed product information"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_product_details(self, state: ExtractionState) -> ExtractionState:
        """Extract detailed product information"""
        try:
            if not state.get('product_url'):
                self.logger.warning("No product URL available for detailed extraction")
                return state
            
            self.logger.info(f"Extracting details from: {state['product_url']}")
            
            # Initialize extractor
            extractor = FixedSearchExtractor(headless=True, download_images=True)
            
            # Create product folder path
            safe_search_term = "".join(c for c in state['search_term'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_search_term = safe_search_term.replace(' ', '_')
            product_folder = os.path.join(state['data_folder'], safe_search_term)
            
            # Extract product details
            product_data = extractor.extract_product_details(
                state['product_url'], 
                state['search_term'], 
                product_folder
            )
            
            if product_data:
                state['product_data'] = product_data
                state['status'] = 'extraction_completed'
                state['current_step'] = 'detailed_extraction'
                state['extraction_success'] = True
                self.logger.info("Product details extracted successfully")
            else:
                state['status'] = 'error'
                state['error_message'] = "Failed to extract product details"
                state['current_step'] = 'extraction_failed'
            
            extractor.close()
            return state
            
        except Exception as e:
            self.logger.error(f"Extraction error: {e}")
            state['status'] = 'error'
            state['error_message'] = str(e)
            state['current_step'] = 'extraction_failed'
            return state

class DataSavingAgent:
    """Agent responsible for saving extracted data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def save_extracted_data(self, state: ExtractionState) -> ExtractionState:
        """Save the extracted data to files"""
        try:
            if not state.get('product_data'):
                self.logger.warning("No product data to save")
                return state
            
            # Use existing folder structure from product_data if available
            if state['product_data'].get('file_paths'):
                folder_path = state['product_data']['file_paths']['product_folder']
                json_path = state['product_data']['file_paths']['json_file']
            else:
                # Fallback: create folder structure
                data_folder = state.get('data_folder', 'data')
                if not os.path.exists(data_folder):
                    os.makedirs(data_folder)
                
                # Create product-specific folder
                safe_search_term = "".join(c for c in state['search_term'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_search_term = safe_search_term.replace(' ', '_')
                folder_path = os.path.join(data_folder, safe_search_term)
                
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                
                # Save product data
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                json_filename = f"product_data_{timestamp}.json"
                json_path = os.path.join(folder_path, json_filename)
                
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(state['product_data'], f, indent=2, ensure_ascii=False)
            
            # Save workflow summary
            summary = {
                'search_term': state['search_term'],
                'timestamp': state['timestamp'],
                'status': state['status'],
                'current_step': state['current_step'],
                'extraction_success': state['extraction_success'],
                'product_url': state.get('product_url'),
                'data_folder': folder_path,
                'json_file': json_path
            }
            
            summary_path = os.path.join(folder_path, "workflow_summary.json")
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            state['status'] = 'completed'
            state['current_step'] = 'data_saved'
            state['workflow_complete'] = True
            
            self.logger.info(f"Data saved to: {folder_path}")
            return state
            
        except Exception as e:
            self.logger.error(f"Data saving error: {e}")
            state['status'] = 'error'
            state['error_message'] = str(e)
            state['current_step'] = 'save_failed'
            return state

class WorkflowManager:
    """Manages the complete extraction workflow"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize agents
        self.search_agent = SearchAgent()
        self.navigation_agent = ProductNavigationAgent()
        self.extraction_agent = ProductExtractionAgent()
        self.saving_agent = DataSavingAgent()
        
        # Create workflow graph
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """Create the workflow graph"""
        workflow = StateGraph(ExtractionState)
        
        # Add nodes
        workflow.add_node("search", self.search_agent.search_products)
        workflow.add_node("navigate", self.navigation_agent.find_and_navigate_product)
        workflow.add_node("extract", self.extraction_agent.extract_product_details)
        workflow.add_node("save", self.saving_agent.save_extracted_data)
        
        # Define edges
        workflow.set_entry_point("search")
        
        # Conditional edges based on state
        def should_continue(state: ExtractionState) -> str:
            if state['status'] == 'error':
                return END
            elif state['current_step'] == 'search_success':
                return "navigate"
            elif state['current_step'] == 'product_found':
                return "extract"
            elif state['current_step'] in ['basic_extraction', 'detailed_extraction']:
                return "save"
            else:
                return END
        
        workflow.add_conditional_edges("search", should_continue)
        workflow.add_conditional_edges("navigate", should_continue)
        workflow.add_conditional_edges("extract", should_continue)
        workflow.add_conditional_edges("save", lambda _: END)
        
        return workflow.compile()
    
    def run_workflow(self, search_term: str, data_folder: str = "data") -> Dict:
        """Run the complete workflow"""
        try:
            # Initialize state
            initial_state = ExtractionState(
                search_term=search_term,
                status="started",
                current_step="initialized",
                error_message=None,
                search_results=None,
                product_url=None,
                product_data=None,
                extraction_success=False,
                workflow_complete=False,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                data_folder=data_folder
            )
            
            self.logger.info(f"Starting workflow for: {search_term}")
            
            # Run workflow
            result = self.workflow.invoke(initial_state)
            
            self.logger.info(f"Workflow completed with status: {result['status']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Workflow error: {e}")
            return {
                'status': 'error',
                'error_message': str(e),
                'workflow_complete': False
            }

def main():
    """Test the workflow"""
    workflow_manager = WorkflowManager()
    
    # Test with a sample search term
    search_term = "Safety Belts & Harness"
    result = workflow_manager.run_workflow(search_term)
    
    print("Workflow Result:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main() 