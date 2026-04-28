import os
import numpy as np
import pickle
import pandas as pd
from dotenv import load_dotenv
from rules import CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI

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

def categorize_transaction(merchant_name: str, bank_category: str, threshold: float = 0.85):
    query_embedding = model.encode([merchant_name])[0]
    scores = cosine_similarity(query_embedding, stored_embeddings)
    
    top_indices = scores.argsort()[::-1][:3]
    top_score = scores[top_indices[0]]
    top_matches = [
        (df.iloc[i]["Name"], df.iloc[i]["Category_clean"], float(scores[i]))
        for i in top_indices
    ]
    top_merchant = df.iloc[top_indices[0]]["Name"]
    
    if top_score >= threshold:
        print(f"top merchant: {top_merchant}")
        print(f"top score: {top_score}")
        print(f"top category: {top_matches[0][1]}")
        
        source = "embeddings"
        category = top_matches[0][1]
    else:
        source = "llm"
        category = llm_handler(merchant_name, top_matches, bank_category, top_score)
    
    return {
        "category": category,
        "confidence": top_score,
        "top_matches": top_matches,
        "source": source,
    }
        
def llm_handler(merchant_name: str, top_matches: list, bank_category: str, top_score: float) -> str:
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

    response = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b:free",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.choices[0].message.content
    print(f"Raw response LLM: {raw}")

    for line in raw.splitlines():
        if line.startswith("CATEGORY:"):
            return line.replace("CATEGORY:", "").strip()

    return "Uncategorized"
    
# test
# l = categorize_transaction("abc","retail and grocery")
# print(l)