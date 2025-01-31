import asyncio
import json
from logging import Logger
from os import path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

scopes = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleDriveClient:
    def __init__(self, settings: dict, logger: Logger) -> None:
        """
        Create the Google Drive service object.

        :param settings: Dictionary with the settings.
        :param logger: Logger object.
        """

        credentials = service_account.Credentials.from_service_account_file(
            path.join(path.dirname(__file__), "config", "service-credentials.json"),
            scopes=scopes,
        )

        delegated_creds = credentials.with_subject(settings["DELEGATE_EMAIL"])
        self.service = build("drive", "v3", credentials=delegated_creds)
        self.logger = logger

    async def cache_check(self, structure: dict) -> bool:
        """
        Check if the cache is up to date.

        :param structure: Structure of the backtest drive.
        """

        if not path.exists(
            path.join(path.dirname(__file__), "cache", "structure.json")
        ):
            self.logger.info("Cache file does not exist. Updating cache.")
            await self.update_cache(structure)
            return False

        self.logger.info("Cache file exists. Checking if it is up to date.")
        with open(
            path.join(path.dirname(__file__), "cache", "structure.json"), "r"
        ) as f:
            cache = json.load(f)

        check = cache == structure

        if not check:
            self.logger.info("Cache is outdated. Updating cache.")
            await self.update_cache(structure)
        else:
            self.logger.info("Cache is up to date.")

        return check

    async def update_cache(self, structure: dict) -> None:
        """
        Update the cache with the structure of the backtest drive in Google Drive.

        :param structure: Structure of the backtest drive.
        """

        self.logger.info("Updating cache file with new structure.")
        with open(
            path.join(path.dirname(__file__), "cache", "structure.json"), "w"
        ) as f:
            json.dump(structure, f)
            self.logger.debug(f"Cache file updated with {structure}")

        self.logger.info("Cache file updated successfully.")

    async def get_structure(self, fileid: str, sharedDrive: str) -> dict:
        """
        Get the structure of the backtest drive in Google Drive.

        :param fileid: ID of the file to get the structure.
        :param sharedDrive: ID of the shared drive.
        """

        self.logger.info("Getting structure of the backtest drive.")
        structure = await self.get_recursive_structure(fileid, sharedDrive)
        self.logger.info("Comleted getting structure of the backtest drive.")

        self.logger.info("Checking if cache is up to date.")
        if await self.cache_check(structure):
            self.logger.info("Cache is the same as the current structure exiting")
            raise SystemExit

        self.logger.info(
            "Cache is not up to date. Updating cache and continue "
            "the rest of the process."
        )

        return structure

    async def get_recursive_structure(self, fileid: str, sharedDrive: str) -> dict:
        """
        Get the recursive structure of the backtest drive in Google Drive.

        :param fileid: ID of the file to get the structure.
        :param sharedDrive: ID of the shared drive.
        """

        self.logger.debug(f"Getting recursive structure for {fileid}")
        structure = {}
        # Use Google's API to get a complete list of the children in a folder
        # (Google's 'service.files()' function gives a COMPLETE LIST
        # of ALL files in your drive)

        for attempt in range(3):
            try:
                results = (
                    self.service.files()
                    .list(
                        q=f"'{fileid}' in parents and trashed = false",
                        corpora="drive",
                        driveId=sharedDrive,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )
                break
            except Exception as e:
                if attempt == 2:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {e}. Exiting")
                    raise e
                self.logger.debug(f"Attempt {attempt + 1} failed: {e}")

        # Results is returned as a dict
        tasks = []
        for item in results["files"]:
            structure[item["id"]] = {
                "name": item["name"],
                "folder": "folder" in item["mimeType"],
            }
            if structure[item["id"]]["folder"]:
                tasks.append(self.get_recursive_structure(item["id"], sharedDrive))
            else:
                structure[item["id"]]["children"] = None

        if tasks:
            children_results = await asyncio.gather(*tasks)
            idx = 0
            for item in results["files"]:
                if structure[item["id"]]["folder"]:
                    structure[item["id"]]["children"] = children_results[idx]
                    idx += 1

        return structure

    async def rename_file(self, file_id: str, new_name: str, old_name: str) -> None:
        """
        Rename a file in Google Drive.

        :param file_id: ID of the file to rename.
        :param new_name: New name for the file.
        :param old_name: Old name of the file.
        """

        self.logger.debug(f"Renaming file {file_id} to {new_name}")
        for attempt in range(3):
            try:
                self.service.files().update(
                    fileId=file_id,
                    body={"name": new_name},
                    supportsAllDrives=True,
                ).execute()
                self.logger.info(
                    f"Renamed file with id <{file_id}> from "
                    f"<{old_name}> to <{new_name}>"
                )
                break
            except HttpError as error:
                if attempt == 2:
                    self.logger.warning(
                        f"Failed to rename file with id <{file_id}> from <{old_name}> "
                        f"to <{new_name}> after 3 attempts: {error}\n"
                    )
                else:
                    self.logger.debug(
                        f"Attempt {attempt + 1} to rename file with id <{file_id}> "
                        f"from <{old_name}> to <{new_name}> failed: {error}\n"
                    )
