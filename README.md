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
- Setup up a service account and save the credentials to config/service-credentials.json

## Usage
To be written
