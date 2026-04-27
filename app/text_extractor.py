import fitz  # pymupdf
import re
from rules import TRANSACTION_RULES, PDF_MARKERS, TRANSACTION_PATTERN
from schema import Transaction


def get_transaction_blocks(document):
    transaction_blocks = []
    flag = False
    for page in document:
        blocks = page.get_text("blocks")
        for block in blocks:
            text = block[4]
            if PDF_MARKERS['start_marker'] in text:
                flag = True
            if PDF_MARKERS['end_marker'] in text:
                break
            if flag:
                transaction_blocks.append(block)
                
    return transaction_blocks


def merge_blocks_on_same_row(blocks, y_tolerance=2):
    if not blocks:
        return []

    # Sort by y1 first, then x1 (top to bottom, left to right)

    groups = []
    current_group = [blocks[0]]

    for i in range(1, len(blocks)):
        current_block = blocks[i]
        last_block = current_group[-1]  # compare against last block IN GROUP not just i-1

        last_y1 = last_block[1]
        curr_y1 = current_block[1]

        if abs(curr_y1 - last_y1) <= y_tolerance:
            # Same row — add to current group
            current_group.append(current_block)
        else:
            # New row — save current group, start fresh
            groups.append(current_group)
            current_group = [current_block]

    # Don't forget the last group
    groups.append(current_group)

    # Merge each group's text in left-to-right order (already sorted by x1)
    merged_texts = []
    for group in groups:
        print(f"group:{group}")
        merged_text = " ".join(block[4].strip() for block in group)
        merged_texts.append(merged_text)

    return merged_texts

def transaction_extractor(file_path):
    doc = fitz.open(file_path)
    
    transactions = []
     
    transaction_blocks = get_transaction_blocks(doc)
    transactions_cleaned = merge_blocks_on_same_row(transaction_blocks)
    #print(transactions_cleaned)
    for text in transactions_cleaned:
        transaction = TRANSACTION_PATTERN.search(text)
        if not transaction:
            continue
        list_result = list(transaction.groups()) 
        #print(block)
        
        for checker_fn, parser_fn in TRANSACTION_RULES:
            if checker_fn(list_result):
                parsed_data = parser_fn(list_result)
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
                break  

    doc.close()
    print(f"\nTotal transactions extracted: {len(transactions)}")
    return transactions