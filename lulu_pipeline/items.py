# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from itemloaders.processors import TakeFirst, Join, Identity
from scrapy.loader import ItemLoader


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


class LuluRayyanProductItem(scrapy.Item):
    """Item for storing individual product information."""
    
    # Basic product information
    name = scrapy.Field()
    category = scrapy.Field()
    subcategory = scrapy.Field()
    url = scrapy.Field()
    image_url = scrapy.Field()
    price = scrapy.Field()
    sku = scrapy.Field()
    brand = scrapy.Field()
    description = scrapy.Field()
    stock_status = scrapy.Field()
    extracted_at = scrapy.Field()


class LuluRayyanItemLoader(ItemLoader):
    """Custom item loader with default processors."""
    
    default_output_processor = TakeFirst()
    
    # For subcategories, we want to keep the list structure
    subcategories_out = Identity()
    
    # For URLs, we want to take the first one
    url_out = TakeFirst()
    
    # For timestamps, we want to take the first one
    scraped_at_out = TakeFirst()
