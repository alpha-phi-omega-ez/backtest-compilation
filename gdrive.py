from os import path
import asyncio
from logging import Logger

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

    async def get_recursive_structure(self, fileid: str, sharedDrive: str) -> dict:
        """
        Get the recursive structure of the backtest drive in Google Drive.

        :param fileid: ID of the file to get the structure.
        :param sharedDrive: ID of the shared drive.
        """

        self.logger.debug(f"Getting recursive structure for {fileid}")
        structure = {}
        # Use Google's API to get a complete list of the children in a folder (Google's 'service.files()' function gives a COMPLETE LIST of ALL files in your drive)

        for attempt in range(3):
            try:
                results = (
                    self.service.files()
                    .list(
                        q=f"'{fileid}' in parents",
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
                    f"Renamed file with id <{file_id}> from <{old_name}> to <{new_name}>"
                )
                break
            except HttpError as error:
                if attempt == 2:
                    self.logger.warning(
                        f"Failed to rename file with id <{file_id}> from <{old_name}> to <{new_name}> after 3 attempts: {error}\n"
                    )
                else:
                    self.logger.debug(
                        f"Attempt {attempt + 1} to rename file with id <{file_id}>from <{old_name}> to <{new_name}> failed: {error}\n"
                    )
