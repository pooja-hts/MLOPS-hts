# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import json
from datetime import datetime
from itemadapter import ItemAdapter
import logging
import os

logger = logging.getLogger(__name__)


class LuluRayyanCategoryJsonWriterPipeline:
    """
    Pipeline to write LuluRayyan category items to JSON file.
    """
    
    def __init__(self):
        self.file = None
        self.categories = []
    
    def open_spider(self, spider):
        """Open JSON file when spider starts."""
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        self.file = open('data/lulurayyan_categories.json', 'w', encoding='utf-8')
        self.file.write('[\n')
        self.first_item = True
    
    def close_spider(self, spider):
        """Close JSON file when spider finishes."""
        if self.file:
            self.file.write('\n]')
            self.file.close()
            logger.info(f"Saved {len(self.categories)} LuluRayyan categories to JSON file")
    
    def process_item(self, item, spider):
        """Write category item to JSON file."""
        # Only process LuluRayyan category items
        if not hasattr(item, 'fields') or 'category_name' not in item.fields:
            return item
            
        if not self.first_item:
            self.file.write(',\n')
        
        # Convert item to dictionary using ItemAdapter
        item_dict = ItemAdapter(item).asdict()
        json.dump(item_dict, self.file, indent=2, ensure_ascii=False)
        self.first_item = False
        self.categories.append(item)
        
        return item


class LuluRayyanCategoryTextWriterPipeline:
    """
    Pipeline to write LuluRayyan category items to human-readable text file.
    """
    
    def __init__(self):
        self.file = None
        self.categories = []
    
    def open_spider(self, spider):
        """Open text file when spider starts."""
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        self.file = open('data/lulurayyan_categories.txt', 'w', encoding='utf-8')
        self.file.write("LuluRayyan Group Categories\n")
        self.file.write("=" * 50 + "\n\n")
        self.file.write(f"Scraped on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.file.write(f"Source: https://lulurayyangroup.com/\n\n")
    
    def close_spider(self, spider):
        """Close text file when spider finishes."""
        if self.file:
            # Write summary
            self.file.write(f"\n" + "=" * 50 + "\n")
            self.file.write(f"Total Categories Extracted: {len(self.categories)}\n")
            self.file.write(f"Scraping completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.file.close()
            logger.info(f"Saved {len(self.categories)} LuluRayyan categories to text file")
    
    def process_item(self, item, spider):
        """Write category item to text file."""
        # Only process LuluRayyan category items
        if not hasattr(item, 'fields') or 'category_name' not in item.fields:
            return item
            
        category_name = item.get('category_name', 'N/A')
        category_url = item.get('category_url', 'N/A')
        category_id = item.get('category_id', 'N/A')
        description = item.get('description', 'N/A')
        image_url = item.get('image_url', 'N/A')
        subcategories = item.get('subcategories', [])
        products_count = item.get('products_count', 0)
        
        self.file.write(f"Category: {category_name}\n")
        self.file.write(f"Category ID: {category_id}\n")
        self.file.write(f"URL: {category_url}\n")
        self.file.write(f"Description: {description}\n")
        self.file.write(f"Image URL: {image_url}\n")
        self.file.write(f"Products Count: {products_count}\n")
        
        # Write subcategories if available
        if subcategories:
            self.file.write(f"Subcategories:\n")
            for subcat in subcategories:
                if isinstance(subcat, dict):
                    subcat_name = subcat.get('name', 'Unknown')
                    subcat_url = subcat.get('url', 'N/A')
                    self.file.write(f"  - {subcat_name} (URL: {subcat_url})\n")
                else:
                    self.file.write(f"  - {subcat}\n")
        
        self.file.write("-" * 40 + "\n\n")
        
        self.categories.append(item)
        return item


class LuluRayyanProductJsonWriterPipeline:
    """
    Pipeline to write LuluRayyan product items to JSON file.
    """
    
    def __init__(self):
        self.file = None
        self.products = []
    
    def open_spider(self, spider):
        """Open JSON file when spider starts."""
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        self.file = open('data/lulurayyan_products.json', 'w', encoding='utf-8')
        self.file.write('[\n')
        self.first_item = True
    
    def close_spider(self, spider):
        """Close JSON file when spider finishes."""
        if self.file:
            self.file.write('\n]')
            self.file.close()
            logger.info(f"Saved {len(self.products)} LuluRayyan products to JSON file")
    
    def process_item(self, item, spider):
        """Write product item to JSON file."""
        # Only process LuluRayyan product items
        if not hasattr(item, 'fields') or 'name' not in item.fields:
            return item
            
        if not self.first_item:
            self.file.write(',\n')
        
        # Convert item to dictionary using ItemAdapter
        item_dict = ItemAdapter(item).asdict()
        json.dump(item_dict, self.file, indent=2, ensure_ascii=False)
        self.first_item = False
        self.products.append(item)
        
        return item


class LuluRayyanProductTextWriterPipeline:
    """
    Pipeline to write LuluRayyan product items to human-readable text file.
    """
    
    def __init__(self):
        self.file = None
        self.products = []
        self.current_category = None
        self.current_subcategory = None
    
    def open_spider(self, spider):
        """Open text file when spider starts."""
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        self.file = open('data/lulurayyan_products.txt', 'w', encoding='utf-8')
        self.file.write("LuluRayyan Group Products\n")
        self.file.write("=" * 50 + "\n\n")
        self.file.write(f"Scraped on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.file.write(f"Source: https://lulurayyangroup.com/\n\n")
    
    def close_spider(self, spider):
        """Close text file when spider finishes."""
        if self.file:
            # Write summary
            self.file.write(f"\n" + "=" * 50 + "\n")
            self.file.write(f"Total Products Extracted: {len(self.products)}\n")
            self.file.write(f"Scraping completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.file.close()
            logger.info(f"Saved {len(self.products)} LuluRayyan products to text file")
    
    def process_item(self, item, spider):
        """Write product item to text file."""
        # Only process LuluRayyan product items
        if not hasattr(item, 'fields') or 'name' not in item.fields:
            return item
            
        category = item.get('category', 'Unknown')
        subcategory = item.get('subcategory', 'Unknown')
        
        # Write category/subcategory header if changed
        if self.current_category != category or self.current_subcategory != subcategory:
            self.file.write(f"\n{'='*60}\n")
            self.file.write(f"Category: {category}\n")
            self.file.write(f"Sub-category: {subcategory}\n")
            self.file.write(f"{'='*60}\n\n")
            self.current_category = category
            self.current_subcategory = subcategory
        
        # Write product details in clean format
        product_name = item.get('name', 'N/A')
        sku = item.get('sku', 'N/A')
        price = item.get('price', 'N/A')
        brand = item.get('brand', 'N/A')
        url = item.get('url', 'N/A')
        image_url = item.get('image_url', 'N/A')
        description = item.get('description', 'N/A')
        stock_status = item.get('stock_status', 'N/A')
        
        self.file.write(f"Product Name: {product_name}\n")
        self.file.write(f"SKU: {sku}\n")
        self.file.write(f"Brand: {brand}\n")
        self.file.write(f"Price: {price}\n")
        self.file.write(f"Description: {description}\n")
        self.file.write(f"Stock Status: {stock_status}\n")
        self.file.write(f"Product URL: {url}\n")
        self.file.write(f"Image URL: {image_url}\n")
        
        self.file.write("-" * 40 + "\n\n")
        
        self.products.append(item)
        return item
