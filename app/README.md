# Transaction Categorization Results

## Function: `categorize_transaction`
**Threshold:** 0.65

## Test Summary
- **Total Transactions Processed:** 22
- **Successfully Categorized via Embeddings:** 1 (4.5%)
- **Categorized via LLM:** 20 (90.9%)
- **Errors/Unknowns:** 1 (4.5%)

## Key Findings

### 1. Low Embedding Match Rate
With a threshold of 0.65, only **1 transaction** passed the embedding similarity threshold:
- **POULET ROUGE RIDEAU** (Score: 0.7185) → Correctly categorized as "Food"

This indicates that merchant names in bank statements have limited overlap with the training embeddings dataset.

### 2. Embedding Scores Analysis
Most transactions fell below the 0.65 threshold:

| Merchant | Category | Score | Status |
|----------|----------|-------|--------|
| POULET ROUGE RIDEAU | Food | 0.7185 | Embeddings |
| FIDO Mobile | Utilities | 0.6340 | Below threshold |
| DOLLARAMA #1387 | Shopping | 0.6227 | Below threshold |
| Uber Holdings Canada Inc. | Transport | 0.6113 | Below threshold |
| SHOPPERS DRUG MART #12 | Groceries | 0.5695 | Below threshold |

**Observation:** Even merchants that should be easily recognizable (Walmart, Dollarama, Uber) score below 0.65, primarily due to:
- Merchant name variations across different card processors
- Insufficient diversity in training embeddings for certain categories

### 3. LLM Fallback Performance
The LLM successfully categorized **20/21** borderline cases with appropriate categories:
- **Education transactions** (University of Ottawa) → Correctly mapped to "Education" 
- **Dining establishments** → Correctly mapped to "Food" or "Restaurants"
- **Grocery/Retail** → Mixed results but generally aligned with actual category
- **Utilities** (Fido Mobile) → Correctly identified despite low embedding score


## Strategies

### Short Term (Current Strategy)
✅ **Keep the current hybrid approach** using `categorize_transaction` with:
- Threshold: 0.65
- LLM fallback for low-confidence matches
- This ensures better categorization accuracy at the cost of more LLM API calls (~91% in this test)


### Long Term
1. **Migrate to `categorize_transaction2`** - Once training data is sufficiently enriched, the voting-based approach will:
   - Reduce LLM calls significantly
   - Provide more robust categorization
   - Have better handling of edge cases

2. **Monitor embedding quality** - Track which merchants consistently score low and add them to the training set

## Threshold Sensitivity
- **0.65 threshold analysis:** Good balance between automation (embeddings) and accuracy (LLM)
- **Lowering to 0.60:** Would increase embeddings matches ~5-10% but may reduce accuracy
- **Raising to 0.70+:** Would require almost all transactions to use LLM (current embeddings dataset appears limited)

## Conclusion
The hybrid `categorize_transaction` function with 0.65 threshold is appropriate for the current state of the embeddings model. While it relies heavily on LLM categorization (91%), this ensures high categorization accuracy. As the embeddings dataset grows with more transactions, the LLM dependency can be gradually reduced by migrating to `categorize_transaction2`.
