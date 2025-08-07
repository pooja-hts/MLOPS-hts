#!/usr/bin/env python3
"""
Fixed iProcure Search to Product Extraction Tool
Clean version with proper WebDriver setup to fix "data:," URL issues
"""

import os
import json
import time
import requests
import logging
from datetime import datetime
from urllib.parse import quote, urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


# Default product name - can be overridden
product_name = "Safety Belts & Harness"
# product_name = "Explosion-proof LED Floodlight"
# product_name = "1G PVC Modern"
class FixedSearchExtractor:
    """Fixed version of the search to extraction tool"""
    
    def __init__(self, headless=False, download_images=True):
        """Initialize with improved WebDriver setup"""
        self.headless = headless
        self.download_images = download_images
        self.base_url = "https://www.iprocure.ai"
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize WebDriver
        self.driver = self._setup_webdriver()
        
        # Test connectivity
        self._test_connectivity()
    
    def _setup_webdriver(self):
        """Set up WebDriver with multiple fallback options"""
        self.logger.info("Setting up WebDriver...")
        
        option_sets = [
            {
                "name": "Standard Setup",
                "options": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage", 
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-web-security",
                    "--allow-running-insecure-content"
                ]
            },
            {
                "name": "Minimal Setup",
                "options": ["--no-sandbox", "--disable-dev-shm-usage"]
            },
            {
                "name": "Basic Setup",
                "options": []
            }
        ]
        
        if self.headless:
            for option_set in option_sets:
                option_set["options"].append("--headless")
        
        for option_set in option_sets:
            try:
                self.logger.info(f"Trying: {option_set['name']}")
                
                options = Options()
                for option in option_set["options"]:
                    options.add_argument(option)
                
                driver = webdriver.Chrome(options=options)
                self.logger.info(f"✅ Success: {option_set['name']}")
                return driver
                
            except Exception as e:
                self.logger.warning(f"❌ Failed: {option_set['name']} - {e}")
                continue
        
        raise Exception("Could not initialize WebDriver. Please check Chrome installation.")
    
    def _test_connectivity(self):
        """Test WebDriver connectivity"""
        try:
            self.logger.info("Testing connectivity...")
            
            # Test Google first
            self.driver.get("https://www.google.com")
            time.sleep(3)
            
            current_url = self.driver.current_url
            self.logger.info(f"Test URL result: {current_url}")
            
            if current_url == "data:,":
                raise Exception("❌ WebDriver cannot access internet (getting 'data:,' URL)")
            
            if "google" not in current_url.lower():
                raise Exception(f"❌ Unexpected redirect: {current_url}")
            
            self.logger.info("✅ Connectivity test passed")
            
        except Exception as e:
            self.logger.error(f"Connectivity test failed: {e}")
            self.logger.error("Please run 'python debug_webdriver_setup.py' to diagnose")
            raise
    
    def test_search_url(self, search_term=product_name):
        """Test the specific search URL"""
        try:
            encoded_term = quote(search_term)
            search_url = f"https://www.iprocure.ai/product-search-result?query={encoded_term}&type=Products"
            
            self.logger.info(f"Testing search URL: {search_url}")
            
            # Navigate to search URL
            self.driver.get(search_url)
            time.sleep(5)
            
            current_url = self.driver.current_url
            page_title = self.driver.title
            
            self.logger.info(f"Current URL: {current_url}")
            self.logger.info(f"Page title: {page_title}")
            
            # Check page content
            page_source = self.driver.page_source.lower()
            
            results = {
                'search_url': search_url,
                'final_url': current_url,
                'page_title': page_title,
                'contains_search_term': search_term.lower() in page_source,
                'contains_tenby': 'tenby' in page_source,
                'contains_blank_plate': 'blank plate' in page_source,
                'product_elements_found': 0
            }
            
            # Look for product elements
            product_selectors = [
                "div:contains('Blank Plate')",
                "div:contains('Tenby')",
                "[class*='product']",
                "[class*='card']",
                "a[href*='product']"
            ]
            
            for selector in product_selectors:
                try:
                    if "contains" in selector:
                        # Use XPath for text search
                        text = selector.split("'")[1]
                        xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]"
                        elements = self.driver.find_elements(By.XPATH, xpath)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        results['product_elements_found'] += len(elements)
                        self.logger.info(f"Found {len(elements)} elements with: {selector}")
                        break
                        
                except Exception as e:
                    self.logger.debug(f"Selector failed {selector}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"Search URL test failed: {e}")
            return {'error': str(e)}
    
    def find_and_click_product(self, search_term=product_name):
        """Find and click on a product from search results"""
        try:
            # First, go to search results
            test_result = self.test_search_url(search_term)
            
            if 'error' in test_result:
                return None
            
            self.logger.info("Looking for clickable product elements...")
            
            # Try different strategies to find product elements
            clickable_elements = []
            
            # Strategy 1: Look for elements containing search term keywords
            search_keywords = self._extract_search_keywords(search_term)
            self.logger.info(f"   Searching for keywords: {search_keywords}")
            
            for keyword in search_keywords:
                try:
                    xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    
                    for element in elements:
                        # Check if element or its parent is clickable
                        if element.is_displayed():
                            # Prioritize links and clickable elements
                            element_tag = element.tag_name
                            element_href = element.get_attribute("href") if element_tag == "a" else None
                            
                            # Check if this element or its parent is a link
                            if element_tag == "a" or element_href:
                                clickable_elements.append(element)
                            else:
                                # Look for parent link
                                try:
                                    parent_link = element.find_element(By.XPATH, "./ancestor::a[1]")
                                    if parent_link and parent_link not in clickable_elements:
                                        clickable_elements.append(parent_link)
                                except:
                                    # If no parent link, still add the element but with lower priority
                                    clickable_elements.append(element)
                            
                    if clickable_elements:
                        self.logger.info(f"   Found {len(clickable_elements)} elements containing: {keyword}")
                        break
                        
                except Exception as e:
                    self.logger.debug(f"Text search failed for {keyword}: {e}")
                    continue
            
            # Strategy 2: Look for any links containing search keywords
            if not clickable_elements:
                try:
                    search_keywords = self._extract_search_keywords(search_term)
                    links = self.driver.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        href = link.get_attribute("href") or ""
                        text = link.text.lower()
                        
                        # Check if link contains product URL or search keywords
                        if (href and 'product' in href) or any(keyword in text for keyword in search_keywords):
                            clickable_elements.append(link)
                            
                except Exception as e:
                    self.logger.debug(f"Link search failed: {e}")
            
            # Strategy 3: Look for any clickable elements with product-related classes
            if not clickable_elements:
                try:
                    product_selectors = [
                        "[class*='product']",
                        "[class*='item']",
                        "[class*='card']",
                        "[class*='result']",
                        ".product-item",
                        ".item",
                        ".card",
                        ".result"
                    ]
                    
                    for selector in product_selectors:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                clickable_elements.append(element)
                        
                        if clickable_elements:
                            self.logger.info(f"   Found elements with selector: {selector}")
                            break
                            
                except Exception as e:
                    self.logger.debug(f"Product selector search failed: {e}")
            
            # Strategy 4: Look for any clickable elements (fallback)
            if not clickable_elements:
                try:
                    # Look for any clickable elements that might be products
                    clickable_selectors = [
                        "a[href]",
                        "button",
                        "[onclick]",
                        "[role='button']"
                    ]
                    
                    for selector in clickable_selectors:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                text = element.text.strip()
                                if text and len(text) > 5:  # Has substantial text
                                    clickable_elements.append(element)
                        
                        if len(clickable_elements) > 0:
                            self.logger.info(f"   Found clickable elements with selector: {selector}")
                            break
                            
                except Exception as e:
                    self.logger.debug(f"Clickable element search failed: {e}")
            
            if not clickable_elements:
                self.logger.warning("No clickable product elements found with original search term")
                
                # Strategy 5: Try with simplified search terms
                simplified_terms = self._get_simplified_search_terms(search_term)
                self.logger.info(f"   Trying simplified search terms: {simplified_terms}")
                
                for simplified_term in simplified_terms:
                    try:
                        # Navigate to search with simplified term
                        encoded_term = quote(simplified_term)
                        search_url = f"https://www.iprocure.ai/product-search-result?query={encoded_term}&type=Products"
                        self.driver.get(search_url)
                        time.sleep(3)
                        
                        # Look for any clickable elements
                        clickable_selectors = [
                            "a[href]",
                            "[class*='product']",
                            "[class*='item']",
                            ".product-item",
                            ".item"
                        ]
                        
                        for selector in clickable_selectors:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for element in elements:
                                if element.is_displayed() and element.is_enabled():
                                    text = element.text.strip()
                                    if text and len(text) > 5:
                                        clickable_elements.append(element)
                            
                            if clickable_elements:
                                self.logger.info(f"   Found elements with simplified term '{simplified_term}'")
                                break
                        
                        if clickable_elements:
                            break
                            
                    except Exception as e:
                        self.logger.debug(f"Simplified search failed for '{simplified_term}': {e}")
                        continue
                
                if not clickable_elements:
                    self.logger.warning("No clickable product elements found even with simplified terms")
                
                # Enhanced debugging - analyze what's actually on the page
                self._debug_page_content(search_term)
                return None
            
            # Try to click on the first promising element
            for i, element in enumerate(clickable_elements[:5]):  # Try more elements
                try:
                    element_text = element.text.strip()[:50] if element.text else "Unknown element"
                    element_tag = element.tag_name
                    element_href = element.get_attribute("href") if element_tag == "a" else None
                    
                    self.logger.info(f"Attempting to click element {i+1}: {element_text}")
                    self.logger.info(f"   Element type: {element_tag}, href: {element_href}")
                    
                    # Check if element is actually clickable
                    if not element.is_displayed():
                        self.logger.debug(f"Element {i+1} not displayed, skipping")
                        continue
                    
                    if not element.is_enabled():
                        self.logger.debug(f"Element {i+1} not enabled, skipping")
                        continue
                    
                    # Scroll to element
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(1)
                    
                    # Get current URL before clicking
                    before_url = self.driver.current_url
                    
                    # Try different click methods with better error handling
                    click_success = False
                    
                    # Method 1: Regular click
                    try:
                        element.click()
                        click_success = True
                        self.logger.debug(f"Regular click successful for element {i+1}")
                    except Exception as e:
                        self.logger.debug(f"Regular click failed for element {i+1}: {e}")
                    
                    # Method 2: JavaScript click (if regular click failed)
                    if not click_success:
                        try:
                            self.driver.execute_script("arguments[0].click();", element)
                            click_success = True
                            self.logger.debug(f"JavaScript click successful for element {i+1}")
                        except Exception as e:
                            self.logger.debug(f"JavaScript click failed for element {i+1}: {e}")
                    
                    # Method 3: Action chains (if other methods failed)
                    if not click_success:
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains
                            ActionChains(self.driver).move_to_element(element).click().perform()
                            click_success = True
                            self.logger.debug(f"Action chains click successful for element {i+1}")
                        except Exception as e:
                            self.logger.debug(f"Action chains click failed for element {i+1}: {e}")
                    
                    if not click_success:
                        self.logger.debug(f"All click methods failed for element {i+1}")
                        continue
                    
                    time.sleep(3)
                    
                    # Check if URL changed (indicating navigation)
                    after_url = self.driver.current_url
                    
                    if after_url != before_url:
                        self.logger.info(f"✅ Successfully clicked and navigated to: {after_url}")
                        return after_url
                    else:
                        self.logger.debug(f"Click didn't result in navigation for element {i+1}, trying next element")
                        
                except Exception as e:
                    self.logger.debug(f"Click failed for element {i+1}: {e}")
                    continue
            
            self.logger.warning("Could not successfully click any product element")
            
            # Fallback: Try to extract basic information from search results page
            self.logger.info("Attempting to extract basic information from search results page...")
            basic_info = self._extract_basic_info_from_search_results(search_term)
            if basic_info:
                return basic_info
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding/clicking product: {e}")
            return None
    
    def _extract_search_keywords(self, search_term):
        """Extract meaningful keywords from search term for dynamic searching"""
        import re
        
        # Convert to lowercase and split by common separators
        keywords = re.split(r'[,\s\-_]+', search_term.lower())
        
        # Filter out very short or common words
        filtered_keywords = []
        skip_words = {'and', 'or', 'the', 'a', 'an', 'with', 'for', 'of', 'in', 'on', 'at', 'to', 'by', 'from'}
        
        for keyword in keywords:
            keyword = keyword.strip()
            if (len(keyword) >= 2 and  # At least 2 characters
                keyword not in skip_words and  # Not a common word
                len(keyword) <= 20):  # Not too long
                filtered_keywords.append(keyword)
        
        # If we don't have enough keywords, try different splitting strategies
        if len(filtered_keywords) < 2:
            # Try splitting by numbers and letters
            alphanumeric_parts = re.findall(r'[A-Za-z]+|\d+', search_term)
            for part in alphanumeric_parts:
                if len(part) >= 2 and part.lower() not in skip_words:
                    filtered_keywords.append(part.lower())
        
        # If still not enough, use the original search term as a fallback
        if len(filtered_keywords) < 2:
            # Use the first few words of the search term
            words = search_term.split()[:3]
            for word in words:
                if len(word) >= 2:
                    filtered_keywords.append(word.lower())
        
        # Remove duplicates and limit to most relevant keywords (first 5)
        unique_keywords = list(dict.fromkeys(filtered_keywords))  # Preserve order
        return unique_keywords[:5]
    
    def _extract_basic_info_from_search_results(self, search_term):
        """Extract basic information from search results page when no product can be clicked"""
        try:
            self.logger.info("Extracting basic information from search results page...")
            
            # Initialize basic product data
            product_data = {
                'url': self.driver.current_url,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'title': search_term,
                'brand': '',
                'supplier': '',
                'category': '',
                'sku': '',
                'model': '',
                'description': '',
                'key_attributes': {},
                'technical_specifications': {},
                'image_downloaded': False,
                'extraction_success': {
                    'title': True,  # We have the search term as title
                    'attributes': False,
                    'description': False,
                    'image': False
                },
                'extraction_source': 'search_results_page'
            }
            
            # Try to extract any visible product information from the search results
            page_source = self.driver.page_source
            page_text = self.driver.page_source.lower()
            
            # Look for product cards or list items
            product_selectors = [
                ".product-card",
                ".product-item", 
                ".search-result",
                ".item-card",
                "[class*='product']",
                "[class*='card']",
                "li",
                ".result-item"
            ]
            
            found_products = []
            for selector in product_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        self.logger.info(f"Found {len(elements)} elements with selector: {selector}")
                        found_products = elements
                        break
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # Extract information from the first few product elements
            if found_products:
                for i, element in enumerate(found_products[:3]):  # Check first 3 products
                    try:
                        element_text = element.text.strip()
                        if element_text and len(element_text) > 10:
                            # Try to extract basic info from element text
                            self._extract_info_from_text(element_text, product_data)
                            
                            # If we found some useful info, break
                            if (product_data.get('brand') or product_data.get('supplier') or 
                                product_data.get('sku') or product_data.get('model')):
                                self.logger.info(f"Found useful information from product element {i+1}")
                                break
                    except Exception as e:
                        self.logger.debug(f"Error extracting from element {i+1}: {e}")
                        continue
            
            # Try to extract from page content using regex patterns
            self._extract_from_page_content(page_source, product_data)
            
            # Log what we found
            extracted_fields = []
            for field in ['brand', 'supplier', 'sku', 'model', 'category']:
                if product_data.get(field):
                    extracted_fields.append(f"{field}: {product_data[field]}")
            
            if extracted_fields:
                self.logger.info(f"Extracted from search results: {', '.join(extracted_fields)}")
            else:
                self.logger.info("No additional information extracted from search results")
            
            return product_data
            
        except Exception as e:
            self.logger.error(f"Error extracting basic info from search results: {e}")
            return None
    
    def _extract_info_from_text(self, text, product_data):
        """Extract basic information from text content"""
        try:
            import re
            
            # Brand patterns
            brand_patterns = [
                r'brand[:\s]+([^,\n]+)',
                r'manufacturer[:\s]+([^,\n]+)',
                r'make[:\s]+([^,\n]+)'
            ]
            
            for pattern in brand_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches and not product_data.get('brand'):
                    brand = matches[0].strip()
                    if brand and len(brand) < 50:
                        product_data['brand'] = brand
                        break
            
            # Supplier patterns
            supplier_patterns = [
                r'supplier[:\s]+([^,\n]+)',
                r'sold by[:\s]+([^,\n]+)',
                r'vendor[:\s]+([^,\n]+)'
            ]
            
            for pattern in supplier_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches and not product_data.get('supplier'):
                    supplier = matches[0].strip()
                    if supplier and len(supplier) < 100:
                        product_data['supplier'] = supplier
                        break
            
            # SKU patterns
            sku_patterns = [
                r'sku[:\s]+([A-Za-z0-9\-_\.]+)',
                r'item code[:\s]+([A-Za-z0-9\-_\.]+)',
                r'product code[:\s]+([A-Za-z0-9\-_\.]+)'
            ]
            
            for pattern in sku_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches and not product_data.get('sku'):
                    sku = matches[0].strip()
                    if sku and len(sku) < 50:
                        product_data['sku'] = sku
                        break
            
            # Model patterns
            model_patterns = [
                r'model[:\s]+([A-Za-z0-9\-_\s\.]+)',
                r'serial number[:\s]+([A-Za-z0-9\-_\s\.]+)'
            ]
            
            for pattern in model_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches and not product_data.get('model'):
                    model = matches[0].strip()
                    if model and len(model) < 50:
                        product_data['model'] = model
                        break
                        
        except Exception as e:
            self.logger.debug(f"Error extracting info from text: {e}")
    
    def _extract_from_page_content(self, page_source, product_data):
        """Extract information from entire page content"""
        try:
            import re
            
            # Look for common patterns in the page
            patterns = [
                (r'brand[:\s]+([^<\n,]+)', 'brand'),
                (r'supplier[:\s]+([^<\n,]+)', 'supplier'),
                (r'sku[:\s]+([A-Za-z0-9\-_\.]+)', 'sku'),
                (r'model[:\s]+([A-Za-z0-9\-_\s\.]+)', 'model'),
                (r'category[:\s]+([^<\n,]+)', 'category')
            ]
            
            for pattern, field in patterns:
                if not product_data.get(field):
                    matches = re.findall(pattern, page_source, re.IGNORECASE)
                    if matches:
                        value = matches[0].strip()
                        if value and len(value) < 100:
                            product_data[field] = value
                            
        except Exception as e:
            self.logger.debug(f"Error extracting from page content: {e}")
    
    def _get_simplified_search_terms(self, search_term):
        """Generate simplified search terms for fallback searches"""
        simplified_terms = []
        
        # Strategy 1: Use first few words
        words = search_term.split()
        if len(words) >= 2:
            simplified_terms.append(" ".join(words[:2]))  # First 2 words
        if len(words) >= 3:
            simplified_terms.append(" ".join(words[:3]))  # First 3 words
        
        # Strategy 2: Use main product type words
        product_types = ['safety', 'boots', 'goggles', 'gloves', 'helmet', 'vest', 'jacket', 
                        'socket', 'switch', 'cable', 'wire', 'plate', 'screwdriver', 'knife', 
                        'mcb', 'contactor', 'breaker', 'fuse', 'lamp', 'light', 'bulb']
        
        search_lower = search_term.lower()
        for product_type in product_types:
            if product_type in search_lower:
                simplified_terms.append(product_type)
        
        # Strategy 3: Use brand/model patterns
        import re
        # Look for brand patterns (e.g., "QR 97", "TSP203SB")
        brand_patterns = re.findall(r'[A-Z]{2,}\s*\d+', search_term)
        for pattern in brand_patterns:
            simplified_terms.append(pattern)
        
        # Strategy 4: Use alphanumeric parts
        alphanumeric_parts = re.findall(r'[A-Za-z]{3,}', search_term)
        for part in alphanumeric_parts[:3]:  # Limit to first 3 parts
            if len(part) >= 3:
                simplified_terms.append(part)
        
        # Remove duplicates and limit
        unique_terms = list(dict.fromkeys(simplified_terms))
        return unique_terms[:5]  # Return first 5 simplified terms
    
    def _extract_title_and_basic_info(self, product_data):
        """Extract title and enhanced basic product information with improved parsing"""
        try:
            page_source = self.driver.page_source.lower()
            page_text = self.driver.page_source
            
            # Extract title from multiple sources
            title_selectors = [
                "h1",
                ".product-title", 
                ".product-name",
                "[class*='title']",
                "[class*='name']",
                ".item-title",
                ".product-header h1",
                ".product-header h2"
            ]
            
            for selector in title_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 5:
                            product_data['title'] = text
                            product_data['extraction_success']['title'] = True
                            self.logger.info(f"   Found title: {text}")
                            break
                    if product_data['title']:
                        break
                except:
                    continue
            
            # Fallback title extraction
            if not product_data['title']:
                search_keywords = self._extract_search_keywords(product_name)
                for keyword in search_keywords:
                    if keyword in page_source and len(keyword) > 3:
                        product_data['title'] = product_name
                        product_data['extraction_success']['title'] = True
                        break
            
            # Enhanced JavaScript extraction with better parsing
            js_script = """
            var info = {};
            
            // Strategy 1: Look for key-value pairs in the page
            var extractInfo = function() {
                var text = document.body.innerText || document.body.textContent || '';
                var lines = text.split('\\n');
                
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i].trim();
                    
                    // Skip empty lines
                    if (!line) continue;
                    
                    // Look for "Label: Value" patterns
                    if (line.includes(':')) {
                        var parts = line.split(':');
                        if (parts.length >= 2) {
                            var key = parts[0].trim().toLowerCase();
                            var value = parts.slice(1).join(':').trim();
                            
                            // Clean up the value - remove leading/trailing special chars
                            value = value.replace(/^[^a-zA-Z0-9]+/, '').replace(/[^a-zA-Z0-9]+$/, '');
                            
                            // Skip if value is empty, too short, or contains unwanted patterns
                            // But be less strict for brand and supplier fields
                            if (!value || value.length < 1) {
                                continue;
                            }
                            
                            // Only apply strict validation for SKU and Model fields
                            if ((key.includes('sku') || key.includes('item code') || key.includes('product code') || key.includes('part number') ||
                                 key.includes('model') || key.includes('serial number') || key.includes('model number')) &&
                                (value.includes('Item Code:') || 
                                 value.includes('Serial Number:') ||
                                 value === '/ Item Code:' ||
                                 value === '/ Serial Number:' ||
                                 value === 'Item Code:' ||
                                 value === 'Serial Number:' ||
                                 value.startsWith('/') ||
                                 value.startsWith('{') ||
                                 value.includes('Feature') ||
                                 value.includes('Value'))) {
                                continue;
                            }
                            
                            // Map to fields
                            if (key.includes('brand') && !info.brand) {
                                info.brand = value;
                            } else if (key.includes('supplier') && !info.supplier) {
                                info.supplier = value;
                            } else if ((key.includes('country') || key.includes('origin') || key.includes('manufactured')) && !info.manufactured_country) {
                                info.manufactured_country = value;
                            } else if ((key.includes('sku') || key.includes('item code') || key.includes('product code') || key.includes('part number')) && !info.sku) {
                                info.sku = value;
                            } else if ((key.includes('model') || key.includes('serial number') || key.includes('model number')) && !info.model) {
                                info.model = value;
                            } else if ((key.includes('unspsc') || key.includes('unspc')) && !info.unspsc) {
                                info.unspsc = value;
                            } else if (key.includes('category') && !info.category) {
                                if (key.includes('main')) {
                                    info.main_category = value;
                                } else {
                                    info.category = value;
                                }
                            }
                        }
                    }
                }
                
                return info;
            };
            
            // Strategy 2: Look for definition lists and tables
            document.querySelectorAll('dl').forEach(dl => {
                var dts = dl.querySelectorAll('dt');
                var dds = dl.querySelectorAll('dd');
                for (var i = 0; i < Math.min(dts.length, dds.length); i++) {
                    var key = (dts[i].textContent || '').trim().toLowerCase();
                    var value = (dds[i].textContent || '').trim();
                    
                    // Clean value
                    if (value && value.length > 0 && value.length < 200 && 
                        value !== '/ Item Code:' && value !== '/ Serial Number:' &&
                        value !== 'Item Code:' && value !== 'Serial Number:' &&
                        !value.startsWith('/') && !value.startsWith('{') &&
                        !value.includes('Feature') && !value.includes('Value')) {
                        
                        if (key.includes('brand') && !info.brand) info.brand = value;
                        if (key.includes('supplier') && !info.supplier) info.supplier = value;
                        if ((key.includes('country') || key.includes('origin')) && !info.manufactured_country) info.manufactured_country = value;
                        if ((key.includes('sku') || key.includes('item code') || key.includes('product code')) && !info.sku) info.sku = value;
                        if ((key.includes('model') || key.includes('serial')) && !info.model) info.model = value;
                        if ((key.includes('unspsc') || key.includes('unspc')) && !info.unspsc) info.unspsc = value;
                        if (key.includes('category') && !info.category) {
                            if (key.includes('main')) info.main_category = value;
                            else info.category = value;
                        }
                    }
                }
            });
            
            // Strategy 3: Look for table rows with better parsing
            document.querySelectorAll('table tr').forEach(row => {
                var cells = row.querySelectorAll('td, th');
                if (cells.length >= 2) {
                    var key = (cells[0].textContent || '').trim().toLowerCase();
                    var value = (cells[1].textContent || '').trim();
                    
                    // Clean and validate value
                    if (value && value.length > 0 && value.length < 200) {
                        // Skip invalid values
                        if (value === '/ Item Code:' || value === '/ Serial Number:' || 
                            value === 'Item Code:' || value === 'Serial Number:' ||
                            value.startsWith('/') || value.startsWith('{') ||
                            value.includes('Feature') || value.includes('Value') ||
                            (value.includes('/') && value.length < 5)) {
                            return;
                        }
                        
                        if (key.includes('brand') && !info.brand) info.brand = value;
                        if (key.includes('supplier') && !info.supplier) info.supplier = value;
                        if ((key.includes('country') || key.includes('origin')) && !info.manufactured_country) info.manufactured_country = value;
                        if ((key.includes('sku') || key.includes('item code') || key.includes('product code')) && !info.sku) info.sku = value;
                        if ((key.includes('model') || key.includes('serial')) && !info.model) info.model = value;
                        if ((key.includes('unspsc') || key.includes('unspc')) && !info.unspsc) info.unspsc = value;
                        if (key.includes('category') && !info.category) {
                            if (key.includes('main')) info.main_category = value;
                            else info.category = value;
                        }
                    }
                }
            });
            
            // Strategy 4: Enhanced UNSPSC extraction
            var unspscPatterns = [
                /UNSPSC[:\\s]+([0-9]{8,12})/gi,
                /UNSPC[:\\s]+([0-9]{8,12})/gi,
                /unspsc code[:\\s]+([0-9]{8,12})/gi,
                /classification[:\\s]+([0-9]{8,12})/gi
            ];
            
            var pageText = document.body.textContent || document.body.innerText || '';
            unspscPatterns.forEach(pattern => {
                if (!info.unspsc) {
                    var matches = pageText.match(pattern);
                    if (matches && matches[0]) {
                        var code = matches[0].replace(/[^0-9]/g, '');
                        if (code.length >= 8) {
                            info.unspsc = code;
                        }
                    }
                }
            });
            
            return extractInfo();
            """
            
            # Execute JavaScript extraction
            try:
                js_info = self.driver.execute_script(js_script)
                if js_info:
                    # Map JavaScript results to product_data with validation
                    for field in ['brand', 'supplier', 'manufactured_country', 'sku', 'model', 'unspsc', 'category', 'main_category']:
                        if field in js_info and js_info[field]:
                            value = str(js_info[field]).strip()
                            # Additional validation
                            if (value and len(value) > 0 and 
                                value != '/ Item Code:' and 
                                value != '/ Serial Number:' and
                                not (value.startswith('/') and len(value) < 5)):
                                product_data[field] = value
                    
                    self.logger.info(f"   JavaScript extracted {len([k for k in js_info.keys() if js_info[k]])} info fields")
                    
            except Exception as e:
                self.logger.debug(f"JavaScript info extraction failed: {e}")
            
            # Enhanced regex extraction with better patterns
            import re
            patterns = [
                # Less strict patterns for brand and supplier
                (r'Brand[:\s]+([^<\n]+?)(?=\s*(?:Supplier|Category|$|\n))', 'brand'),
                (r'Supplier[:\s]+([^<\n]+?)(?=\s*(?:Brand|Category|$|\n))', 'supplier'),
                (r'(?:Manufactured Country|Manufacturing Country|Origin Country|Country)[:\s]+([^<\n,/]+?)(?=\s*(?:Brand|Supplier|$|\n))', 'manufactured_country'),
                # Improved SKU pattern - avoid placeholder text
                (r'(?:SKU|Item Code|Product Code|Part Number)[:\s]+([A-Za-z0-9\-_\.]+)(?:\s|$)', 'sku'),
                # Improved Model pattern - avoid placeholder text  
                (r'(?:Model|Serial Number|Model Number)[:\s]+([A-Za-z0-9\-_\s\.]+?)(?=\s*(?:Brand|Supplier|$|\n))', 'model'),
                # Enhanced UNSPSC pattern
                (r'(?:UNSPSC|UNSPC)[:\s]+([0-9]{8,12})', 'unspsc'),
                (r'Category[:\s]+([^<\n,/]+?)(?=\s*(?:Brand|Supplier|$|\n))', 'category'),
                (r'Main Category[:\s]+([^<\n,/]+?)(?=\s*(?:Brand|Supplier|$|\n))', 'main_category')
            ]
            
            for pattern, key in patterns:
                if not product_data.get(key):
                    matches = re.findall(pattern, page_text, re.IGNORECASE | re.MULTILINE)
                    if matches:
                        value = matches[0].strip()
                        
                        # Different validation for different field types
                        is_valid = True
                        
                        # Basic validation for all fields
                        if not value or len(value) == 0 or len(value) >= 200:
                            is_valid = False
                        
                        # Strict validation only for SKU and Model fields
                        elif key in ['sku', 'model']:
                            if (value in ['/ Item Code:', '/ Serial Number:', 'Item Code:', 'Serial Number:'] or
                                value.startswith('/') or value.startswith('{') or
                                any(skip in value for skip in ['Feature', 'Value', 'Item Code:', 'Serial Number:'])):
                                is_valid = False
                        
                        # Less strict validation for brand and supplier
                        elif key in ['brand', 'supplier']:
                            if value.startswith('/') or value.startswith('{'):
                                is_valid = False
                        
                        if is_valid:
                            product_data[key] = value
            
            # Clean up extracted data to remove duplicates and invalid entries
            self._clean_extracted_data(product_data)
            
            # Additional extraction for SKU and Model from product details
            self._extract_sku_and_model_from_details(product_data)
            
            # Extract from key attributes if available
            self._extract_from_key_attributes(product_data)
            
            # Enhanced UNSPSC extraction
            self._extract_unspsc_code(product_data)
            
            # Debug: Look for actual values in the page
            if (not product_data.get('sku') or product_data['sku'] in ['/ Item Code:', 'Item Code:', ''] or
                not product_data.get('model') or product_data['model'] in ['/ Serial Number:', 'Serial Number:', '']):
                self._debug_extract_actual_values(product_data)
            
            # Fallback extraction for brand and supplier
            if not product_data.get('brand') or not product_data.get('supplier'):
                self._extract_brand_supplier_fallback(product_data)
            
            # Extract Main Category from specific HTML structure
            self._extract_main_category(product_data)
            
            # Extract Category from specific HTML structure
            self._extract_category(product_data)
            
            # Log extraction results
            extracted_fields = []
            for field in ['brand', 'supplier', 'manufactured_country', 'sku', 'model', 'unspsc', 'category', 'main_category']:
                if product_data.get(field):
                    extracted_fields.append(f"{field}: {product_data[field]}")
            
            if extracted_fields:
                self.logger.info(f"   ✅ Extracted fields: {', '.join(extracted_fields)}")
            else:
                self.logger.warning("   ⚠️ No additional info fields extracted")
            
        except Exception as e:
            self.logger.warning(f"Error extracting title/basic info: {e}")

    def _extract_sku_and_model_from_details(self, product_data):
        """Extract SKU and Model from product details with better accuracy"""
        try:
            # First, let's check if we already have valid values
            if (product_data.get('sku') and product_data['sku'] not in ['/ Item Code:', 'Item Code:', ''] and
                product_data.get('model') and product_data['model'] not in ['/ Serial Number:', 'Serial Number:', '']):
                return
            
            # Look for SKU and Model in the product details section
            detail_selectors = [
                ".product-details",
                ".product-info", 
                ".item-details",
                ".specifications",
                ".product-specs",
                "[class*='detail']",
                "[class*='spec']",
                ".product-attributes",
                ".product-features",
                ".item-info",
                ".product-data"
            ]
            
            for selector in detail_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text
                        
                        # Look for SKU patterns
                        if not product_data.get('sku') or product_data['sku'] in ['/ Item Code:', 'Item Code:']:
                            sku_patterns = [
                                r'Item Code[:\s]+([A-Za-z0-9\-_\.]+)',
                                r'SKU[:\s]+([A-Za-z0-9\-_\.]+)',
                                r'Product Code[:\s]+([A-Za-z0-9\-_\.]+)',
                                r'Part Number[:\s]+([A-Za-z0-9\-_\.]+)'
                            ]
                            
                            import re
                            for pattern in sku_patterns:
                                matches = re.findall(pattern, text, re.IGNORECASE)
                                if matches:
                                    sku_value = matches[0].strip()
                                    if (sku_value and len(sku_value) > 0 and 
                                        sku_value not in ['/ Item Code:', 'Item Code:', '/', '{'] and
                                        not sku_value.startswith('/')):
                                        product_data['sku'] = sku_value
                                        self.logger.info(f"   Found SKU: {sku_value}")
                                        break
                        
                        # Look for Model patterns
                        if not product_data.get('model') or product_data['model'] in ['/ Serial Number:', 'Serial Number:']:
                            model_patterns = [
                                r'Serial Number[:\s]+([A-Za-z0-9\-_\s\.]+)',
                                r'Model[:\s]+([A-Za-z0-9\-_\s\.]+)',
                                r'Model Number[:\s]+([A-Za-z0-9\-_\s\.]+)'
                            ]
                            
                            for pattern in model_patterns:
                                matches = re.findall(pattern, text, re.IGNORECASE)
                                if matches:
                                    model_value = matches[0].strip()
                                    if (model_value and len(model_value) > 0 and 
                                        model_value not in ['/ Serial Number:', 'Serial Number:', '/', '{'] and
                                        not model_value.startswith('/')):
                                        product_data['model'] = model_value
                                        self.logger.info(f"   Found Model: {model_value}")
                                        break
                        
                        # If we found both, we can stop
                        if (product_data.get('sku') and product_data['sku'] not in ['/ Item Code:', 'Item Code:'] and
                            product_data.get('model') and product_data['model'] not in ['/ Serial Number:', 'Serial Number:']):
                            return
                            
                except Exception as e:
                    self.logger.debug(f"Detail selector failed {selector}: {e}")
                    continue
            
            # Fallback: Look in the entire page for better patterns
            if (not product_data.get('sku') or product_data['sku'] in ['/ Item Code:', 'Item Code:'] or
                not product_data.get('model') or product_data['model'] in ['/ Serial Number:', 'Serial Number:']):
                
                page_text = self.driver.page_source
                
                # Enhanced SKU extraction
                if not product_data.get('sku') or product_data['sku'] in ['/ Item Code:', 'Item Code:']:
                    enhanced_sku_patterns = [
                        r'Item Code[:\s]*([A-Za-z0-9\-_\.]+)(?:\s|$|</)',
                        r'SKU[:\s]*([A-Za-z0-9\-_\.]+)(?:\s|$|</)',
                        r'Product Code[:\s]*([A-Za-z0-9\-_\.]+)(?:\s|$|</)',
                        r'Part Number[:\s]*([A-Za-z0-9\-_\.]+)(?:\s|$|</)'
                    ]
                    
                    import re
                    for pattern in enhanced_sku_patterns:
                        matches = re.findall(pattern, page_text, re.IGNORECASE)
                        if matches:
                            sku_value = matches[0].strip()
                            if (sku_value and len(sku_value) > 0 and 
                                sku_value not in ['/ Item Code:', 'Item Code:', '/', '{', 'Feature', 'Value'] and
                                not sku_value.startswith('/')):
                                product_data['sku'] = sku_value
                                self.logger.info(f"   Found SKU (fallback): {sku_value}")
                                break
                
                # Enhanced Model extraction
                if not product_data.get('model') or product_data['model'] in ['/ Serial Number:', 'Serial Number:']:
                    enhanced_model_patterns = [
                        r'Serial Number[:\s]*([A-Za-z0-9\-_\s\.]+)(?:\s|$|</)',
                        r'Model[:\s]*([A-Za-z0-9\-_\s\.]+)(?:\s|$|</)',
                        r'Model Number[:\s]*([A-Za-z0-9\-_\s\.]+)(?:\s|$|</)'
                    ]
                    
                    for pattern in enhanced_model_patterns:
                        matches = re.findall(pattern, page_text, re.IGNORECASE)
                        if matches:
                            model_value = matches[0].strip()
                            if (model_value and len(model_value) > 0 and 
                                model_value not in ['/ Serial Number:', 'Serial Number:', '/', '{', 'Feature', 'Value'] and
                                not model_value.startswith('/')):
                                product_data['model'] = model_value
                                self.logger.info(f"   Found Model (fallback): {model_value}")
                                break
                                
        except Exception as e:
            self.logger.debug(f"Error extracting SKU/Model from details: {e}")

    def _extract_from_key_attributes(self, product_data):
        """Extract SKU and Model from key attributes section"""
        try:
            # Check if we have key_attributes and if they contain the data we need
            if 'key_attributes' in product_data and product_data['key_attributes']:
                attributes = product_data['key_attributes']
                
                # Look for Brand in key attributes
                if not product_data.get('brand'):
                    brand_keys = ['Brand', 'Manufacturer', 'Make']
                    for key in brand_keys:
                        if key in attributes:
                            value = attributes[key]
                            if (value and value not in ['Feature', 'Value', '{'] and
                                not value.startswith('/') and len(value) > 0):
                                product_data['brand'] = value
                                self.logger.info(f"   Found Brand in key attributes: {value}")
                                break
                
                # Look for Supplier in key attributes
                if not product_data.get('supplier'):
                    supplier_keys = ['Supplier', 'Vendor', 'Distributor']
                    for key in supplier_keys:
                        if key in attributes:
                            value = attributes[key]
                            if (value and value not in ['Feature', 'Value', '{'] and
                                not value.startswith('/') and len(value) > 0):
                                product_data['supplier'] = value
                                self.logger.info(f"   Found Supplier in key attributes: {value}")
                                break
                
                # Look for SKU in key attributes
                if not product_data.get('sku') or product_data['sku'] in ['/ Item Code:', 'Item Code:', '']:
                    sku_keys = ['SKU', 'Item Code', 'Product Code', 'Part Number', 'Code']
                    for key in sku_keys:
                        if key in attributes:
                            value = attributes[key]
                            if (value and value not in ['/ Item Code:', 'Item Code:', 'Feature', 'Value', '{'] and
                                not value.startswith('/') and len(value) > 0):
                                product_data['sku'] = value
                                self.logger.info(f"   Found SKU in key attributes: {value}")
                                break
                
                # Look for Model in key attributes
                if not product_data.get('model') or product_data['model'] in ['/ Serial Number:', 'Serial Number:', '']:
                    model_keys = ['Model', 'Serial Number', 'Model Number', 'Serial']
                    for key in model_keys:
                        if key in attributes:
                            value = attributes[key]
                            if (value and value not in ['/ Serial Number:', 'Serial Number:', 'Feature', 'Value', '{'] and
                                not value.startswith('/') and len(value) > 0):
                                product_data['model'] = value
                                self.logger.info(f"   Found Model in key attributes: {value}")
                                break
                
                # Look for UNSPSC in key attributes
                if not product_data.get('unspsc'):
                    unspsc_keys = ['UNSPSC', 'UNSPC', 'Classification']
                    for key in unspsc_keys:
                        if key in attributes:
                            value = attributes[key]
                            if value and len(str(value)) >= 8:
                                # Clean the value to get just numbers
                                import re
                                numbers = re.findall(r'[0-9]+', str(value))
                                if numbers and len(numbers[0]) >= 8:
                                    product_data['unspsc'] = numbers[0]
                                    self.logger.info(f"   Found UNSPSC in key attributes: {numbers[0]}")
                                    break
                                    
        except Exception as e:
            self.logger.debug(f"Error extracting from key attributes: {e}")

    def _debug_extract_actual_values(self, product_data):
        """Debug method to find actual SKU and Model values in the page"""
        try:
            self.logger.info("🔍 DEBUG: Looking for actual SKU and Model values...")
            
            # Get the page source and look for patterns
            page_source = self.driver.page_source
            
            # Look for patterns that might contain the actual values
            import re
            
            # Look for any text that looks like a product code or model number
            # Common patterns: alphanumeric codes, numbers with letters, etc.
            
            # Pattern 1: Look for codes like "838007" (from the description)
            number_patterns = re.findall(r'\b([A-Za-z0-9]{6,10})\b', page_source)
            
            # Pattern 2: Look for specific patterns in the HTML
            sku_patterns = [
                r'Item Code[:\s]*([A-Za-z0-9\-_\.]+)',
                r'SKU[:\s]*([A-Za-z0-9\-_\.]+)',
                r'Product Code[:\s]*([A-Za-z0-9\-_\.]+)',
                r'Code[:\s]*([A-Za-z0-9\-_\.]+)',
                r'([A-Za-z0-9]{6,10})(?:\s|$|</)'
            ]
            
            model_patterns = [
                r'Serial Number[:\s]*([A-Za-z0-9\-_\s\.]+)',
                r'Model[:\s]*([A-Za-z0-9\-_\s\.]+)',
                r'Model Number[:\s]*([A-Za-z0-9\-_\s\.]+)',
                r'Serial[:\s]*([A-Za-z0-9\-_\s\.]+)'
            ]
            
            # Try to find SKU
            if not product_data.get('sku') or product_data['sku'] in ['/ Item Code:', 'Item Code:', '']:
                for pattern in sku_patterns:
                    matches = re.findall(pattern, page_source, re.IGNORECASE)
                    for match in matches:
                        if (match and len(match) >= 3 and 
                            match not in ['/ Item Code:', 'Item Code:', 'Feature', 'Value', '{'] and
                            not match.startswith('/') and
                            not match.startswith('{') and
                            match.isalnum()):  # Only alphanumeric
                            product_data['sku'] = match
                            self.logger.info(f"   DEBUG: Found potential SKU: {match}")
                            break
                    if product_data.get('sku') and product_data['sku'] not in ['/ Item Code:', 'Item Code:', '']:
                        break
            
            # Try to find Model
            if not product_data.get('model') or product_data['model'] in ['/ Serial Number:', 'Serial Number:', '']:
                for pattern in model_patterns:
                    matches = re.findall(pattern, page_source, re.IGNORECASE)
                    for match in matches:
                        if (match and len(match) >= 3 and 
                            match not in ['/ Serial Number:', 'Serial Number:', 'Feature', 'Value', '{'] and
                            not match.startswith('/') and
                            not match.startswith('{') and
                            match.isalnum()):  # Only alphanumeric
                            product_data['model'] = match
                            self.logger.info(f"   DEBUG: Found potential Model: {match}")
                            break
                    if product_data.get('model') and product_data['model'] not in ['/ Serial Number:', 'Serial Number:', '']:
                        break
            
            # If still not found, look for any alphanumeric codes that might be SKU/Model
            if (not product_data.get('sku') or product_data['sku'] in ['/ Item Code:', 'Item Code:', ''] or
                not product_data.get('model') or product_data['model'] in ['/ Serial Number:', 'Serial Number:', '']):
                
                # Look for codes in the format like "838007" from the description
                potential_codes = re.findall(r'\b([A-Za-z0-9]{6,10})\b', page_source)
                
                for code in potential_codes:
                    if (code and code.isalnum() and len(code) >= 6 and
                        code not in ['/ Item Code:', 'Item Code:', '/ Serial Number:', 'Serial Number:', 'Feature', 'Value', '{'] and
                        not code.startswith('/') and not code.startswith('{')):
                        
                        # If we don't have SKU, use this as SKU
                        if not product_data.get('sku') or product_data['sku'] in ['/ Item Code:', 'Item Code:', '']:
                            product_data['sku'] = code
                            self.logger.info(f"   DEBUG: Using potential code as SKU: {code}")
                            break
                        # If we don't have Model, use this as Model
                        elif not product_data.get('model') or product_data['model'] in ['/ Serial Number:', 'Serial Number:', '']:
                            product_data['model'] = code
                            self.logger.info(f"   DEBUG: Using potential code as Model: {code}")
                            break
                            
        except Exception as e:
            self.logger.debug(f"Error in debug extraction: {e}")

    def _extract_brand_supplier_fallback(self, product_data):
        """Fallback method to extract brand and supplier from page source"""
        try:
            page_source = self.driver.page_source
            
            # Look for brand patterns
            if not product_data.get('brand'):
                brand_patterns = [
                    r'Brand[:\s]+([^<\n,]+)',
                    r'Manufacturer[:\s]+([^<\n,]+)',
                    r'Make[:\s]+([^<\n,]+)',
                    r'Tenby',  # Known brand from the data
                    r'Brand[:\s]*([A-Za-z\s]+)'
                ]
                
                import re
                for pattern in brand_patterns:
                    matches = re.findall(pattern, page_source, re.IGNORECASE)
                    if matches:
                        brand = matches[0].strip()
                        if (brand and len(brand) > 0 and len(brand) < 100 and
                            brand not in ['Feature', 'Value', '{'] and
                            not brand.startswith('/')):
                            product_data['brand'] = brand
                            self.logger.info(f"   Fallback: Found Brand: {brand}")
                            break
            
            # Look for supplier patterns
            if not product_data.get('supplier'):
                supplier_patterns = [
                    r'Supplier[:\s]+([^<\n,]+)',
                    r'Vendor[:\s]+([^<\n,]+)',
                    r'Distributor[:\s]+([^<\n,]+)',
                    r'Sold by[:\s]+([^<\n,]+)',
                    r'Khalid and Naeem Trading',  # Known supplier from the data
                    r'Supplier[:\s]*([A-Za-z\s]+)'
                ]
                
                for pattern in supplier_patterns:
                    matches = re.findall(pattern, page_source, re.IGNORECASE)
                    if matches:
                        supplier = matches[0].strip()
                        if (supplier and len(supplier) > 0 and len(supplier) < 200 and
                            supplier not in ['Feature', 'Value', '{'] and
                            not supplier.startswith('/')):
                            product_data['supplier'] = supplier
                            self.logger.info(f"   Fallback: Found Supplier: {supplier}")
                            break
                            
        except Exception as e:
            self.logger.debug(f"Error in brand/supplier fallback extraction: {e}")

    def _extract_main_category(self, product_data):
        """Extract Main Category from specific HTML structure"""
        try:
            if product_data.get('main_category'):
                return  # Already found
            
            # Look for the specific HTML structure for Main Category
            main_category_selectors = [
                # Look for span with title attribute containing the full category
                # "span[title*='Electrical Systems']",
                # "span[title*='Lighting']",
                # "span[title*='Components']",
                # "span[title*='Accessories']",
                # "span[title*='Supplies']",
                # Look for spans with cursor-help class
                "span.cursor-help[title]",
                # Look for spans near "Main Category:" text
                "span:contains('Main Category:') + span",
                "span:contains('Main Category:') ~ span"
            ]
            
            for selector in main_category_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        # Get the title attribute which contains the full text
                        title_attr = element.get_attribute('title')
                        if title_attr and len(title_attr) > 10:
                            # Clean up the title text
                            main_category = title_attr.strip()
                            if (main_category and 
                                'Electrical' in main_category and 
                                len(main_category) > 20):
                                product_data['main_category'] = main_category
                                self.logger.info(f"   Found Main Category: {main_category}")
                                return
                                
                except Exception as e:
                    self.logger.debug(f"Main category selector failed {selector}: {e}")
                    continue
            
            # JavaScript extraction for Main Category
            js_script = """
            var mainCategory = '';
            
            // Look for spans with cursor-help class and title attribute
            var cursorHelpSpans = document.querySelectorAll('span.cursor-help[title]');
            for (var i = 0; i < cursorHelpSpans.length; i++) {
                var span = cursorHelpSpans[i];
                var title = span.getAttribute('title');
                if (title && title.includes('Electrical') && title.length > 20) {
                    mainCategory = title.trim();
                    break;
                }
            }
            
            // If not found, look for spans near "Main Category:" text
            if (!mainCategory) {
                var allSpans = document.querySelectorAll('span');
                for (var i = 0; i < allSpans.length; i++) {
                    var span = allSpans[i];
                    var text = span.textContent || span.innerText || '';
                    if (text.includes('Main Category:')) {
                        // Look for the next span or sibling span with title
                        var nextSpan = span.nextElementSibling;
                        if (nextSpan && nextSpan.tagName === 'SPAN') {
                            var title = nextSpan.getAttribute('title');
                            if (title && title.includes('Electrical')) {
                                mainCategory = title.trim();
                                break;
                            }
                        }
                        
                        // Look for parent's next sibling
                        var parent = span.parentElement;
                        if (parent) {
                            var siblings = parent.querySelectorAll('span[title]');
                            for (var j = 0; j < siblings.length; j++) {
                                var title = siblings[j].getAttribute('title');
                                if (title && title.includes('Electrical')) {
                                    mainCategory = title.trim();
                                    break;
                                }
                            }
                        }
                    }
                }
            }
            
            return mainCategory;
            """
            
            try:
                js_result = self.driver.execute_script(js_script)
                if js_result and len(js_result) > 20:
                    product_data['main_category'] = js_result
                    self.logger.info(f"   Found Main Category (JavaScript): {js_result}")
                    return
            except Exception as e:
                self.logger.debug(f"JavaScript main category extraction failed: {e}")
                            
        except Exception as e:
            self.logger.debug(f"Error extracting main category: {e}")

    def _extract_category(self, product_data):
        """Extract Category from specific HTML structure"""
        try:
            if product_data.get('category'):
                return  # Already found
            
            # Look for the specific HTML structure for Category
            category_selectors = [
                # Look for span with title attribute containing the full category
                "span[title*='Electrical switches']",
                "span[title*='accessories']",
                "span[title*='switches']",
                # Look for spans with cursor-help class
                "span.cursor-help[title]",
                # Look for spans near "Category:" text
                "span:contains('Category:') + span",
                "span:contains('Category:') ~ span"
            ]
            
            for selector in category_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        # Get the title attribute which contains the full text
                        title_attr = element.get_attribute('title')
                        if title_attr and len(title_attr) > 5:
                            # Clean up the title text
                            category = title_attr.strip()
                            
                            # First priority: exact match
                            if category == 'Electrical switches and accessories':
                                product_data['category'] = category
                                self.logger.info(f"   Found exact Category: {category}")
                                return
                            
                            # Second priority: contains the full text
                            elif (category and 
                                  'Electrical switches and accessories' in category and 
                                  len(category) > 20):
                                product_data['category'] = 'Electrical switches and accessories'
                                self.logger.info(f"   Found complete Category: {product_data['category']}")
                                return
                            
                            # Third priority: partial matches
                            elif (category and 
                                  ('Electrical' in category or 'switches' in category.lower() or 'accessories' in category.lower()) and 
                                  len(category) > 10):
                                product_data['category'] = category
                                self.logger.info(f"   Found Category: {category}")
                                return
                                
                except Exception as e:
                    self.logger.debug(f"Category selector failed {selector}: {e}")
                    continue
            
            # JavaScript extraction for Category
            js_script = """
            var category = '';
            
            // Strategy 1: Look for spans with cursor-help class and title attribute
            var cursorHelpSpans = document.querySelectorAll('span.cursor-help[title]');
            for (var i = 0; i < cursorHelpSpans.length; i++) {
                var span = cursorHelpSpans[i];
                var title = span.getAttribute('title');
                var visibleText = span.textContent || span.innerText || '';
                
                // Prefer the title attribute if it's longer and contains relevant keywords
                if (title && title.length > visibleText.length && 
                    (title.includes('Electrical') || title.includes('switches') || title.includes('accessories'))) {
                    category = title.trim();
                    break;
                }
            }
            
            // Strategy 2: Look for spans near "Category:" text specifically
            if (!category) {
                var allSpans = document.querySelectorAll('span');
                for (var i = 0; i < allSpans.length; i++) {
                    var span = allSpans[i];
                    var text = span.textContent || span.innerText || '';
                    if (text.includes('Category:')) {
                        // Look for the next span or sibling span with title
                        var nextSpan = span.nextElementSibling;
                        if (nextSpan && nextSpan.tagName === 'SPAN') {
                            var title = nextSpan.getAttribute('title');
                            var nextText = nextSpan.textContent || nextSpan.innerText || '';
                            
                            // Use title if it's longer and more complete
                            if (title && title.length > nextText.length && 
                                (title.includes('Electrical') || title.includes('switches') || title.includes('accessories'))) {
                                category = title.trim();
                                break;
                            }
                        }
                        
                        // Look for parent's next sibling
                        var parent = span.parentElement;
                        if (parent) {
                            var siblings = parent.querySelectorAll('span[title]');
                            for (var j = 0; j < siblings.length; j++) {
                                var title = siblings[j].getAttribute('title');
                                var siblingText = siblings[j].textContent || siblings[j].innerText || '';
                                
                                // Use title if it's longer and more complete
                                if (title && title.length > siblingText.length && 
                                    (title.includes('Electrical') || title.includes('switches') || title.includes('accessories'))) {
                                    category = title.trim();
                                    break;
                                }
                            }
                        }
                    }
                }
            }
            
            // Strategy 3: Look for any span with title containing the full category
            if (!category) {
                var allSpansWithTitle = document.querySelectorAll('span[title]');
                for (var i = 0; i < allSpansWithTitle.length; i++) {
                    var span = allSpansWithTitle[i];
                    var title = span.getAttribute('title');
                    var visibleText = span.textContent || span.innerText || '';
                    
                    // Check if this looks like a category with full text
                    if (title && title.includes('Electrical switches and accessories') && title.length > visibleText.length) {
                        category = title.trim();
                        break;
                    }
                }
            }
            
            return category;
            """
            
            try:
                js_result = self.driver.execute_script(js_script)
                if js_result and len(js_result) > 10:
                    product_data['category'] = js_result
                    self.logger.info(f"   Found Category (JavaScript): {js_result}")
                    return
            except Exception as e:
                self.logger.debug(f"JavaScript category extraction failed: {e}")
            
            # Fallback: Look for the specific text pattern in the page
            page_source = self.driver.page_source
            
            # First, try to find the exact complete category text
            import re
            exact_category_pattern = r'<span[^>]*title="([^"]*Electrical switches and accessories[^"]*)"[^>]*>'
            exact_matches = re.findall(exact_category_pattern, page_source, re.IGNORECASE | re.DOTALL)
            if exact_matches:
                for match in exact_matches:
                    category = match.strip()
                    if category and 'Electrical switches and accessories' in category:
                        product_data['category'] = 'Electrical switches and accessories'
                        self.logger.info(f"   Found exact Category: {product_data['category']}")
                        return
                            
        except Exception as e:
            self.logger.debug(f"Error extracting category: {e}")

    def _extract_unspsc_code(self, product_data):
        """Enhanced UNSPSC code extraction"""
        try:
            if product_data.get('unspsc'):
                return  # Already found
            
            page_text = self.driver.page_source
            
            # Comprehensive UNSPSC patterns
            unspsc_patterns = [
                r'UNSPSC[:\s]*([0-9]{8,12})',
                r'UNSPC[:\s]*([0-9]{8,12})',
                r'unspsc code[:\s]*([0-9]{8,12})',
                r'unspc code[:\s]*([0-9]{8,12})',
                r'classification[:\s]*([0-9]{8,12})',
                r'UNSPSC[:\s]*([0-9]{4,4}-[0-9]{2,2}-[0-9]{2,2})',
                r'UNSPC[:\s]*([0-9]{4,4}-[0-9]{2,2}-[0-9]{2,2})',
                # Look for 8-12 digit numbers that might be UNSPSC
                r'([0-9]{8,12})(?:\s|$|</)',
                # Look for 4-2-2 format
                r'([0-9]{4,4}-[0-9]{2,2}-[0-9]{2,2})(?:\s|$|</)'
            ]
            
            import re
            for pattern in unspsc_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    for match in matches:
                        # Clean the match
                        code = re.sub(r'[^0-9\-]', '', str(match))
                        
                        # Validate UNSPSC format
                        if (len(code) >= 8 and 
                            (len(code) == 8 or len(code) == 10 or len(code) == 12) and
                            code.isdigit()):
                            product_data['unspsc'] = code
                            self.logger.info(f"   Found UNSPSC: {code}")
                            return
                        elif '-' in code and len(code) == 10:  # 4-2-2 format
                            product_data['unspsc'] = code
                            self.logger.info(f"   Found UNSPSC: {code}")
                            return
            
            # Look in specific elements that might contain UNSPSC
            unspsc_selectors = [
                "[class*='unspsc']",
                "[class*='unspc']", 
                "[class*='classification']",
                "[id*='unspsc']",
                "[id*='unspc']"
            ]
            
            for selector in unspsc_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text
                        # Look for 8-12 digit numbers
                        numbers = re.findall(r'[0-9]{8,12}', text)
                        if numbers:
                            code = numbers[0]
                            if len(code) >= 8:
                                product_data['unspsc'] = code
                                self.logger.info(f"   Found UNSPSC in element: {code}")
                                return
                except Exception as e:
                    self.logger.debug(f"UNSPSC selector failed {selector}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.debug(f"Error extracting UNSPSC: {e}")

    def _clean_extracted_data(self, product_data):
        """Clean up extracted data to remove invalid entries and duplicates"""
        try:
            # Fields to clean
            fields_to_clean = ['brand', 'supplier', 'manufactured_country', 'sku', 'model', 'unspsc', 'category', 'main_category']
            
            for field in fields_to_clean:
                if field in product_data and product_data[field]:
                    value = str(product_data[field]).strip()
                    
                    # Remove invalid values
                    invalid_patterns = [
                        '/ Item Code:',
                        '/ Serial Number:',
                        'Item Code:',
                        'Serial Number:',
                        'Feature',
                        'Value',
                        '{',
                        '}',
                        '/68453e3dce9b0a422ee865ac">',
                        'Feature:',
                        'Value:'
                    ]
                    
                    # Check if value is invalid
                    is_invalid = False
                    for pattern in invalid_patterns:
                        if pattern in value:
                            is_invalid = True
                            break
                    
                    # Additional validation - less strict for brand and supplier
                    if is_invalid:
                        product_data[field] = ''
                    elif len(value) < 1:
                        product_data[field] = ''
                    elif field in ['sku', 'model'] and (value.startswith('/') or value.startswith('{') or value in ['Feature', 'Value', 'Feature:', 'Value:']):
                        product_data[field] = ''
                    elif field in ['brand', 'supplier'] and (value.startswith('/') or value.startswith('{')):
                        product_data[field] = ''
                    elif value.endswith('...') and len(value) < 10:
                        product_data[field] = ''
                    else:
                        # Clean up the value
                        # Remove HTML-like content
                        import re
                        cleaned_value = re.sub(r'<[^>]+>', '', value)
                        # Remove excessive whitespace
                        cleaned_value = re.sub(r'\s+', ' ', cleaned_value).strip()
                        # Remove trailing dots if too many
                        if cleaned_value.endswith('...') and len(cleaned_value) > 20:
                            cleaned_value = cleaned_value[:-3].strip()
                        
                        product_data[field] = cleaned_value
            
            # Remove duplicate data from key_attributes if it exists in main fields
            if 'key_attributes' in product_data:
                main_fields = {
                    'Brand': 'brand',
                    'Model': 'model', 
                    'Category': 'category'
                }
                
                for attr_key, main_field in main_fields.items():
                    if (attr_key in product_data['key_attributes'] and 
                        main_field in product_data and 
                        product_data[main_field]):
                        # Remove from key_attributes if it's a duplicate
                        if (product_data['key_attributes'][attr_key] == product_data[main_field] or
                            product_data['key_attributes'][attr_key] in ['/ Item Code:', '/ Serial Number:', '{', 'Value']):
                            del product_data['key_attributes'][attr_key]
            
        except Exception as e:
            self.logger.debug(f"Error cleaning extracted data: {e}")
    
    def _debug_page_content(self, search_term):
        """Debug what's actually on the page when no elements are found"""
        try:
            self.logger.info("🔍 DEBUGGING PAGE CONTENT:")
            
            # Check page source for search keywords
            page_source = self.driver.page_source.lower()
            search_keywords = self._extract_search_keywords(search_term)
            
            for keyword in search_keywords:
                count = page_source.count(keyword)
                self.logger.info(f"   '{keyword}' appears {count} times on page")
            
            # Check for common elements
            common_selectors = [
                ("div elements", "div"),
                ("links", "a"),
                ("images", "img"),
                ("buttons", "button"),
                ("spans", "span"),
                ("paragraphs", "p")
            ]
            
            for name, selector in common_selectors:
                try:
                    elements = self.driver.find_elements(By.TAG_NAME, selector)
                    self.logger.info(f"   Found {len(elements)} {name}")
                except:
                    pass
            
            # Check for product-related classes
            product_classes = [
                ".product", "[class*='product']", ".item", "[class*='item']",
                ".card", "[class*='card']", ".result", "[class*='result']"
            ]
            
            for selector in product_classes:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        self.logger.info(f"   Found {len(elements)} elements with selector: {selector}")
                except:
                    pass
            
            # Check if there's a "no results" message
            no_result_indicators = ["no results", "not found", "no products", "no items"]
            for indicator in no_result_indicators:
                if indicator in page_source:
                    self.logger.warning(f"   ⚠️  Page contains '{indicator}' - may be no search results")
            
        except Exception as e:
            self.logger.debug(f"Debug analysis failed: {e}")
    
    def extract_product_details(self, url, search_term=None, product_folder=None):
        """Enhanced extraction with better attribute and description finding"""
        try:
            self.logger.info(f"Extracting details from: {url}")
            
            # Navigate to product page
            self.driver.get(url)
            time.sleep(5)
            
            # Initialize product data
            product_data = {
                'url': url,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'title': '',
                'brand': '',
                'supplier': '',
                'category': '',
                'sku': '',
                'model': '',
                'description': '',
                'key_attributes': {},
                'technical_specifications': {},
                'image_downloaded': False,
                'extraction_success': {
                    'title': False,
                    'attributes': False,
                    'description': False,
                    'image': False
                }
            }
            
            self.logger.info("🔍 Step 1: Extracting product title and basic info...")
            self._extract_title_and_basic_info(product_data)
            
            self.logger.info("🔍 Step 2: Extracting key attributes and specifications...")
            self._extract_key_attributes(product_data)
            
            self.logger.info("🔍 Step 3: Extracting product description...")
            self._extract_product_description(product_data)
            
            self.logger.info("🔍 Step 4: Downloading product image...")
            if self.download_images:
                self._download_product_image(product_data, product_folder)
            
            # Log extraction success
            success = product_data['extraction_success']
            self.logger.info(f"✅ Extraction Summary:")
            self.logger.info(f"   Title: {'✅' if success['title'] else '❌'}")
            self.logger.info(f"   Attributes: {'✅' if success['attributes'] else '❌'} ({len(product_data['key_attributes'])} found)")
            self.logger.info(f"   Description: {'✅' if success['description'] else '❌'} ({len(product_data['description'])} chars)")
            self.logger.info(f"   Image: {'✅' if success['image'] else '❌'}")
            
            return product_data
            
        except Exception as e:
            self.logger.error(f"Error extracting product details: {e}")
            return None
    

    def _extract_brand_and_supplier_info(self, product_data, page_source):
        """Extract brand and supplier information dynamically"""
        try:
            # Common brand patterns to look for
            brand_patterns = [
                r'brand[:\s]+([^<\n,]+)',
                r'manufacturer[:\s]+([^<\n,]+)',
                r'make[:\s]+([^<\n,]+)'
            ]
            
            import re
            for pattern in brand_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches:
                    brand = matches[0].strip()
                    if brand and len(brand) < 50:  # Reasonable brand name length
                        product_data['brand'] = brand
                        break
            
            # Common supplier patterns
            supplier_patterns = [
                r'supplier[:\s]+([^<\n,]+)',
                r'sold by[:\s]+([^<\n,]+)',
                r'vendor[:\s]+([^<\n,]+)',
                r'distributed by[:\s]+([^<\n,]+)'
            ]
            
            for pattern in supplier_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches:
                    supplier = matches[0].strip()
                    if supplier and len(supplier) < 100:  # Reasonable supplier name length
                        product_data['supplier'] = supplier
                        break
                        
        except Exception as e:
            self.logger.debug(f"Error extracting brand/supplier: {e}")
    
    # def _extract_category_info(self, product_data, page_source):
    #     """Extract category information dynamically"""
    #     try:
    #         # Common category patterns
    #         category_patterns = [
    #             r'category[:\s]+([^<\n,]+)',
    #             r'product category[:\s]+([^<\n,]+)',
    #             r'type[:\s]+([^<\n,]+)',
    #             r'classification[:\s]+([^<\n,]+)'
    #         ]
            
    #         import re
    #         for pattern in category_patterns:
    #             matches = re.findall(pattern, page_source, re.IGNORECASE)
    #             if matches:
    #                 category = matches[0].strip()
    #                 if category and len(category) < 100:  # Reasonable category length
    #                     product_data['category'] = category
    #                     break
            
    #         # If no specific category found, try to infer from search term
    #         if not product_data['category']:
    #             search_term_lower = product_data.get('title', '').lower()
    #             if any(term in search_term_lower for term in ['socket', 'switch', 'electrical']):
    #                 product_data['category'] = "Electrical Components"
    #             elif any(term in search_term_lower for term in ['phone', 'telephone', 'telecom']):
    #                 product_data['category'] = "Telecommunications"
    #             elif any(term in search_term_lower for term in ['cable', 'wire', 'connector']):
    #                 product_data['category'] = "Electrical Accessories"
                    
    #     except Exception as e:
    #         self.logger.debug(f"Error extracting category: {e}")
    
    def _extract_key_attributes(self, product_data):
        """Enhanced extraction of key attributes and specifications"""
        try:
            attributes_found = 0
            
            # Strategy 1: Extract from tables (most common for specifications)
            self.logger.info("   Looking for specification tables...")
            table_selectors = [
                "table",
                ".specifications table",
                ".specs table", 
                ".product-specs table",
                ".attributes table",
                ".technical-details table"
            ]
            
            for selector in table_selectors:
                try:
                    tables = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for table in tables:
                        rows = table.find_elements(By.CSS_SELECTOR, "tr")
                        for row in rows:
                            cells = row.find_elements(By.CSS_SELECTOR, "td, th")
                            if len(cells) >= 2:
                                key = cells[0].text.strip()
                                value = cells[1].text.strip()
                                if self._is_valid_attribute(key, value):
                                    product_data['key_attributes'][key] = value
                                    attributes_found += 1
                                    
                    if attributes_found > 0:
                        self.logger.info(f"   Found {attributes_found} attributes from tables")
                        break
                        
                except Exception as e:
                    self.logger.debug(f"Table extraction failed for {selector}: {e}")
                    continue
            
            # Strategy 2: Extract from definition lists
            self.logger.info("   Looking for definition lists...")
            try:
                dl_elements = self.driver.find_elements(By.CSS_SELECTOR, "dl")
                for dl in dl_elements:
                    dts = dl.find_elements(By.CSS_SELECTOR, "dt")
                    dds = dl.find_elements(By.CSS_SELECTOR, "dd")
                    
                    for dt, dd in zip(dts, dds):
                        key = dt.text.strip()
                        value = dd.text.strip()
                        if self._is_valid_attribute(key, value):
                            product_data['key_attributes'][key] = value
                            attributes_found += 1
                            
                if len(dts) > 0:
                    self.logger.info(f"   Found {len(dts)} attributes from definition lists")
                    
            except Exception as e:
                self.logger.debug(f"Definition list extraction failed: {e}")
            
            # Strategy 3: Extract from labeled divs/spans
            self.logger.info("   Looking for labeled specifications...")
            label_selectors = [
                ".spec-item",
                ".attribute-item", 
                ".product-detail",
                ".feature-item",
                "[class*='spec']",
                "[class*='attribute']"
            ]
            
            for selector in label_selectors:
                try:
                    items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for item in items:
                        # Look for label:value patterns
                        text = item.text.strip()
                        if ':' in text:
                            parts = text.split(':', 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                value = parts[1].strip()
                                if self._is_valid_attribute(key, value):
                                    product_data['key_attributes'][key] = value
                                    attributes_found += 1
                                    
                except Exception as e:
                    self.logger.debug(f"Labeled spec extraction failed for {selector}: {e}")
                    continue
            
            # Strategy 4: Extract from page source patterns
            self.logger.info("   Analyzing page source for specifications...")
            page_source = self.driver.page_source
            
            # Common specification patterns
            spec_patterns = [
                (r'Material[:\s]*([^<\n]+)', 'Material'),
                (r'Color[:\s]*([^<\n]+)', 'Color'),
                (r'Voltage[:\s]*([^<\n]+)', 'Voltage'),
                (r'Current[:\s]*([^<\n]+)', 'Current'),
                (r'Rating[:\s]*([^<\n]+)', 'Rating'),
                (r'Standard[:\s]*([^<\n]+)', 'Standard'),
                (r'Gang[:\s]*([^<\n]+)', 'Gang'),
                (r'Mounting[:\s]*([^<\n]+)', 'Mounting'),
                (r'Finish[:\s]*([^<\n]+)', 'Finish'),
                (r'Type[:\s]*([^<\n]+)', 'Type'),
                (r'Brand[:\s]*([^<\n]+)', 'Brand'),
                (r'Model[:\s]*([^<\n]+)', 'Model'),
                (r'UNSPSC[:\s]*([^<\n]+)', 'UNSPSC'),
                (r'Category[:\s]*([^<\n]+)', 'Category')
            ]
            
            import re
            for pattern, key in spec_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches:
                    value = matches[0].strip()
                    if self._is_valid_attribute(key, value):
                        product_data['key_attributes'][key] = value
                        attributes_found += 1
            
            # Clean up any invalid attributes that might have been extracted
            self._clean_key_attributes(product_data)
            
            # Mark success if we found attributes
            if len(product_data['key_attributes']) > 0:
                product_data['extraction_success']['attributes'] = True
                self.logger.info(f"   ✅ Total attributes found: {len(product_data['key_attributes'])}")
            else:
                self.logger.warning("   ❌ No attributes found")
                
        except Exception as e:
            self.logger.error(f"Error extracting attributes: {e}")
    
    def _is_valid_attribute(self, key, value):
        """Validate if a key-value pair is a valid attribute"""
        try:
            # Basic validation
            if not key or not value:
                return False
            
            # Check key length
            if len(key) >= 50:
                return False
            
            # Check value length
            if len(value) >= 200:
                return False
            
            # Invalid key patterns
            invalid_keys = ['Feature', 'Value', 'Key', 'Attribute']
            if key in invalid_keys:
                return False
            
            # Invalid value patterns
            invalid_values = [
                '/ Item Code:', '/ Serial Number:', 'Item Code:', 'Serial Number:',
                'Feature', 'Value', '{', '}', '...', 'design ideal for creating',
                'in any electrical setup', 'For resident', 'resident...',
                '/68453e3dce9b0a422ee865ac">'
            ]
            
            for invalid_val in invalid_values:
                if invalid_val in value:
                    return False
            
            # Check for incomplete or placeholder values
            if (value.startswith('/') or 
                value.startswith('{') or 
                value.endswith('...') or
                value.count('...') > 2 or
                len(value.split()) > 20):  # Too many words
                return False
            
            # Check for repetitive text
            if value.count('electrical setup') > 0 or value.count('resident') > 1:
                return False
            
            # Check for HTML-like content
            if '<' in value and '>' in value:
                return False
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Error validating attribute: {e}")
            return False
    
    def _clean_key_attributes(self, product_data):
        """Clean up key attributes to remove invalid entries"""
        try:
            if 'key_attributes' not in product_data:
                return
            
            # Invalid patterns to remove
            invalid_patterns = [
                '/ Item Code:', '/ Serial Number:', 'Item Code:', 'Serial Number:',
                'Feature', 'Value', '{', '}', 'design ideal for creating',
                'in any electrical setup', 'For resident', 'resident...',
                '/68453e3dce9b0a422ee865ac">'
            ]
            
            # Keys to remove
            keys_to_remove = []
            
            for key, value in product_data['key_attributes'].items():
                should_remove = False
                
                # Check for invalid patterns in value
                for pattern in invalid_patterns:
                    if pattern in str(value):
                        should_remove = True
                        break
                
                # Check for incomplete values
                if (str(value).startswith('/') or 
                    str(value).startswith('{') or 
                    str(value).endswith('...') or
                    str(value).count('...') > 2 or
                    len(str(value).split()) > 20):
                    should_remove = True
                
                # Check for repetitive text
                if (str(value).count('electrical setup') > 0 or 
                    str(value).count('resident') > 1):
                    should_remove = True
                
                # Check for HTML-like content
                if '<' in str(value) and '>' in str(value):
                    should_remove = True
                
                # Remove UNSPSC entries with just ":" value
                if key == 'UNSPSC' and str(value).strip() == ':':
                    should_remove = True
                
                # Remove empty or invalid values
                if str(value).strip() in ['', ':', 'N/A', 'Not available', 'None']:
                    should_remove = True
                
                if should_remove:
                    keys_to_remove.append(key)
            
            # Remove invalid attributes
            for key in keys_to_remove:
                del product_data['key_attributes'][key]
                self.logger.debug(f"   Removed invalid attribute: {key}")
                
        except Exception as e:
            self.logger.debug(f"Error cleaning key attributes: {e}")
    
    def _extract_product_description(self, product_data):
        """Extract full product description by clicking the Product Description tab/button"""
        try:
            descriptions = []
            
            # Step 1: Find and click the "Product Description" tab/button
            self.logger.info("   Looking for Product Description tab/button...")
            
            description_clicked = False
            click_selectors = [
                # Text-based selectors for clickable elements
                "//button[contains(text(), 'Product Description')]",
                "//a[contains(text(), 'Product Description')]", 
                "//div[contains(text(), 'Product Description') and (@onclick or @role='button' or @class*='clickable')]",
                "//span[contains(text(), 'Product Description')]/parent::*[@onclick or @role='button']",
                "//li[contains(text(), 'Product Description')]",
                "//tab[contains(text(), 'Product Description')]",
                # CSS selectors for common tab patterns
                ".tab[data-tab*='description']",
                ".tab-button[data-target*='description']",
                "[role='tab'][aria-controls*='description']",
                ".nav-item:contains('Product Description')",
                ".tab:contains('Product Description')",
                # Generic clickable elements containing the text
                "*[onclick]:contains('Product Description')",
                "button:contains('Product Description')",
                "a:contains('Product Description')"
            ]
            
            for selector in click_selectors:
                try:
                    if selector.startswith("//") or selector.startswith("*"):
                        # XPath selectors
                        if ":contains(" in selector:
                            # Convert CSS :contains to XPath
                            text_part = selector.split(":contains('")[1].split("')")[0]
                            element_part = selector.split(":contains(")[0]
                            xpath_selector = f"//{element_part}[contains(text(), '{text_part}')]"
                            elements = self.driver.find_elements(By.XPATH, xpath_selector)
                        else:
                            elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS selectors with :contains need special handling
                        if ":contains(" in selector:
                            # Skip CSS :contains as it's not supported in Selenium
                            continue
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        try:
                            # Check if element is clickable and visible
                            if element.is_displayed() and element.is_enabled():
                                self.logger.info(f"   Found clickable element: {element.text[:50]}...")
                                
                                # Scroll to element
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                                time.sleep(1)
                                
                                # Try clicking
                                try:
                                    element.click()
                                except:
                                    # Fallback to JavaScript click
                                    self.driver.execute_script("arguments[0].click();", element)
                                
                                time.sleep(2)  # Wait for content to load
                                description_clicked = True
                                self.logger.info("   ✅ Successfully clicked Product Description tab")
                                break
                                
                        except Exception as e:
                            self.logger.debug(f"Failed to click element: {e}")
                            continue
                    
                    if description_clicked:
                        break
                        
                except Exception as e:
                    self.logger.debug(f"Selector failed {selector}: {e}")
                    continue
            
            if not description_clicked:
                self.logger.warning("   ⚠️ Could not find/click Product Description tab, trying direct extraction")
            
            # Step 2: Extract the full description after clicking (or direct extraction)
            time.sleep(2)  # Allow content to fully load
            
            # JavaScript extraction for complete text after tab click
            js_script = """
            var descriptions = [];
            
            // Look for description content that might be revealed after clicking
            var selectors = [
                // Common description container selectors after tab click
                '.tab-content .description',
                '.tab-pane.active .description', 
                '[role="tabpanel"][aria-expanded="true"] .description',
                '.product-description-content',
                '.description-panel',
                '.tab-content p',
                '.description-tab-content',
                // General description selectors
                'p.text-gray-700.text-sm.leading-relaxed.mb-6',
                'p[class*="text-gray-700"]',
                '.product-description', 
                '.description',
                '[class*="description"]',
                // Look for any substantial paragraphs
                'p'
            ];
            
            selectors.forEach(sel => {
                try {
                    document.querySelectorAll(sel).forEach(el => {
                        // Get full text content
                        var text = el.textContent || el.innerText || '';
                        text = text.trim();
                        
                        // Filter for substantial, relevant content
                        if (text.length > 100 && 
                            !text.toLowerCase().includes("couldn't find") &&
                            !text.toLowerCase().includes("sourcing team") &&
                            !text.toLowerCase().includes("don't worry") &&
                            !text.toLowerCase().includes("discover, connect")) {
                            descriptions.push({
                                text: text,
                                selector: sel,
                                length: text.length
                            });
                        }
                    });
                } catch(e) {}
            });
            
            // Sort by length (longest first)
            return descriptions.sort((a,b) => b.length - a.length);
            """
            
            js_results = self.driver.execute_script(js_script)
            if js_results and len(js_results) > 0:
                for desc in js_results:
                    descriptions.append(desc['text'])
                self.logger.info(f"   JavaScript found {len(js_results)} descriptions after tab click")
            
            # Fallback: Enhanced Selenium extraction
            if not descriptions:
                fallback_selectors = [
                    # Tab content selectors
                    ".tab-content .description",
                    ".tab-pane.active",
                    "[role='tabpanel'][aria-expanded='true']",
                    ".product-description-content",
                    # General selectors
                    "p.text-gray-700.text-sm.leading-relaxed.mb-6",
                    "p[class*='text-gray-700']", 
                    ".product-description",
                    ".description",
                    "[class*='description']"
                ]
                
                for selector in fallback_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for el in elements:
                            # Try textContent first (most complete)
                            text = el.get_attribute('textContent')
                            if not text:
                                text = el.get_attribute('innerText')
                            if not text:
                                text = el.text
                            
                            if text and len(text.strip()) > 100:
                                clean_text = text.strip()
                                # Skip generic messages
                                if not any(skip in clean_text.lower() for skip in [
                                    "couldn't find", "sourcing team", "don't worry", "discover, connect"
                                ]):
                                    descriptions.append(clean_text)
                                    self.logger.info(f"   Found description with selector: {selector}")
                        
                        if descriptions:
                            break
                            
                    except Exception as e:
                        self.logger.debug(f"Fallback selector failed {selector}: {e}")
                        continue
            
            # Step 3: Process and set the best description
            if descriptions:
                # Remove duplicates and sort by length
                unique_descriptions = list(dict.fromkeys(descriptions))
                unique_descriptions.sort(key=len, reverse=True)
                
                best_description = unique_descriptions[0]
                product_data['description'] = best_description
                product_data['extraction_success']['description'] = True
                self.logger.info(f"   ✅ Full description extracted: {len(best_description)} chars")
                
                # Store alternatives
                if len(unique_descriptions) > 1:
                    product_data['alternative_descriptions'] = unique_descriptions[1:3]
                    
            else:
                product_data['description'] = "Not found"
                product_data['extraction_success']['description'] = False
                self.logger.warning("   ❌ No description found even after trying to click tab")
                
        except Exception as e:
            self.logger.error(f"Error extracting description: {e}")
            product_data['description'] = "Not found"
            product_data['extraction_success']['description'] = False
        
    def _download_product_image(self, product_data, product_folder=None):
        """Download product image after successful attribute extraction"""
        try:
            # Only download image if we have successfully extracted attributes or description
            success = product_data['extraction_success']
            if not (success['attributes'] or success['description']):
                self.logger.info("   Skipping image download - no attributes/description extracted")
                return
            
            images_found = []
            
            # Strategy 1: Look for main product images
            img_selectors = [
                ".product-image img",
                ".main-image img",
                ".item-image img",
                "img[alt*='product' i]",
                "img[class*='product' i]",
                "img[src*='product' i]",
                ".gallery img",
                ".carousel img"
            ]
            
            for selector in img_selectors:
                try:
                    images = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for img in images:
                        src = img.get_attribute("src")
                        alt = img.get_attribute("alt") or ""
                        
                        if (src and 
                            len(src) > 10 and 
                            not src.startswith('data:') and
                            any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp'])):
                            
                            images_found.append({
                                'src': src,
                                'alt': alt,
                                'selector': selector
                            })
                            
                except Exception as e:
                    self.logger.debug(f"Image selector failed {selector}: {e}")
                    continue
            
            # Strategy 2: Look for any substantial images
            if not images_found:
                try:
                    all_images = self.driver.find_elements(By.TAG_NAME, "img")
                    for img in all_images:
                        src = img.get_attribute("src")
                        if (src and 
                            len(src) > 20 and 
                            not src.startswith('data:') and
                            'logo' not in src.lower() and
                            'icon' not in src.lower()):
                            
                            images_found.append({
                                'src': src,
                                'alt': img.get_attribute("alt") or "",
                                'selector': 'general_img'
                            })
                            
                except Exception as e:
                    self.logger.debug(f"General image search failed: {e}")
            
            # Download the best image
            if images_found:
                # Prioritize product-specific images
                best_image = None
                for img in images_found:
                    if any(term in img['alt'].lower() for term in ['product', 'main', 'primary']):
                        best_image = img
                        break
                
                if not best_image:
                    best_image = images_found[0]  # Take first available
                
                image_info = self._download_image(best_image['src'], product_folder)
                if image_info:
                    product_data['image_downloaded'] = image_info
                    product_data['image_path'] = image_info['file_path']  # Add image path for UI
                    product_data['extraction_success']['image'] = True
                    self.logger.info(f"   ✅ Image downloaded: {image_info['file_path']}")
                else:
                    self.logger.warning("   ❌ Image download failed")
            else:
                self.logger.warning("   ❌ No suitable images found")
                
        except Exception as e:
            self.logger.error(f"Error downloading image: {e}")
    
    def _download_image(self, image_url, product_folder=None):
        """Download product image to product folder"""
        try:
            if not image_url.startswith('http'):
                image_url = urljoin(self.base_url, image_url)
            
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Generate filename
            import hashlib
            url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
            filename = f"product_image_{url_hash}.jpg"
            
            # Save image in product folder if available
            if product_folder and os.path.exists(product_folder):
                file_path = os.path.join(product_folder, filename)
            else:
                file_path = filename
            
            # Save image
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            return {
                'filename': filename,
                'file_path': file_path,
                'url': image_url,
                'size_bytes': len(response.content)
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to download image: {e}")
            return None
    
    def save_data(self, data, search_term=None, data_folder="data"):
        """Save data to JSON file in organized folder structure"""
        try:
            # Create data folder if it doesn't exist
            if not os.path.exists(data_folder):
                os.makedirs(data_folder)
                self.logger.info(f"Created data folder: {data_folder}")
            
            # Create product-specific folder
            if search_term:
                # Clean search term for folder name
                safe_search_term = "".join(c for c in search_term if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_search_term = safe_search_term.replace(' ', '_')
                product_folder = os.path.join(data_folder, safe_search_term)
            else:
                product_folder = os.path.join(data_folder, f"product_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            # Create product folder if it doesn't exist
            if not os.path.exists(product_folder):
                os.makedirs(product_folder)
                self.logger.info(f"Created product folder: {product_folder}")
            
            # Save JSON data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_filename = f"product_data_{timestamp}.json"
            json_path = os.path.join(product_folder, json_filename)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Data saved to: {json_path}")
            
            # Update data with file paths
            data['file_paths'] = {
                'json_file': json_path,
                'product_folder': product_folder,
                'search_term': search_term,
                'timestamp': timestamp
            }
            
            return json_path
            
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
            return None
    
    def run_complete_workflow(self, search_term=product_name, data_folder="data"):
        """Run the complete workflow from search to extraction"""
        try:
            print("="*70)
            print("FIXED iPROCURE SEARCH TO EXTRACTION WORKFLOW")
            print("="*70)
            print(f"Search term: {search_term}")
            print(f"Data folder: {data_folder}")
            print()
            
            # Create product folder path
            safe_search_term = "".join(c for c in search_term if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_search_term = safe_search_term.replace(' ', '_')
            product_folder = os.path.join(data_folder, safe_search_term)
            
            # Step 1: Test search URL
            print("🔍 Step 1: Testing search URL...")
            search_result = self.test_search_url(search_term)
            
            if 'error' in search_result:
                print(f"❌ Search URL test failed: {search_result['error']}")
                return None
            
            print("✅ Search URL accessible")
            print(f"   Final URL: {search_result['final_url']}")
            print(f"   Page title: {search_result['page_title']}")
            print(f"   Contains search term: {search_result['contains_search_term']}")
            print(f"   Contains Tenby: {search_result['contains_tenby']}")
            print(f"   Product elements found: {search_result['product_elements_found']}")
            print()
            
            # Step 2: Find and click product
            print("🖱️ Step 2: Finding and clicking product...")
            product_result = self.find_and_click_product(search_term)
            
            if not product_result:
                print("❌ Could not find or click product")
                return None
            
            # Check if we got a URL (full product page) or basic data (search results)
            if isinstance(product_result, str):
                # We got a URL, extract full product details
                product_url = product_result
                print(f"✅ Successfully navigated to product page")
                print(f"   Product URL: {product_url}")
                print()
                
                # Step 3: Extract product details
                print("📦 Step 3: Extracting product details...")
                product_data = self.extract_product_details(product_url, search_term, product_folder)
            else:
                # We got basic data from search results
                product_data = product_result
                print(f"✅ Extracted basic information from search results")
                print(f"   Extraction source: {product_data.get('extraction_source', 'unknown')}")
                print()
            
            if not product_data:
                print("❌ Could not extract product details")
                return None
            
            print("✅ Product details extracted successfully!")
            print()
            
            # Step 4: Save results
            print("💾 Step 4: Saving results...")
            filename = self.save_data(product_data, search_term, data_folder)
            
            # Display results
            print("📊 DETAILED EXTRACTION RESULTS")
            print("="*50)
            
            # Basic Info
            print("🏷️ PRODUCT INFORMATION:")
            print(f"   Title: {product_data.get('title', 'N/A')}")
            print(f"   Brand: {product_data.get('brand', 'N/A')}")
            print(f"   Supplier: {product_data.get('supplier', 'N/A')}")
            print(f"   Category: {product_data.get('category', 'N/A')}")
            print(f"   SKU: {product_data.get('sku', 'N/A')}")
            print()
            
            # Key Attributes
            attributes = product_data.get('key_attributes', {})
            print("🔧 KEY ATTRIBUTES:")
            if attributes:
                for key, value in attributes.items():
                    print(f"   {key}: {value}")
            else:
                print("   No attributes extracted")
            print()
            
            # Description
            description = product_data.get('description', '')
            print("📝 PRODUCT DESCRIPTION:")
            if description:
                print(f"   Length: {len(description)} characters")
                print(f"   Preview: {description[:150]}...")
                if len(description) > 150:
                    print("   [Description truncated for display]")
            else:
                print("   No description found")
            print()
            
            # Image
            print("🖼️ PRODUCT IMAGE:")
            if product_data.get('image_downloaded'):
                img_info = product_data['image_downloaded']
                print(f"   ✅ Downloaded: {img_info['filename']}")
                print(f"   Size: {img_info['size_bytes']} bytes")
                print(f"   URL: {img_info['url']}")
            else:
                print("   ❌ No image downloaded")
            print()
            
            # Success Summary
            success = product_data.get('extraction_success', {})
            print("📈 EXTRACTION SUCCESS SUMMARY:")
            print(f"   Title: {'✅ Success' if success.get('title') else '❌ Failed'}")
            print(f"   Attributes: {'✅ Success' if success.get('attributes') else '❌ Failed'} ({len(attributes)} found)")
            print(f"   Description: {'✅ Success' if success.get('description') else '❌ Failed'}")
            print(f"   Image: {'✅ Success' if success.get('image') else '❌ Failed'}")
            print()
            
            print(f"💾 Complete data saved to: {filename}")
            
            return product_data
            
        except Exception as e:
            print(f"❌ Workflow failed: {e}")
            return None
    
    def close(self):
        """Close the WebDriver"""
        try:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
        except Exception as e:
            self.logger.warning(f"Error closing WebDriver: {e}")

def main():
    """Main function to run the fixed extraction tool"""
    
    print("Fixed iProcure Search to Product Extraction Tool")
    print("This version should fix the 'data:,' URL issues")
    print("="*70)
    
    extractor = None
    
    try:
        # Initialize extractor (show browser for debugging)
        extractor = FixedSearchExtractor(headless=False, download_images=True)
        
        # Run the complete workflow
        result = extractor.run_complete_workflow(product_name)
        
        if result:
            print("\n✅ Workflow completed successfully!")
        else:
            print("\n❌ Workflow failed")
            
        input("\nPress Enter to close browser...")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nIf you're still getting 'data:,' URLs, please:")
        print("1. Run 'python debug_webdriver_setup.py' for detailed diagnostics")
        print("2. Check your internet connection")
        print("3. Make sure Chrome and ChromeDriver are properly installed")
        
    finally:
        if extractor:
            extractor.close()

if __name__ == "__main__":
    main() 