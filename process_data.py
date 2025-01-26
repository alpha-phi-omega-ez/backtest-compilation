from gdrive import GoogleDriveClient
import re
from datetime import date
from logging import Logger
import asyncio
from gsheet import GoogleSheetClient

examtype_mapping = {
    "Q": "Quiz",
    "E": "Exam",
    "M": "Midterm",
}

exam_date_mapping = {
    "F": "Fall",
    "S": "Spring",
    "U": "Summer",
    "SU": "Summer",
}

# To check if classes have an invalid year
current_year = date.today().year % 100

find_department = re.compile("([^A-Z]|^)([A-Z]{4})$")
find_classname = re.compile(r"(^\*?)([A-Z]{4})-([0-9]{3}[0-9X]) (.+)$")


async def process_test(
    children,
    name: str,
    dptname: str,
    classnum: str,
    fid: str,
    results: dict,
    full_classname: str,
    all_classnames: dict,
    logger: Logger,
    errors: list[str],
    invalid_filenames: list[str],
    gdrive_client,
) -> None:
    """
    Process a single test in the Google Drive structure. (example: CSCI-1200 F1F22.pdf)

    :param children: Children folders of the test folder.
    :param name: Name of the test.
    :param dptname: Name of the department.
    :param classnum: Number of the class.
    :param fid: ID of the test file.
    :param results: Dictionary to store the results.
    :param full_classname: Full name of the class.
    :param all_classnames: Dictionary of all class names.
    :param logger: Logger object to log information.
    :param errors: List of errors to write to Google Sheets.
    :param invalid_filenames: List of invalid filenames to write to Google Sheets.
    :param gdrive_client: GoogleDriveClient object to interact with Google Drive.
    """
    logger.info(f"Processing file: {name} in {dptname}-{classnum}")

    if children is not None:
        errors.append(f"Folder in {dptname}-{classnum}: {name}")
        logger.error(f"Folder found instead of file in {dptname}-{classnum}: {name}")
        return

    class_start = (
        "("
        + "("
        + dptname
        + ")(-| )?"
        + classnum
        + r"( |_|-)?( |_|-)?( |_|-)?)?(M1?|E[1-9]|Q|Q[1-9][0-9]?) ?(F|S|U|S[U])([0-9]{2})(.*?)(\.pdf)?$"
    )

    match = re.match(class_start, name, re.IGNORECASE)
    if match is None:
        invalid_filenames.append(f"Invalid filename in {dptname}-{classnum}: {name}")
        logger.error(f"Invalid filename in {dptname}-{classnum}: {name}")
        return

    exam_num = match.group(7)
    if exam_num[0] == "M":
        exam_num = "M"

    semester = match.group(8)
    if semester.lower() == "su":
        semester = "U"

    year = match.group(9)
    if int(year) > current_year and dptname.upper() != "BEAR":
        invalid_filenames.append(f"Invalid year in {dptname}-{classnum}: {name}")
        logger.error(f"Invalid year in {dptname}-{classnum}: {name}")
        return

    correct_filename = f"{dptname}-{classnum} {exam_num}{semester}{year}.pdf"
    if correct_filename != name:
        await gdrive_client.rename_file(
            fid,
            correct_filename,
            name,
        )

    examtype = (examtype_mapping[exam_num[0].upper()] + " " + exam_num[1:]).strip()
    examsemester = exam_date_mapping[semester.upper()] + " 20" + year

    if full_classname in results:
        inserted = False
        for exam in results[full_classname]:
            if exam["type"] == examtype:
                exam["tests"].append(examsemester)
                inserted = True
                logger.info(
                    f"Appended {examsemester} to existing exam type {examtype} for {full_classname}"
                )
                break
        if not inserted:
            results[full_classname].append(
                {
                    "type": examtype,
                    "tests": [examsemester],
                }
            )
            logger.info(
                f"Added new exam type {examtype} with {examsemester} for {full_classname}"
            )
    else:
        results[full_classname] = [
            {
                "type": examtype,
                "tests": [examsemester],
            }
        ]
        logger.info(
            f"Created new entry for {full_classname} with exam type {examtype} and {examsemester}"
        )

    all_classnames[full_classname][2] += 1
    logger.info(
        f"Incremented test count for {full_classname} to {all_classnames[full_classname][2]}"
    )


