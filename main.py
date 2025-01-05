import argparse
import datetime
import os.path
import re
import sys
import json
from typing import Any

from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from google.oauth2 import service_account
import pymongo

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]

CONFIG = json.load(open("config/config.json"))

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


def get_recursive_structure(service, fileid, sharedDrive) -> dict:
    structure = {}
    # Use Google's API to get a complete list of the children in a folder (Google's 'service.files()' function gives a COMPLETE LIST of ALL files in your drive)

    for _ in range(3):
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
        except Exception as e:
            print(f"Error: {e}")
            continue

    # Results is returned as a dict
    for item in results["files"]:
        structure[item["id"]] = {
            "name": item["name"],
            "folder": "folder" in item["mimeType"],
        }
        if structure[item["id"]]["folder"]:
            # Get the children using the same exact function
            structure[item["id"]]["children"] = get_recursive_structure(
                service, item["id"], sharedDrive
            )
        else:
            # Used as a way to tell this is not a folder
            structure[item["id"]]["children"] = None

    return structure


def interpret_backtests(
    structure,
    error_output=None,
    crosslisted_output=None,
    invalid_filename_output=None,
    rename_filename_output=None,
    unlikely_filename="unlikely_exceptions.txt",
) -> Any:
    # Handles opening files;
    # files are not opened twice and each opened file is put into open_files
    open_files = {}
    if error_output != None:
        efile = open(error_output, "w")
        open_files[error_output] = efile
    else:
        efile = sys.stdout
    if invalid_filename_output != None:
        if invalid_filename_output in open_files:
            iffile = open_files[invalid_filename_output]
        else:
            iffile = open(invalid_filename_output, "w")
            open_files[invalid_filename_output] = iffile
    else:
        iffile = sys.stdout
    if crosslisted_output != None:
        if crosslisted_output in open_files:
            cfile = open_files[crosslisted_output]
        else:
            cfile = open(crosslisted_output, "w")
            open_files[crosslisted_output] = cfile
    else:
        cfile = sys.stdout
    if rename_filename_output != None:
        if rename_filename_output in open_files:
            rffile = open_files[rename_filename_output]
        else:
            rffile = open(rename_filename_output, "w")
            open_files[rename_filename_output] = rffile
    else:
        rffile = sys.stdout

    # Check for duplicate errors
    all_dpts = set()
    all_classnums = set()
    all_classnames = {}

    # This will be returned, containing all the backtests
    # with valid names in valid classes
    # Results will be a dict that has the keys of classname, dept, classnum, examnum, examtype, semester, and year
    old_results = []
    results = {}

    # Stop 'unlikely CLASS name' spam by creating a set of removed CLASS names
    unlikely = False
    uexceptions = set()
    if os.path.exists(unlikely_filename):
        with open(unlikely_filename, "r") as file:
            for line in file:
                uexceptions.add(line.strip())

    # To check if classes have an invalid year
    current_year = datetime.date.today().year % 100
    for did in structure.keys():
        # Filter out files in the root directory which are do not represent current departments
        if structure[did]["children"] != None and len(structure[did]["name"]) <= 6:
            match = re.search("([^A-Z]|^)([A-Z]{4})$", structure[did]["name"])
            # Expects some text before four capital letters
            if match == None:
                efile.write(f"Invalid DEPARTMENT: {structure[did]['name']}\n")
                continue
            dptname = match.group(2)
            if dptname in all_dpts:
                efile.write(f"Duplicate DEPARTMENT: {dptname}\n")
            all_dpts.add(dptname)
            classes = structure[did]["children"]
            for cid in classes.keys():
                if classes[cid]["children"] == None:
                    efile.write(
                        f"File in {dptname} folder is not a CLASS: {classes[cid]['name']}\n"
                    )
                    continue
                classes[cid]["name"]
                match = re.search(
                    r"(^\*?)([A-Z]{4})-([0-9]{3}[0-9X]) (.+)$", classes[cid]["name"]
                )
                if match == None:
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
                if classname not in uexceptions and not re.match(
                    "([A-Z][a-z]*|[A-Z]{4}),?(( |-)[A-Z][a-z]*,?|( |-)[A-Z]{4}| of| and| to| in| for| and| the)*( I| II| 1| 2)?$",
                    classname,
                ):
                    unlikely = True
                    efile.write(
                        f"Unlikely CLASS name listed as {dptname}-{classnum}: {classname}\n"
                    )
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
                    if files[fid]["children"] != None:
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
                    if match == None:
                        iffile.write(
                            f"Invalid filename in {dptname}-{classnum}: {files[fid]['name']}\n"
                        )
                        continue
                    exam_num = match.group(7)
                    # No M1/M2/etc
                    if exam_num[0] == "M":
                        exam_num = "M"
                    semester = match.group(8)
                    if semester == "Su" or semester == "SU":
                        semester = "U"
                    year = match.group(9)
                    if int(year) > current_year:
                        iffile.write(
                            f"Invalid year in {dptname}-{classnum}: {files[fid]['name']}\n"
                        )
                        continue
                    correct_filename = (
                        f"{dptname}-{classnum} {exam_num}{semester}{year}.pdf"
                    )
                    if correct_filename != files[fid]["name"]:
                        rffile.write(
                            f"Correct the name of file with id <{fid}> from <{files[fid]['name']}> to <{correct_filename}>\n"
                        )
                    old_results.append(
                        {
                            "classname": classnum + " " + classname,
                            "dept": dptname,
                            "examtype": (
                                examtype_mapping[exam_num[0].upper()]
                                + " "
                                + exam_num[1:]
                            ).strip(),
                            "semester": exam_date_mapping[semester.upper()]
                            + " 20"
                            + year,
                        }
                    )
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
    if unlikely:
        efile.write(
            f"If a course is known to exist but its name is listed as 'unlikely', please add it to {unlikely_filename}\n"
        )

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


