from loguru import logger
import os

def setup_logger(log_dir="logs", log_file="spectraiim.log"):
    """
    Configure the Loguru logger.
    Args:
        log_dir (str): Directory to store log files.
        log_file (str): Name of the log file.
    Returns:
        logger: Configured Loguru logger instance.
    """
    # Ensure the log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Full path to the log file
    log_path = os.path.join(log_dir, log_file)

    # Remove default Loguru logger to customize handlers
    logger.remove()

    # Add a file handler with rotation, retention, and compression
    logger.add(
        log_path,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        rotation="5 MB",  # Rotate when file size reaches 5 MB
        retention="7 days",  # Retain logs for 7 days
        compression="zip",  # Compress old logs
        level="DEBUG"  # Log levels from DEBUG and above
    )

    # Add a console handler
    logger.add(
        lambda msg: print(msg, end=""),
        format="<level>{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}</level>",
        level="INFO"  # Show INFO and above in console
    )

    return logger
