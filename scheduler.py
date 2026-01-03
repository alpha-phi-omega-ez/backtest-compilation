"""Scheduler script that runs main.py during specific hours."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from time import sleep
from zoneinfo import ZoneInfo

from main import main as run_backtest_main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Eastern timezone (automatically handles EST/EDT transitions)
EASTERN_TZ = ZoneInfo("America/New_York")

SCHEDULED_HOURS = [9, 11, 13, 15, 17, 19]

STARTING_HOUR = 9

# Offsets used to not run exactly on the hour
MINUTE_OFFSET = 2
SECOND_OFFSET = 7


def should_run() -> bool:
    """Check if main.py should run based on current hour in Eastern time."""
    current_hour = datetime.now(EASTERN_TZ).hour
    # Run between 9:00 (9 AM) and 19:00 (7 PM) inclusive, 20 to allow offset at 7pm
    return 9 <= current_hour <= 20


def get_next_scheduled_hour(current_hour: int) -> int:
    """Get the next scheduled hour (9, 11, 13, 15, 17, 19)."""
    for hour in SCHEDULED_HOURS:
        if current_hour < hour:
            return hour
    # If past 19:00, return None (will be handled by calculating delay to next 9am)
    return None


def calculate_sleep_seconds() -> int:
    """Calculate seconds to sleep until next scheduled run in Eastern time."""
    now = datetime.now(EASTERN_TZ)
    current_hour = now.hour

    if not should_run():
        # Outside allowed hours: calculate delay until next 9am
        if current_hour < 9:
            # Before 9am today: wait until start time
            next_run = now.replace(
                hour=STARTING_HOUR,
                minute=MINUTE_OFFSET,
                second=SECOND_OFFSET,
                microsecond=SECOND_OFFSET,
            )
        else:
            # After 7pm (hour > 19): wait until next morning start time
            next_run = (now + timedelta(days=1)).replace(
                hour=STARTING_HOUR,
                minute=MINUTE_OFFSET,
                second=SECOND_OFFSET,
                microsecond=SECOND_OFFSET,
            )

        delay = (next_run - now).total_seconds()
        next_run_str = next_run.strftime("%Y-%m-%d %H:%M:%S %Z")
        logger.info(f"Outside allowed hours. Next run at {next_run_str} (Eastern Time)")
        return int(delay)
    else:
        # Inside allowed hours: calculate delay until next 2-hour interval
        next_hour = get_next_scheduled_hour(current_hour)
        if next_hour is None:
            # Shouldn't happen if should_run() is True, but handle edge case
            next_run = (now + timedelta(days=1)).replace(
                hour=STARTING_HOUR,
                minute=MINUTE_OFFSET,
                second=SECOND_OFFSET,
                microsecond=SECOND_OFFSET,
            )
        else:
            # Calculate next run time
            if current_hour < next_hour:
                # Next run is today
                next_run = now.replace(
                    hour=next_hour,
                    minute=MINUTE_OFFSET,
                    second=SECOND_OFFSET,
                    microsecond=SECOND_OFFSET,
                )
            else:
                # Shouldn't happen, but handle edge case
                next_run = (now + timedelta(days=1)).replace(
                    hour=STARTING_HOUR,
                    minute=MINUTE_OFFSET,
                    second=SECOND_OFFSET,
                    microsecond=SECOND_OFFSET,
                )

        delay = (next_run - now).total_seconds()
        next_run_str = next_run.strftime("%Y-%m-%d %H:%M:%S %Z")
        logger.info(f"Next scheduled run at {next_run_str} (Eastern Time)")
        return int(delay)


def run_main() -> None:
    """Run main.py by directly calling the async main function."""
    logger.info("Running main.py")
    try:
        asyncio.run(run_backtest_main())
        logger.info("main.py completed successfully")
    except KeyboardInterrupt:
        logger.info("main.py interrupted by user")
        raise
    except Exception as e:
        logger.error(f"Error running main.py: {e}", exc_info=True)


def main() -> None:
    """Main scheduler loop."""
    logger.info("Scheduler started (using Eastern Time)")

    while True:
        now = datetime.now(EASTERN_TZ)
        current_hour = now.hour
        current_time_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        logger.info(f"Current time: {current_time_str} (hour: {current_hour})")

        if should_run():
            run_main()

        sleep_seconds = calculate_sleep_seconds()
        next_run_time = datetime.now(EASTERN_TZ) + timedelta(seconds=sleep_seconds)
        next_run_str = next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        sleep_hours = sleep_seconds / 3600
        logger.info(
            f"Sleeping for {sleep_seconds} seconds ({sleep_hours:.2f} hours). "
            f"Next run at: {next_run_str}"
        )
        sleep(sleep_seconds)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted, shutting down")
        sys.exit(0)
