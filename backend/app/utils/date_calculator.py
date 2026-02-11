"""
Date Calculation Helper for Memory Collector Agent

This module provides utility functions to help calculate dates from relative time expressions.
The Memory Collector agent uses these patterns to intelligently interpret user input.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
import re


class DateCalculator:
    """Helper class for calculating dates from natural language expressions."""
    
    @staticmethod
    def parse_relative_date(expression: str, reference_date: Optional[datetime] = None) -> Tuple[Optional[datetime], str]:
        """
        Parse a relative date expression into an actual datetime.
        
        Args:
            expression: Natural language date expression
            reference_date: Reference date (defaults to now)
            
        Returns:
            Tuple of (calculated_datetime, interpretation_explanation)
        """
        if reference_date is None:
            reference_date = datetime.now()
        
        expr_lower = expression.lower().strip()
        
        # Last summer
        if "last summer" in expr_lower:
            current_year = reference_date.year
            if reference_date.month >= 9:  # After summer
                summer_year = current_year
            else:
                summer_year = current_year - 1
            return datetime(summer_year, 7, 15, 14, 0, 0), f"Calculated as mid-July {summer_year}"
        
        # This summer
        if "this summer" in expr_lower or "summer" in expr_lower:
            current_year = reference_date.year
            if reference_date.month < 6:  # Before summer
                summer_year = current_year
            else:
                summer_year = current_year
            return datetime(summer_year, 7, 15, 14, 0, 0), f"Calculated as mid-July {summer_year}"
        
        # X years ago
        years_match = re.search(r'(\d+)\s+years?\s+ago', expr_lower)
        if years_match:
            years = int(years_match.group(1))
            date = reference_date - timedelta(days=365 * years)
            return date, f"Calculated as {years} years before {reference_date.strftime('%Y-%m-%d')}"
        
        # X months ago
        months_match = re.search(r'(\d+)\s+months?\s+ago', expr_lower)
        if months_match:
            months = int(months_match.group(1))
            date = reference_date - timedelta(days=30 * months)  # Approximate
            return date, f"Calculated as approximately {months} months before {reference_date.strftime('%Y-%m-%d')}"
        
        # Last Christmas
        if "last christmas" in expr_lower:
            current_year = reference_date.year
            if reference_date.month == 12 and reference_date.day >= 25:
                christmas_year = current_year
            else:
                christmas_year = current_year - 1
            return datetime(christmas_year, 12, 25, 10, 0, 0), f"Calculated as Christmas {christmas_year}"
        
        # Last birthday / my birthday
        if "birthday" in expr_lower:
            # This is tricky - would need user's birth month
            # For now, return None and explanation
            return None, "Birthday mentioned but specific date unknown - would need birth month"
        
        # Specific holiday patterns
        holidays = {
            "christmas": (12, 25),
            "new year": (1, 1),
            "valentine": (2, 14),
            "halloween": (10, 31),
            "thanksgiving": (11, 25),  # Approximate
        }
        
        for holiday, (month, day) in holidays.items():
            if holiday in expr_lower:
                # Check if year is mentioned
                year_match = re.search(r'\b(19|20)\d{2}\b', expression)
                if year_match:
                    year = int(year_match.group(0))
                else:
                    # Use most recent occurrence
                    year = reference_date.year
                    if reference_date.month > month or (reference_date.month == month and reference_date.day > day):
                        year = reference_date.year
                    else:
                        year = reference_date.year - 1
                
                return datetime(year, month, day, 10, 0, 0), f"Calculated as {holiday.title()} {year}"
        
        # Explicit year mentioned
        year_match = re.search(r'\b(19|20)\d{2}\b', expression)
        if year_match:
            year = int(year_match.group(0))
            # Try to extract month
            months = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12
            }
            for month_name, month_num in months.items():
                if month_name in expr_lower:
                    return datetime(year, month_num, 15, 12, 0, 0), f"Calculated as mid-{month_name.title()} {year}"
            
            # Just year, no month - use mid-year
            return datetime(year, 6, 15, 12, 0, 0), f"Calculated as mid-{year} (no specific month mentioned)"
        
        # Could not parse
        return None, "Could not calculate specific date from expression"


# Example usage patterns for the agent:
EXAMPLE_CALCULATIONS = {
    "last summer": "2025-07-15 14:00:00 (if current date is 2026-02-07)",
    "2 years ago": "2024-02-07 (if current date is 2026-02-07)",
    "Christmas 2020": "2020-12-25 10:00:00",
    "last Christmas": "2025-12-25 10:00:00 (if current date is 2026-02-07)",
    "my wedding in June 2020": "2020-06-15 12:00:00",
    "Halloween last year": "2025-10-31 10:00:00",
}


if __name__ == "__main__":
    # Test the calculator
    calculator = DateCalculator()
    reference = datetime(2026, 2, 7)  # Today's date
    
    test_cases = [
        "last summer",
        "2 years ago",
        "Christmas 2020",
        "last Christmas",
        "my wedding in June 2020",
    ]
    
    print("Date Calculation Test Results:")
    print("=" * 70)
    for expression in test_cases:
        calculated, explanation = calculator.parse_relative_date(expression, reference)
        print(f"\nInput: {expression}")
        print(f"Result: {calculated}")
        print(f"Explanation: {explanation}")
