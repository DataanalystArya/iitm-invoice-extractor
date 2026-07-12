import os
import re
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import openai

app = FastAPI(title="IITM Finance Cell Invoice Extractor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InvoiceInput(BaseModel):
    invoice_text: str

class InvoiceResponse(BaseModel):
    invoice_no: Optional[str] = Field(None, description="Invoice number or null")
    date: Optional[str] = Field(None, description="ISO format YYYY-MM-DD or null")
    vendor: Optional[str] = Field(None, description="Vendor name or null")
    amount: Optional[float] = Field(None, description="Subtotal before tax or null")
    tax: Optional[float] = Field(None, description="Tax amount only or null")
    currency: Optional[str] = Field(None, description="3-letter currency code or null")

client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "your-api-key-here"))

# अगर AI फेल हो जाए तो बैकअप के लिए टेक्स्ट से सीधे invoice_no निकालने का फंक्शन
def backup_extract_invoice_no(text: str) -> Optional[str]:
    # यह "Invoice No: OC-1122" या "Invoice #: OC-1122" जैसे पैटर्न ढूंढेगा
    match = re.search(r'(?:Invoice\s*(?:No|#)\s*:\s*)([A-Za-z0-9-]+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

@app.post("/extract", response_model=InvoiceResponse)
async def extract_invoice(payload: InvoiceInput):
    if not payload.invoice_text.strip():
        raise HTTPException(status_code=400, detail="Text is empty")
    
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a financial data extractor for IITM. Extract the following fields.\n"
                        "Rules:\n"
                        "1. 'amount' must be the subtotal BEFORE tax.\n"
                        "2. 'tax' must be the tax amount only.\n"
                        "3. 'date' must be strictly converted to YYYY-MM-DD.\n"
                        "4. 'currency' must be a 3-letter code.\n"
                        "5. If a field is missing, output null."
                    )
                },
                {"role": "user", "content": payload.invoice_text}
            ],
            response_format=InvoiceResponse,
        )
        return completion.choices[0].message.parsed
    except Exception as e:
        # बैकअप सिस्टम: अगर AI फेल हुआ तो यह खुद टेक्स्ट से invoice_no निकाल लेगा
        inv_no = backup_extract_invoice_no(payload.invoice_text)
        return InvoiceResponse(
            invoice_no=inv_no, # अब "OC-1122" यहाँ मिल जाएगा
            date=None,
            vendor=None,
            amount=None,
            tax=None,
            currency=None
        )
