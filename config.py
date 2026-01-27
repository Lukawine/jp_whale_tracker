import os

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBHMYa_sp4sgqV78K0Xl-CqKlaxG80zAZE") # Directly writing API key as requested
    TDNET_BASE_URL = "https://www.release.tdnet.info/inbs/" # This might need adjustment based on actual TDnet structure
    TARGET_STOCK_CODES = ['7203', '9984'] # Example stock codes (Toyota, Softbank Group)
    # Keywords to filter announcements (Using actual Japanese terms found in TDnet titles)
    # 業績予想 (Earnings Forecast/Revision), 自己株式 (Treasury Stock/Buyback), 売出 (Offering/Sale)
    ANNOUNCEMENT_KEYWORDS = ["業績予想", "自己株式", "売出"]
    DOWNLOAD_DIR = "./data/downloads"
    ANALYSIS_DIR = "./data/analysis"
    # Database Config
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tdnet_analyzer.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHEDULER_API_ENABLED = True
