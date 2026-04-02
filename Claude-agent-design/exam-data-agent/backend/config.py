import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "dws")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

# 安全限制
SQL_TIMEOUT_SECONDS = 30
MAX_RESULT_ROWS = 1000
MAX_INPUT_LENGTH = 500
ALLOWED_TABLES = [
    "dws.dws_user_daily_quiz_stats_day",
    "dws.dws_active_user_report_week",
    "dws.dws_pay_user_report_week",
    "dws.dws_retention_user_report_week",
    "dws.dws_user_behavior_report_week",
    "dws.dws_customer_service",
    "dws.dws_v_salesflow_dateil",
]
