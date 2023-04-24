# backtest-compilation  
A python script to compile backtests in the Google Drive.  

## Set up
To set up how to use this script, please look at:  
https://developers.google.com/drive/api/quickstart/python  
Note that this requires a Google Cloud project with permissions, which is kind of annoying to set up.  
I have already created a project at https://console.cloud.google.com/welcome?pli=1&project=backtest-compilation,  
The permissions that this project needs to have in Google OAuth is from the Google Drive API: 	.../auth/drive.metadata.readonly.  
If you want to use my Google Cloud project, contact me I guess but it's probably better to have one for the frat.  

## Usage
The arguments for this script are listed if you use the -h argument.  
You need to get the id for the backtest drive folder in Google (such as 0AJ1INTLLjH1EUk9PVA from https://drive.google.com/drive/u/0/folders/0AJ1INTLLjH1EUk9PVA) in order to run it, and this folder must be acessible to the user that you log in as.  
Arguments can be used to split up the output (which is parsing errors and filesystem problems which are found during compilation) into several different files. The function which is run creates a Python dictionary with information about every backtest parsed, but currently nothing is done with it after the script completes. If you actually want to use this, you'll have to add something in Python to do so.
For testing, rather than running things through the Google Drive every time the script has the ability to instead load data using Python's Pickle library. The code to do this is commented out in the script because of security vulnerabilities, and do not run this script on any pickle file that you do not implicitly trust. As well as that, it's probably a good idea to change this to JSON instead but I'm not doing it yet lol.  
