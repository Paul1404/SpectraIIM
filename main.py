import sqlite3
import os
import time
import subprocess
from datetime import datetime
import platform

# Configuration
PING_TARGET = "8.8.8.8"  # Default target for pinging
DNS_TEST_DOMAIN = "google.com"  # Domain to test DNS resolution
PING_INTERVAL = 60  # Interval in seconds between tests
DB_FILE = "spectra_iim.db"

# Database setup
def setup_database():
    """Create the database and table if they do not exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            latency_ms REAL,
            packet_loss REAL,
            jitter_ms REAL,
            download_speed REAL,
            upload_speed REAL,
            dns_resolution_time_ms REAL,
            downtime INTEGER,
            traceroute TEXT
        )
    """)
    conn.commit()
    conn.close()

# Ping function
def ping_target(target: str):
    """Ping a target and return latency, jitter, and packet loss."""
    try:
        result = subprocess.run(
            ["ping", "-c", "4", target],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.split("\n")
            rtt_line = next((line for line in lines if "rtt min/avg/max" in line), None)
            stats = rtt_line.split("=")[1].strip() if rtt_line else None
            latency_avg = float(stats.split("/")[1]) if stats else None
            jitter = float(stats.split("/")[2]) - float(stats.split("/")[0]) if stats else None
            return latency_avg, jitter, 0.0  # 0% packet loss if successful
        else:
            return None, None, 100.0  # 100% packet loss if ping fails
    except Exception as e:
        print(f"Error during ping: {e}")
        return None, None, 100.0

# DNS resolution time test
def test_dns_resolution(domain: str):
    """Test DNS resolution time."""
    try:
        start_time = time.time()
        subprocess.run(["nslookup", domain], capture_output=True, timeout=5)
        end_time = time.time()
        return (end_time - start_time) * 1000  # Convert to milliseconds
    except Exception as e:
        print(f"DNS resolution test failed: {e}")
        return None

# Speed test (dummy placeholder for actual implementation)
def test_speed():
    """Perform speed tests and return download/upload speeds."""
    # TODO: Replace with a library like speedtest-cli for real results
    return 50.0, 10.0  # Dummy download/upload speeds in Mbps

# Traceroute test
def perform_traceroute(target: str):
    """Perform a traceroute and return the path as a string."""
    traceroute_command = ["tracert", target] if platform.system() == "Windows" else ["traceroute", target]
    try:
        result = subprocess.run(
            traceroute_command,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",  # Ensure proper decoding
            errors="replace"   # Replace problematic characters
        )
        return result.stdout.strip() if result.returncode == 0 else "Traceroute failed"
    except Exception as e:
        print(f"Traceroute failed: {e}")
        return "Traceroute error"

# Log results to database
def log_to_database(timestamp, latency, jitter, packet_loss, download, upload, dns_time, downtime, traceroute):
    """Log results into the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO network_logs (
            timestamp, latency_ms, jitter_ms, packet_loss, 
            download_speed, upload_speed, dns_resolution_time_ms, 
            downtime, traceroute
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, latency, jitter, packet_loss, download, upload, dns_time, downtime, traceroute))
    conn.commit()
    conn.close()

# Main monitoring loop
def monitor_network():
    """Continuously monitor the network and log metrics."""
    print("Starting network monitoring...")
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Measure latency, jitter, and packet loss
        latency, jitter, packet_loss = ping_target(PING_TARGET)

        # Test DNS resolution time
        dns_time = test_dns_resolution(DNS_TEST_DOMAIN)

        # Perform speed tests
        download_speed, upload_speed = test_speed()

        # Perform traceroute
        traceroute = perform_traceroute(PING_TARGET)

        # Calculate downtime (assume no response = 100% downtime for now)
        downtime = 1 if latency is None else 0

        # Log results
        log_to_database(
            timestamp, latency, jitter, packet_loss, 
            download_speed, upload_speed, dns_time, 
            downtime, traceroute
        )

        # Print results for debugging
        print(f"[{timestamp}] Latency: {latency} ms, Jitter: {jitter} ms, Packet Loss: {packet_loss}%, "
              f"Download: {download_speed} Mbps, Upload: {upload_speed} Mbps, "
              f"DNS Time: {dns_time} ms, Downtime: {downtime}, Traceroute: {traceroute}")

        time.sleep(PING_INTERVAL)

if __name__ == "__main__":
    setup_database()
    monitor_network()
