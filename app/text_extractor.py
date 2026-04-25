import fitz  # pymupdf
import re
from rules import TRANSACTION_RULES, PDF_MARKERS
from schema import Transaction


def transaction_extractor(file_path):
    doc = fitz.open(file_path)
    
    transactions = []
    capture = False
    
    for page in doc:
        blocks = page.get_text("blocks")
        
        for block in blocks:
            text = block[4]
            
            if PDF_MARKERS['start_marker'] in text:
                capture = True
                continue
            
            if PDF_MARKERS['end_marker'] in text:
                capture = False
                continue
            
            if capture:
                lines = text.strip().split("\n")
                print(f"Processing lines: {lines}")
                
                # Needs fixing, probably updating the rules 
                for checker_fn, parser_fn in TRANSACTION_RULES:
                    if checker_fn(lines):
                        parsed_data = parser_fn(lines)
                        if parsed_data:
                            transaction_data = Transaction(
                                transaction_date=parsed_data["transaction_date"],
                                post_date=parsed_data["post_date"],
                                name=parsed_data["name"],
                                bank_category=parsed_data["category"],
                                amount=parsed_data["amount"],
                            )
                            transactions.append(transaction_data)
                            print(f"✓ Parsed: {transaction_data}")
                        break  # Stop at first matching rule
    
    doc.close()
    print(f"\nTotal transactions extracted: {len(transactions)}")
    return transactions