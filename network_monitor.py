import time
import subprocess
import platform
from datetime import datetime, timedelta
from typing import Optional, Tuple, Any

import psycopg2
from psycopg2 import sql, OperationalError, IntegrityError
from speedtest import Speedtest, ConfigRetrievalError

from config import Config
from logging_setup import setup_logger

logger = setup_logger()

DB_CONFIG = {
    "dbname": Config.DB_NAME,
    "user": Config.DB_USER,
    "password": Config.DB_PASSWORD,
    "host": Config.DB_HOST,
    "port": Config.DB_PORT,
}

def validate_database_connection() -> None:
    """Validate database connection for the application user."""
    try:
        with psycopg2.connect(**DB_CONFIG):
            logger.info("Database connection successful!")
    except OperationalError as op_err:
        logger.error(f"Operational error during database connection: {op_err}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error connecting to database: {e}")
        raise

def setup_database() -> None:
    """Create the PostgreSQL database table if it does not exist."""
    logger.info("Starting database setup...")
    try:
        validate_database_connection()
        create_table_query = """
CREATE TABLE IF NOT EXISTS network_logs (
id SERIAL PRIMARY KEY,
timestamp TIMESTAMP NOT NULL,
latency_ms REAL,
packet_loss REAL,
jitter_ms REAL,
download_speed REAL,
upload_speed REAL,
dns_resolution_time_ms REAL,
downtime BOOLEAN,
traceroute TEXT
)
        """
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                logger.info("Table 'network_logs' is ready.")
    except psycopg2.Error as db_err:
        logger.error(f"Database error during setup: {db_err}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during database setup: {e}")
        raise

def ping_target(target: str) -> Tuple[Optional[float], Optional[float], float]:
    """Ping a target and return latency, jitter, and packet loss."""
    logger.info(f"Pinging target: {target}")
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
            if rtt_line:
                stats = rtt_line.split("=")[1].strip().replace(" ms", "")
                min_rtt, avg_rtt, max_rtt, _ = map(float, stats.split("/"))
                jitter = max_rtt - min_rtt
                logger.debug(f"Ping stats: Latency={avg_rtt} ms, Jitter={jitter} ms")
                return avg_rtt, jitter, 0.0
            else:
                logger.warning("Ping output did not contain RTT stats.")
                return None, None, 100.0
        else:
            logger.warning(f"Ping command failed with return code {result.returncode}.")
            return None, None, 100.0
    except subprocess.TimeoutExpired:
        logger.error(f"Ping command timed out for target: {target}")
        return None, None, 100.0
    except Exception as e:
        logger.exception(f"Error during ping to {target}: {e}")
        return None, None, 100.0

def test_dns_resolution(domain: str) -> Optional[float]:
    """Test DNS resolution time."""
    logger.info(f"Testing DNS resolution for domain: {domain}")
    try:
        start_time = time.time()
        result = subprocess.run(
            ["nslookup", domain],
            capture_output=True,
            timeout=5
        )
        end_time = time.time()
        if result.returncode == 0:
            resolution_time = (end_time - start_time) * 1000
            logger.debug(f"DNS resolution time for {domain}: {resolution_time:.2f} ms")
            return resolution_time
        else:
            logger.warning(f"DNS resolution command failed with return code {result.returncode}.")
            return None
    except subprocess.TimeoutExpired:
        logger.error(f"DNS resolution command timed out for domain: {domain}")
        return None
    except Exception as e:
        logger.exception(f"Error during DNS resolution for {domain}: {e}")
        return None

def test_speed() -> Tuple[Optional[float], Optional[float]]:
    """Perform speed tests and return download/upload speeds."""
    logger.info("Starting speed test.")
    try:
        st = Speedtest()
        st.get_best_server()
        download_speed = st.download() / 1_000_000
        upload_speed = st.upload() / 1_000_000
        logger.debug(f"Speed test results: Download={download_speed:.2f} Mbps, Upload={upload_speed:.2f} Mbps")
        return download_speed, upload_speed
    except ConfigRetrievalError as e:
        logger.error(f"Blocked by Speedtest API: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Error during speed test: {e}")
        return None, None

