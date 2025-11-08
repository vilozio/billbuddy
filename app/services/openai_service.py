"""OpenAI service for receipt OCR and categorization"""
import json
import base64
from typing import Optional
from pathlib import Path
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Config
from app.models.receipt import Receipt
from app.utils.logger import setup_logger

logger = setup_logger(__name__, Config.LOG_LEVEL)


class OpenAIService:
    """Service for processing receipts using OpenAI GPT-4 Vision API"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        logger.info(f"OpenAI service initialized with model: {self.model}")
    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode image to base64 string
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded image string
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _create_receipt_prompt(self) -> str:
        """
        Create structured prompt for receipt extraction
        
        Returns:
            Formatted prompt string
        """
        return """You are a receipt data extraction expert. Analyze the receipt image and extract all relevant information.

Please extract the following information and return it as a JSON object:

{
  "date": "YYYY-MM-DD format (extract transaction date)",
  "merchant": "Store/business name",
  "total": 0.00 (total amount paid as a number),
  "tax": 0.00 (tax amount as a number),
  "payment_method": "cash/credit card/debit card/etc.",
  "category": "automatically categorize based on merchant and items",
  "items": ["item 1", "item 2", "item 3"]
}

Categories to use (choose the most appropriate one):
- Groceries (supermarkets, food stores)
- Dining (restaurants, cafes, fast food)
- Transportation (gas, parking, public transit)
- Utilities (electricity, water, internet, phone)
- Entertainment (movies, events, subscriptions)
- Healthcare (pharmacy, medical)
- Shopping (retail, clothing, electronics)
- Services (repairs, cleaning, professional services)
- Other (if none of the above fit)

Important notes:
- If any field cannot be found, use reasonable defaults: empty string for text, 0.0 for numbers, empty array for items
- Ensure the date is in YYYY-MM-DD format
- Extract ALL items if visible on the receipt
- Be accurate with numerical values
- Return ONLY the JSON object, no additional text or explanation"""
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def process_receipt_image(self, image_path: str) -> Optional[Receipt]:
        """
        Process a receipt image and extract structured data
        
        Args:
            image_path: Path to the receipt image file
            
        Returns:
            Receipt object with extracted data, or None if processing fails
        """
        try:
            logger.info(f"Processing receipt image: {image_path}")
            
            # Encode image
            base64_image = self._encode_image(image_path)
            
            # Create the API request
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self._create_receipt_prompt()
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1  # Low temperature for consistent extraction
            )
            
            # Extract the response
            content = response.choices[0].message.content
            logger.debug(f"OpenAI response: {content}")
            
            # Parse JSON response
            # Sometimes the model might wrap JSON in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(content)
            
            # Create Receipt object
            receipt = Receipt.from_dict(data)
            logger.info(f"Successfully extracted receipt data: {receipt.merchant}, ${receipt.total}")
            
            return receipt
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response content: {content}")
            return None
        except Exception as e:
            logger.error(f"Error processing receipt image: {e}", exc_info=True)
            return None
    
    def process_receipt_pdf(self, pdf_path: str) -> Optional[Receipt]:
        """
        Process a PDF receipt by converting to image first
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Receipt object with extracted data, or None if processing fails
        """
        try:
            from pdf2image import convert_from_path
            
            logger.info(f"Converting PDF to image: {pdf_path}")
            
            # Convert first page of PDF to image
            images = convert_from_path(pdf_path, first_page=1, last_page=1)
            
            if not images:
                logger.error("Failed to convert PDF to image")
                return None
            
            # Save temporary image
            temp_image_path = Path(pdf_path).with_suffix('.jpg')
            images[0].save(temp_image_path, 'JPEG')
            
            # Process the image
            receipt = self.process_receipt_image(str(temp_image_path))
            
            # Clean up temporary image
            temp_image_path.unlink()
            
            return receipt
            
        except ImportError:
            logger.error("pdf2image not installed. Cannot process PDF receipts.")
            return None
        except Exception as e:
            logger.error(f"Error processing PDF receipt: {e}", exc_info=True)
            return None

