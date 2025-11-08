"""Receipt data model"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Receipt:
    """
    Data model for a receipt with all extracted information
    """
    date: str  # Transaction date in YYYY-MM-DD format
    merchant: str  # Merchant or store name
    total: float  # Total amount paid
    tax: float  # Tax amount
    payment_method: str  # Payment method (cash, card, etc.)
    category: str  # Category (groceries, dining, utilities, etc.)
    items: List[str]  # List of purchased items
    drive_link: str = ""  # Google Drive link to the receipt file
    
    def to_sheet_row(self) -> List:
        """
        Convert receipt to a list format suitable for Google Sheets
        Returns: [Date, Merchant, Amount, Tax, Payment Method, Category, Items, Drive Link]
        """
        items_str = ", ".join(self.items) if self.items else "N/A"
        return [
            self.date,
            self.merchant,
            self.total,
            self.tax,
            self.payment_method,
            self.category,
            items_str,
            self.drive_link
        ]
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Receipt':
        """
        Create a Receipt instance from a dictionary
        """
        return cls(
            date=data.get('date', ''),
            merchant=data.get('merchant', ''),
            total=float(data.get('total', 0.0)),
            tax=float(data.get('tax', 0.0)),
            payment_method=data.get('payment_method', ''),
            category=data.get('category', ''),
            items=data.get('items', []),
            drive_link=data.get('drive_link', '')
        )
    
    def __str__(self) -> str:
        """String representation of the receipt"""
        items_preview = ", ".join(self.items[:3]) if self.items else "N/A"
        if len(self.items) > 3:
            items_preview += f" ... (+{len(self.items) - 3} more)"
        
        return (
            f"Receipt:\n"
            f"  Date: {self.date}\n"
            f"  Merchant: {self.merchant}\n"
            f"  Total: ${self.total:.2f}\n"
            f"  Tax: ${self.tax:.2f}\n"
            f"  Payment: {self.payment_method}\n"
            f"  Category: {self.category}\n"
            f"  Items: {items_preview}"
        )