def perform_traceroute(target: str) -> str:
    """Perform a traceroute and return the path as a string."""
    logger.info(f"Starting traceroute to target: {target}")
    traceroute_command = ["tracert", target] if platform.system() == "Windows" else ["traceroute", target]
    try:
        result = subprocess.run(
            traceroute_command,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode == 0:
            logger.debug(f"Traceroute to {target} completed successfully.")
            return result.stdout.strip()
        else:
            logger.warning(f"Traceroute to {target} failed with return code {result.returncode}.")
            return "Traceroute failed"
    except subprocess.TimeoutExpired:
        logger.error(f"Traceroute command timed out for target: {target}")
        return "Traceroute timeout"
    except Exception as e:
        logger.exception(f"Unexpected error during traceroute to {target}: {e}")
        return "Traceroute error"

def log_to_database(log_data: Tuple[Any, ...]) -> None:
    """Log results into the PostgreSQL database."""
    logger.info("Logging data to the database.")
    insert_query = """
INSERT INTO network_logs (
timestamp, latency_ms, jitter_ms, packet_loss,
download_speed, upload_speed, dns_resolution_time_ms,
downtime, traceroute
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(insert_query, log_data)
                conn.commit()
                logger.debug(f"Data logged successfully: {log_data}")
    except IntegrityError as int_err:
        logger.error(f"Integrity error while logging data: {int_err}")
    except OperationalError as op_err:
        logger.error(f"Operational error: {op_err}. Retrying...")
        time.sleep(5)
        try:
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(insert_query, log_data)
                    conn.commit()
                    logger.debug(f"Data logged successfully after retry: {log_data}")
        except Exception as retry_err:
            logger.exception(f"Retry failed: {retry_err}")
    except Exception as e:
        logger.exception(f"Unexpected error while logging to database: {e}")

def monitor_network() -> None:
    """Continuously monitor the network and log metrics."""
    logger.info("Starting network monitoring...")

    last_speedtest_time = datetime.min
    downtime_start = None
    cumulative_downtime = timedelta(0)

    while True:
        timestamp = datetime.now()

        latency, jitter, packet_loss = ping_target(Config.PING_TARGET)
        dns_time = test_dns_resolution(Config.DNS_TEST_DOMAIN)

        run_speedtest = False
        if timestamp - last_speedtest_time >= timedelta(seconds=Config.SPEEDTEST_INTERVAL):
            logger.info("Scheduled speed test interval reached.")
            run_speedtest = True
        elif latency is None or (latency and latency > 100) or (packet_loss and packet_loss > 5.0):
            logger.warning("High latency or packet loss detected. Triggering speed test.")
            run_speedtest = True

        if run_speedtest:
            download_speed, upload_speed = test_speed()
            last_speedtest_time = timestamp
        else:
            download_speed, upload_speed = None, None

        traceroute = perform_traceroute(Config.PING_TARGET)

        is_downtime = latency is None
        if is_downtime:
            if downtime_start is None:
                downtime_start = timestamp
                logger.warning(f"Downtime started at {timestamp}.")
        else:
            if downtime_start:
                downtime_duration = timestamp - downtime_start
                cumulative_downtime += downtime_duration
                logger.info(f"Downtime ended. Duration: {downtime_duration}. Total downtime: {cumulative_downtime}.")
                downtime_start = None

        log_data = (
            timestamp, latency, jitter, packet_loss,
            download_speed, upload_speed, dns_time,
            is_downtime, traceroute
        )

        log_to_database(log_data)

        logger.info(
            f"[{timestamp}] Latency: {latency} ms, Jitter: {jitter} ms, "
            f"Packet Loss: {packet_loss}%, Download: {download_speed or 'N/A'} Mbps, "
            f"Upload: {upload_speed or 'N/A'} Mbps, DNS Time: {dns_time} ms, "
            f"Downtime: {is_downtime}, Traceroute: {traceroute[:100]}..."
        )

        time.sleep(Config.PING_INTERVAL)

def main() -> None:
    try:
        logger.info("Initializing the SpectraIIM network monitoring service...")
        setup_database()
        monitor_network()
    except KeyboardInterrupt:
        logger.warning("SpectraIIM monitoring service interrupted by user. Exiting...")
    except Exception as e:
        logger.exception(f"Critical failure in the SpectraIIM monitoring service: {e}")
    finally:
        logger.info("SpectraIIM monitoring service has stopped.")

if __name__ == "__main__":
    main()