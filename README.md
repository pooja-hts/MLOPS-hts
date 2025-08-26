# Lulu Pipeline

A complete Scrapy-based web scraping pipeline for extracting product categories and products from the LuluRayyan Group website.

## Features

- **Product Category Extraction**: Automatically discovers and extracts product categories by analyzing product pages
- **Subcategory Discovery**: Navigates through category pages to find subcategories
- **Product Data Extraction**: Extracts detailed product information including names, prices, SKUs, descriptions, and images
- **Multiple Output Formats**: Generates both JSON and human-readable text files
- **Selenium Integration**: Uses Selenium WebDriver for dynamic content and JavaScript-heavy pages
- **Configurable Filtering**: Supports category-specific filtering for targeted extraction
- **Cross-Platform Support**: Works on Windows, macOS, and Linux with proper encoding handling

## Project Structure

```
lulu_pipeline/
├── lulu_pipeline/
│   ├── __init__.py
│   ├── settings.py          # Scrapy configuration
│   ├── items.py            # Data models
│   ├── pipelines.py        # Data processing pipelines
│   └── spiders/
│       ├── __init__.py
│       └── lulu.py         # Main spider
├── scrapy.cfg              # Scrapy project config
├── requirements.txt         # Python dependencies
├── run_lulu_spider.py      # Execution script
├── test_pipeline.py        # Test script for verification
├── run_lulu_spider.bat     # Windows batch file
├── run_lulu_spider.sh      # Unix/Linux shell script
└── README.md               # This file
```

## Installation

1. **Clone or download the project**:
   ```bash
   cd lulu_pipeline
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Chrome WebDriver** (for Selenium):
   - Download ChromeDriver from: https://chromedriver.chromium.org/
   - Add it to your system PATH or place it in the project directory

## Testing the Pipeline

Before running the spider, you can test if all components are working correctly:

```bash
python test_pipeline.py
```

This will verify:
- Project structure is correct
- All required modules can be imported
- Items can be created and populated
- Pipelines can be instantiated

## Usage

### Basic Usage

Run the spider to extract all categories and products:

```bash
python run_lulu_spider.py
```

### With Category Filtering

Extract data for a specific category only:

```bash
python run_lulu_spider.py "CategoryName"
```

### Cross-Platform Execution

**Windows:**
- Double-click `run_lulu_spider.bat` or run from command prompt
- The batch file automatically sets UTF-8 encoding to handle special characters

**Unix/Linux:**
```bash
chmod +x run_lulu_spider.sh
./run_lulu_spider.sh
```

**Python (any platform):**
```bash
python run_lulu_spider.py
```

### Using Scrapy Directly

```bash
# Extract all categories and products
scrapy crawl lulurayyan_product_categories

# Extract with category filter
scrapy crawl lulurayyan_product_categories -a category_filter="CategoryName"
```

## Output Files

The pipeline generates the following output files in the `data/` directory:

- **`lulurayyan_categories.json`**: Structured JSON data of all categories and subcategories
- **`lulurayyan_categories.txt`**: Human-readable text format of categories
- **`lulurayyan_products.json`**: Complete product data in JSON format
- **`lulurayyan_products.txt`**: Human-readable product listings

## Data Structure

### Category Item
```json
{
  "category_name": "Category Name",
  "category_url": "https://example.com/category",
  "category_id": "category-slug",
  "subcategories": [...],
  "products_count": 42,
  "description": "Category description",
  "image_url": "https://example.com/image.jpg",
  "scraped_at": "2024-01-01T12:00:00"
}
```

### Product Item
```json
{
  "name": "Product Name",
  "category": "Main Category",
  "subcategory": "Sub Category",
  "url": "https://example.com/product",
  "image_url": "https://example.com/product.jpg",
  "price": "$99.99",
  "sku": "PROD-001",
  "brand": "Brand Name",
  "description": "Product description",
  "stock_status": "In Stock",
  "extracted_at": "2024-01-01T12:00:00"
}
```

## Configuration

### Scrapy Settings

Key settings in `lulu_pipeline/settings.py`:

- **`DOWNLOAD_DELAY`**: 3 seconds between requests
- **`CONCURRENT_REQUESTS_PER_DOMAIN`**: 1 (to be respectful to the server)
- **`ROBOTSTXT_OBEY`**: False (for this specific use case)
- **`ITEM_PIPELINES`**: Configured for JSON and text output

### Pipeline Configuration

The pipeline includes:
- `LuluRayyanCategoryJsonWriterPipeline`: Saves categories to JSON
- `LuluRayyanCategoryTextWriterPipeline`: Saves categories to text
- `LuluRayyanProductJsonWriterPipeline`: Saves products to JSON
- `LuluRayyanProductTextWriterPipeline`: Saves products to text

## How It Works

1. **Homepage Analysis**: The spider starts at the LuluRayyan homepage
2. **Product Discovery**: Finds product links and clicks on them to discover categories
3. **Category Extraction**: Extracts category information from product pages
4. **Subcategory Navigation**: Visits each category page to find subcategories
5. **Product Extraction**: Extracts products from each subcategory page
6. **Data Processing**: Processes and saves data through configured pipelines

## Troubleshooting

### Common Issues

1. **ChromeDriver not found**:
   - Ensure ChromeDriver is installed and in your PATH
   - Or place chromedriver.exe in the project directory

2. **Selenium errors**:
   - Check Chrome browser version compatibility
   - Update ChromeDriver if needed

3. **Scrapy not found**:
   - Install requirements: `pip install -r requirements.txt`

4. **Windows encoding issues**:
   - The pipeline automatically handles Windows console encoding
   - If you see encoding errors, ensure you're using the provided batch file or Python script

### Logs

- **`lulu_scrapy_run.log`**: Execution log from the run script
- **`scrapy.log`**: Scrapy framework logs

## Performance Notes

- **Rate Limiting**: Built-in delays to be respectful to the target website
- **Memory Usage**: Processes data in batches to manage memory efficiently
- **Error Handling**: Robust error handling with fallback mechanisms

## Legal and Ethical Considerations

- **Respect robots.txt**: Check the website's robots.txt file
- **Rate Limiting**: Built-in delays to avoid overwhelming the server
- **Terms of Service**: Ensure compliance with the website's terms of service
- **Data Usage**: Use extracted data responsibly and in accordance with applicable laws

## Support

For issues or questions:
1. **Run the test script first**: `python test_pipeline.py`
2. Check the logs for error messages
3. Verify all dependencies are installed
4. Ensure ChromeDriver is properly configured
5. Check the target website is accessible

## License

This project is for educational and research purposes. Please ensure compliance with the target website's terms of service and applicable laws.
