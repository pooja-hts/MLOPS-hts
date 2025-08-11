import requests
from bs4 import BeautifulSoup
import json
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin, urlparse
import pandas as pd

class iProcureProductListExtractor:
    def __init__(self, headless=True, delay=2, debug=False):
        """
        Initialize the iProcure product list extractor
        
        Args:
            headless (bool): Run browser in headless mode
            delay (int): Delay between requests in seconds
            debug (bool): Enable debug mode for verbose output
        """
        self.delay = delay
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Setup Selenium WebDriver
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
    def get_driver(self):
        """Initialize and return Chrome WebDriver"""
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            print("Make sure ChromeDriver is installed and in PATH")
            return None
    
    def extract_with_requests(self, url):
        """
        Extract product list using requests and BeautifulSoup
        
        Args:
            url (str): URL to extract from
            
        Returns:
            list: List of product dictionaries
        """
        try:
            if self.debug:
                print(f"Making request to: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            if self.debug:
                print(f"Response status: {response.status_code}")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return self.parse_product_list(soup, url)
            
        except requests.RequestException as e:
            print(f"Error fetching URL with requests: {e}")
            return []
    
    def extract_with_selenium(self, url):
        """
        Extract product list using Selenium (for dynamic content)
        
        Args:
            url (str): URL to extract from
            
        Returns:
            list: List of product dictionaries
        """
        driver = self.get_driver()
        if not driver:
            return []
        
        try:
            print(f"Loading page with Selenium: {url}")
            driver.get(url)
            
            # Wait for page to load
            time.sleep(5)
            
            # Wait for content to load
            wait = WebDriverWait(driver, 15)
            
            # Try to find product containers
            product_selectors = [
                '[class*="product"]',
                '[class*="item"]',
                '[class*="card"]',
                '[class*="list"]',
                '[class*="grid"]',
                '.product-item',
                '.item-card',
                '.product-card',
                '[data-testid*="product"]'
            ]
            
            products_found = False
            for selector in product_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(elements) > 0:
                        products_found = True
                        print(f"Products found using selector: {selector} ({len(elements)} elements)")
                        break
                except:
                    continue
            
            if not products_found:
                print("No products found with common selectors, trying to parse entire page")
            
            # Simple extraction - just get products from current page
            print("Extracting products from current page...")
            
            # Wait a moment for any dynamic content to load
            time.sleep(3)
            
            # Parse current page content
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            products = self.parse_product_list(soup, url)
            
            print(f"Extraction complete. Total products found: {len(products)}")
            return products
            
        except Exception as e:
            print(f"Error with Selenium: {e}")
            return []
        finally:
            driver.quit()
    
    def handle_infinite_scroll(self, driver, max_scrolls=20):
        """
        Handle infinite scroll to load all products
        
        Args:
            driver: Selenium WebDriver instance
            max_scrolls: Maximum number of scroll attempts
            
        Returns:
            bool: True if new content was loaded
        """
        print("Handling infinite scroll...")
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        no_new_content_count = 0
        
        while scroll_count < max_scrolls and no_new_content_count < 5:
            # Scroll to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Wait for new content to load
            time.sleep(3)
            
            # Calculate new scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                no_new_content_count += 1
                print(f"No new content loaded. Attempt {no_new_content_count}/5")
                
                # Try scrolling in smaller increments
                for i in range(3):
                    driver.execute_script("window.scrollBy(0, 300);")
                    time.sleep(1)
            else:
                no_new_content_count = 0
                print(f"New content loaded. Height changed from {last_height} to {new_height}")
            
            last_height = new_height
            scroll_count += 1
            
            # Check for load more buttons
            try:
                load_buttons = driver.find_elements(By.XPATH, 
                    "//button[contains(text(), 'Load') or contains(text(), 'More') or contains(text(), 'Show')]")
                for button in load_buttons:
                    if button.is_displayed() and button.is_enabled():
                        print(f"Clicking load more button: {button.text}")
                        button.click()
                        time.sleep(3)
                        no_new_content_count = 0  # Reset counter
            except:
                pass
        
        print(f"Infinite scroll completed. Total scrolls: {scroll_count}")
        return scroll_count > 0
    
    def handle_pagination(self, driver, base_url, max_pages=50):
        """
        Handle pagination to extract products from multiple pages
        
        Args:
            driver: Selenium WebDriver instance
            base_url: Base URL for the site
            max_pages: Maximum number of pages to process
            
        Returns:
            list: All products from all pages
        """
        print("Handling pagination...")
        all_products = []
        current_page = 1
        
        while current_page <= max_pages:
            print(f"Processing page {current_page}...")
            
            # Wait for page to load
            time.sleep(3)
            
            # Parse current page
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            page_products = self.parse_product_list(soup, base_url)
            
            if page_products:
                all_products.extend(page_products)
                print(f"Found {len(page_products)} products on page {current_page}")
            else:
                print(f"No products found on page {current_page}")
            
            # Look for next page button
            next_page_found = False
            
            # Try different next page selectors
            next_selectors = [
                "//a[contains(text(), 'Next')]",
                "//button[contains(text(), 'Next')]",
                "//a[contains(text(), '>')]",
                "//button[contains(text(), '>')]",
                "//a[contains(text(), '»')]",
                "//button[contains(text(), '»')]",
                "//a[@aria-label='Next']",
                "//button[@aria-label='Next']",
                "//a[contains(@class, 'next')]",
                "//button[contains(@class, 'next')]",
                "//a[contains(@class, 'pagination') and contains(text(), 'Next')]",
                "//button[contains(@class, 'pagination') and contains(text(), 'Next')]"
            ]
            
            for selector in next_selectors:
                try:
                    next_buttons = driver.find_elements(By.XPATH, selector)
                    for button in next_buttons:
                        if button.is_displayed() and button.is_enabled():
                            print(f"Found next page button: {button.text}")
                            try:
                                button.click()
                                time.sleep(5)
                                next_page_found = True
                                current_page += 1
                                print(f"Clicked next page button, moving to page {current_page}")
                                break
                            except Exception as e:
                                print(f"Error clicking next page button: {e}")
                    if next_page_found:
                        break
                except:
                    continue
            
            if not next_page_found:
                print("No next page button found. Reached end of pagination.")
                break
        
        print(f"Pagination completed. Total pages processed: {current_page}")
        return all_products
    
    def parse_product_list(self, soup, base_url):
        """Parse product list from HTML"""
        products = []
        
        if self.debug:
            print("Starting product list parsing...")
            print(f"Page title: {soup.title.string if soup.title else 'No title'}")
            # Save HTML for debugging
            with open('debug_product_list.html', 'w', encoding='utf-8') as f:
                f.write(str(soup))
            print("Saved debug HTML to debug_product_list.html")
        
        # Focus only on H3 elements for product names
        print("Focusing on H3 elements for product extraction...")
        h3_products = self.find_products_by_specific_elements(soup, base_url)
        
        if h3_products:
            products.extend(h3_products)
            print(f"Found {len(h3_products)} products using H3 selectors")
        else:
            print("No products found in H3 elements, trying fallback methods...")
            # Fallback to other methods only if no H3 products found
            fallback_approaches = [
                self.find_products_by_containers,
                self.find_products_by_links,
                self.find_products_by_visible_text
            ]
            
            for approach in fallback_approaches:
                try:
                    found_products = approach(soup, base_url)
                    if found_products:
                        products.extend(found_products)
                        print(f"Found {len(found_products)} products using fallback {approach.__name__}")
                        break
                except Exception as e:
                    if self.debug:
                        print(f"Error with fallback approach {approach.__name__}: {e}")
                    continue
        
        # Remove duplicates but keep all H3 products (no validation filtering)
        seen_names = set()
        unique_products = []
        for product in products:
            name = product.get('name', '').strip()
            if name and name.lower() not in seen_names:
                seen_names.add(name.lower())
                unique_products.append(product)
        
        return unique_products
    
    def find_products_by_specific_elements(self, soup, base_url):
        """Find products by looking for H3 elements that contain product names"""
        products = []
        
        # Primary focus: H3 elements with the specific classes you identified
        primary_h3_selectors = [
            'h3.text-md.font-semibold.text-gray-800.truncate.cursor-pointer',
            'h3[class*="text-md"][class*="font-semibold"][class*="text-gray-800"]',
            'h3[class*="truncate"][class*="cursor-pointer"]'
        ]
        
        # Secondary H3 selectors as fallback
        secondary_h3_selectors = [
            'h3.text-md',
            'h3.font-semibold',
            'h3[class*="text"]',
            'h3[class*="product"]',
            'h3[class*="title"]',
            'h3[class*="name"]'
        ]
        
        # Try primary selectors first - extract ALL H3 elements without validation
        for selector in primary_h3_selectors:
            elements = soup.select(selector)
            if self.debug:
                print(f"Primary H3 selector '{selector}' found {len(elements)} elements")
            
            for i, elem in enumerate(elements, 1):
                text = elem.get_text(strip=True)
                if text:  # Only check if text is not empty, no validation filtering
                    product = {
                        'name': text,
                        'type': 'h3_element',
                        'selector': selector,
                        'source': 'primary_h3_element',
                        'index': i
                    }
                    products.append(product)
            
            # If we found products with primary selectors, don't try secondary ones
            if products:
                print(f"Found {len(products)} products using primary H3 selectors (all extracted)")
                return products
        
        # If no products found with primary selectors, try secondary ones
        print("No products found with primary H3 selectors, trying secondary selectors...")
        for selector in secondary_h3_selectors:
            elements = soup.select(selector)
            if self.debug:
                print(f"Secondary H3 selector '{selector}' found {len(elements)} elements")
            
            for i, elem in enumerate(elements, 1):
                text = elem.get_text(strip=True)
                if text:  # Only check if text is not empty, no validation filtering
                    product = {
                        'name': text,
                        'type': 'h3_element',
                        'selector': selector,
                        'source': 'secondary_h3_element',
                        'index': i
                    }
                    products.append(product)
        
        if products:
            print(f"Found {len(products)} products using H3 selectors (all extracted)")
        else:
            print("No products found in any H3 elements")
        
        return products
    
    def find_products_by_visible_text(self, soup, base_url):
        """Find products by looking for visible text content"""
        products = []
        
        # Remove script and style tags to focus on visible content
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        
        # Get all text content
        text_content = soup.get_text()
        
        # Split into lines and filter
        lines = text_content.split('\n')
        for line in lines:
            line = line.strip()
            if self.is_valid_product_name(line):
                product = {
                    'name': line,
                    'type': 'visible_text',
                    'source': 'text_content'
                }
                products.append(product)
        
        return products
    
    def find_products_by_links(self, soup, base_url):
        """Find products by looking for product links"""
        products = []
        
        # Look for links that might contain product information
        product_links = soup.find_all('a', href=True)
        
        for link in product_links:
            link_text = link.get_text(strip=True)
            href = link.get('href', '')
            
            # Check if link text looks like a product name
            if self.is_valid_product_name(link_text):
                product = {
                    'name': link_text,
                    'url': urljoin(base_url, href),
                    'type': 'link',
                    'source': 'anchor_tag'
                }
                products.append(product)
            
            # Check if href contains product information
            if 'product' in href.lower() or 'item' in href.lower():
                if link_text and len(link_text) > 3:
                    product = {
                        'name': link_text,
                        'url': urljoin(base_url, href),
                        'type': 'product_link',
                        'source': 'href_pattern'
                    }
                    products.append(product)
        
        return products
    
    def find_products_by_containers(self, soup, base_url):
        """Find products by looking for product containers (excluding H3 elements)"""
        products = []
        
        # Look for containers that might contain products (excluding H3 elements)
        container_selectors = [
            '[class*="product"]',
            '[class*="item"]',
            '[class*="card"]',
            '[class*="list"]',
            '[class*="grid"]',
            '.product-item',
            '.item-card',
            '.product-card',
            '[data-testid*="product"]',
            'div:has(h4)',
            'div:has(strong)',
            'div:has(b)',
            'section',
            'article'
        ]
        
        for selector in container_selectors:
            containers = soup.select(selector)
            if self.debug:
                print(f"Selector '{selector}' found {len(containers)} containers")
            
            for container in containers:
                # Extract text that might be product names
                text_elements = container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b', 'span', 'div', 'p'])
                
                for elem in text_elements:
                    text = elem.get_text(strip=True)
                    if self.is_valid_product_name(text):
                        product = {
                            'name': text,
                            'type': 'container',
                            'selector': selector,
                            'source': 'container_element'
                        }
                        products.append(product)
        
        return products
    
    def find_products_by_images(self, soup, base_url):
        """Find products by looking for product images and their associated text"""
        products = []
        
        # Look for images that might be products
        images = soup.find_all('img')
        
        for img in images:
            # Check alt text
            alt_text = img.get('alt', '')
            if self.is_valid_product_name(alt_text):
                product = {
                    'name': alt_text,
                    'image_url': urljoin(base_url, img.get('src', '')),
                    'type': 'image_alt',
                    'source': 'img_alt'
                }
                products.append(product)
            
            # Check title attribute
            title_text = img.get('title', '')
            if self.is_valid_product_name(title_text):
                product = {
                    'name': title_text,
                    'image_url': urljoin(base_url, img.get('src', '')),
                    'type': 'image_title',
                    'source': 'img_title'
                }
                products.append(product)
            
            # Look for text near the image
            parent = img.parent
            if parent:
                nearby_text = parent.get_text(strip=True)
                if self.is_valid_product_name(nearby_text):
                    product = {
                        'name': nearby_text,
                        'image_url': urljoin(base_url, img.get('src', '')),
                        'type': 'image_nearby',
                        'source': 'img_parent_text'
                    }
                    products.append(product)
        
        return products
    
    def find_products_by_structure(self, soup, base_url):
        """Find products by analyzing page structure"""
        products = []
        
        # Look for lists that might contain products
        lists = soup.find_all(['ul', 'ol'])
        
        for list_elem in lists:
            list_items = list_elem.find_all('li')
            for item in list_items:
                text = item.get_text(strip=True)
                if self.is_valid_product_name(text):
                    product = {
                        'name': text,
                        'type': 'list_item',
                        'source': 'list_structure'
                    }
                    products.append(product)
        
        # Look for table rows that might contain products
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                for cell in cells:
                    text = cell.get_text(strip=True)
                    if self.is_valid_product_name(text):
                        product = {
                            'name': text,
                            'type': 'table_cell',
                            'source': 'table_structure'
                        }
                        products.append(product)
        
        return products

    def is_valid_product_name(self, text):
        """Check if text looks like a valid product name"""
        if not text or len(text) < 3:
            return False
        
        # Skip JavaScript, CSS, and other code content
        code_indicators = [
            'function(', 'var ', 'const ', 'let ', 'if(', 'for(', 'while(',
            'document.', 'window.', 'self.', 'console.',
            '{', '}', ';', '=>', '()', '[]',
            'http://', 'https://', 'www.',
            'static/', '_next/', 'chunks/',
            'jsx-', 'css-', 'class=', 'id=',
            'data-', 'aria-', 'role=',
            '<!--', '-->', '<script', '</script>',
            'import ', 'export ', 'require(',
            'new Date()', 'getTime()', 'push(',
            'Object.defineProperty', 'navigator.',
            'webkit', 'moz-', 'ms-',
            'rgba(', 'rgb(', '#', 'px', 'em', 'rem',
            'margin:', 'padding:', 'border:', 'background:',
            'font-family:', 'font-size:', 'color:',
            'display:', 'position:', 'width:', 'height:'
        ]
        
        text_lower = text.lower()
        for indicator in code_indicators:
            if indicator in text_lower:
                return False
        
        # Skip very long text (likely not a product name)
        if len(text) > 200:
            return False
        
        # Skip text with too many special characters
        special_char_count = sum(1 for c in text if c in '{}[]()<>;:,./\\|`~!@#$%^&*+=')
        if special_char_count > len(text) * 0.3:  # More than 30% special chars
            return False
        
        # Skip text that's mostly numbers or symbols
        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count < len(text) * 0.3:  # Less than 30% alphabetic
            return False
        
        # Look for product-like patterns
        product_indicators = [
            # Product code patterns
            r'[A-Z]{2,3}-[A-Z0-9]+',  # EX-A2F, Ex-E1FU
            r'[A-Z][a-z]+-[A-Z0-9]+',  # Mixed case patterns
            # Product keywords
            r'\b(gland|cable|connector|pipe|conduit|wire|electrical|led|floodlight|explosion|proof|nickel|plated|steel|aluminum|copper|plastic|rubber|silicone|brass|zinc|galvanized|pvc|emt|rigid|flexible|armored|shielded|twisted|pair|coaxial|fiber|optic|power|control|signal|data|communication|telecom|automation|industrial|commercial|residential|outdoor|indoor|waterproof|dustproof|corrosion|resistant|high|temperature|low|voltage|medium|voltage|high|voltage|ac|dc|v|w|amp|ampere|ohm|watt|kwh|mwh|kva|pf|hz|frequency|phase|single|three|neutral|ground|earth|bonding|earthing|lighting|switch|socket|outlet|receptacle|plug|adapter|junction|box|panel|board|breaker|fuse|relay|contactor|starter|motor|transformer|capacitor|resistor|diode|transistor|ic|integrated|circuit|sensor|proximity|limit|pressure|temperature|flow|level|position|speed|encoder|encoder|servo|stepper|vfd|drive|inverter|ups|battery|charger|solar|wind|generator|compressor|pump|valve|actuator|solenoid|cylinder|gear|belt|chain|bearing|coupling|clutch|brake|filter|lubricant|grease|oil|coolant|heater|cooler|fan|blower|exhaust|ventilation|air|conditioning|refrigeration|heating|cooling|drying|humidification|dehumidification|sterilization|cleaning|washing|drying|packaging|labeling|marking|printing|scanning|weighing|counting|sorting|conveying|lifting|hoisting|crane|forklift|pallet|rack|shelf|cabinet|enclosure|housing|cover|cap|plug|seal|gasket|o-ring|washer|nut|bolt|screw|rivet|nail|staple|clip|clamp|bracket|mount|bracket|support|stand|base|foot|leg|wheel|caster|handle|knob|lever|button|switch|key|lock|hinge|latch|catch|spring|damper|shock|absorber|vibration|isolation|noise|reduction|sound|proofing|insulation|thermal|acoustic|fire|smoke|gas|detector|alarm|siren|beacon|light|strobe|emergency|exit|entrance|door|window|gate|barrier|fence|wall|ceiling|floor|roof|foundation|structure|frame|beam|column|truss|girder|plate|sheet|tube|pipe|rod|bar|wire|cable|rope|chain|belt|fabric|textile|paper|plastic|metal|wood|glass|ceramic|composite|alloy|polymer|elastomer|thermoplastic|thermoset|resin|adhesive|sealant|coating|paint|varnish|lacquer|powder|liquid|solid|gas|vapor|aerosol|paste|gel|foam|sponge|rubber|silicone|neoprene|epdm|nitrile|butyl|viton|ptfe|peek|delrin|nylon|polyester|polyethylene|polypropylene|pvc|abs|pc|pmma|ps|pp|pe|pa|pom|pbt|pet)\b',
            # Common product suffixes
            r'\b(connector|adapter|coupling|reducer|elbow|tee|cross|union|coupling|flange|gland|seal|gasket|washer|nut|bolt|screw|rivet|nail|staple|clip|clamp|bracket|mount|support|stand|base|foot|leg|wheel|caster|handle|knob|lever|button|switch|key|lock|hinge|latch|catch|spring|damper|shock|absorber|detector|alarm|siren|beacon|light|strobe|emergency|exit|entrance|door|window|gate|barrier|fence|wall|ceiling|floor|roof|foundation|structure|frame|beam|column|truss|girder|plate|sheet|tube|pipe|rod|bar|wire|cable|rope|chain|belt|fabric|textile|paper|plastic|metal|wood|glass|ceramic|composite|alloy|polymer|elastomer|thermoplastic|thermoset|resin|adhesive|sealant|coating|paint|varnish|lacquer|powder|liquid|solid|gas|vapor|aerosol|paste|gel|foam|sponge|rubber|silicone|neoprene|epdm|nitrile|butyl|viton|ptfe|peek|delrin|nylon|polyester|polyethylene|polypropylene|pvc|abs|pc|pmma|ps|pp|pe|pa|pom|pbt|pet)\b',
            # Size/measurement patterns
            r'\d+\s*(mm|cm|m|inch|ft|yd|kg|g|lb|oz|l|ml|gal|pt|qt)',
            r'\d+\s*["\']',  # Inches with quotes
            r'\d+\s*%',  # Percentages
            # Material patterns
            r'\b(steel|aluminum|copper|plastic|rubber|silicone|brass|zinc|galvanized|pvc|emt|rigid|flexible|armored|shielded|twisted|pair|coaxial|fiber|optic|power|control|signal|data|communication|telecom|automation|industrial|commercial|residential|outdoor|indoor|waterproof|dustproof|corrosion|resistant|high|temperature|low|voltage|medium|voltage|high|voltage|ac|dc|v|w|amp|ampere|ohm|watt|kwh|mwh|kva|pf|hz|frequency|phase|single|three|neutral|ground|earth|bonding|earthing|lighting|switch|socket|outlet|receptacle|plug|adapter|junction|box|panel|board|breaker|fuse|relay|contactor|starter|motor|transformer|capacitor|resistor|diode|transistor|ic|integrated|circuit|sensor|proximity|limit|pressure|temperature|flow|level|position|speed|encoder|encoder|servo|stepper|vfd|drive|inverter|ups|battery|charger|solar|wind|generator|compressor|pump|valve|actuator|solenoid|cylinder|gear|belt|chain|bearing|coupling|clutch|brake|filter|lubricant|grease|oil|coolant|heater|cooler|fan|blower|exhaust|ventilation|air|conditioning|refrigeration|heating|cooling|drying|humidification|dehumidification|sterilization|cleaning|washing|drying|packaging|labeling|marking|printing|scanning|weighing|counting|sorting|conveying|lifting|hoisting|crane|forklift|pallet|rack|shelf|cabinet|enclosure|housing|cover|cap|plug|seal|gasket|o-ring|washer|nut|bolt|screw|rivet|nail|staple|clip|clamp|bracket|mount|bracket|support|stand|base|foot|leg|wheel|caster|handle|knob|lever|button|switch|key|lock|hinge|latch|catch|spring|damper|shock|absorber|vibration|isolation|noise|reduction|sound|proofing|insulation|thermal|acoustic|fire|smoke|gas|detector|alarm|siren|beacon|light|strobe|emergency|exit|entrance|door|window|gate|barrier|fence|wall|ceiling|floor|roof|foundation|structure|frame|beam|column|truss|girder|plate|sheet|tube|pipe|rod|bar|wire|cable|rope|chain|belt|fabric|textile|paper|plastic|metal|wood|glass|ceramic|composite|alloy|polymer|elastomer|thermoplastic|thermoset|resin|adhesive|sealant|coating|paint|varnish|lacquer|powder|liquid|solid|gas|vapor|aerosol|paste|gel|foam|sponge|rubber|silicone|neoprene|epdm|nitrile|butyl|viton|ptfe|peek|delrin|nylon|polyester|polyethylene|polypropylene|pvc|abs|pc|pmma|ps|pp|pe|pa|pom|pbt|pet)\b'
        ]
        
        # Check if text matches any product pattern
        for pattern in product_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Check if text contains common product words
        product_words = [
            'gland', 'cable', 'connector', 'pipe', 'conduit', 'wire', 'electrical',
            'led', 'floodlight', 'explosion', 'proof', 'nickel', 'plated', 'steel',
            'aluminum', 'copper', 'plastic', 'rubber', 'silicone', 'brass', 'zinc',
            'galvanized', 'pvc', 'emt', 'rigid', 'flexible', 'armored', 'shielded',
            'power', 'control', 'signal', 'data', 'communication', 'telecom',
            'automation', 'industrial', 'commercial', 'residential', 'outdoor',
            'indoor', 'waterproof', 'dustproof', 'corrosion', 'resistant',
            'temperature', 'voltage', 'sensor', 'switch', 'socket', 'outlet',
            'plug', 'adapter', 'junction', 'box', 'panel', 'board', 'breaker',
            'fuse', 'relay', 'contactor', 'starter', 'motor', 'transformer',
            'capacitor', 'resistor', 'diode', 'transistor', 'integrated', 'circuit',
            'proximity', 'limit', 'pressure', 'flow', 'level', 'position', 'speed',
            'encoder', 'servo', 'stepper', 'drive', 'inverter', 'ups', 'battery',
            'charger', 'solar', 'wind', 'generator', 'compressor', 'pump', 'valve',
            'actuator', 'solenoid', 'cylinder', 'gear', 'belt', 'chain', 'bearing',
            'coupling', 'clutch', 'brake', 'filter', 'lubricant', 'grease', 'oil',
            'coolant', 'heater', 'cooler', 'fan', 'blower', 'exhaust', 'ventilation',
            'air', 'conditioning', 'refrigeration', 'heating', 'cooling', 'drying',
            'humidification', 'dehumidification', 'sterilization', 'cleaning',
            'washing', 'packaging', 'labeling', 'marking', 'printing', 'scanning',
            'weighing', 'counting', 'sorting', 'conveying', 'lifting', 'hoisting',
            'crane', 'forklift', 'pallet', 'rack', 'shelf', 'cabinet', 'enclosure',
            'housing', 'cover', 'cap', 'plug', 'seal', 'gasket', 'o-ring', 'washer',
            'nut', 'bolt', 'screw', 'rivet', 'nail', 'staple', 'clip', 'clamp',
            'bracket', 'mount', 'support', 'stand', 'base', 'foot', 'leg', 'wheel',
            'caster', 'handle', 'knob', 'lever', 'button', 'switch', 'key', 'lock',
            'hinge', 'latch', 'catch', 'spring', 'damper', 'shock', 'absorber',
            'vibration', 'isolation', 'noise', 'reduction', 'sound', 'proofing',
            'insulation', 'thermal', 'acoustic', 'fire', 'smoke', 'gas', 'detector',
            'alarm', 'siren', 'beacon', 'light', 'strobe', 'emergency', 'exit',
            'entrance', 'door', 'window', 'gate', 'barrier', 'fence', 'wall',
            'ceiling', 'floor', 'roof', 'foundation', 'structure', 'frame', 'beam',
            'column', 'truss', 'girder', 'plate', 'sheet', 'tube', 'pipe', 'rod',
            'bar', 'wire', 'cable', 'rope', 'chain', 'belt', 'fabric', 'textile',
            'paper', 'plastic', 'metal', 'wood', 'glass', 'ceramic', 'composite',
            'alloy', 'polymer', 'elastomer', 'thermoplastic', 'thermoset', 'resin',
            'adhesive', 'sealant', 'coating', 'paint', 'varnish', 'lacquer',
            'powder', 'liquid', 'solid', 'gas', 'vapor', 'aerosol', 'paste', 'gel',
            'foam', 'sponge', 'rubber', 'silicone', 'neoprene', 'epdm', 'nitrile',
            'butyl', 'viton', 'ptfe', 'peek', 'delrin', 'nylon', 'polyester',
            'polyethylene', 'polypropylene', 'pvc', 'abs', 'pc', 'pmma', 'ps', 'pp',
            'pe', 'pa', 'pom', 'pbt', 'pet'
        ]
        
        text_lower = text.lower()
        word_count = sum(1 for word in product_words if word in text_lower)
        
        # If it contains multiple product words, it's likely a product name
        return word_count >= 1
    
    def extract_product_list(self, url, method='both'):
        """
        Main method to extract product list from iProcure
        
        Args:
            url (str): URL to extract from
            method (str): 'requests', 'selenium', or 'both'
            
        Returns:
            list: List of product dictionaries
        """
        print(f"Starting to extract product list from: {url}")
        
        all_products = []
        
        if method in ['requests', 'both']:
            print("Trying with requests method...")
            products_requests = self.extract_with_requests(url)
            all_products.extend(products_requests)
            print(f"Found {len(products_requests)} products with requests")
        
        if method in ['selenium', 'both']:
            print("Trying with Selenium method...")
            products_selenium = self.extract_with_selenium(url)
            
            # Avoid duplicates if using both methods
            if method == 'both' and all_products:
                new_products = []
                existing_names = {p.get('name', '').lower() for p in all_products}
                for product in products_selenium:
                    if product.get('name', '').lower() not in existing_names:
                        new_products.append(product)
                all_products.extend(new_products)
                print(f"Found {len(new_products)} additional products with Selenium")
            else:
                all_products.extend(products_selenium)
                print(f"Found {len(products_selenium)} products with Selenium")
        
        print(f"Total products found: {len(all_products)}")
        return all_products
    
    def extract_all_products(self, url, method='selenium', max_pages=50, max_scrolls=20):
        """
        Extract ALL products from the page using advanced pagination and infinite scroll
        
        Args:
            url (str): URL to extract from
            method (str): 'requests', 'selenium', or 'both'
            max_pages (int): Maximum number of pages to process
            max_scrolls (int): Maximum number of scroll attempts per page
            
        Returns:
            list: List of all product dictionaries
        """
        print(f"Starting comprehensive product extraction from: {url}")
        
        if method in ['requests', 'both']:
            print("Note: Requests method may not capture all products due to dynamic loading")
        
        if method in ['selenium', 'both']:
            driver = self.get_driver()
            if not driver:
                return []
            
            try:
                print(f"Loading page with Selenium: {url}")
                driver.get(url)
                
                # Wait for initial page load
                time.sleep(5)
                
                all_products = []
                current_page = 1
                
                while current_page <= max_pages:
                    print(f"\n=== Processing Page {current_page} ===")
                    
                    # Handle infinite scroll on current page
                    print("Handling infinite scroll...")
                    self.handle_infinite_scroll(driver, max_scrolls)
                    
                    # Parse current page content
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    page_products = self.parse_product_list(soup, url)
                    
                    if page_products:
                        # Add page number to each product
                        for product in page_products:
                            product['page'] = current_page
                        
                        all_products.extend(page_products)
                        print(f"Found {len(page_products)} products on page {current_page}")
                        print(f"Total products so far: {len(all_products)}")
                    else:
                        print(f"No products found on page {current_page}")
                    
                    # Try to find and click next page button
                    next_page_found = False
                    
                    # Look for next page indicators
                    next_indicators = [
                        "//a[contains(text(), 'Next')]",
                        "//button[contains(text(), 'Next')]",
                        "//a[contains(text(), '>')]",
                        "//button[contains(text(), '>')]",
                        "//a[contains(text(), '»')]",
                        "//button[contains(text(), '»')]",
                        "//a[@aria-label='Next']",
                        "//button[@aria-label='Next']",
                        "//a[contains(@class, 'next')]",
                        "//button[contains(@class, 'next')]",
                        "//a[contains(@class, 'pagination') and contains(text(), 'Next')]",
                        "//button[contains(@class, 'pagination') and contains(text(), 'Next')]"
                    ]
                    
                    for indicator in next_indicators:
                        try:
                            next_elements = driver.find_elements(By.XPATH, indicator)
                            for element in next_elements:
                                if element.is_displayed() and element.is_enabled():
                                    print(f"Found next page element: {element.text}")
                                    try:
                                        element.click()
                                        time.sleep(5)
                                        next_page_found = True
                                        current_page += 1
                                        print(f"Clicked next page element, moving to page {current_page}")
                                        break
                                    except Exception as e:
                                        print(f"Error clicking next page element: {e}")
                            if next_page_found:
                                break
                        except:
                            continue
                    
                    if not next_page_found:
                        print("No next page found. Reached end of pagination.")
                        break
                
                print(f"\n=== Extraction Complete ===")
                print(f"Total pages processed: {current_page}")
                print(f"Total products extracted: {len(all_products)}")
                
                return all_products
                
            except Exception as e:
                print(f"Error during comprehensive extraction: {e}")
                return []
            finally:
                driver.quit()
        
        # Fallback to regular extraction
        return self.extract_product_list(url, method)
    
    def save_results(self, products, filename_prefix="iprocure_product_list"):
        """
        Save results to JSON format only
        
        Args:
            products (list): List of product dictionaries
            filename_prefix (str): Prefix for output files
        """
        if not products:
            print("No products to save")
            return
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Save as JSON only
        json_filename = f"{filename_prefix}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        print(f"Saved JSON: {json_filename}")

def main():
    """Extract product names from iProcure"""
    # Initialize extractor with debug mode
    extractor = iProcureProductListExtractor(headless=True, delay=2, debug=True)
    
    # URL to extract from
    url = "https://iprocure.ai/pages/productpages"
    
    try:
        print("=== iProcure Product List Extractor ===")
        print(f"Target URL: {url}")
        print("Extracting product names from the current page...")
        
        # Directly extract products from the current page using Selenium
        products = extractor.extract_with_selenium(url)
        
        if products:
            # Print summary
            print(f"\n=== Extraction Complete ===")
            print(f"Total products found: {len(products)}")
            
            # Print all products found
            print(f"\nAll products found:")
            for i, product in enumerate(products, 1):
                print(f"{i:2d}. {product.get('name', 'N/A')}")
                if product.get('type'):
                    print(f"     Type: {product.get('type')}")
                if product.get('source'):
                    print(f"     Source: {product.get('source')}")
                print()
            
            # Save results
            print(f"Saving results...")
            extractor.save_results(products, "iprocure_product_list")
            
            print(f"\n=== SUCCESS ===")
            print(f"All {len(products)} products have been extracted and saved to JSON!")
            
        else:
            print("No products found. The website structure might have changed or requires different selectors.")
            print("Try running with debug=True or check the website manually.")
    
    except Exception as e:
        print(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 