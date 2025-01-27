# backtest-compilation  
A Python script to compile backtests. The script reads the folder and file structure of the backtest drive in a Google Workspace. It reports updated counts and errors to a Google sheet to allow easy viewing of what needs to be done to reach parity between physical and digital copies of tests. It finds differences between the folders and files and existing backtests in the MongoDB collections holding backtest data. It updates the collections so that the website reflects the current backtest offerings.

## Set up
To set up how to use this script, please look at installing Python:
https://developers.google.com/drive/api/quickstart/python

Install and setup [UV](https://docs.astral.sh/uv/getting-started/)
- Install packages using uv

Note that this requires a Google Cloud project with permissions, which is annoying to set up.  
- Create a project at https://console.cloud.google.com
- Enable the Google Drive API
- Enable the Google Sheets API
- Setup up a service account and save the credentials to config/service-credentials.json

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