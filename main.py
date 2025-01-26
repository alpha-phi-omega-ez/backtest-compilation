import logging

from sys import stdout
from time import time
from mongo import MongoClient
from gdrive import GoogleDriveClient
from gsheet import GoogleSheetClient
from process_data import interpret_backtests

from settings import get_settings
import asyncio


async def main() -> None:
    total_start = time()
    settings = get_settings()
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
    mongo_client = MongoClient(settings, logger)
    sheet_client = GoogleSheetClient(settings, logger)

    start_time = time()
    structure = await gdrive_client.get_recursive_structure(
        settings["FOLDER_ID"], settings["FOLDER_ID"]
    )
    end_time = time()
    logger.info(
        f"Time taken to get recursive structure: {end_time - start_time} seconds"
    )

    start_time = time()
    # This function is based off the fact that structure is constructed with an 'id' based off of the Google Drive id
    # If the backtest drive is ever moved off of Google Drive into a physical filesystem or elsewhere, I recommend to change get_recursive_structure so that the id stored is the complete path of the file
    all_backtests, all_dpts, all_classnames = await interpret_backtests(
        logger, structure, sheet_client, gdrive_client
    )
    end_time = time()
    logger.info(f"Time taken to interpret backtests: {end_time - start_time} seconds")

    start_time = time()
    await mongo_client.add_to_mongo(all_backtests, all_dpts, all_classnames)
    end_time = time()
    logger.info(f"Time taken to add to mongo: {end_time - start_time} seconds")

    start_time = time()
    await sheet_client.update_counts(all_classnames)
    end_time = time()
    logger.info(
        f"Time taken to update counts on Google Sheet: {end_time - start_time} seconds"
    )

    total_end = time()
    logger.info(f"Total time taken: {total_end - total_start} seconds")

    mongo_client.close()


if __name__ == "__main__":
    asyncio.run(main())
