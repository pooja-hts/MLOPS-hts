import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
import streamlit as st

class LuluDataLoader:
    """Data loader for Lulu Rayyan products"""
    
    def __init__(self, data_path: str = "data/lulurayyan_products.json"):
        self.data_path = Path(data_path)
        self.data = None
        self.df = None
    
    def load_data(self) -> List[Dict]:
        """Load product data from JSON file"""
        try:
            if self.data_path.exists():
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                return self.data
            else:
                st.error(f"Data file not found at: {self.data_path.absolute()}")
                return []
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return []
    
    def get_dataframe(self) -> pd.DataFrame:
        """Get data as pandas DataFrame"""
        if self.df is None:
            if self.data is None:
                self.load_data()
            if self.data:
                self.df = pd.DataFrame(self.data)
        return self.df
    
    def get_categories(self) -> List[str]:
        """Get unique categories"""
        df = self.get_dataframe()
        if df is not None and not df.empty:
            return sorted(df['category'].unique().tolist())
        return []
    
    def get_subcategories(self, category: str = None) -> List[str]:
        """Get subcategories for a specific category"""
        df = self.get_dataframe()
        if df is not None and not df.empty:
            if category:
                filtered_df = df[df['category'] == category]
                return sorted(filtered_df['subcategory'].unique().tolist())
            else:
                return sorted(df['subcategory'].unique().tolist())
        return []
    
    def get_brands(self) -> List[str]:
        """Get unique brands"""
        df = self.get_dataframe()
        if df is not None and not df.empty:
            return sorted(df['brand'].unique().tolist())
        return []
    
    def filter_data(self, category: str = None, subcategory: str = None, brand: str = None) -> pd.DataFrame:
        """Filter data based on criteria"""
        df = self.get_dataframe()
        if df is None or df.empty:
            return pd.DataFrame()
        
        filtered_df = df.copy()
        
        if category and category != 'All':
            filtered_df = filtered_df[filtered_df['category'] == category]
        
        if subcategory and subcategory != 'All':
            filtered_df = filtered_df[filtered_df['subcategory'] == subcategory]
        
        if brand and brand != 'All':
            filtered_df = filtered_df[filtered_df['brand'] == brand]
        
        return filtered_df
    
    def get_metrics(self, df: pd.DataFrame) -> Dict:
        """Calculate key metrics from filtered data"""
        if df.empty:
            return {
                'total_products': 0,
                'categories': 0,
                'brands': 0,
                'avg_price': 0
            }
        
        # Extract numeric price values
        price_values = df['price'].str.extract(r'(\d+\.?\d*)').astype(float)
        avg_price = price_values.mean() if not price_values.empty else 0
        
        return {
            'total_products': len(df),
            'categories': df['category'].nunique(),
            'brands': df['brand'].nunique(),
            'avg_price': round(avg_price, 2) if not pd.isna(avg_price) else 0
        }
