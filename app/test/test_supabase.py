import requests

from schema import CategoryResult
from task_handler import upload_category_analysis_to_supabase
import asyncio

async def main():
    job_id = "job_001"

    sample_data = [
        CategoryResult(
            name="Starbucks",
            bank_category="Food & Drink",
            actual_category="Coffee Shops",
            source="model",
            confidence_score=0.95,
            top_matches=[{"category": "Coffee Shops", "score": 0.95}]
        )
    ]

    result = await upload_category_analysis_to_supabase(
        job_id=job_id,
        category_analysis=sample_data,
        use_batch_with_retry=True  # handles retries + batching automatically
    )

    print(result)

asyncio.run(main())