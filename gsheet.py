import asyncio
import json
import re
from datetime import datetime
from logging import Logger
from os import path

from google.oauth2 import service_account
from gspread import auth
from gspread.exceptions import APIError, WorksheetNotFound
from gspread.worksheet import Worksheet

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
]


async def async_items(d: dict):
    for k, v in d.items():
        yield k, v


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
        try:
            self.sheet = self.gc.open_by_url(settings["SHEET_URL"])
        except APIError as e:
            logger.error(f"API Error: {e}")
            logger.error("Please check the Google Sheet URL and try again.")
            exit(1)

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

    async def check_error_cache(
        self,
        errors: list[str],
        invalid_filenames: list[str],
        crosslisted_output: list[str],
    ) -> bool:
        """
        Check if the errors are the same as the ones in the Google Sheet.

        :param errors: List of errors to check.
        :param invalid_filenames: List of invalid filenames to check.
        :param crosslisted_output: List of crosslisted classes to check.
        :return: True if the errors are the same, False otherwise.
        """

        if not path.exists(
            path.join(path.dirname(__file__), "cache", "sheet_errors.json")
        ):
            await self.update_error_cache(errors, invalid_filenames, crosslisted_output)
            return False

        try:
            with open(
                path.join(path.dirname(__file__), "cache", "sheet_errors.json"), "r"
            ) as f:
                cache = json.load(f)
        except PermissionError:
            self.logger.exception("Permission error reading cache (sheet_errors.json)")
            return False

        check = (
            (cache["errors"] == errors)
            and (cache["invalid_filenames"] == invalid_filenames)
            and (cache["crosslisted_output"] == crosslisted_output)
        )

        if not check:
            self.logger.info("Errors are outdated. Updating errors.")
            await self.update_error_cache(errors, invalid_filenames, crosslisted_output)
        else:
            self.logger.info("Errors match the cache.")

        return check

    async def update_error_cache(
        self,
        errors: list[str],
        invalid_filenames: list[str],
        crosslisted_output: list[str],
    ) -> None:
        """
        Update the cache with the errors in the Google Sheet.

        :param errors: List of errors to update.
        :param invalid_filenames: List of invalid filenames to update.
        :param crosslisted_output: List of crosslisted classes to update.
        """

        data = {
            "errors": errors,
            "invalid_filenames": invalid_filenames,
            "crosslisted_output": crosslisted_output,
        }

        self.logger.info("Updating cache file with new structure.")
        try:
            with open(
                path.join(path.dirname(__file__), "cache", "sheet_errors.json"), "w"
            ) as f:
                json.dump(data, f)
                self.logger.debug(f"Cache file updated with {data}")
            self.logger.info("Cache file updated successfully.")
        except PermissionError:
            self.logger.exception("Permission error writing cache (sheet_errors.json)")

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

        for _ in range(2):
            try:
                tab.update_cell(1 + index, 1, type)
                tab.format(
                    f"A{1 + index}",
                    {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 1, "green": 0, "blue": 0},
                    },
                )
                break
            except APIError as e:
                self.logger.info(
                    f"API Error: {e}\nWaiting 60 seconds to way "
                    "for the rate limit to reset"
                )
                # Wait for 60 seconds to stay under rate limits
                await asyncio.sleep(60)

        self.logger.debug("Writing errors")
        for _ in range(2):
            try:
                tab.update(
                    [[error] for error in errors],
                    f"A{2 + index}:A{len(errors) + 2 + index}",
                )
                break
            except APIError as e:
                self.logger.info(
                    f"API Error: {e}\nWaiting 60 seconds to way "
                    "for the rate limit to reset"
                )
                # Wait for 60 seconds to stay under rate limits
                await asyncio.sleep(60)

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

        if await self.check_error_cache(errors, invalid_filenames, crosslisted_output):
            self.logger.info("Errors are the same as the ones in the Google Sheet.")
            return

        tab = await self.get_or_create_tab("Errors in Drive")
        for _ in range(2):
            try:
                tab.clear()
                tab.format(
                    "A:A",
                    {
                        "textFormat": {"bold": False},
                        "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                    },
                )
                break
            except APIError as e:
                self.logger.info(
                    f"API Error: {e}\nWaiting 60 seconds to wait "
                    "for the rate limit to reset"
                )
                await asyncio.sleep(60)

        index = await self.write_errors(errors, "Errors", tab)
        index = await self.write_errors(
            invalid_filenames, "Invalid Filenames", tab, index
        )
        index = await self.write_errors(
            crosslisted_output, "Crosslisted Classes", tab, index
        )

    async def check_class_cache(self, all_classnames: dict) -> bool:
        """
        Check if the class counts are the same as the ones in the Google Sheet.

        :param all_classnames: Dictionary with the classes and their counts.
        :return: True if the class counts are the same, False otherwise.
        """

        if not path.exists(
            path.join(path.dirname(__file__), "cache", "sheet_classes.json")
        ):
            await self.update_class_cache(all_classnames)
            return False

        try:
            with open(
                path.join(path.dirname(__file__), "cache", "sheet_classes.json"), "r"
            ) as f:
                cache = json.load(f)
        except PermissionError:
            self.logger.exception("Permission error reading cache (sheet_classes.json)")
            return False

        check = cache == all_classnames

        if not check:
            self.logger.info("Class counts are outdated. Updating class counts.")
            await self.update_class_cache(all_classnames)
        else:
            self.logger.info("Class counts match the cache.")

        return check

    async def update_class_cache(self, all_classnames: dict) -> None:
        """
        Update the cache with the class counts in the Google Sheet.

        :param all_classnames: Dictionary with the classes and their counts.
        """

        self.logger.info("Updating cache file with new class counts.")
        try:
            with open(
                path.join(path.dirname(__file__), "cache", "sheet_classes.json"), "w"
            ) as f:
                json.dump(all_classnames, f)
                self.logger.debug(f"Cache file updated with {all_classnames}")
            self.logger.info("Cache file updated successfully.")
        except PermissionError:
            self.logger.exception("Permission error writing cache (sheet_classes.json)")

    async def get_location(
        self,
        classname: str,
        tab: Worksheet,
        count: int,
        classes_not_found: list[str],
        items: list[tuple[int, int]],
    ) -> None:
        """
        Find the row of a class in the Google Sheet.

        :param classname: Name of the class to update.
        :param tab: Worksheet object for the tab.
        :param count: Count of the class to update.
        :param classes_not_found: List of classes not found in the tab.
        :param items: List of tuples with the row and count of the class.
        """

        self.logger.debug(f"Finding class {' '.join(classname.split(' ')[1:])}")
        find_course = re.compile(
            rf".*{' '.join(classname.split(' ')[1:])}.*", re.IGNORECASE
        )
        cell = tab.find(find_course)
        if cell:
            self.logger.debug(f"Class {classname} found in tab")
            items.append((cell.row, count))
        else:
            self.logger.info(f"Class {classname} not found in tab")
            classes_not_found.append(classname)

    async def update_counts(self, all_classnames: dict) -> None:
        """
        Update the counts of the classes in the Google Sheet.

        :param all_classnames: Dictionary with the classes and their counts.
        """

        if await self.check_class_cache(all_classnames):
            self.logger.info(
                "Class counts are the same as the ones in the Google Sheet."
            )
            return

        tab = await self.get_or_create_tab("Physical Copies of Backtests")

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
                self.logger.debug(f"Block from {start} to {i - 1}")
                indices.append((start, i - 1))  # Mark the end of a non-empty block
                start = None

        # Handle the last block if it ends with a non-empty string
        if start is not None:
            indices.append((start, len(col_values)))

        for index in indices:
            for _ in range(2):
                try:
                    tab.format(
                        f"F{index[0]}:F{index[1]}",
                        {"backgroundColor": {"red": 1, "green": 1, "blue": 0}},
                    )
                    break
                except APIError as e:
                    self.logger.info(
                        f"API Error: {e}\nWaiting 60 seconds to wait "
                        "for the rate limit to reset"
                    )
                    await asyncio.sleep(60)

        classes_not_found = []
        counts = []
        # Can't use asyncio.gather because of rate limits by google (300 per minute)
        async for key, values in async_items(all_classnames):
            for _ in range(2):
                try:
                    await self.get_location(
                        key, tab, values[2], classes_not_found, counts
                    )
                    break
                except APIError as e:
                    # Hit rate limit delay for 60 seconds in attempt to
                    # stay below rate limits
                    self.logger.info(
                        f"API Error: {e}\nWaiting 60 seconds to way for the "
                        "rate limit to reset"
                    )
                    await asyncio.sleep(60)

        counts.sort(key=lambda x: x[0])

        # Batch update the counts in the tab
        batch_data = []
        current_batch = []
        current_row = None

        for row, value in counts:
            if current_row is None or row == current_row + 1:
                current_batch.append(value)
            else:
                if current_batch:
                    self.logger.info(
                        "Adding batch data for range "
                        f"{current_row - len(current_batch) + 1}, {current_row}"
                    )
                    batch_data.append(
                        (current_row - len(current_batch) + 1, current_batch)
                    )
                current_batch = [value]
            current_row = row

        if current_batch and current_row:
            batch_data.append((current_row - len(current_batch) + 1, current_batch))

        for start_row, values in batch_data:
            cell_range = f"F{start_row}:F{start_row + len(values) - 1}"
            for _ in range(2):
                try:
                    self.logger.debug(f"Updating counts for {values}")
                    tab.update([[value] for value in values], cell_range)
                    tab.format(
                        cell_range,
                        {"backgroundColor": {"red": 0, "green": 1, "blue": 0}},
                    )
                    break
                except APIError as e:
                    self.logger.info(
                        f"API Error: {e}\nWaiting 60 seconds to wait "
                        "for the rate limit to reset"
                    )
                    await asyncio.sleep(60)

        self.logger.debug(f"Counts updated for {len(all_classnames)} classes")

        tab = await self.get_or_create_tab("Classes Not Found")
        for _ in range(2):
            try:
                tab.clear()
                tab.format(
                    "A:A",
                    {
                        "textFormat": {"bold": False},
                        "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                    },
                )
                break
            except APIError as e:
                self.logger.info(
                    f"API Error: {e}\nWaiting 60 seconds to wait "
                    "for the rate limit to reset"
                )
                await asyncio.sleep(60)

        await self.write_errors(classes_not_found, "Classes Not Found", tab)

        tab = await self.get_or_create_tab("Physical Copies of Backtests")
        for _ in range(2):
            try:
                tab.update_cell(
                    24, 16, datetime.now().strftime("%-m/%-d/%y %I:%M:%S %p")
                )
                break
            except APIError as e:
                self.logger.info(
                    f"API Error: {e}\nWaiting 60 seconds to way "
                    "for the rate limit to reset"
                )
                # Wait for 60 seconds to stay under rate limits
                await asyncio.sleep(60)
        self.logger.debug("Updated runtime on gsheet")