def add_to_mongo(results: dict, all_dpts: set, all_classnames: dict) -> None:
    client = pymongo.MongoClient(CONFIG["MONGO_URI"])
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

    if codes_to_remove:
        backtest_course_code_collection.delete_many(
            {"course_code": {"$in": list(codes_to_remove)}}
        )

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
        print(f"Added class names {classes_to_add}")

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

    current_courses = {}
    for course in backtest_courses_collection.find():
        current_courses[course["name"]] = course["_id"]

    for classname, exams in results.items():
        current_course = backtest_courses_collection.find_one({"name": classname})
        if not current_course:
            raise ValueError(f"Course {classname} not found in database")
        current_tests = backtest_collection.find_one(
            {"course_ids": {"$in": [current_course["_id"]]}}
        )

        for exam in exams:
            exam["tests"] = sort_tests(exam["tests"])

        exams.sort(key=sort_key)

        if not current_tests:
            course_id = current_courses[classname]
            course_ids = [course_id]

            backtest_collection.insert_one({"tests": exams, "course_ids": course_ids})
            print(f"Added tests {classname}")

        elif current_tests["tests"] != exams:
            backtest_collection.update_one(
                {"_id": current_tests["_id"]}, {"$set": {"tests": exams}}
            )
            print(f"Updated tests {classname}")


def main() -> None:
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """

    credentials = service_account.Credentials.from_service_account_file(
        "config/service-credentials.json", scopes=SCOPES
    )

    delegated_creds = credentials.with_subject(CONFIG["DELEGATE_EMAIL"])

    try:
        service = build("drive", "v3", credentials=delegated_creds)

        parser = argparse.ArgumentParser(description="Compile backtests from Google.")
        parser.add_argument(
            "-e",
            "--error_file",
            nargs="?",
            const=None,
            default=None,
            help="The file to print general errors in file structure to (default is stdout)",
        )
        parser.add_argument(
            "-c",
            "--crosslisted_file",
            nargs="?",
            const=None,
            default=None,
            help="The file to print crosslisted courses to (default is stdout)",
        )
        parser.add_argument(
            "-i",
            "--invalid_file",
            nargs="?",
            const=None,
            default=None,
            help="Where to print backtest filenames which could not be parsed (default is stdout)",
        )
        parser.add_argument(
            "-r",
            "--rename_file",
            nargs="?",
            const=None,
            default=None,
            help="Where to print backtest filenames which should be renamed (default is stdout)",
        )
        parser.add_argument(
            "-u",
            "--unlikely_file",
            nargs="?",
            const="unlikely_exceptions.txt",
            default="unlikely_exceptions.txt",
            help='Class names in this file will not be listed as "unlikely" (does not follow correct English grammar) in the errors (default is unlikely_exceptions.txt)',
        )

        args = parser.parse_args()

        folder_id = CONFIG["FOLDER_ID"]

        structure = get_recursive_structure(service, folder_id, folder_id)

        # This function is based off the fact that structure is constructed with an 'id' based off of the Google Drive id
        # If the backtest drive is ever moved off of Google Drive into a physical filesystem or elsewhere, I recommend to change get_recursive_structure so that the id stored is the complete path of the file
        all_backtests, all_dpts, all_classnames = interpret_backtests(
            structure,
            error_output=args.error_file,
            crosslisted_output=args.crosslisted_file,
            invalid_filename_output=args.invalid_file,
            rename_filename_output=args.rename_file,
            unlikely_filename=args.unlikely_file,
        )

        with open("backtests_mongo.json", "w") as f:
            json.dump(all_backtests, f, indent=4)

        add_to_mongo(all_backtests, all_dpts, all_classnames)

    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f"An error occurred: {error}")


if __name__ == "__main__":
    main()
