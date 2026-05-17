import os
from typing import Optional, List
from notion_client import Client
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
    

    def get_transactions(self, limit: int = 100):
        """
        Retrieve transactions from the Notion database.
        """

        try:
            response = self.client.databases.query(
                database_id=self.database_id,
                page_size=limit
            )

            transactions = []

            for page in response["results"]:
                props = page["properties"]

                # Safe extraction helpers
                name = ""
                if props["Name"]["title"]:
                    name = props["Name"]["title"][0]["plain_text"]

                amount = props["Amount"]["number"]

                date = None
                if props["Date"]["date"]:
                    date = props["Date"]["date"]["start"]

                category = None
                if props["Category"]["relation"]:
                    category = props["Category"]["relation"][0]["id"]

                transactions.append({
                    "id": page["id"],
                    "name": name,
                    "amount": amount,
                    "date": date,
                    "category": category
                })

            return transactions

        except Exception as e:
            print(f"✗ Error retrieving transactions: {str(e)}")
            raise
    
notion = NotionManager()
transaction = notion.get_transactions()
for t in transaction:
    print(t)