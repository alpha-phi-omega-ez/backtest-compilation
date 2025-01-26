from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from logging import Logger

type_order = {"Quiz": 1, "Exam": 2, "Midterm": 3}
season_order = {"Spring": 1, "Summer": 2, "Fall": 3}


class MongoClient:
    def __init__(self, settings: dict, logger: Logger) -> None:
        """
        Create the MongoDB client and connect to the database.

        :param settings: Dictionary with the settings.
        :param logger: Logger object.
        """

        self.client = AsyncIOMotorClient(settings["MONGO_URI"])
        self.database = self.client.apo_main
        self.backtest_course_code_collection = self.database.get_collection(
            "backtest_course_code_collection"
        )
        self.backtest_courses_collection = self.database.get_collection(
            "backtest_courses_collection"
        )
        self.backtest_collection = self.database.get_collection("backtest_collection")
        self.logger = logger

    def close(self) -> None:
        """
        Close the MongoDB client.
        """

        self.client.close()

    @staticmethod
    def sort_key(exam: dict) -> tuple[int, int | float]:
        """
        Sort the exams by type.

        :param exam: Dictionary with the exam information.
        :return: Tuple with the type order and the test number.
        """

        type_parts = exam["type"].split()
        type_prefix = type_parts[0]
        type_number = type_parts[1] if len(type_parts) > 1 else "0"
        return (
            type_order[type_prefix],
            int(type_number) if type_number.isdigit() else float("inf"),
        )

    @staticmethod
    async def sort_tests(tests: list[str]) -> list[str]:
        """
        Sort the tests by sesmester and number.

        :param tests: List of tests.
        :return: Sorted list of tests.
        """

        return sorted(
            tests,
            key=lambda x: (int(x.split()[1]), season_order[x.split()[0]]),
            reverse=True,
        )

    async def process_class(
        self,
        classname: str,
        exams: list[dict],
        current_courses: dict,
    ) -> None:
        """
        Process the class and update the tests in the DB.

        :param classname: Name of the class.
        :param exams: List of exams.
        :param current_courses: Dictionary with the current courses.
        """

        current_course = await self.backtest_courses_collection.find_one(
            {"name": classname}
        )
        if not current_course:
            self.logger.error(f"Course {classname} not found in database")
            raise ValueError(f"Course {classname} not found in database")

        current_tests = await self.backtest_collection.find_one(
            {"course_ids": {"$in": [current_course["_id"]]}}
        )

        sort_tasks = [self.sort_tests(exam["tests"]) for exam in exams]
        sorted_tests = await asyncio.gather(*sort_tasks)
        for exam, sorted_test in zip(exams, sorted_tests):
            exam["tests"] = sorted_test

        exams.sort(key=self.sort_key)

        self.logger.debug(f"Sorted exams: {exams}")
        self.logger.debug(f"Current tests: {current_tests}")

        if not current_tests:
            course_id = current_courses[classname]
            course_ids = [course_id]

            await self.backtest_collection.insert_one(
                {"tests": exams, "course_ids": course_ids}
            )
            self.logger.info(f"Added tests for {classname}")

        elif current_tests["tests"] != exams:
            await self.backtest_collection.update_one(
                {"_id": current_tests["_id"]}, {"$set": {"tests": exams}}
            )
            self.logger.info(f"Updated tests for {classname}")

    async def update_course_codes(self, all_dpts: set) -> None:
        """
        Update the course codes in the database.

        :param all_dpts: Set with all the course codes.
        """

        existing_codes = set()
        async for item in self.backtest_course_code_collection.find():
            existing_codes.add(item["course_code"])

        codes_to_add = all_dpts - existing_codes
        codes_to_remove = existing_codes - all_dpts

        if codes_to_add:
            await self.backtest_course_code_collection.insert_many(
                [{"course_code": code} for code in codes_to_add]
            )
            self.logger.info(f"Added course codes {codes_to_add}")

        if codes_to_remove:
            await self.backtest_course_code_collection.delete_many(
                {"course_code": {"$in": list(codes_to_remove)}}
            )
            self.logger.info(f"Removed course codes {codes_to_remove}")

    async def add_to_mongo(
        self, results: dict, all_dpts: set, all_classnames: dict
    ) -> None:
        """
        Add the backtests to the MongoDB.

        :param results: Dictionary with the results.
        :param all_dpts: Set with all the course codes.
        :param all_classnames: Dictionary with all the class names.
        """

        await self.update_course_codes(all_dpts)

        existing_classes = set()
        async for item in self.backtest_courses_collection.find():
            existing_classes.add(item["name"])

        classnames = set(all_classnames.keys())
        classes_to_add = classnames - existing_classes
        classes_to_remove = list(existing_classes - classnames)

        if classes_to_add:
            await self.backtest_courses_collection.insert_many(
                [
                    {"name": classname, "course_code": all_classnames[classname][0]}
                    for classname in classes_to_add
                ]
            )
            self.logger.info(f"Added class names {classes_to_add}")

        if classes_to_remove:
            await self.backtest_courses_collection.delete_many(
                {"name": {"$in": classes_to_remove}}
            )

            class_backtests_to_remove = set()
            async for item in self.backtest_courses_collection.find(
                {"name": {"$in": classes_to_remove}}
            ):
                class_backtests_to_remove.add(item["_id"])

            await self.backtest_collection.delete_many(
                {"course_ids": {"$in": list(class_backtests_to_remove)}}
            )
            self.logger.info(f"Removed class names {classes_to_remove}")

        current_courses = {}
        async for course in self.backtest_courses_collection.find():
            current_courses[course["name"]] = course["_id"]

        # Add empty backtest collection items to prevent errors
        if classes_to_add:
            await self.backtest_collection.insert_many(
                [
                    {"course_ids": [current_courses[classname]], "tests": []}
                    for classname in classes_to_add
                ]
            )
            self.logger.debug(
                f"Added empty backtest collection items for {classes_to_add}"
            )

        tasks = []
        for classname, exams in results.items():
            tasks.append(
                self.process_class(
                    classname,
                    exams,
                    current_courses,
                )
            )
        await asyncio.gather(*tasks)
