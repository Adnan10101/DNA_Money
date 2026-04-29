import re

# ============================================================================
# PDF MARKERS - Configure these if PDF structure changes
# ============================================================================
PDF_MARKERS = {
    'start_marker': "Your new charges and credits\n",
    'end_marker': "Transactions are assigned a spend category based on where the goods or services are purchased, not on what was purchased. For example,\nitems purchased at a convenience store in a gas station will appear under Transportation, not Retail and Grocery.\n"
}

# ============================================================================
# Notion Categories
# ============================================================================
NOTION_CATEGORIES = [
    "Shopping",
    "Entertainments",
    "Utilities",
    "Education",
    "Transport",
    "Health & Wellness",
    "Rent",
    "Groceries",
    "Food",
    "Charity",
    "Home",
    "Travel",
    "Housing",
    "subscriptions"
]

# ============================================================================
# LLM Prompt - need to work on this
# ============================================================================
CATEGORIZATION_PROMPT = """You are categorizing a bank transaction for a personal budget tracker.

Merchant name: "{merchant_name}"
Bank's category: "{bank_category}"

Closest matches from the user's transaction history (all low confidence):
{top_matches_str}

Available categories to choose from:
""" + ", ".join(NOTION_CATEGORIES) + """

Reason step by step:
1. Assess whether the embedding matches are useful or too low confidence to trust
2. Consider what the bank's category tells you
3. Consider what the merchant name itself suggests
4. Pick the single best category from the available list

Respond in this exact format:
REASONING: <your step by step reasoning>
CATEGORY: <single category name from the list above>"""

# ============================================================================
# PATTERN DEFINITIONS
# ============================================================================
date_pattern = r"^[A-Z][a-z]{2}\s\d{2}$"

PROVINCES = r"\b(AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT)\b"

TRANSACTION_PATTERN = re.compile(
    r"([A-Z][a-z]{2}\s+\d{1,2})\n"  # transaction date (Jan 06)
    r"([A-Z][a-z]{2}\s+\d{1,2})\s*" # post date (Feb 09)
    r"(?:Ý\s*)?"                      # optional Ý character
    r"([^\n]+)\n"                     # name/description
    r"([^\n]+)\n"                     # category
    r"(-?\d+\.?\d*)",                   # amount (handles 11.95 or 8.50 or 8 etc)
    re.DOTALL
)

# ============================================================================
# TRANSACTION RULE: YD-Character (Ý) Handling
# When Ý character appears between post_date and description
# ============================================================================
def is_yd_transaction(lines):
    """Check if transaction has Ý character separating post_date from description"""
    if len(lines) < 4:
        return False
    # Ý typically appears in the second line (post_date line)
    for line in lines:
        if "Ý" in line:
            return True
    return False

def parse_yd_transaction(lines):
    """
    Parse transaction with Ý character.
    Example: ['Jan 31', 'Feb 02 Ý UBER CANADA/UBEREATS TORONTO ON', 'Restaurants', '20.00']
    After split: transaction_date, post_date, name, category, amount
    """
    if len(lines) < 4:
        return None
    
    transaction_date = lines[0]
    
    # Find and split the line containing Ý
    post_date_and_name = lines[1]
    if "Ý" in post_date_and_name:
        parts = post_date_and_name.split("Ý")
        post_date = parts[0].strip()
        name = parts[1].strip()
    else:
        return None
    
    category = lines[2]
    amount = lines[3]
    
    return {
        "transaction_date": transaction_date,
        "post_date": post_date,
        "name": name,
        "category": category,
        "amount": amount,
    }

# ============================================================================
# TRANSACTION RULE: Normal Transaction (5 fields)
# ============================================================================
def is_normal_transaction(lines):
    """Check if transaction is in standard format (5 fields with date pattern match)"""
    return len(lines) == 5 and re.match(date_pattern, lines[0])

def parse_normal_transaction(lines):
    """Parse standard transaction format"""
    return {
        "transaction_date": lines[0],
        "post_date": lines[1],
        "name": lines[2],
        "category": lines[3],
        "amount": lines[4],
    }

# ============================================================================
# TRANSACTION RULES - Ordered by priority (first match wins)
# ============================================================================
TRANSACTION_RULES = [
    #(is_yd_transaction, parse_yd_transaction),      # Check Ý rule first (highest priority)
    (is_normal_transaction, parse_normal_transaction)  # Fall back to normal parsing
]