async def process_course(
    files,
    classname: str,
    dptname: str,
    all_classnums: set[tuple[str, str]],
    all_classnames: dict,
    results: dict,
    logger: Logger,
    errors: list[str],
    crosslisted_output: list[str],
    invalid_filenames: list[str],
    gdrive_client: GoogleDriveClient,
) -> None:
    """
    Process a single class in the Google Drive structure. (example: CSCI-1200)

    :param files: Files in the class folder.
    :param classname: Name of the class.
    :param dptname: Name of the department.
    :param all_classnums: Set of all class numbers.
    :param all_classnames: Dictionary of all class names.
    :param results: Dictionary to store the results.
    :param logger: Logger object to log information.
    :param errors: List of errors to write to Google Sheets.
    :param crosslisted_output: List of crosslisted classes to write to Google Sheets.
    :param invalid_filenames: List of invalid filenames to write to Google Sheets.
    :param gdrive_client: GoogleDriveClient object to interact with Google Drive.
    """

    logger.info(f"Processing class: {classname} in department {dptname}")

    if files is None:
        errors.append(f"File in {dptname} folder is not a CLASS: {classname}")
        logger.error(f"File in {dptname} folder is not a CLASS: {classname}")
        return

    match = find_classname.search(classname)
    if match is None:
        errors.append(f"Invalid CLASS in {dptname}: {classname}")
        logger.error(f"Invalid CLASS in {dptname}: {classname}")
        return
    elif match.group(2) != dptname:
        errors.append(
            f"Department name does not match: {dptname} and {match.groups(2)} in {classname}"
        )
        logger.warning(
            f"Department name does not match: {dptname} and {match.groups(2)} in {classname}"
        )

    classnum = match.group(3)
    if (dptname, classnum) not in all_classnums:
        all_classnums.add((dptname, classnum))
        logger.info(f"Added class number {classnum} for department {dptname}")
    else:
        errors.append(f"Duplicate CLASS in {dptname}: {classnum}")
        logger.error(f"Duplicate CLASS in {dptname}: {classnum}")
    classname = match.group(4)

    full_classname = dptname + "-" + classnum + " " + classname
    if full_classname not in all_classnames:
        all_classnames[full_classname] = [dptname, classnum, 0]
        logger.info(f"Added new class {full_classname}")
    else:
        dptname2, classnum2, _ = all_classnames[full_classname]
        if dptname2 != dptname:
            crosslisted_output.append(
                f"Crosslisted CLASS: {full_classname} is {dptname2}-{classnum2} and {dptname}-{classnum}"
            )
            logger.info(
                f"Crosslisted CLASS: {full_classname} is {dptname2}-{classnum2} and {dptname}-{classnum}"
            )

    tasks = []
    for fid in files.keys():
        tasks.append(
            process_test(
                files[fid]["children"],
                files[fid]["name"],
                dptname,
                classnum,
                fid,
                results,
                full_classname,
                all_classnames,
                logger,
                errors,
                invalid_filenames,
                gdrive_client,
            )
        )
    await asyncio.gather(*tasks)
    logger.info(f"Finished processing class: {classname} in department {dptname}")


async def process_department(
    structure: dict,
    did: str,
    all_dpts: set[str],
    all_classnums: set[tuple[str, str]],
    all_classnames: dict,
    results: dict,
    logger: Logger,
    errors: list[str],
    crosslisted_output: list[str],
    invalid_filenames: list[str],
    gdrive_client: GoogleDriveClient,
) -> None:
    """
    Process a single department in the Google Drive structure. (example: CSCI)

    :param structure: Structure of the Google Drive.
    :param did: ID of the department to process.
    :param all_dpts: Set of all department names.
    :param all_classnums: Set of all class numbers.
    :param all_classnames: Dictionary of all class names.
    :param results: Dictionary to store the results.
    :param logger: Logger object to log information.
    :param errors: List of errors to write to Google Sheets.
    :param crosslisted_output: List of crosslisted classes to write to Google Sheets.
    :param invalid_filenames: List of invalid filenames to write to Google Sheets.
    :param gdrive_client: GoogleDriveClient object to interact with Google Drive.
    """

    # Filter out files in the root directory which are do not represent current departments
    logger.info(f"Processing department: {structure[did]['name']}")
    if structure[did]["children"] is not None and len(structure[did]["name"]) <= 6:
        match = find_department.search(structure[did]["name"])
        # Expects some text before four capital letters
        if match is None:
            errors.append(f"Invalid DEPARTMENT: {structure[did]['name']}")
            logger.error(f"Invalid DEPARTMENT: {structure[did]['name']}")
            return
        dptname = match.group(2)
        if dptname in all_dpts:
            errors.append(f"Duplicate DEPARTMENT: {dptname}")
            logger.error(f"Duplicate DEPARTMENT: {dptname}")
        else:
            all_dpts.add(dptname)
            logger.info(f"Added department: {dptname}")

        classes = structure[did]["children"]
        tasks = []
        for cid in classes.keys():
            tasks.append(
                process_course(
                    classes[cid]["children"],
                    classes[cid]["name"],
                    dptname,
                    all_classnums,
                    all_classnames,
                    results,
                    logger,
                    errors,
                    crosslisted_output,
                    invalid_filenames,
                    gdrive_client,
                )
            )

        await asyncio.gather(*tasks)
        logger.info(f"Finished processing department: {structure[did]['name']}")
    else:
        logger.warning(f"Skipping invalid department: {structure[did]['name']}")


async def interpret_backtests(
    logger: Logger,
    structure: dict,
    sheet_client: GoogleSheetClient,
    gdrive_client: GoogleDriveClient,
) -> tuple[dict, set[str], dict]:
    """
    Take in the structure of the Google Drive and interpret the backtests to be used for mongoDB and Google Sheets.

    :param logger: Logger object to log information.
    :param structure: Structure of the Google Drive.
    :param sheet_client: GoogleSheetClient object to write errors to Google Sheets.
    :param gdrive_client: GoogleDriveClient object to interact with Google Drive.
    """

    errors = []
    invalid_filenames = []
    crosslisted_output = []

    # Check for duplicate errors
    all_dpts = set()
    all_classnums = set()
    all_classnames = {}

    # data to be used for the mongo database
    results = {}

    logger.info("Starting to process departments")
    tasks = []
    for did in structure.keys():
        logger.info(f"Queueing department {structure[did]['name']} for processing")
        tasks.append(
            process_department(
                structure,
                did,
                all_dpts,
                all_classnums,
                all_classnames,
                results,
                logger,
                errors,
                crosslisted_output,
                invalid_filenames,
                gdrive_client,
            )
        )

    await asyncio.gather(*tasks)
    logger.info("Finished processing all departments")

    logger.info("Writing all errors to Google Sheets")
    await sheet_client.write_all_errors(errors, invalid_filenames, crosslisted_output)
    logger.info("Finished writing errors to Google Sheets")

    return results, all_dpts, all_classnames
