import os
import numpy as np
import pickle
import pandas as pd
from dotenv import load_dotenv

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

def categorize_transaction(merchant_name: str, threshold: float = 0.85):
    query_embedding = model.encode([merchant_name])[0]
    scores = cosine_similarity(query_embedding, stored_embeddings)
    
    top_indices = scores.argsort()[::-1][:3]
    top_score = scores[top_indices[0]]
    top_category = df.iloc[top_indices[0]]["Category_clean"]
    top_merchant = df.iloc[top_indices[0]]["Name"]
    
    if top_score >= threshold:
        print(f"top merchant: {top_merchant}")
        print(f"top score: {top_score}")
        print(f"top category: {top_category}")
        return {
            "category": top_category,
            "confidence": float(top_score),
            "matched_to": top_merchant,
            "source": "embeddings"
        }
    else:
        top_matches = [
            (df.iloc[i]["Name"], df.iloc[i]["Category_clean"], float(scores[i]))
            for i in top_indices
        ]
        return {
            "category": None,
            "confidence": float(top_score),
            "top_matches": top_matches,
            "source": "needs_llm"
        }