import os

# Set test environment before importing app modules
os.environ["APP_ENV"] = "test"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""
os.environ["SCOUT_WEBHOOK_URL"] = ""
