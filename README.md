# backtest-compilation  
A Python script to compile backtests. The script reads the folder and file structure of the backtest drive in a Google Workspace. It reports updated counts and errors to a Google sheet to allow easy viewing of what needs to be done to reach parity between physical and digital copies of tests. It finds differences between the folders and files and existing backtests in the MongoDB collections holding backtest data. It updates the collections so that the website reflects the current backtest offerings.

## Set up
Install and setup [UV](https://docs.astral.sh/uv/getting-started/)
- Install packages using uv

```bash
uv sync
```

### Google Cloud Integration

Note that this requires a Google Cloud project with permissions, which is annoying to set up.  
- Create a project at https://console.cloud.google.com
- Enable the Google Drive API
- Enable the Google Sheets API
- Setup up a service account and save the credentials to config/service-credentials.json

### MongoDB Integration

This program depends on MongoDB to update collections and documents to match the files in a google drive. Details on the structure of the backtest data in the MongoDB collections can be found in the [backend repo](https://github.com/alpha-phi-omega-ez/backend/blob/main/server/models/backtest.py). There is a collection of course codes (CSCI, MATH, CHEM, etc.), backtest courses (Data Structures, Algorithms, Operating Systems, etc.), and backtests that contains the types of exams that are available for that class (Fall 2021, Spring 2024, Summer 2025, etc.)

Here is an example of the [docker compose for MongoDB](https://github.com/alpha-phi-omega-ez/deployment/blob/main/main-website-docker-compose.yml#L3-L15) for use with this code and the production system for APOEZ.

## Usage
For testing and one off operation do the setup above and ensure you have set the environment variables, this can be done through a .env file. Then run the application with `uv run python main.py`. A full run can take around 10 minutes due to slow API calls with google drive API and quoto limits on the google sheets API. Future runs store a cache that can cut times down significantly by removing the need to redo work on things like the google sheets API.

For production deployment use the [docker container](https://github.com/alpha-phi-omega-ez/backtest-compilation/pkgs/container/backtest-compilation). It is setup to run with cron on a schedule.

For both you need to put the service credentials json file in a file named `service-credentials.json` in ./config/

## Environment Variables

| Variable Name          | Default Value | Description                                                   |
|------------------------|---------------|---------------------------------------------------------------|
| `FOLDER_ID` | None          | Shared Drive ID for the backtest drive |
| `DELEGATE_EMAIL`| None          | Email that the scripts executres actions as, ensure this email has permissions to view and edit the shared drive and google sheet |
| `SHEET_URL`          | None          | URL to the backtest google sheet with counts and where to list errors |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB URI |
| `LOG_LEVEL` | `INFO` | Set the log level for the application, defaults to INFO |
| `SENTRY_DSN` | None | Set the DSN for sentry use to track errors |
| `SENTRY_TRACE_RATE` | `1.0` | Set the sentry trace rate | 

## Running

uv creates a virtual environment that stores all the packages. To run the application you can use uv or python linked in the virtual environment.

To run the script one off you can call `main.py` directly

```bash
uv run main.py
```

### Production

In production the code is run in a docker container which can be found in the [packages for this repo](https://github.com/alpha-phi-omega-ez/backtest-compilation/pkgs/container/backtest-compilation). The docker container runs [scheduler.py](scheduler.py) which handles when to run the main code.
