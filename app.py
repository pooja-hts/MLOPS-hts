import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import requests
from PIL import Image
import io

# Page configuration
st.set_page_config(
    page_title="Lulu Rayyan Products Dashboard",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Note: Server options like CORS and XSRF protection need to be set via command line
# or config.toml file, not at runtime

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .filter-section {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }
    .product-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_product_data():
    """Load product data from JSON file"""
    try:
        # Try to load from the data directory
        data_path = Path("data/lulurayyan_products.json")
        if data_path.exists():
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        else:
            st.error(f"Data file not found at: {data_path.absolute()}")
            return []
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return []

def create_filters(df):
    """Create filter widgets in the sidebar"""
    st.sidebar.markdown("## 🔍 Filters")
    
    # Category filter
    category_values = df['category'].dropna().unique().tolist()
    categories = ['All'] + sorted(category_values)
    selected_category = st.sidebar.selectbox("Category", categories)
    
    # Subcategory filter (dependent on category)
    if selected_category == 'All':
        subcategory_values = df['subcategory'].dropna().unique().tolist()
        subcategories = ['All'] + sorted(subcategory_values)
    else:
        # Filter data by selected category
        category_df = df[df['category'] == selected_category]
        subcategory_values = category_df['subcategory'].dropna().unique().tolist()
        subcategories = ['All'] + sorted(subcategory_values)
    
    selected_subcategory = st.sidebar.selectbox("Subcategory", subcategories)
    
    # Brand filter (dependent on both category and subcategory)
    if selected_category == 'All' and selected_subcategory == 'All':
        # No filters applied - show all brands
        brand_values = df['brand'].dropna().unique().tolist()
        brands = ['All'] + sorted(brand_values)
    elif selected_category != 'All' and selected_subcategory == 'All':
        # Only category filter applied - show brands from that category
        category_df = df[df['category'] == selected_category]
        brand_values = category_df['brand'].dropna().unique().tolist()
        brands = ['All'] + sorted(brand_values)
    elif selected_category != 'All' and selected_subcategory != 'All':
        # Both category and subcategory filters applied - show brands from that specific combination
        filtered_df = df[(df['category'] == selected_category) & (df['subcategory'] == selected_subcategory)]
        brand_values = filtered_df['brand'].dropna().unique().tolist()
        brands = ['All'] + sorted(brand_values)
    else:
        # Subcategory filter applied but category is 'All' (shouldn't happen with current logic, but safety check)
        brand_values = df['brand'].dropna().unique().tolist()
        brands = ['All'] + sorted(brand_values)
    
    selected_brand = st.sidebar.selectbox("Brand", brands)
    
    return selected_category, selected_subcategory, selected_brand

def filter_data(df, category, subcategory, brand):
    """Filter data based on selected criteria"""
    filtered_df = df.copy()
    
    if category != 'All':
        filtered_df = filtered_df[filtered_df['category'] == category]
    
    if subcategory != 'All':
        filtered_df = filtered_df[filtered_df['subcategory'] == subcategory]
    
    if brand != 'All':
        filtered_df = filtered_df[filtered_df['brand'] == brand]
    
    return filtered_df

def display_metrics(df):
    """Display key metrics"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Products", len(df))
    
    with col2:
        st.metric("Categories", df['category'].nunique())
    
    with col3:
        st.metric("Brands", df['brand'].nunique())
    
    with col4:
        try:
            avg_price = df['price'].str.extract(r'(\d+\.?\d*)').astype(float).mean()
            if pd.isna(avg_price):
                st.metric("Avg Price (QAR)", "N/A")
            else:
                st.metric("Avg Price (QAR)", f"{avg_price:.2f}")
        except:
            st.metric("Avg Price (QAR)", "N/A")

def display_charts(df):
    """Display charts and visualizations"""
    st.markdown("## 📊 Data Visualizations")
    
    # Check if DataFrame has enough data for charts
    if df.empty:
        st.warning("No data available for charts with the current filters.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Category distribution
        try:
            category_counts = df['category'].dropna().value_counts()
            if len(category_counts) > 0:
                fig_category = px.pie(
                    values=category_counts.values,
                    names=category_counts.index,
                    title="Products by Category"
                )
                st.plotly_chart(fig_category, use_container_width=True)
            else:
                st.info("No category data available for chart")
        except Exception as e:
            st.error(f"Error creating category chart: {e}")
    
    with col2:
        # Brand distribution
        try:
            brand_counts = df['brand'].dropna().value_counts()
            if len(brand_counts) > 0:
                # Ensure we have valid data for the bar chart
                valid_brands = brand_counts[brand_counts.index.notna()]
                if len(valid_brands) > 0:
                    fig_brand = px.bar(
                        x=valid_brands.index.tolist(),
                        y=valid_brands.values.tolist(),
                        title="Products by Brand"
                    )
                    st.plotly_chart(fig_brand, use_container_width=True)
                else:
                    st.info("No valid brand data available for chart")
            else:
                st.info("No brand data available for chart")
        except Exception as e:
            st.error(f"Error creating brand chart: {e}")

def display_products(df):
    """Display filtered products in cards"""
    st.markdown("## 🛍️ Products")
    
    if df.empty:
        st.warning("No products found with the selected filters.")
        return
    
    for idx, product in df.iterrows():
        with st.container():
            col1, col2 = st.columns([1, 3])
            
            with col1:
                # Better image URL handling
                image_url = product.get('image_url')
                
                # Check if image_url exists and is valid
                if (image_url and 
                    isinstance(image_url, str) and 
                    image_url.strip() != '' and 
                    image_url.lower() != 'nan' and
                    (image_url.startswith('http://') or image_url.startswith('https://'))):
                    
                    try:
                        # Check if domain is reachable before attempting download
                        image_loaded = False
                        
                        try:
                            # Extract domain from URL
                            from urllib.parse import urlparse
                            parsed_url = urlparse(image_url)
                            domain = parsed_url.netloc
                            
                            # Check if domain is reachable (basic connectivity test)
                            try:
                                import socket
                                socket.gethostbyname(domain)
                                domain_reachable = True
                            except socket.gaierror:
                                domain_reachable = False
                            
                            if domain_reachable:
                                # Create cache directory if it doesn't exist
                                cache_dir = Path("image_cache")
                                cache_dir.mkdir(exist_ok=True)
                                
                                # Generate a unique filename for the image
                                import hashlib
                                image_hash = hashlib.md5(image_url.encode()).hexdigest()
                                image_extension = image_url.split('.')[-1].split('?')[0] if '.' in image_url else 'jpg'
                                cached_image_path = cache_dir / f"{image_hash}.{image_extension}"
                                
                                # Check if image is already cached
                                if cached_image_path.exists():
                                    # Read the cached image file and convert to PIL Image
                                    with open(cached_image_path, 'rb') as f:
                                        image_data = f.read()
                                    cached_image = Image.open(io.BytesIO(image_data))
                                    st.image(cached_image, width=150, caption="Product Image")
                                    image_loaded = True
                                else:
                                    # Download the image
                                    headers = {
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                                        'Referer': 'https://lulurayyangroup.com/',
                                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                                        'Accept-Language': 'en-US,en;q=0.9',
                                        'Accept-Encoding': 'gzip, deflate, br',
                                        'Connection': 'keep-alive',
                                        'Upgrade-Insecure-Requests': '1'
                                    }
                                    
                                    response = requests.get(image_url, timeout=15, headers=headers, allow_redirects=True)
                                    
                                    if response.status_code == 200:
                                        # Check if content is actually an image
                                        content_type = response.headers.get('content-type', '')
                                        if content_type.startswith('image/'):
                                            # Save to cache
                                            with open(cached_image_path, 'wb') as f:
                                                f.write(response.content)
                                            
                                            # Display the image
                                            image = Image.open(io.BytesIO(response.content))
                                            st.image(image, width=150, caption="Product Image")
                                            image_loaded = True
                                        else:
                                            # Content type not image
                                            pass
                                    else:
                                        # HTTP error
                                        pass
                            else:
                                # Domain not reachable, show simple message
                                st.info(f"Image server {domain} is not accessible")
                                
                        except Exception as e:
                            # Silent error handling
                            pass
                        
                        if not image_loaded:
                            st.image("https://via.placeholder.com/150x150?text=Image+Not+Available", width=150)
                                
                    except Exception as e:
                        # Silent error handling
                        st.image("https://via.placeholder.com/150x150?text=Image+Error", width=150)
                else:
                    st.image("https://via.placeholder.com/150x150?text=No+Image", width=150)
            
            with col2:
                st.markdown(f"""
                <div class="product-card">
                    <h3>{product['name']}</h3>
                    <p><strong>Category:</strong> {product['category']} > {product['subcategory']}</p>
                    <p><strong>Brand:</strong> {product['brand']}</p>
                    <p><strong>SKU:</strong> {product['sku']}</p>
                    <p><strong>Price:</strong> {product['price']}</p>
                    <p><strong>Description:</strong> {product['description'][:200]}{'...' if len(product['description']) > 200 else ''}</p>
                    <p><strong>Extracted:</strong> {product['extracted_at']}</p>
                    <a href="{product['url']}" target="_blank">View Product</a>
                </div>
                """, unsafe_allow_html=True)
            
            st.divider()

def clear_image_cache():
    """Clear the image cache directory"""
    import shutil
    cache_dir = Path("image_cache")
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        st.success("Image cache cleared successfully!")
    else:
        st.info("No image cache found.")

def check_image_availability(df):
    """Check availability of all images in the dataset"""
    st.sidebar.markdown("## 🔍 Image Status")
    
    total_images = len(df[df['image_url'].notna() & (df['image_url'] != '')])
    if total_images == 0:
        st.sidebar.info("No images found in dataset")
        return
    
    # Check a sample of images for availability
    sample_size = min(5, total_images)
    sample_images = df[df['image_url'].notna() & (df['image_url'] != '')].sample(n=sample_size)
    
    available_count = 0
    unavailable_count = 0
    
    for _, product in sample_images.iterrows():
        image_url = product['image_url']
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(image_url)
            domain = parsed_url.netloc
            
            import socket
            socket.gethostbyname(domain)
            available_count += 1
        except:
            unavailable_count += 1
    
    st.sidebar.info(f"Sample check: {available_count}/{sample_size} images accessible")
    st.sidebar.info(f"Total images in dataset: {total_images}")
    
    if unavailable_count > 0:
        st.sidebar.warning("Some image servers may be unreachable")

def main():
    """Main application function"""
    # Header
    st.markdown('<h1 class="main-header">🛍️ Lulu Rayyan Products Dashboard</h1>', unsafe_allow_html=True)
    
    # Add cache management in sidebar
    with st.sidebar.expander("🗂️ Cache Management"):
        if st.button("Clear Image Cache"):
            clear_image_cache()
        cache_dir = Path("image_cache")
        if cache_dir.exists():
            cache_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
            st.info(f"Cache size: {cache_size / 1024:.1f} KB")
        else:
            st.info("No image cache found")
    
    # Load data
    data = load_product_data()
    
    if not data:
        st.error("No data available. Please ensure the data file exists and contains valid JSON data.")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Check image availability (after DataFrame is created)
    check_image_availability(df)
    
    # Create filters
    selected_category, selected_subcategory, selected_brand = create_filters(df)
    
    # Filter data
    filtered_df = filter_data(df, selected_category, selected_subcategory, selected_brand)
    
    # Display metrics
    st.markdown("## 📈 Key Metrics")
    display_metrics(filtered_df)
    
    # Display charts
    display_charts(filtered_df)
    
    # Display products
    display_products(filtered_df)
    
    # Data download
    st.markdown("## 📥 Download Data")
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="Download Filtered Data as CSV",
        data=csv,
        file_name=f"lulu_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
    
    # Raw data view
    with st.expander("🔍 View Raw Data"):
        st.dataframe(filtered_df)

if __name__ == "__main__":
    main()
