import os
import re
import numpy as np
import pickle
import pandas as pd
from dotenv import load_dotenv
from rules import CATEGORIZATION_PROMPT, PROVINCES
from dotenv import load_dotenv
from openai import OpenAI
from collections import defaultdict

load_dotenv()

load_dotenv()
EMBEDDING_MODEL_PATH = os.getenv("EMBEDDING_MODEL_PATH")
EXPENSES_EMBEDDING_DATA_PATH = os.getenv("EXPENSES_EMBEDDING_DATA_PATH")

# Load model and data once at module initialization
print("Loading embedding model and data...")
with open(EMBEDDING_MODEL_PATH, 'rb') as file:
    model = pickle.load(file)
df = pd.read_csv(EXPENSES_EMBEDDING_DATA_PATH)
stored_embeddings = np.array(df["embeddings"].apply(eval).tolist())
print("Model and data loaded successfully!")

def cosine_similarity(a, b):
    return np.dot(a, b.T) / (np.linalg.norm(a) * np.linalg.norm(b, axis=1))

def clean_merchant(name: str) -> str:
    if not isinstance(name, str):
        return ""
    name = re.sub(PROVINCES + r".*$", "", name, flags=re.IGNORECASE)
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

# sometimes categorize_transaction performs better than cate_transaction2
# need to come up with a hybrid solution
# for now gonna keep cate_transaction1 since it is not too strict with the categorization
# as every transacation when  sent to cate_trans2 requires an llm call
# One of the main reasons being the merchant name entered manually in notion is way different
# when compared to what is given in the estatements, example: uber (in notion), Uber holdings (in estatements)
# eventually cate_trans2 will perform better and require fewer and fewer llm calls but untill
# then i would need to rely on another strategy until i get enough data points.
# By perform better i mean maximise the embeddings categorization and reducnig the llm calls  

# this will be the function used primarily (for now)
def categorize_transaction(merchant_name: str, bank_category: str, threshold: float = 0.65):
    try:
        clean_merchant_name = clean_merchant(merchant_name)
        query_embedding = model.encode([clean_merchant_name])[0]
        scores = cosine_similarity(query_embedding, stored_embeddings)
        
        top_indices = scores.argsort()[::-1][:5]
        top_score = scores[top_indices[0]]
        #print(top_score)
        top_matches = [
            (df.iloc[i]["Name_clean"], df.iloc[i]["Category_clean"], float(scores[i]))
            for i in top_indices
        ]

        category_scores = defaultdict(float)
        for _, category, score in top_matches:
            category_scores[category] += score
        
        best_category = max(category_scores, key=category_scores.get)
        aggregated_score = category_scores[best_category] / len(top_matches)
        print(f"{merchant_name}: {best_category} : {aggregated_score}")
        
        if aggregated_score >= threshold:
            source = "embeddings"
            category = best_category
        else:
            source = "llm"
            category = llm_handler(merchant_name, top_matches, bank_category, top_score)
        
        return {
            "category": category or "Uncategorized",
            "confidence": aggregated_score,
            "top_matches": top_matches,
            "source": source,
        }
    except Exception as e:
        print(f"Error in categorize_transaction for {merchant_name}: {e}")
        # Fallback to LLM if embedding fails
        try:
            category = llm_handler(merchant_name, [], bank_category, 0.0)
            return {
                "category": category or "Uncategorized",
                "confidence": 0.0,
                "top_matches": [],
                "source": "llm",
            }
        except Exception as llm_error:
            print(f"LLM fallback also failed: {llm_error}")
            return {
                "category": "Uncategorized",
                "confidence": 0.0,
                "top_matches": [],
                "source": "error",
            }


# new scoring metric - testing
def categorize_transaction2(merchant_name: str, bank_category: str, threshold: float = 0.60):
    TOP_N = 10
    EXACT_MATCH_THRESHOLD = 0.99
    clean_merchant_name = clean_merchant(merchant_name)
    query_embedding = model.encode([clean_merchant_name])[0]
    scores = cosine_similarity(query_embedding, stored_embeddings)
    
    top_indices = scores.argsort()[::-1][:TOP_N]
    top_matches = [
        (df.iloc[i]["Name_clean"], df.iloc[i]["Category_clean"], float(scores[i]))
        for i in top_indices
    ]
    print(f"name {clean_merchant_name}")
    print(f"top matches {top_matches[0:3]}")
    # Squared voting
    category_scores = defaultdict(float)
    for _, category, score in top_matches:
        category_scores[category] += score ** 2

    category_normalized = {
        cat: total / TOP_N
        for cat, total in category_scores.items()
    }

    best_category = max(category_normalized, key=category_normalized.get)
    best_score = category_normalized[best_category]

    print(f"best cate {best_category}, best score {best_score}")
    # Early exit — exact match AND voting agrees
    top_name, top_category, top_score = top_matches[0]
    
    print(f"top cate:{top_category}, top score: {top_score}")
    if top_score >= EXACT_MATCH_THRESHOLD and top_category == best_category:
        return {
            "category": top_category,
            "confidence": best_score,
            "top_matches": top_matches,
            "source": "embeddings",
        }

    if best_score >= threshold:
        source = "embeddings"
        category = best_category
    else:
        source = "llm"
        category = llm_handler(merchant_name, top_matches, bank_category, best_score)

    return {
        "category": category,
        "confidence": best_score,
        "top_matches": top_matches,
        "source": source,
    }
        
def llm_handler(merchant_name: str, top_matches: list, bank_category: str, top_score: float) -> str:
    print("called_llm_handler")
    try:
        client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )
        top_matches_str = "\n".join([
            f"  - '{match[0]}' → {match[1]} (similarity: {match[2]:.2f})"
            for match in top_matches
        ])

        prompt = CATEGORIZATION_PROMPT.format(
            merchant_name = merchant_name,
            bank_category = bank_category,
            top_matches_str = top_matches_str,
        )

        # should implement a model config or something here
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-super-120b-a12b:free",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )

        # Validate response structure
        if not response or not response.choices or len(response.choices) == 0:
            print(f"Invalid LLM response structure for {merchant_name}")
            return "Uncategorized"

        raw = response.choices[0].message.content
        if not raw:
            print(f"Empty LLM response content for {merchant_name}")
            return "Uncategorized"

        #print(f"Raw response LLM: {raw}")

        for line in raw.splitlines():
            if line.startswith("CATEGORY:"):
                category = line.replace("CATEGORY:", "").strip()
                if category:
                    return category

        return "Uncategorized"
    
    except Exception as e:
        print(f"Error in llm_handler for {merchant_name}: {e}")
        return "Uncategorized"
    
# test
# l = categorize_transaction2("walmart","retail and grocery")
# print(l)