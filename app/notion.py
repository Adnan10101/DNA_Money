import os
from typing import Optional, List
from notion_client import Client
from schema import Transaction
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class NotionManager:
    """Manager for Notion API interactions"""
    
    def __init__(self, api_token: Optional[str] = None, database_id: Optional[str] = None):
        self.api_token = api_token or os.getenv("NOTION_API_TOKEN")
        self.database_id = database_id or os.getenv("NOTION_DATABASE_ID")
        
        if not self.api_token or not self.database_id:
            raise ValueError(
                "Notion API token and database ID are required. "
                "Set NOTION_API_TOKEN and NOTION_DATABASE_ID environment variables."
            )
        
        self.client = Client(auth=self.api_token)
    
    # defining a column cleanup here for now, ideally i would need to clean it up as soon as 
    # it as has been fetched/categorized from taskhandler
    def format_date(self,date_str, year=2026):
        # Convert "Mar 25" -> "2026-03-25"
        dt = datetime.strptime(f"{date_str} {year}", "%b %d %Y")
        return dt.strftime("%Y-%m-%d")
    
    
    def add_transaction(self, transaction: Transaction) -> dict:
        try:
            category = self.get_notion_category_id(transaction.actual_category)
            page = self.client.pages.create(
                parent = {"database_id" : self.database_id},
                properties = {
                    "Name": {"title": [{"text": {"content": transaction.name}}]},
                    "Category": {"relation":[{"id": category}]},
                    "Amount": {"number": transaction.amount},
                    "Date":{"date":{"start": self.format_date(transaction.transaction_date)}},
                }
            )
           
            print(f"✓ Added transaction to Notion: {transaction.name} ({transaction.amount})")
            return page
        except Exception as e:
            print(f"✗ Error adding transaction to Notion: {transaction.name} - {str(e)}")
            raise
    
    def add_transactions_batch(self, transactions: List[Transaction]) -> tuple:
        successful_count = 0
        failed_transactions = []
        
        for trans in transactions:
            try:
                self.add_transaction(trans)
                successful_count += 1
            except Exception as e:
                print(f"Failed to add transaction: {trans.name}")
                failed_transactions.append({
                    "transaction": trans,
                    "error": str(e)
                })
        
        return successful_count, failed_transactions


    # notion has its own way of naming categories (done by a uuid smh)
    def get_notion_category_id(self, category_name):
        db = self.client.databases.retrieve(database_id="2fdf202d-177d-81f3-8758-ee21dbb9bd19")
        response = self.client.data_sources.query(
            data_source_id=db["data_sources"][0]["id"],
            filter={
                "property": "Name",
                "title": {
                    "equals": category_name
                }
            }
        )
        
        results = response["results"]
        print(results)
        if results:
            return results[0]["id"]
        
        return None