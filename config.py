import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = int(os.getenv("DB_PORT", 5432))

    PING_TARGET = os.getenv("PING_TARGET", "1.1.1.1")
    DNS_TEST_DOMAIN = os.getenv("DNS_TEST_DOMAIN", "one.one.one.one")
    PING_INTERVAL = int(os.getenv("PING_INTERVAL", 60))
    SPEEDTEST_INTERVAL = int(os.getenv("SPEEDTEST_INTERVAL", 1800))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")