import pandas as pd
from typing import List
from io import BytesIO
from datetime import datetime


class ExportService:
    """Service for exporting data to various formats."""
    
    @staticmethod
    def export_to_csv(data: List[dict], filename: str = None) -> BytesIO:
        """
        Export data to CSV format.
        
        Args:
            data: List of dictionaries to export
            filename: Optional filename
        
        Returns:
            BytesIO object containing CSV data
        """
        df = pd.DataFrame(data)
        
        # Convert datetime columns to string
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        buffer = BytesIO()
        df.to_csv(buffer, index=False, encoding='utf-8')
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def export_to_excel(data: List[dict], filename: str = None) -> BytesIO:
        """
        Export data to Excel format.
        
        Args:
            data: List of dictionaries to export
            filename: Optional filename
        
        Returns:
            BytesIO object containing Excel data
        """
        df = pd.DataFrame(data)
        
        # Convert datetime columns to string
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Data')
        
        buffer.seek(0)
        return buffer


# Singleton instance
export_service = ExportService()
