# -*- coding: utf-8 -*-

import scrapy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
import logging
import time
import json
import os
import re

logger = logging.getLogger(__name__)

class LuluRayyanCategoryItem(scrapy.Item):
    """Item to store category information"""
    category_name = scrapy.Field()
    category_url = scrapy.Field()
    category_id = scrapy.Field()
    subcategories = scrapy.Field()
    products_count = scrapy.Field()
    description = scrapy.Field()
    image_url = scrapy.Field()
    scraped_at = scrapy.Field()

class LuluRayyanProductCategoriesSpider(scrapy.Spider):
    """
    Spider specifically for extracting product categories by clicking on products
    and looking for 'Product categories' sections
    """
    
    name = 'lulurayyan_product_categories'
    allowed_domains = ['lulurayyangroup.com']
    start_urls = ['https://lulurayyangroup.com/']
    
    custom_settings = {
        'DOWNLOAD_DELAY': 3,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'ROBOTSTXT_OBEY': False,
        'CLOSESPIDER_TIMEOUT': 0,
        'DOWNLOAD_TIMEOUT': 30,
        'ITEM_PIPELINES': {
            'lulu_pipeline.pipelines.LuluRayyanCategoryJsonWriterPipeline': 300,
        }
    }
    
    def __init__(self, *args, **kwargs):
        super(LuluRayyanProductCategoriesSpider, self).__init__(*args, **kwargs)
        self.product_categories_found = []
        self.products_data = []
        self.driver = None
        self.output_dir = 'data'
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Allow filtering by specific category
        self.category_filter = kwargs.get('category_filter', None)
        if self.category_filter:
            print(f"🎯 FILTERING: Only processing category: {self.category_filter}")
            logger.info(f"Category filter applied: {self.category_filter}")
    
    def start_requests(self):
        """Initial request to the homepage"""
        yield scrapy.Request(
            url=self.start_urls[0],
            callback=self.parse_homepage,
            dont_filter=True
        )
    
    def parse_homepage(self, response):
        """Parse homepage to find products and extract their categories"""
        print("\n" + "="*60)
        print("🚀 STARTING COMPLETE DATA EXTRACTION PIPELINE")
        print("="*60)
        logger.info("Starting product category extraction from homepage")
        
        # Set up Chrome options
        chrome_options = self.get_chrome_options()
        
        try:
            # Initialize Chrome driver
            print("📱 Initializing Chrome driver...")
            logger.info("Initializing Chrome driver...")
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Chrome driver initialized successfully")
            print("✅ Chrome driver initialized successfully")
            
            # Navigate to homepage
            print("🌐 Navigating to homepage...")
            self.driver.get(response.url)
            time.sleep(3)
            print(f"✅ Loaded homepage: {response.url}")
            
            # Extract product categories by clicking on products
            print("\n📋 STEP 1: Extracting product categories from individual products...")
            print("-" * 50)
            logger.info("Extracting product categories from individual products...")
            product_categories = self.extract_product_categories_from_products(self.driver)
            print(f"✅ STEP 1 COMPLETED: Found {len(product_categories)} main categories")
            
            # Extract subcategories for each category found
            print("\n🔍 STEP 2: Extracting subcategories from main categories...")
            print("-" * 50)
            logger.info("Extracting subcategories from main categories...")
            enhanced_categories = self.extract_subcategories_from_categories(self.driver, product_categories)
            print(f"✅ STEP 2 COMPLETED: Enhanced {len(enhanced_categories)} categories with subcategories")
            
            # Extract products from each subcategory
            print("\n🛍️ STEP 3: Extracting products from subcategories...")
            print("-" * 50)
            logger.info("Extracting products from subcategories...")
            all_products = self.extract_products_from_subcategories(self.driver, enhanced_categories)
            self.products_data = all_products  # Store for later use
            print(f"✅ STEP 3 COMPLETED: Extracted {len(all_products)} products")
            
            # Process each enhanced category with subcategories and products
            print(f"\n📝 Processing and saving data...")
            print("-" * 50)
            
            # Apply category filter if specified
            if self.category_filter:
                enhanced_categories = [cat for cat in enhanced_categories if cat.get('name', '').lower() == self.category_filter.lower()]
                print(f"🎯 Filtered to {len(enhanced_categories)} categories matching '{self.category_filter}'")
                if not enhanced_categories:
                    print(f"❌ No categories found matching '{self.category_filter}'")
                    return
            
            for i, cat_data in enumerate(enhanced_categories):
                category_item = LuluRayyanCategoryItem()
                category_item['category_name'] = cat_data.get('name')
                category_item['category_url'] = cat_data.get('url')
                category_item['category_id'] = cat_data.get('id')
                category_item['description'] = f"Found via product: {cat_data.get('source_product', 'Unknown')}"
                category_item['image_url'] = ''
                category_item['subcategories'] = cat_data.get('subcategories', [])
                
                # Count products for this category
                category_products = [p for p in all_products if p.get('category') == cat_data.get('name')]
                category_item['products_count'] = len(category_products)
                
                category_item['scraped_at'] = datetime.now().isoformat()
                
                self.product_categories_found.append(category_item)
                yield category_item
                
                subcat_count = len(cat_data.get('subcategories', []))
                print(f"  📋 Category {i+1}/{len(enhanced_categories)}: {cat_data.get('name')[:50]}... ({subcat_count} subcategories, {len(category_products)} products)")
                logger.info(f"Found product category: {cat_data.get('name')} from product: {cat_data.get('source_product')} with {subcat_count} subcategories and {len(category_products)} products")
            
            print(f"\n🎉 EXTRACTION PIPELINE COMPLETED SUCCESSFULLY!")
            print(f"📊 Final Summary:")
            print(f"   • Categories: {len(self.product_categories_found)}")
            
            # Calculate actual subcategories (excluding first duplicates)
            total_actual_subcategories = 0
            for cat in enhanced_categories:
                subcategories = cat.get('subcategories', [])
                actual_count = len(subcategories[1:]) if len(subcategories) > 1 else 0
                total_actual_subcategories += actual_count
            
            print(f"   • Actual Subcategories: {total_actual_subcategories} (excluding duplicates)")
            print(f"   • Products: {len(all_products)}")
            
            logger.info(f"Total product categories found: {len(self.product_categories_found)}")
            logger.info(f"Total products extracted: {len(all_products)}")
        
        except Exception as e:
            logger.error(f"Error in homepage parsing: {e}")
        
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def get_chrome_options(self):
        """Configure Chrome options for headless browsing"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--disable-javascript')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
                "media_stream": 2,
            }
        })
        
        return chrome_options
    
    def extract_product_categories_from_products(self, driver):
        """Extract product categories by clicking on products and looking for 'Product categories' section"""
        product_categories = []
        
        try:
            print(f"🔍 Searching for product links on homepage...")
            
            # Find product links on the page
            product_selectors = [
                '.product a[href*="product"]',
                '.woocommerce-product a[href*="product"]',
                '.product-item a[href*="product"]',
                'a[href*="product"]'
            ]
            
            products_found = []
            for selector in product_selectors:
                try:
                    products = driver.find_elements(By.CSS_SELECTOR, selector)
                    if products:
                        products_found = products
                        print(f"✅ Found {len(products)} products using selector: {selector}")
                        break
                except:
                    continue
            
            logger.info(f"Found {len(products_found)} products to check for categories")
            
            # Limit to first 10 products to get more comprehensive coverage
            products_to_check = products_found[:10]
            print(f"📊 Will process {len(products_to_check)} products for category extraction")
            
            for i, product_link in enumerate(products_to_check):
                try:
                    product_url = product_link.get_attribute('href')
                    product_name = product_link.text.strip() or f"Product {i+1}"
                    
                    if not product_url or 'product' not in product_url:
                        continue
                    
                    logger.info(f"Checking product {i+1}: {product_name}")
                    
                    # Open product page in new tab
                    driver.execute_script("window.open('');")
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.get(product_url)
                    time.sleep(3)
                    
                    # Look for "Product categories" section
                    categories = self.extract_product_categories_section(driver)
                    
                    if categories:
                        for cat in categories:
                            cat['source_product'] = product_name
                            cat['source_product_url'] = product_url
                            product_categories.append(cat)
                        
                        logger.info(f"Found {len(categories)} categories for product: {product_name}")
                    else:
                        logger.info(f"No categories found for product: {product_name}")
                    
                    # Close tab and switch back
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    
                except Exception as e:
                    logger.error(f"Error checking product {i+1}: {e}")
                    # Make sure we're back on the main tab
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    continue
            
            # Remove duplicates based on category name and URL
            unique_categories = []
            seen_categories = set()
            for cat in product_categories:
                category_key = (cat.get('name', ''), cat.get('url', ''))
                if category_key not in seen_categories:
                    seen_categories.add(category_key)
                    unique_categories.append(cat)
            
            logger.info(f"Extracted {len(unique_categories)} unique product categories from {len(products_to_check)} products")
            return unique_categories
        
        except Exception as e:
            logger.error(f"Error extracting product categories from products: {e}")
            return []
    
    def extract_subcategories_from_categories(self, driver, categories):
        """Extract subcategories by clicking on main categories"""
        enhanced_categories = []
        
        try:
            logger.info("Extracting subcategories from main categories...")
            
            for i, category in enumerate(categories):
                try:
                    category_url = category.get('url')
                    category_name = category.get('name', f'Category {i+1}')
                    
                    if not category_url:
                        enhanced_categories.append(category)
                        continue
                    
                    logger.info(f"Checking category {i+1}: {category_name}")
                    
                    # Open category page in new tab
                    driver.execute_script("window.open('');")
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.get(category_url)
                    time.sleep(3)
                    
                    # Extract subcategories from the category page
                    subcategories = self.extract_subcategories_from_page(driver)
                    
                    # Update category with subcategories
                    category['subcategories'] = subcategories
                    category['subcategories_count'] = len(subcategories)
                    
                    enhanced_categories.append(category)
                    
                    logger.info(f"Found {len(subcategories)} subcategories for category: {category_name}")
                    
                    # Close tab and switch back
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    
                except Exception as e:
                    logger.error(f"Error checking category {i+1}: {e}")
                    # Make sure we're back on the main tab
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    
                    # Add category without subcategories
                    category['subcategories'] = []
                    category['subcategories_count'] = 0
                    enhanced_categories.append(category)
                    continue
                    
            return enhanced_categories
            
        except Exception as e:
            logger.error(f"Error extracting subcategories from categories: {e}")
            return categories

    def extract_subcategories_from_page(self, driver):
        """Extract subcategories from a category page"""
        subcategories = []
        
        try:
            # Common selectors for subcategories
            subcategory_selectors = [
                '.product-subcategories a',
                '.subcategories a',
                '.category-children a',
                '.sub-categories a',
                '.woocommerce-product-category a',
                '.product-categories a',
                '.category-list a',
                '.categories-widget a',
                'a[href*="product-category"]',
                'a[href*="category"]'
            ]
            
            for selector in subcategory_selectors:
                try:
                    if selector.startswith('a['):
                        # Direct link selector
                        subcat_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    else:
                        # Container + link selector
                        subcat_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if subcat_elements:
                        for element in subcat_elements:
                            try:
                                name = element.text.strip()
                                url = element.get_attribute('href')
                                
                                if name and url and ('product-category' in url or 'category' in url):
                                    category_id = self.extract_category_id_from_url(url)
                                    subcategories.append({
                                        'name': name,
                                        'url': url,
                                        'id': category_id,
                                        'source': 'subcategory_extraction'
                                    })
                            except Exception:
                                continue
                    
                    if subcategories:  # If found subcategories, break
                        break
                        
                except Exception:
                    continue
                
            # Alternative: Look for any text containing "Subcategories" or similar
            if not subcategories:
                try:
                    # Look for subcategory sections
                    subcat_section_selectors = [
                        '//h2[contains(text(), "Subcategories")]/following-sibling::*',
                        '//h3[contains(text(), "Subcategories")]/following-sibling::*',
                        '//h4[contains(text(), "Subcategories")]/following-sibling::*',
                        '//strong[contains(text(), "Subcategories")]/following-sibling::*',
                        '.subcategories',
                        '.sub-categories'
                    ]
                    
                    for selector in subcat_section_selectors:
                        try:
                            if selector.startswith('//'):
                                elements = driver.find_elements(By.XPATH, selector)
                            else:
                                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            
                            if elements:
                                for element in elements:
                                    links = element.find_elements(By.TAG_NAME, 'a')
                                    for link in links:
                                        try:
                                            name = link.text.strip()
                                            url = link.get_attribute('href')
                                            
                                            if name and url and ('product-category' in url or 'category' in url):
                                                category_id = self.extract_category_id_from_url(url)
                                                subcategories.append({
                                                    'name': name,
                                                    'url': url,
                                                    'id': category_id,
                                                    'source': 'subcategory_section'
                                                })
                                        except Exception:
                                            continue
                                            
                                if subcategories:
                                    break
                                    
                        except Exception:
                            continue
        
                except Exception:
                    pass
            
            return subcategories
            
        except Exception as e:
            logger.error(f"Error extracting subcategories from page: {e}")
            return []

    def extract_products_from_subcategories(self, driver, enhanced_categories):
        """Extract products from each subcategory"""
        products_data = []
        
        try:
            print(f"🛍️  Starting product extraction from subcategories...")
            logger.info("Starting product extraction from subcategories...")
            
            # Calculate total items to process (subcategories + main categories without subcategories)
            total_items = 0
            for cat in enhanced_categories:
                subcategories = cat.get('subcategories', [])
                if len(subcategories) > 1:
                    # Category has subcategories - count actual subcategories (excluding first duplicate)
                    total_items += len(subcategories[1:])
                else:
                    # Category has NO subcategories - count as 1 (main category)
                    total_items += 1
            
            print(f"📊 Total items to process: {total_items} (subcategories + main categories without subcategories)")
            
            processed_items = 0
            
            for category in enhanced_categories:
                category_name = category.get('name', 'Unknown Category')
                subcategories = category.get('subcategories', [])
                
                print(f"  📁 Processing category: {category_name} ({len(subcategories)} subcategories)")
                logger.info(f"Processing category: {category_name} with {len(subcategories)} subcategories")
                
                # Check if category has subcategories
                if len(subcategories) > 1:
                    # Category has subcategories - skip first duplicate and process actual subcategories
                    actual_subcategories = subcategories[1:]
                    print(f"    📝 Found {len(actual_subcategories)} actual subcategories (skipping first duplicate)")
                    
                    for subcategory in actual_subcategories:
                        try:
                            subcategory_name = subcategory.get('name', 'Unknown Subcategory')
                            subcategory_url = subcategory.get('url', '')
                            
                            if not subcategory_url:
                                continue
                            
                            processed_items += 1
                            print(f"    🛍️  Processing subcategory {processed_items}/{total_items}: {subcategory_name[:50]}...")
                            logger.info(f"Extracting products from subcategory: {subcategory_name}")
                            
                            # Open subcategory page in new tab
                            driver.execute_script("window.open('');")
                            driver.switch_to.window(driver.window_handles[-1])
                            driver.get(subcategory_url)
                            time.sleep(2)
                            
                            print(f"      🔍 Checking if page has products...")
                            # First check if there are any products on the page
                            has_products = self.check_if_page_has_products(driver)
                            
                            if has_products:
                                # Extract products from this subcategory page
                                products = self.extract_products_from_page(driver, category_name, subcategory_name)
                                
                                if products:
                                    products_data.extend(products)
                                    print(f"      ✅ Found {len(products)} products")
                                    logger.info(f"Found {len(products)} products in subcategory: {subcategory_name}")
                                else:
                                    print(f"      ⚠️  No products extracted (extraction failed)")
                                    # Add empty product entry to show extraction failed
                                    empty_product = {
                                        'name': f"Extraction failed for {subcategory_name}",
                                        'category': category_name,
                                        'subcategory': subcategory_name,
                                        'url': subcategory_url,
                                        'image_url': '',
                                        'price': '',
                                        'sku': '',
                                        'description': f"Product extraction failed for this subcategory",
                                        'stock_status': 'Extraction failed',
                                        'extracted_at': datetime.now().isoformat()
                                    }
                                    products_data.append(empty_product)
                            else:
                                print(f"      ⚠️  No products found on page (0 products)")
                                # Add empty product entry to show 0 products
                                empty_product = {
                                    'name': f"No products in {subcategory_name}",
                                    'category': category_name,
                                    'subcategory': subcategory_name,
                                    'url': subcategory_url,
                                    'image_url': '',
                                    'price': '',
                                    'sku': '',
                                    'description': f"No products available in this subcategory",
                                    'stock_status': 'No products',
                                    'extracted_at': datetime.now().isoformat()
                                }
                                products_data.append(empty_product)
                            
                            # Close tab and switch back
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            
                        except Exception as e:
                            print(f"      ❌ Error: {str(e)[:50]}...")
                            logger.error(f"Error extracting products from subcategory {subcategory.get('name')}: {e}")
                            # Try to return to main tab
                            try:
                                if len(driver.window_handles) > 1:
                                    driver.close()
                                    driver.switch_to.window(driver.window_handles[0])
                            except:
                                pass
                    continue
        
                else:
                    # Category has NO subcategories - extract products directly from main category page
                    processed_items += 1
                    print(f"    📝 No subcategories found - extracting products directly from main category: {category_name} ({processed_items}/{total_items})")
                    
                    try:
                        category_url = category.get('url', '')
                        if category_url:
                            # Open main category page in new tab
                            driver.execute_script("window.open('');")
                            driver.switch_to.window(driver.window_handles[-1])
                            driver.get(category_url)
                            time.sleep(2)
                            
                            print(f"      🔍 Checking if main category page has products...")
                            # Check if the main category page has products
                            has_products = self.check_if_page_has_products(driver)
                            
                            if has_products:
                                # Extract products from main category page
                                products = self.extract_products_from_page(driver, category_name, category_name)
                                
                                if products:
                                    products_data.extend(products)
                                    print(f"      ✅ Found {len(products)} products in main category")
                                    logger.info(f"Found {len(products)} products in main category: {category_name}")
                                else:
                                    print(f"      ⚠️  No products extracted from main category (extraction failed)")
                                    # Add empty product entry to show extraction failed
                                    empty_product = {
                                        'name': f"Extraction failed for main category {category_name}",
                                        'category': category_name,
                                        'subcategory': category_name,
                                        'url': category_url,
                                        'image_url': '',
                                        'price': '',
                                        'sku': '',
                                        'description': f"Product extraction failed for main category",
                                        'stock_status': 'Extraction failed',
                                        'extracted_at': datetime.now().isoformat()
                                    }
                                    products_data.append(empty_product)
                            else:
                                print(f"      ⚠️  No products found on main category page (0 products)")
                                # Add empty product entry to show 0 products
                                empty_product = {
                                    'name': f"No products in main category {category_name}",
                                    'category': category_name,
                                    'subcategory': category_name,
                                    'url': category_url,
                                    'image_url': '',
                                    'price': '',
                                    'sku': '',
                                    'description': f"No products available in main category",
                                    'stock_status': 'No products',
                                    'extracted_at': datetime.now().isoformat()
                                }
                                products_data.append(empty_product)
                            
                            # Close tab and switch back
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                        else:
                            print(f"      ❌ No URL available for main category")
        
                    except Exception as e:
                        print(f"      ❌ Error extracting from main category: {str(e)[:50]}...")
                        logger.error(f"Error extracting products from main category {category_name}: {e}")
                        # Try to return to main tab
                        try:
                            if len(driver.window_handles) > 1:
                                driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                        except:
                            pass
            
            print(f"✅ Product extraction completed: {len(products_data)} total products")
            logger.info(f"Total products extracted: {len(products_data)}")
            return products_data
            
        except Exception as e:
            logger.error(f"Error in product extraction from subcategories: {e}")
            return []

    def extract_products_from_page(self, driver, category_name, subcategory_name):
        """Extract product details from a subcategory page"""
        products = []
        
        try:
            logger.info(f"Extracting products from: {driver.current_url}")
            
            # Common product selectors
            product_selectors = [
                '.product',
                '.woocommerce-product',
                '.product-item',
                '.product-card',
                '.product-box',
                '[class*="product"]'
            ]
            
            products_found = []
            for selector in product_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        products_found = elements
                        break
                except Exception:
                    continue
            
            logger.info(f"Found {len(products_found)} product elements on page")
            
            # Extract details from each product
            print(f"      🔍 Extracting details from {min(len(products_found), 20)} products...")
            for i, product_element in enumerate(products_found[:20]):  # Limit to first 20 products
                try:
                    product_data = self.extract_single_product_details(driver, product_element, category_name, subcategory_name)
                    if product_data:
                        products.append(product_data)
                        if (i + 1) % 5 == 0:  # Show progress every 5 products
                            print(f"        📊 Progress: {i+1}/{min(len(products_found), 20)} products processed")
                        
                except Exception as e:
                    logger.error(f"Error extracting product {i+1}: {e}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Error extracting products from page: {e}")
            return []

    def extract_single_product_details(self, driver, product_element, category_name, subcategory_name):
        """Extract detailed information from a single product element"""
        try:
            product_data = {
                'category': category_name,
                'subcategory': subcategory_name,
                'extracted_at': datetime.now().isoformat()
            }
            
            # Extract product name
            try:
                name_selectors = [
                    '.product-title',
                    '.woocommerce-loop-product__title',
                    '.product-name',
                    'h2 a',
                    'h3 a',
                    'h4 a',
                    '.title a',
                    'a[title]'
                ]
                
                for selector in name_selectors:
                    try:
                        element = product_element.find_element(By.CSS_SELECTOR, selector)
                        product_data['name'] = element.text.strip()
                        if not product_data['name'] and element.get_attribute('title'):
                            product_data['name'] = element.get_attribute('title').strip()
                        if product_data['name']:
                            break
                    except Exception:
                        continue
                            
                if not product_data.get('name'):
                    product_data['name'] = f"Product {len(product_data) + 1}"
                    
            except Exception as e:
                logger.error(f"Error extracting product name: {e}")
                product_data['name'] = "Unknown Product"
            
            # Extract product URL
            try:
                link_selectors = [
                    'a[href*="product"]',
                    'a[href*="item"]',
                    'a'
                ]
                
                for selector in link_selectors:
                    try:
                        element = product_element.find_element(By.CSS_SELECTOR, selector)
                        href = element.get_attribute('href')
                        if href and ('product' in href or 'item' in href):
                            product_data['url'] = href
                            break
                    except Exception:
                        continue
        
            except Exception as e:
                logger.error(f"Error extracting product URL: {e}")
                product_data['url'] = ""
            
            # Extract product image
            try:
                img_selectors = [
                    'img[src*="product"]',
                    'img[src*="item"]',
                    'img'
                ]
                
                for selector in img_selectors:
                    try:
                        element = product_element.find_element(By.CSS_SELECTOR, selector)
                        src = element.get_attribute('src')
                        if src:
                            product_data['image_url'] = src
                            break
                    except Exception:
                        continue
                        
            except Exception as e:
                logger.error(f"Error extracting product image: {e}")
                product_data['image_url'] = ""
            
            # Extract product price
            try:
                price_selectors = [
                    '.price',
                    '.product-price',
                    '.woocommerce-Price-amount',
                    '[class*="price"]',
                    '.amount'
                ]
                
                for selector in price_selectors:
                    try:
                        element = product_element.find_element(By.CSS_SELECTOR, selector)
                        price_text = element.text.strip()
                        if price_text and any(char.isdigit() for char in price_text):
                            product_data['price'] = price_text
                            break
                    except Exception:
                        continue
                        
            except Exception as e:
                logger.error(f"Error extracting product price: {e}")
                product_data['price'] = ""
            
            # Extract product SKU/ID
            try:
                sku_selectors = [
                    '.sku',
                    '.product-sku',
                    '[data-sku]',
                    '[data-product-id]'
                ]
                
                for selector in sku_selectors:
                    try:
                        element = product_element.find_element(By.CSS_SELECTOR, selector)
                        sku = element.text.strip() or element.get_attribute('data-sku') or element.get_attribute('data-product-id')
                        if sku:
                            product_data['sku'] = sku
                            break
                    except Exception:
                            continue
                    
            except Exception as e:
                logger.error(f"Error extracting product SKU: {e}")
                product_data['sku'] = ""
            
            # Extract product description/short description - ENHANCED VERSION WITH PRODUCT PAGE VISIT
            try:
                print(f"        🔍 Extracting enhanced description for: {product_data.get('name', 'Unknown Product')}")
                
                # First try to get description from the product listing page
                best_description = self._extract_description_from_listing(product_element)
                
                # Always try to visit the individual product page for better description
                print(f"        🌐 Visiting product page for better description...")
                product_url = product_data.get('url', '')
                if product_url:
                    page_description = self._extract_description_from_product_page(driver, product_url)
                    if page_description and len(page_description) > len(best_description or ""):
                        best_description = page_description
                        print(f"        ✅ Found better description from product page ({len(best_description)} chars)")
                    else:
                        print(f"        ⚠️  No better description found on product page")
                else:
                    print(f"        ❌ No product URL available for page visit")
                
                # Use the best description we found
                if best_description:
                    # Clean up the description
                    cleaned_desc = best_description.replace('\n', ' ').replace('\r', ' ').strip()
                    cleaned_desc = ' '.join(cleaned_desc.split())  # Remove extra spaces
                    
                    # Truncate if too long but keep more content
                    if len(cleaned_desc) > 400:
                        product_data['description'] = cleaned_desc[:400] + "..."
                    else:
                        product_data['description'] = cleaned_desc
                    
                    print(f"        ✅ Final description: {len(product_data['description'])} chars")
                    logger.info(f"Description extracted for {product_data.get('name', 'Unknown')}: {len(product_data['description'])} chars")
                else:
                    # Fallback to basic description extraction
                    basic_desc = self._extract_basic_description(product_element)
                    if basic_desc:
                        product_data['description'] = basic_desc
                        print(f"        ⚠️  Using basic description ({len(basic_desc)} chars)")
                    else:
                        product_data['description'] = ""
                        print(f"        ❌ No description found")
                
                # Extract brand and SKU from product page if we have a URL
                product_url = product_data.get('url', '')
                if product_url:
                    print(f"        🏷️  Extracting brand and SKU from product page...")
                    # Open product page to extract brand and SKU
                    try:
                        current_window = driver.current_window_handle
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[-1])
                        driver.get(product_url)
                        time.sleep(2)
                        
                        # Extract brand and SKU
                        brand = self._extract_brand_from_page(driver)
                        sku = self._extract_sku_from_page(driver)
                        
                        if brand:
                            product_data['brand'] = brand
                            print(f"        ✅ Brand extracted: {brand}")
                        if sku:
                            product_data['sku'] = sku
                            print(f"        ✅ SKU extracted: {sku}")
                        
                        # Close tab and switch back
                        driver.close()
                        driver.switch_to.window(current_window)
                        
                    except Exception as e:
                        logger.error(f"Error extracting brand/SKU: {e}")
                        # Try to return to original tab
                        try:
                            if len(driver.window_handles) > 1:
                                driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                        except:
                            pass
                        
            except Exception as e:
                logger.error(f"Error extracting product description: {e}")
                product_data['description'] = ""
            
            # Extract product availability/stock status
            try:
                stock_selectors = [
                    '.stock',
                    '.availability',
                    '.in-stock',
                    '.out-of-stock',
                    '[class*="stock"]'
                ]
                
                for selector in stock_selectors:
                    try:
                        element = product_element.find_element(By.CSS_SELECTOR, selector)
                        stock_text = element.text.strip()
                        if stock_text:
                            product_data['stock_status'] = stock_text
                            break
                    except Exception:
                        continue
        
            except Exception as e:
                logger.error(f"Error extracting stock status: {e}")
                product_data['stock_status'] = ""
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error in single product extraction: {e}")
            return None

    def check_if_page_has_products(self, driver):
        """Check if the page has products or shows 'No products found' message"""
        try:
            # Look for "No products found" messages
            no_products_selectors = [
                '//*[contains(text(), "No products were found")]',
                '//*[contains(text(), "No products found")]',
                '//*[contains(text(), "No products available")]',
                '//*[contains(text(), "No items found")]',
                '//*[contains(text(), "No results found")]',
                '.no-products',
                '.no-results',
                '.empty-category',
                '.woocommerce-info',
                '.woocommerce-message'
            ]
            
            for selector in no_products_selectors:
                try:
                    if selector.startswith('//'):
                        # XPath selector
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS selector
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        for element in elements:
                            text = element.text.strip().lower()
                            if any(phrase in text for phrase in ['no products', 'no items', 'no results', 'no matching']):
                                print(f"        🔍 Detected 'No products' message: {element.text[:100]}...")
                                return False
                except Exception:
                    continue
            
            # Look for actual product elements
            product_selectors = [
                '.product',
                '.woocommerce-product',
                '.product-item',
                '.product-card',
                '.product-box',
                '[class*="product"]',
                '.woocommerce ul.products li',
                '.products-grid li',
                '.product-list li'
            ]
            
            for selector in product_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Check if these are actual product elements (not empty containers)
                        valid_products = 0
                        for element in elements:
                            # Look for product name or link within the element
                            try:
                                name_element = element.find_element(By.CSS_SELECTOR, 'a, .product-title, .product-name, h2, h3, h4')
                                if name_element and name_element.text.strip():
                                    valid_products += 1
                            except Exception:
                                continue
            
                        if valid_products > 0:
                            print(f"        🔍 Found {valid_products} valid product elements")
                            return True
                        else:
                            print(f"        🔍 Found {len(elements)} product containers but no valid products")
                            return False
                except Exception:
                    continue
            
            # If we can't find either "no products" message or valid products, assume no products
            print(f"        🔍 Could not determine product status, assuming no products")
            return False
        
        except Exception as e:
            logger.error(f"Error checking if page has products: {e}")
            print(f"        🔍 Error checking products, assuming no products")
            return False
    
    def extract_product_categories_section(self, driver):
        """Extract categories from the 'Product categories' section on a product page"""
        categories = []
        
        try:
            # Look for "Product categories" section
            category_section_selectors = [
                '//h2[contains(text(), "Product categories")]/following-sibling::*',
                '//h3[contains(text(), "Product categories")]/following-sibling::*',
                '//h4[contains(text(), "Product categories")]/following-sibling::*',
                '//strong[contains(text(), "Product categories")]/following-sibling::*',
                '//span[contains(text(), "Product categories")]/following-sibling::*',
                '.product-categories',
                '.woocommerce-product-categories',
                '[class*="category"]',
                '[class*="categories"]'
            ]
            
            for selector in category_section_selectors:
                try:
                    if selector.startswith('//'):
                        # XPath selector
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS selector
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        for element in elements:
                            # Look for links within this section
                            links = element.find_elements(By.TAG_NAME, 'a')
                            
                            for link in links:
                                try:
                                    name = link.text.strip()
                                    url = link.get_attribute('href')
                                    
                                    if name and url and ('product-category' in url or 'category' in url):
                                        category_id = self.extract_category_id_from_url(url)
                                        categories.append({
                                            'name': name,
                                            'url': url,
                                            'id': category_id,
                                            'source': 'product_page_categories'
                                        })
                                except Exception:
                                    continue
                        
                        if categories:  # If we found categories, break
                            break
                            
                except Exception:
                    continue
            
            # Alternative: Look for any text containing "Product categories" and extract nearby links
            if not categories:
                try:
                    # Find text containing "Product categories"
                    page_text = driver.find_element(By.TAG_NAME, 'body').text
                    if 'Product categories' in page_text:
                        # Look for all category links on the page
                        category_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'product-category') or contains(@href, 'category')]")
                        
                        for link in category_links:
                            try:
                                name = link.text.strip()
                                url = link.get_attribute('href')
                                
                                if name and url:
                                    category_id = self.extract_category_id_from_url(url)
                                    categories.append({
                                        'name': name,
                                        'url': url,
                                        'id': category_id,
                                        'source': 'product_page_categories_alternative'
                                    })
                            except Exception:
                                continue
                except Exception:
                    pass
            
            return categories
        
        except Exception as e:
            logger.error(f"Error extracting product categories section: {e}")
            return []
    
    def extract_category_id_from_url(self, url):
        """Extract category ID/slug from URL"""
        try:
            # Extract category slug from URL
            if 'product-category/' in url:
                # Remove trailing slash and extract the last part
                slug = url.rstrip('/').split('product-category/')[-1]
                # Remove any additional path segments
                slug = slug.split('/')[0]
                return slug
            return None
        except Exception:
            return None
    
    def _is_duplicate_content(self, description, product_name):
        """Check if description is just duplicate of product name or other basic info"""
        if not description or not product_name:
            return False
        
        # Convert to lowercase for comparison
        desc_lower = description.lower()
        name_lower = product_name.lower()
        
        # Check if description is mostly the same as product name
        if desc_lower == name_lower:
            return True
        
        # Check if description contains mostly the same words as product name
        name_words = set(name_lower.split())
        desc_words = set(desc_lower.split())
        
        # If more than 70% of words are the same, consider it duplicate
        if len(name_words) > 0 and len(desc_words.intersection(name_words)) / len(name_words) > 0.7:
            return True
        
        # Check for common duplicate patterns
        duplicate_patterns = [
            'brand:', 'price:', 'sku:', 'model:', 'part number:',
            'ر.ق', 'qar', 'dhs', 'aed', 'sar', 'kwd', 'bd'
        ]
        
        for pattern in duplicate_patterns:
            if pattern in desc_lower and len(desc_lower) < 100:
                return True
        
        return False
    
    def _extract_basic_description(self, product_element):
        """Fallback method to extract basic description when enhanced method fails"""
        try:
            # Try to get any meaningful text content
            basic_selectors = [
                'p',
                'div',
                'span',
                '.product-info',
                '.product-details'
            ]
            
            for selector in basic_selectors:
                try:
                    elements = product_element.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 30 and len(text) < 200:
                            # Basic cleaning
                            cleaned = text.replace('\n', ' ').replace('\r', ' ').strip()
                            cleaned = ' '.join(cleaned.split())
                            return cleaned
                except Exception:
                    continue
            
            return None
            
        except Exception:
            return None
    
    def _extract_description_from_listing(self, product_element):
        """Extract description from product listing page"""
        try:
            # Comprehensive selectors for product descriptions on listing page
            desc_selectors = [
                '.product-description',
                '.product-excerpt', 
                '.short-description',
                '.description',
                '.product-summary',
                '.product-details',
                '.product-info',
                '.woocommerce-product-details__short-description',
                '.woocommerce-product-details__description',
                '.product-content',
                '.product-text',
                '.product-about',
                'p',
                'div[class*="description"]',
                'div[class*="summary"]',
                'div[class*="details"]',
                'div[class*="content"]',
                'div[class*="text"]',
                'span[class*="description"]',
                'span[class*="summary"]'
            ]
            
            best_description = ""
            best_length = 0
            
            for selector in desc_selectors:
                try:
                    elements = product_element.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        desc = element.text.strip()
                        if desc and len(desc) > 20:  # More meaningful description threshold
                            # Clean up the description
                            cleaned_desc = desc.replace('\n', ' ').replace('\r', ' ').strip()
                            cleaned_desc = ' '.join(cleaned_desc.split())  # Remove extra spaces
                            
                            # Check if this description is better (longer and more meaningful)
                            if len(cleaned_desc) > best_length and not self._is_duplicate_content(cleaned_desc, ""):
                                best_description = cleaned_desc
                                best_length = len(cleaned_desc)
                                
                except Exception:
                    continue
            
            return best_description
            
        except Exception as e:
            logger.error(f"Error extracting description from listing: {e}")
            return None
    
    def _extract_description_from_product_page(self, driver, product_url):
        """Extract description by visiting individual product page"""
        try:
            # Store current window handle
            current_window = driver.current_window_handle
            
            # Open product page in new tab
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            driver.get(product_url)
            time.sleep(3)  # Wait for page to load
            
            # Extract brand and SKU first
            brand = self._extract_brand_from_page(driver)
            sku = self._extract_sku_from_page(driver)
            
            # Update product data if we found brand/SKU
            if brand or sku:
                print(f"        🏷️  Found - Brand: {brand or 'N/A'}, SKU: {sku or 'N/A'}")
            
            # Target the specific WooCommerce product description structure
            # Based on the HTML: <div class="woocommerce-product-details__short-description"><ul><li>...</li></ul></div>
            page_desc_selectors = [
                # Priority 1: The exact WooCommerce structure
                '.woocommerce-product-details__short-description ul li',
                '.woocommerce-product-details__short-description',
                # Priority 2: Other WooCommerce description areas
                '.woocommerce-product-details__description',
                '.woocommerce-product-attributes',
                # Priority 3: General product description areas
                '.product-description',
                '.product-excerpt',
                '.short-description',
                '.description',
                '.product-summary',
                '.product-details',
                '.product-info',
                '.product-content',
                '.product-text',
                '.product-about',
                '.entry-content',
                '.product-long-description',
                # Priority 4: List elements
                'ul li',
                'ol li',
                '.features-list li',
                '.attributes-list li',
                # Priority 5: Generic selectors
                'div[class*="description"]',
                'div[class*="summary"]',
                'div[class*="details"]',
                'div[class*="content"]',
                'div[class*="text"]',
                'div[class*="features"]',
                'div[class*="attributes"]',
                'p',
                'span[class*="description"]',
                'span[class*="summary"]'
            ]
            
            best_description = ""
            best_length = 0
            list_items = []
            
            # First, try to get the specific WooCommerce description with list items
            try:
                # Look specifically for the WooCommerce description div
                desc_div = driver.find_element(By.CSS_SELECTOR, '.woocommerce-product-details__short-description')
                if desc_div:
                    # Get all list items
                    list_elements = desc_div.find_elements(By.CSS_SELECTOR, 'ul li')
                    if list_elements:
                        for li in list_elements:
                            item_text = li.text.strip()
                            if item_text and len(item_text) > 10:
                                list_items.append(item_text)
                        
                        if list_items:
                            # Combine list items into a comprehensive description
                            combined_desc = ' | '.join(list_items)
                            best_description = combined_desc
                            best_length = len(combined_desc)
                            print(f"        🎯 Found WooCommerce description with {len(list_items)} list items")
                            print(f"        📝 List items: {list_items}")
                            
            except Exception:
                print(f"        ⚠️  WooCommerce description not found, trying other selectors...")
            
            # If we didn't find the WooCommerce description, try other selectors
            if not best_description:
                for selector in page_desc_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            desc = element.text.strip()
                            if desc and len(desc) > 30:  # Higher threshold for product page
                                # Clean up the description
                                cleaned_desc = desc.replace('\n', ' ').replace('\r', ' ').strip()
                                cleaned_desc = ' '.join(cleaned_desc.split())
                                
                                # Check if this description is better and not duplicate
                                if len(cleaned_desc) > best_length and not self._is_duplicate_content(cleaned_desc, ""):
                                    best_description = cleaned_desc
                                    best_length = len(cleaned_desc)
                                    
                    except Exception:
                        continue
            
            # Close tab and switch back
            driver.close()
            driver.switch_to.window(current_window)
            
            return best_description
            
        except Exception as e:
            logger.error(f"Error extracting description from product page: {e}")
            # Try to return to original tab
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
            except:
                pass
            return None
    
    def _extract_brand_from_page(self, driver):
        """Extract brand information from product page"""
        try:
            brand_selectors = [
                '//*[contains(text(), "Brand:")]',
                '//*[contains(text(), "Brand")]',
                '.brand',
                '.product-brand',
                '.brand-name',
                '[class*="brand"]',
                'span:contains("Brand")',
                'div:contains("Brand")'
            ]
            
            for selector in brand_selectors:
                try:
                    if selector.startswith('//'):
                        # XPath selector
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS selector
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        text = element.text.strip()
                        if 'brand:' in text.lower():
                            # Extract brand name after "Brand:"
                            brand = text.split('Brand:', 1)[-1].strip()
                            if brand:
                                return brand
                        elif 'brand' in text.lower() and len(text) < 100:
                            # Try to extract brand from text
                            brand = text.replace('Brand', '').replace(':', '').strip()
                            if brand and len(brand) > 1:
                                return brand
                                
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting brand: {e}")
            return None
    
    def _extract_sku_from_page(self, driver):
        """Extract SKU information from product page"""
        try:
            sku_selectors = [
                '//*[contains(text(), "SKU:")]',
                '//*[contains(text(), "SKU")]',
                '.sku',
                '.product-sku',
                '.sku-number',
                '[class*="sku"]',
                'span:contains("SKU")',
                'div:contains("SKU")'
            ]
            
            for selector in sku_selectors:
                try:
                    if selector.startswith('//'):
                        # XPath selector
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS selector
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        text = element.text.strip()
                        if 'sku:' in text.lower():
                            # Extract SKU after "SKU:"
                            sku = text.split('SKU:', 1)[-1].strip()
                            if sku:
                                return sku
                        elif 'sku' in text.lower() and len(text) < 100:
                            # Try to extract SKU from text
                            sku = text.replace('SKU', '').replace(':', '').strip()
                            if sku and len(sku) > 1:
                                return sku
                                
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting SKU: {e}")
            return None
    
    def closed(self, reason):
        """Called when spider closes"""
        logger.info(f"Spider closed: {reason}")
        logger.info(f"Total product categories found: {len(self.product_categories_found)}")
        logger.info(f"Total products extracted: {len(self.products_data)}")
        
        # Save product categories to JSON file (always overwrite the same file)
        categories_file = os.path.join(self.output_dir, 'lulurayyan_product_categories.json')
        
        try:
            categories_data = []
            for item in self.product_categories_found:
                categories_data.append(dict(item))
            
            with open(categories_file, 'w', encoding='utf-8') as f:
                json.dump(categories_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Product categories saved to: {categories_file}")
            
            # Save products data to separate JSON file
            products_file = os.path.join(self.output_dir, 'lulurayyan_products.json')
            
            try:
                with open(products_file, 'w', encoding='utf-8') as f:
                    json.dump(self.products_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Products data saved to: {products_file}")
            except Exception as e:
                logger.error(f"Error saving products to file: {e}")
            
            # Print summary
            print(f"\n=== COMPLETE DATA EXTRACTION SUMMARY ===")
            print(f"Total product categories found: {len(self.product_categories_found)}")
            print(f"Total products extracted: {len(self.products_data)}")
            print(f"Categories saved to: {categories_file}")
            print(f"Products saved to: {products_file}")
            
            if self.product_categories_found:
                print(f"\nProduct categories found:")
                for i, cat in enumerate(self.product_categories_found[:10], 1):
                    name = cat.get('category_name', 'Unknown')
                    url = cat.get('category_url', 'No URL')
                    source = cat.get('description', 'Unknown source')
                    subcategories = cat.get('subcategories', [])
                    subcat_count = len(subcategories)
                    products_count = cat.get('products_count', 0)
                    
                    print(f"  {i}. {name}")
                    print(f"     URL: {url}")
                    print(f"     Source: {source}")
                    print(f"     Subcategories: {subcat_count}")
                    print(f"     Products: {products_count}")
                    
                    # Show first few subcategories
                    if subcategories:
                        for j, subcat in enumerate(subcategories[:3], 1):
                            print(f"       {j}. {subcat.get('name', 'Unknown')} - {subcat.get('url', 'No URL')}")
                        if subcat_count > 3:
                            print(f"       ... and {subcat_count - 3} more subcategories")
                
                if len(self.product_categories_found) > 10:
                    print(f"  ... and {len(self.product_categories_found) - 10} more categories")
            
            if self.products_data:
                print(f"\nSample products extracted:")
                for i, product in enumerate(self.products_data[:5], 1):
                    name = product.get('name', 'Unknown')
                    category = product.get('category', 'Unknown')
                    subcategory = product.get('subcategory', 'Unknown')
                    price = product.get('price', 'No price')
                    print(f"  {i}. {name}")
                    print(f"     Category: {category} > {subcategory}")
                    print(f"     Price: {price}")
                
                if len(self.products_data) > 5:
                    print(f"  ... and {len(self.products_data) - 5} more products")
            
            print(f"==========================================\n")
        
        except Exception as e:
            logger.error(f"Error saving data: {e}")
        
        # Clean up driver
        if self.driver:
            self.driver.quit()


if __name__ == "__main__":
    # Example of how to run the spider
    print("LuluRayyan Spiders")
    print("1. Main categories: scrapy crawl lulurayyan_categories")
    print("2. Product categories (by clicking products): scrapy crawl lulurayyan_product_categories")
    print("3. Test specific URL: scrapy crawl lulurayyan_category_test -a category_url='URL_HERE'")
    print("\nNote: The product categories spider will:")
    print("  - Click on products to find main categories")
    print("  - Navigate to each category page to extract subcategories")
    print("  - Extract products and details from each subcategory")
    print("  - Save categories to lulurayyan_product_categories.json")
    print("  - Save products to lulurayyan_products.json")

