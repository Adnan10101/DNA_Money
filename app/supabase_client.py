import os
import asyncio
from typing import List, Dict, Optional
from dotenv import load_dotenv
from supabase import create_client, Client
from schema import CategoryResult

load_dotenv()


class SupabaseManager:
    _instance: Optional['SupabaseManager'] = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._initialize_client()
            
    def _initialize_client(self):
        """Initialize Supabase client"""
        supabase_url = os.getenv("SUPABASE_URL")
        
        supabase_key = os.getenv("SUPABASE_KEY")
        print(supabase_key)
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "Supabase URL and API key are required. "
                "Set SUPABASE_URL and SUPABASE_KEY environment variables."
            )
        
        self._client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized successfully!")
    
    @property
    def client(self) -> Client:
        """Get the Supabase client"""
        if self._client is None:
            self._initialize_client()
        return self._client
    
    async def upload_category_analysis(
        self, 
        category_analysis: List[CategoryResult], 
        job_id: str,
        table_name: str = "category_analysis"
    ) -> Dict:
        """
        Upload category analysis results to Supabase asynchronously
        
        Args:
            category_analysis: List of CategoryResult objects to upload
            job_id: Job ID for tracking
            table_name: Name of the Supabase table to insert into
            
        Returns:
            Dictionary with upload status and results
        """
        try:
            if not category_analysis:
                return {
                    "success": False,
                    "message": "No data to upload",
                    "rows_inserted": 0
                }
            
            # Convert CategoryResult objects to dictionaries
            data_to_insert = []
            for item in category_analysis:
                record = {
                    "job_id": job_id,
                    "merchant_name": item.name,
                    "bank_category": item.bank_category,
                    "actual_category": item.actual_category,
                    "source": item.source,
                    "confidence_score": item.confidence_score,
                    "top_matches": item.top_matches  # JSON array
                }
                data_to_insert.append(record)
            
            # Run database operation in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._insert_data,
                table_name,
                data_to_insert
            )
            
            return {
                "success": True,
                "message": f"Successfully uploaded {len(data_to_insert)} records",
                "rows_inserted": len(data_to_insert),
                "job_id": job_id
            }
            
        except Exception as e:
            error_msg = f"Error uploading category analysis to Supabase: {str(e)}"
            print(f"[Supabase Upload Error] {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "rows_inserted": 0,
                "job_id": job_id
            }
    
    def _insert_data(self, table_name: str, data: List[Dict]) -> Dict:
        """
        Insert data into Supabase table (blocking operation)
        This runs in a thread pool executor
        """
        response = self.client.table(table_name).insert(data).execute()
        return response
    
    async def upload_batch_with_retry(
        self,
        category_analysis: List[CategoryResult],
        job_id: str,
        table_name: str = "category_analysis",
        max_retries: int = 3,
        batch_size: int = 100
    ) -> Dict:
        
        total_inserted = 0
        failed_batches = 0
        
        # Split into batches
        batches = [
            category_analysis[i:i + batch_size]
            for i in range(0, len(category_analysis), batch_size)
        ]
        
        print(f"[Supabase] Uploading {len(category_analysis)} records in {len(batches)} batches")
        
        for batch_idx, batch in enumerate(batches):
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    result = await self.upload_category_analysis(batch, job_id, table_name)
                    
                    if result["success"]:
                        total_inserted += result["rows_inserted"]
                        print(f"[Supabase] Batch {batch_idx + 1}/{len(batches)} uploaded successfully")
                        success = True
                    else:
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 2 ** retry_count
                            print(f"[Supabase] Batch {batch_idx + 1} failed, retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            failed_batches += 1
                            print(f"[Supabase] Batch {batch_idx + 1} failed after {max_retries} retries")
                
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count
                        print(f"[Supabase] Error in batch {batch_idx + 1}, retrying in {wait_time}s: {str(e)}")
                        await asyncio.sleep(wait_time)
                    else:
                        failed_batches += 1
                        print(f"[Supabase] Batch {batch_idx + 1} failed after {max_retries} retries: {str(e)}")
        
        return {
            "success": failed_batches == 0,
            "total_inserted": total_inserted,
            "total_records": len(category_analysis),
            "failed_batches": failed_batches,
            "job_id": job_id,
            "message": f"Uploaded {total_inserted}/{len(category_analysis)} records"
        }
    
    # async def fetch_analysis_by_job_id(
    #     self,
    #     job_id: str,
    #     table_name: str = "category_analysis"
    # ) -> List[Dict]:
    #     """
    #     Fetch category analysis records by job_id
    #     """
    #     try:
    #         loop = asyncio.get_event_loop()
    #         response = await loop.run_in_executor(
    #             None,
    #             lambda: self.client.table(table_name).select("*").eq("job_id", job_id).execute()
    #         )
    #         return response.data if response else []
    #     except Exception as e:
    #         print(f"[Supabase] Error fetching data: {str(e)}")
    #         return []
