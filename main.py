import logging
import re
from datetime import date
from os import getenv
from sys import stdout
from time import sleep, time
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pymongo import MongoClient

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]

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

find_department = re.compile("([^A-Z]|^)([A-Z]{4})$")
find_classname = re.compile(r"(^\*?)([A-Z]{4})-([0-9]{3}[0-9X]) (.+)$")


def get_recursive_structure(service, fileid, sharedDrive, logger) -> dict:
    logger.debug(f"Getting recursive structure for {fileid}")
    structure = {}
    # Use Google's API to get a complete list of the children in a folder (Google's 'service.files()' function gives a COMPLETE LIST of ALL files in your drive)

    for attempt in range(3):
        try:
            results = (
                service.files()
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
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Exiting")
                raise e
            logger.debug(f"Attempt {attempt + 1} failed: {e}")
            sleep(1)

    # Results is returned as a dict
    for item in results["files"]:
        structure[item["id"]] = {
            "name": item["name"],
            "folder": "folder" in item["mimeType"],
        }
        if structure[item["id"]]["folder"]:
            # Get the children using the same exact function
            structure[item["id"]]["children"] = get_recursive_structure(
                service, item["id"], sharedDrive, logger
            )
        else:
            # Used as a way to tell this is not a folder
            structure[item["id"]]["children"] = None

    return structure


def interpret_backtests(
    logger,
    service,
    structure,
    error_output=None,
    crosslisted_output=None,
    invalid_filename_output=None,
) -> Any:
    # Handles opening files;
    # files are not opened twice and each opened file is put into open_files
    open_files = {}
    if error_output is not None:
        efile = open(error_output, "w")
        open_files[error_output] = efile
    else:
        efile = stdout
    if invalid_filename_output is not None:
        if invalid_filename_output in open_files:
            iffile = open_files[invalid_filename_output]
        else:
            iffile = open(invalid_filename_output, "w")
            open_files[invalid_filename_output] = iffile
    else:
        iffile = stdout
    if crosslisted_output is not None:
        if crosslisted_output in open_files:
            cfile = open_files[crosslisted_output]
        else:
            cfile = open(crosslisted_output, "w")
            open_files[crosslisted_output] = cfile
    else:
        cfile = stdout

    # Check for duplicate errors
    all_dpts = set()
    all_classnums = set()
    all_classnames = {}

    # data to be used for the mongo database
    results = {}

    # To check if classes have an invalid year
    current_year = date.today().year % 100
    for did in structure.keys():
        # Filter out files in the root directory which are do not represent current departments
        if structure[did]["children"] is not None and len(structure[did]["name"]) <= 6:
            match = find_department.search(structure[did]["name"])
            # Expects some text before four capital letters
            if match is None:
                efile.write(f"Invalid DEPARTMENT: {structure[did]['name']}\n")
                continue
            dptname = match.group(2)
            if dptname in all_dpts:
                efile.write(f"Duplicate DEPARTMENT: {dptname}\n")
            all_dpts.add(dptname)

            classes = structure[did]["children"]
            for cid in classes.keys():
                if classes[cid]["children"] is None:
                    efile.write(
                        f"File in {dptname} folder is not a CLASS: {classes[cid]['name']}\n"
                    )
                    continue

                match = find_classname.search(classes[cid]["name"])
                if match is None:
                    efile.write(f"Invalid CLASS in {dptname}: {classes[cid]['name']}\n")
                    continue
                elif match.group(2) != dptname:
                    efile.write(
                        f"Department name does not match: {dptname} and {match.groups(2)} in {classes[cid]['name']}\n"
                    )

                classnum = match.group(3)
                if (dptname, classnum) not in all_classnums:
                    all_classnums.add((dptname, classnum))
                else:
                    efile.write(f"Duplicate CLASS in {dptname}: {classnum}\n")
                classname = match.group(4)

                full_classname = classnum + " " + classname
                if full_classname not in all_classnames:
                    all_classnames[full_classname] = (dptname, classnum)
                else:
                    dptname2, classnum2 = all_classnames[full_classname]
                    if dptname2 != dptname:
                        cfile.write(
                            f"Crosslisted CLASS: {full_classname} is {dptname2}-{classnum2} and {dptname}-{classnum}\n"
                        )

                files = classes[cid]["children"]
                for fid in files.keys():
                    if files[fid]["children"] is not None:
                        efile.write(
                            f"Folder in {dptname}-{classnum}: {files[fid]['name']}\n"
                        )
                        continue
                    dptname_capitalized = dptname[0].upper() + dptname[1:].lower()
                    dptname_lower = dptname.lower()
                    # This is the worst thing ever
                    class_start = (
                        "("
                        + "("
                        + dptname
                        + "|"
                        + dptname_capitalized
                        + "|"
                        + dptname_lower
                        + ")(-| )?"
                        + classnum
                        + r"( |_|-)?( |_|-)?( |_|-)?)?(M1?|E[1-9]|Q|Q[1-9][0-9]?) ?(F|S|U|S[uU])([0-9]{2})(.*?)(\.pdf)?$"
                    )

                    match = re.match(class_start, files[fid]["name"])
                    if match is None:
                        iffile.write(
                            f"Invalid filename in {dptname}-{classnum}: {files[fid]['name']}\n"
                        )
                        continue
                    exam_num = match.group(7)
                    # No M1/M2/etc
                    if exam_num[0] == "M":
                        exam_num = "M"
                    semester = match.group(8)
                    if semester.lower() == "su":
                        semester = "U"

                    year = match.group(9)
                    if int(year) > current_year and dptname != "BEAR":
                        iffile.write(
                            f"Invalid year in {dptname}-{classnum}: {files[fid]['name']}\n"
                        )
                        continue

                    correct_filename = (
                        f"{dptname}-{classnum} {exam_num}{semester}{year}.pdf"
                    )
                    if correct_filename != files[fid]["name"]:
                        for attempt in range(3):
                            try:
                                service.files().update(
                                    fileId=fid,
                                    body={"name": correct_filename},
                                    supportsAllDrives=True,
                                ).execute()
                                logger.info(
                                    f"Renamed file with id <{fid}> from <{files[fid]['name']}> to <{correct_filename}>"
                                )
                                break
                            except HttpError as error:
                                if attempt == 2:
                                    logger.warning(
                                        f"Failed to rename file with id <{fid}> from <{files[fid]['name']}> to <{correct_filename}> after 3 attempts: {error}\n"
                                    )
                                else:
                                    logger.debug(
                                        f"Attempt {attempt + 1} to rename file with id <{fid}> from <{files[fid]['name']}> to <{correct_filename}> failed: {error}\n"
                                    )
                                    sleep(1)

                    examtype = (
                        examtype_mapping[exam_num[0].upper()] + " " + exam_num[1:]
                    ).strip()
                    examsemester = exam_date_mapping[semester.upper()] + " 20" + year
                    if classnum + " " + classname in results:
                        inserted = False
                        for exam in results[classnum + " " + classname]:
                            if exam["type"] == examtype:
                                exam["tests"].append(examsemester)
                                inserted = True
                                break
                        if not inserted:
                            results[classnum + " " + classname].append(
                                {
                                    "type": examtype,
                                    "tests": [examsemester],
                                }
                            )
                    else:
                        results[classnum + " " + classname] = [
                            {
                                "type": examtype,
                                "tests": [examsemester],
                            }
                        ]

    for file in open_files.values():
        file.close()

    return results, all_dpts, all_classnames


type_order = {"Quiz": 1, "Exam": 2, "Midterm": 3}
season_order = {"Spring": 1, "Summer": 2, "Fall": 3}


# Sort the exams by type and tests by date
def sort_key(exam: dict) -> tuple[int, int | float]:
    type_parts = exam["type"].split()
    type_prefix = type_parts[0]
    type_number = type_parts[1] if len(type_parts) > 1 else "0"
    return (
        type_order[type_prefix],
        int(type_number) if type_number.isdigit() else float("inf"),
    )


def sort_tests(tests: list[str]) -> list[str]:
    return sorted(
        tests,
        key=lambda x: (int(x.split()[1]), season_order[x.split()[0]]),
        reverse=True,
    )


def add_to_mongo(results: dict, all_dpts: set, all_classnames: dict, logger) -> None:
    client = MongoClient(getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client["apo_main"]
    backtest_course_code_collection = db["backtest_course_code_collection"]
    backtest_courses_collection = db["backtest_courses_collection"]
    backtest_collection = db["backtest_collection"]

    existing_codes = set(
        item["course_code"] for item in backtest_course_code_collection.find()
    )

    codes_to_add = all_dpts - existing_codes
    codes_to_remove = existing_codes - all_dpts

    if codes_to_add:
        backtest_course_code_collection.insert_many(
            [{"course_code": code} for code in codes_to_add]
        )
        logger.info(f"Added course codes {codes_to_add}")

    if codes_to_remove:
        backtest_course_code_collection.delete_many(
            {"course_code": {"$in": list(codes_to_remove)}}
        )
        logger.info(f"Removed course codes {codes_to_remove}")

    existing_classes = set(item["name"] for item in backtest_courses_collection.find())

    classnames = set(all_classnames.keys())
    classes_to_add = classnames - existing_classes
    classes_to_remove = list(existing_classes - classnames)

    if classes_to_add:
        backtest_courses_collection.insert_many(
            [
                {"name": classname, "course_code": all_classnames[classname][0]}
                for classname in classes_to_add
            ]
        )
        logger.info(f"Added class names {classes_to_add}")

    if classes_to_remove:
        backtest_courses_collection.delete_many({"name": {"$in": classes_to_remove}})

        class_backtests_to_remove = set(
            item["_id"]
            for item in backtest_courses_collection.find(
                {"name": {"$in": classes_to_remove}}
            )
        )
        backtest_collection.delete_many(
            {"course_ids": {"$in": list(class_backtests_to_remove)}}
        )
        logger.info(f"Removed class names {classes_to_remove}")

    current_courses = {}
    for course in backtest_courses_collection.find():
        current_courses[course["name"]] = course["_id"]

    # Add empty backtest collection items to prevent errors
    if classes_to_add:
        backtest_collection.insert_many(
            [
                {"course_ids": [current_courses[classname]], "tests": []}
                for classname in classes_to_add
            ]
        )
        logger.debug(f"Added empty backtest collection items for {classes_to_add}")

    for classname, exams in results.items():
        current_course = backtest_courses_collection.find_one({"name": classname})
        if not current_course:
            logger.error(f"Course {classname} not found in database")
            raise ValueError(f"Course {classname} not found in database")
        current_tests = backtest_collection.find_one(
            {"course_ids": {"$in": [current_course["_id"]]}}
        )

        for exam in exams:
            exam["tests"] = sort_tests(exam["tests"])

        exams.sort(key=sort_key)

        logger.debug(f"Sorted exams: {exams}")
        logger.debug(f"Current tests: {current_tests}")

        if not current_tests:
            course_id = current_courses[classname]
            course_ids = [course_id]

            backtest_collection.insert_one({"tests": exams, "course_ids": course_ids})
            logger.info(f"Added tests for {classname}")

        elif current_tests["tests"] != exams:
            backtest_collection.update_one(
                {"_id": current_tests["_id"]}, {"$set": {"tests": exams}}
            )
            logger.info(f"Updated tests for {classname}")

    client.close()


def main() -> None:
    # Setup logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(stdout),
        ],
    )
    logger = logging.getLogger(__name__)

    # Create google drive service object
    credentials = service_account.Credentials.from_service_account_file(
        "config/service-credentials.json", scopes=SCOPES
    )

    delegated_creds = credentials.with_subject(getenv("DELEGATE_EMAIL"))

    service = build("drive", "v3", credentials=delegated_creds)

    folder_id = getenv("FOLDER_ID")
    start_time = time()
    structure = get_recursive_structure(service, folder_id, folder_id, logger)
    end_time = time()
    logger.info(
        f"Time taken to get recursive structure: {end_time - start_time} seconds"
    )

    start_time = time()
    # This function is based off the fact that structure is constructed with an 'id' based off of the Google Drive id
    # If the backtest drive is ever moved off of Google Drive into a physical filesystem or elsewhere, I recommend to change get_recursive_structure so that the id stored is the complete path of the file
    all_backtests, all_dpts, all_classnames = interpret_backtests(
        logger, service, structure
    )

    end_time = time()
    logger.info(f"Time taken to interpret backtests: {end_time - start_time} seconds")

    start_time = time()

    add_to_mongo(all_backtests, all_dpts, all_classnames, logger)

    end_time = time()
    logger.info(f"Time taken to add to mongo: {end_time - start_time} seconds")


if __name__ == "__main__":
    main()
