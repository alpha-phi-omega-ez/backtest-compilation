from gspread import auth
from gspread.exceptions import WorksheetNotFound, APIError
from gspread.worksheet import Worksheet
from google.oauth2 import service_account

from os import path
from logging import Logger
import asyncio
import re

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleSheetClient:
    def __init__(self, settings: dict, logger: Logger) -> None:
        """
        Authenticate and open the Google Sheet by its name.

        :param settings: Dictionary with the settings.
        :param logger: Logger object.
        """

        credentials = service_account.Credentials.from_service_account_file(
            path.join(path.dirname(__file__), "config", "service-credentials.json"),
            scopes=scopes,
        )
        delegated_creds = credentials.with_subject(settings["DELEGATE_EMAIL"])

        self.gc = auth.authorize(delegated_creds)
        self.sheet = self.gc.open_by_url(settings["SHEET_URL"])

        self.logger = logger

    async def get_or_create_tab(
        self,
        tab_name: str,
        rows: int = 200,
        cols: int = 1,
    ) -> Worksheet:
        """
        Get the tab by name, or create it if it doesn't exist.

        :param tab_name: Name of the tab to find or create.
        :param rows: Number of rows for the new tab (default: 200).
        :param cols: Number of columns for the new tab (default: 4).
        :return: gspread Worksheet object for the tab.
        """

        try:
            self.logger.debug(f"Tab {tab_name} already exists")
            return self.sheet.worksheet(tab_name)  # Try to get the existing tab
        except WorksheetNotFound:
            # If the tab doesn't exist, create it
            self.logger.debug(f"Creating tab {tab_name}")
            return self.sheet.add_worksheet(title=tab_name, rows=rows, cols=cols)

    async def write_errors(
        self,
        errors: list[str],
        type: str,
        tab: Worksheet,
        index: int = 0,
    ) -> int:
        """
        Writes the errors to the Google Sheet.

        :param errors: List of error messages to write.
        :param type: Type of the errors to write.
        :param index: Starting index to write the errors (default: 0).
        :return: Ending index of the written errors.
        """

        self.logger.debug(f"Errors: {errors}")

        try:
            tab.update_cell(1 + index, 1, type)
            tab.format(
                f"A{1 + index}",
                {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 1, "green": 0, "blue": 0},
                },
            )
        except APIError as e:
            self.logger.info(
                f"API Error: {e}\nWaiting 60 seconds to way for the rate limit to reset"
            )
            # Wait for 60 seconds to stay under rate limits
            await asyncio.sleep(60)
            tab.update_cell(1 + index, 1, type)
            tab.format(
                f"A{1 + index}",
                {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 1, "green": 0, "blue": 0},
                },
            )

        self.logger.debug("Writing errors")
        tab.update(
            [[error] for error in errors],
            f"A{2 + index}:A{len(errors) + 2 + index}",
        )

        self.logger.debug(f"Errors written ending at row {len(errors) + 2 + index}")
        return len(errors) + 2 + index

    async def write_all_errors(
        self,
        errors: list[str],
        invalid_filenames: list[str],
        crosslisted_output: list[str],
    ) -> None:
        """
        Write all the errors to the Google Sheet.

        :param errors: List of errors to write.
        :param invalid_filenames: List of invalid filenames to write.
        :param crosslisted_output: List of crosslisted classes to write.
        """

        tab = await self.get_or_create_tab("Errors in Drive")

        # check if errors have changed

        tab.clear()
        tab.format(
            "A:A",
            {
                "textFormat": {"bold": False},
                "backgroundColor": {"red": 1, "green": 1, "blue": 1},
            },
        )
        self.logger.debug("Tab cleared")

        index = await self.write_errors(errors, "Errors", tab)
        index = await self.write_errors(
            invalid_filenames, "Invalid Filenames", tab, index
        )
        index = await self.write_errors(
            crosslisted_output, "Crosslisted Classes", tab, index
        )

        # save errors

    async def update_count(
        self, classname: str, tab: Worksheet, count: int, classes_not_found: list[str]
    ) -> None:
        """
        Update the count of a class in the Google Sheet.

        :param classname: Name of the class to update.
        """

        self.logger.debug(f"Updating count for {' '.join(classname.split(' ')[1:])}")
        find_course = re.compile(rf".*{' '.join(classname.split(' ')[1:])}.*")
        cell = tab.find(find_course)
        if cell:
            tab.update_cell(cell.row, cell.col + 5, count)
            tab.format(
                f"F{cell.row}", {"backgroundColor": {"red": 0, "green": 1, "blue": 0}}
            )
            self.logger.debug(f"Count {count} updated for {classname}")
        else:
            self.logger.error(f"Class {classname} not found in tab")
            classes_not_found.append(classname)

    async def update_counts(self, all_classnames: dict) -> None:
        """
        Update the counts of the classes in the Google Sheet.

        :param all_classnames: Dictionary with the classes and their counts.
        """

        tab = await self.get_or_create_tab("Physical Copies of Backtests")

        # find the classes that have changed

        col_values = tab.col_values(6)
        self.logger.debug(f"Column values: {col_values}")

        # Initialize variables
        indices = []
        start = None

        # Loop through the list
        for i, item in enumerate(col_values[1:], start=2):  # Ignore the first item
            if item and start is None:
                start = i  # Mark the start of a non-empty block
            elif not item and start is not None:
                indices.append((start, i - 1))  # Mark the end of a non-empty block
                start = None

        # Handle the last block if it ends with a non-empty string
        if start is not None:
            indices.append((start, len(col_values)))

        for index in indices:
            tab.format(
                f"F{index[0]}:F{index[1]}",
                {"backgroundColor": {"red": 1, "green": 1, "blue": 0}},
            )

        classes_not_found = []
        # Can't use asyncio.gather ecause of rate limits by google (300 per minute)
        for key, values in all_classnames.items():
            try:
                await self.update_count(key, tab, values[2], classes_not_found)
            except APIError as e:
                # Hit rate limit delay for 60 seconds in attempt to stay below rate limits
                self.logger.info(
                    f"API Error: {e}\nWaiting 60 seconds to way for the rate limit to reset"
                )
                await asyncio.sleep(60)
                await self.update_count(key, tab, values[2], classes_not_found)

        self.logger.debug(f"Counts updated for {len(all_classnames)} classes")

        # save classes that are up to date

        # check if classes not found errors have changed

        tab = await self.get_or_create_tab("Classes Not Found")
        tab.clear()
        tab.format(
            "A:A",
            {
                "textFormat": {"bold": False},
                "backgroundColor": {"red": 1, "green": 1, "blue": 1},
            },
        )
        await self.write_errors(classes_not_found, "Classes Not Found", tab)

        # save classes not found errors
