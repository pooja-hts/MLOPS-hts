#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the Lulu Pipeline components are working correctly.
"""

import os
import sys
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_imports():
    """Test if all required modules can be imported."""
    try:
        import scrapy
        logger.info(f"✓ Scrapy imported successfully (version: {scrapy.__version__})")
    except ImportError as e:
        logger.error(f"✗ Failed to import Scrapy: {e}")
        return False
    
    try:
        import selenium
        logger.info(f"✓ Selenium imported successfully (version: {selenium.__version__})")
    except ImportError as e:
        logger.error(f"✗ Failed to import Selenium: {e}")
        return False
    
    try:
        from lulu_pipeline.items import LuluRayyanCategoryItem, LuluRayyanProductItem
        logger.info("✓ LuluRayyan items imported successfully")
    except ImportError as e:
        logger.error(f"✗ Failed to import items: {e}")
        return False
    
    try:
        from lulu_pipeline.pipelines import (
            LuluRayyanCategoryJsonWriterPipeline,
            LuluRayyanCategoryTextWriterPipeline
        )
        logger.info("✓ LuluRayyan pipelines imported successfully")
    except ImportError as e:
        logger.error(f"✗ Failed to import pipelines: {e}")
        return False
    
    return True

def test_items():
    """Test if items can be created and populated."""
    try:
        from lulu_pipeline.items import LuluRayyanCategoryItem, LuluRayyanProductItem
        
        # Test category item
        category_item = LuluRayyanCategoryItem()
        category_item['category_name'] = 'Test Category'
        category_item['category_url'] = 'https://example.com/category'
        category_item['category_id'] = 'test-category'
        category_item['subcategories'] = []
        category_item['products_count'] = 0
        category_item['description'] = 'Test description'
        category_item['image_url'] = 'https://example.com/image.jpg'
        category_item['scraped_at'] = '2024-01-01T12:00:00'
        
        logger.info("✓ Category item created and populated successfully")
        
        # Test product item
        product_item = LuluRayyanProductItem()
        product_item['name'] = 'Test Product'
        product_item['category'] = 'Test Category'
        product_item['subcategory'] = 'Test Subcategory'
        product_item['url'] = 'https://example.com/product'
        product_item['image_url'] = 'https://example.com/product.jpg'
        product_item['price'] = '$99.99'
        product_item['sku'] = 'TEST-001'
        product_item['brand'] = 'Test Brand'
        product_item['description'] = 'Test product description'
        product_item['stock_status'] = 'In Stock'
        product_item['extracted_at'] = '2024-01-01T12:00:00'
        
        logger.info("✓ Product item created and populated successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to test items: {e}")
        return False

def test_pipelines():
    """Test if pipelines can be instantiated."""
    try:
        from lulu_pipeline.pipelines import (
            LuluRayyanCategoryJsonWriterPipeline,
            LuluRayyanCategoryTextWriterPipeline
        )
        
        # Test pipeline instantiation
        json_pipeline = LuluRayyanCategoryJsonWriterPipeline()
        text_pipeline = LuluRayyanCategoryTextWriterPipeline()
        
        logger.info("✓ Pipelines instantiated successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to test pipelines: {e}")
        return False

def test_project_structure():
    """Test if the project structure is correct."""
    required_files = [
        'scrapy.cfg',
        'lulu_pipeline/__init__.py',
        'lulu_pipeline/settings.py',
        'lulu_pipeline/items.py',
        'lulu_pipeline/pipelines.py',
        'lulu_pipeline/spiders/__init__.py',
        'lulu_pipeline/spiders/lulu.py',
        'requirements.txt',
        'run_lulu_spider.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        logger.error(f"✗ Missing required files: {missing_files}")
        return False
    else:
        logger.info("✓ All required files present")
        return True

def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Lulu Pipeline Test Suite")
    logger.info("=" * 60)
    
    tests = [
        ("Project Structure", test_project_structure),
        ("Module Imports", test_imports),
        ("Item Creation", test_items),
        ("Pipeline Instantiation", test_pipelines)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\nRunning test: {test_name}")
        logger.info("-" * 40)
        
        try:
            if test_func():
                logger.info(f"✓ {test_name} PASSED")
                passed += 1
            else:
                logger.error(f"✗ {test_name} FAILED")
        except Exception as e:
            logger.error(f"✗ {test_name} FAILED with exception: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! The pipeline is ready to use.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
