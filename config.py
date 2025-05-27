import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # InfluxDB settings
    INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
    INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
    INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "network_logs")

    # Monitoring settings
    PING_TARGET = os.getenv("PING_TARGET", "1.1.1.1")
    DNS_TEST_DOMAIN = os.getenv("DNS_TEST_DOMAIN", "one.one.one.one")
    PING_INTERVAL = int(os.getenv("PING_INTERVAL", 60))
    SPEEDTEST_INTERVAL = int(os.getenv("SPEEDTEST_INTERVAL", 1800))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")