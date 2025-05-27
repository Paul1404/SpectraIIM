import time
import subprocess
import platform
import shutil
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from config import Config
from logging_setup import setup_logger

logger = setup_logger()

# InfluxDB configuration
INFLUXDB_URL: str = Config.INFLUXDB_URL
INFLUXDB_TOKEN: str = Config.INFLUXDB_TOKEN
INFLUXDB_ORG: str = Config.INFLUXDB_ORG
INFLUXDB_BUCKET: str = Config.INFLUXDB_BUCKET

client = InfluxDBClient(
    url=INFLUXDB_URL,
    token=INFLUXDB_TOKEN,
    org=INFLUXDB_ORG
)
write_api = client.write_api(write_options=SYNCHRONOUS)

def ping_target(target: str) -> Tuple[Optional[float], Optional[float], float]:
    logger.info(f"Pinging target: {target}")
    try:
        result = subprocess.run(
            ["ping", "-c", "4", target],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            rtt_line = next((line for line in lines if "rtt min/avg/max" in line), None)
            if rtt_line:
                stats = rtt_line.split("=")[1].strip().replace(" ms", "")
                min_rtt, avg_rtt, max_rtt, _ = map(float, stats.split("/"))
                jitter = max_rtt - min_rtt
                logger.debug(f"Ping stats: Latency={avg_rtt} ms, Jitter={jitter} ms")
                return avg_rtt, jitter, 0.0
            logger.warning("Ping output did not contain RTT stats.")
            return None, None, 100.0
        logger.warning(f"Ping command failed with return code {result.returncode}.")
        return None, None, 100.0
    except subprocess.TimeoutExpired:
        logger.error(f"Ping command timed out for target: {target}")
        return None, None, 100.0
    except Exception as e:
        logger.exception(f"Error during ping to {target}: {e}")
        return None, None, 100.0

def test_dns_resolution(domain: str) -> Optional[float]:
    logger.info(f"Testing DNS resolution for domain: {domain}")
    try:
        start_time = time.time()
        result = subprocess.run(
            ["nslookup", domain],
            capture_output=True,
            text=True,
            timeout=5
        )
        end_time = time.time()
        if result.returncode == 0:
            resolution_time = (end_time - start_time) * 1000
            logger.debug(f"DNS resolution time for {domain}: {resolution_time:.2f} ms")
            return resolution_time
        logger.warning(f"DNS resolution command failed with return code {result.returncode}.")
        return None
    except subprocess.TimeoutExpired:
        logger.error(f"DNS resolution command timed out for domain: {domain}")
        return None
    except Exception as e:
        logger.exception(f"Error during DNS resolution for {domain}: {e}")
        return None

def test_speed() -> Tuple[Optional[float], Optional[float]]:
    logger.info("Starting speed test.")
    try:
        from speedtest import Speedtest
        st = Speedtest()
        st.get_best_server()
        download_speed = st.download() / 1_000_000
        upload_speed = st.upload() / 1_000_000
        logger.debug(f"Speed test results: Download={download_speed:.2f} Mbps, Upload={upload_speed:.2f} Mbps")
        return download_speed, upload_speed
    except Exception as e:
        logger.error(f"Error during speed test: {e}")
        return None, None

def perform_traceroute(target: str) -> Dict[str, Any]:
    """
    Perform a traceroute and return a summary dict:
    {
        "hop_count": int,
        "last_hop_ip": str,
        "max_hop_latency": float,
        "hops_json": str,  # JSON string of hops
        "full_text": str
    }
    """
    if platform.system() == "Windows":
        traceroute_cmd = "tracert"
        traceroute_args = [traceroute_cmd, target]
    else:
        traceroute_cmd = "traceroute"
        traceroute_args = [traceroute_cmd, "-n", target]

    if shutil.which(traceroute_cmd) is None:
        return {
            "hop_count": None,
            "last_hop_ip": None,
            "max_hop_latency": None,
            "hops_json": "[]",
            "full_text": f"{traceroute_cmd} not available"
        }

    try:
            result = subprocess.run(
                traceroute_args,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )
            output = result.stdout.strip()
            hops = []
            max_latency = None

            if result.returncode == 0:
                lines = output.splitlines()
                for line in lines[1:]:
                    # Match: hop_num, then pairs of (ip, latency)
                    m = re.match(r"\s*(\d+)\s+(.*)", line)
                    if not m:
                        continue
                    hop_num = int(m.group(1))
                    rest = m.group(2)
                    # Find all (ip, latency) pairs
                    pairs = re.findall(r"([\d\.]+)\s+([\d\.]+)\s*ms", rest)
                    if pairs:
                        for ip, latency in pairs:
                            lat = float(latency)
                            hops.append({
                                "hop": hop_num,
                                "ip": ip,
                                "latency": lat
                            })
                            if max_latency is None or lat > max_latency:
                                max_latency = lat
                    else:
                        # If no pairs, maybe all stars/timeouts, skip
                        continue

            last_hop_ip = hops[-1]["ip"] if hops else None

            return {
                "hop_count": len(set([h['hop'] for h in hops])),  # unique hop numbers
                "last_hop_ip": last_hop_ip,
                "max_hop_latency": max_latency,
                "hops_json": json.dumps(hops),
                "full_text": output
            }
    except subprocess.TimeoutExpired:
        return {
            "hop_count": None,
            "last_hop_ip": None,
            "max_hop_latency": None,
            "hops_json": "[]",
            "full_text": "Traceroute timeout"
        }
    except Exception as e:
        return {
            "hop_count": None,
            "last_hop_ip": None,
            "max_hop_latency": None,
            "hops_json": "[]",
            "full_text": f"Traceroute error: {e}"
        }

def log_to_influxdb(
    timestamp: datetime,
    latency: Optional[float],
    jitter: Optional[float],
    packet_loss: Optional[float],
    download_speed: Optional[float],
    upload_speed: Optional[float],
    dns_time: Optional[float],
    is_downtime: bool,
    traceroute_summary: Dict[str, Any]
) -> None:
    """Log results into InfluxDB."""
    try:
        point = (
            Point("network_log")
            .tag("target", Config.PING_TARGET)
            .field("latency_ms", latency if latency is not None else float("nan"))
            .field("jitter_ms", jitter if jitter is not None else float("nan"))
            .field("packet_loss", packet_loss if packet_loss is not None else float("nan"))
            .field("download_speed", download_speed if download_speed is not None else float("nan"))
            .field("upload_speed", upload_speed if upload_speed is not None else float("nan"))
            .field("dns_resolution_time_ms", dns_time if dns_time is not None else float("nan"))
            .field("downtime", int(is_downtime))
            .field("traceroute", traceroute_summary["full_text"])
            .field("traceroute_hop_count", traceroute_summary["hop_count"] if traceroute_summary["hop_count"] is not None else 0)
            .field("traceroute_last_hop_ip", traceroute_summary["last_hop_ip"] if traceroute_summary["last_hop_ip"] is not None else "")
            .field("traceroute_max_hop_latency", traceroute_summary["max_hop_latency"] if traceroute_summary["max_hop_latency"] is not None else float("nan"))
            .field("traceroute_hops_json", traceroute_summary["hops_json"])
            .time(timestamp, WritePrecision.NS)
        )
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        logger.debug("Data logged to InfluxDB.")
    except Exception as e:
        logger.exception(f"Error writing to InfluxDB: {e}")

def monitor_network() -> None:
    logger.info("Starting network monitoring...")

    last_speedtest_time: datetime = datetime.min
    downtime_start: Optional[datetime] = None
    cumulative_downtime: timedelta = timedelta(0)

    while True:
        timestamp: datetime = datetime.utcnow()

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

        traceroute_summary = perform_traceroute(Config.PING_TARGET)

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

        log_to_influxdb(
            timestamp, latency, jitter, packet_loss,
            download_speed, upload_speed, dns_time,
            is_downtime, traceroute_summary
        )

        logger.info(
            f"[{timestamp}] Latency: {latency} ms, Jitter: {jitter} ms, "
            f"Packet Loss: {packet_loss}%, Download: {download_speed or 'N/A'} Mbps, "
            f"Upload: {upload_speed or 'N/A'} Mbps, DNS Time: {dns_time} ms, "
            f"Downtime: {is_downtime}, "
            f"Traceroute hops: {traceroute_summary['hop_count']}, "
            f"Last hop IP: {traceroute_summary['last_hop_ip']}, "
            f"Max hop latency: {traceroute_summary['max_hop_latency']}, "
            f"Traceroute: {traceroute_summary['full_text'][:100]}..."
        )

        time.sleep(Config.PING_INTERVAL)

def main() -> None:
    try:
        logger.info("Initializing the SpectraIIM network monitoring service...")
        monitor_network()
    except KeyboardInterrupt:
        logger.warning("SpectraIIM monitoring service interrupted by user. Exiting...")
    except Exception as e:
        logger.exception(f"Critical failure in the SpectraIIM monitoring service: {e}")
    finally:
        logger.info("SpectraIIM monitoring service has stopped.")

if __name__ == "__main__":
    main()