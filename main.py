import asyncio
import logging
from sys import stdout
from time import time

import sentry_sdk

from gdrive import GoogleDriveClient
from gsheet import GoogleSheetClient
from mongo import MongoClient
from process_data import interpret_backtests
from settings import get_settings


async def main() -> None:
    mongo_client = None
    structure_start_time, structure_end_time = None, None
    processing_start_time, processing_end_time = None, None
    mongo_start_time, mongo_end_time = None, None
    sheets_start_time, sheets_end_time = None, None
    try:
        total_start = time()
        settings = get_settings()

        sentry_sdk.init(
            dsn=settings["SENTRY_DSN"],
            traces_sample_rate=settings["SENTRY_TRACE_RATE"],
        )

        # Setup logger
        logging.basicConfig(
            level=settings["LOG_LEVEL"],
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(stdout),
            ],
        )
        logger = logging.getLogger(__name__)

        gdrive_client = GoogleDriveClient(settings, logger)

        structure_start_time = time()
        structure = await gdrive_client.get_structure(
            settings["FOLDER_ID"], settings["FOLDER_ID"]
        )
        structure_end_time = time()

        sheet_client = GoogleSheetClient(settings, logger)

        processing_start_time = time()
        all_backtests, all_dpts, all_classnames = await interpret_backtests(
            logger, structure, sheet_client, gdrive_client
        )
        processing_end_time = time()

        mongo_client = MongoClient(settings, logger)
        mongo_start_time = time()
        await mongo_client.add_to_mongo(all_backtests, all_dpts, all_classnames)
        mongo_end_time = time()
        await mongo_client.close()

        sheets_start_time = time()
        await sheet_client.update_counts(all_classnames)
        sheets_end_time = time()

    except (KeyboardInterrupt, SystemExit) as _:
        logger.info("Signal recieved ending program")
    finally:
        if mongo_client:
            await mongo_client.close()
        total_end = time()
        if structure_start_time and structure_end_time:
            logger.info(
                f"Time taken to get recursive structure: "
                f"{structure_end_time - structure_start_time} seconds"
            )
        if processing_start_time and processing_end_time:
            logger.info(
                f"Time taken to process backtests: "
                f"{processing_end_time - processing_start_time} seconds"
            )
        if mongo_start_time and mongo_end_time:
            logger.info(
                f"Time taken to add to MongoDB: "
                f"{mongo_end_time - mongo_start_time} seconds"
            )
        if sheets_start_time and sheets_end_time:
            logger.info(
                f"Time taken to update Google Sheets: "
                f"{sheets_end_time - sheets_start_time} seconds"
            )
        logger.info(f"Total time taken: {total_end - total_start} seconds")


if __name__ == "__main__":
    asyncio.run(main())
