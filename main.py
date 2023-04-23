from __future__ import print_function

import argparse
import sys
import os.path
import re
# import pickle
import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']

def get_recursive_structure(service, fileid):
  structure = {}
  # Use Google's API to get a complete list of the children in a folder (Google's 'service.files()' function gives a COMPLETE LIST of ALL files in your drive)
  results = service.files().list(q = f"'{fileid}' in parents", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
  # Results is returned as a dict
  for item in results['files']:
    structure[item['id']] = {'name': item['name'], 'folder': 'folder' in item['mimeType']}
    if structure[item['id']]['folder']:
      # Get the children using the same exact function
      structure[item['id']]['children'] = get_recursive_structure(service, item['id'])
    else:
      # Used as a way to tell this is not a folder
      structure[item['id']]['children'] = None
  return structure

def interpret_backtests(structure, error_output = None, crosslisted_output = None, invalid_filename_output = None, rename_filename_output = None, unlikely_filename = 'unlikely_exceptions.txt'):
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
  results = []
  
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
    if structure[did]['children'] != None and len(structure[did]['name']) <= 6:
      match = re.search('([^A-Z]|^)([A-Z]{4})$', structure[did]['name'])
      # Expects some text before four capital letters
      if match == None:
        efile.write(f"Invalid DEPARTMENT: {structure[did]['name']}\n")
        continue
      dptname = match.group(2)
      if dptname in all_dpts:
        efile.write(f"Duplicate DEPARTMENT: {dptname}\n")
      all_dpts.add(dptname)
      classes = structure[did]['children']
      for cid in classes.keys():
        if classes[cid]['children'] == None:
          efile.write(f"File in {dptname} folder is not a CLASS: {classes[cid]['name']}\n")
          continue
        classes[cid]['name']
        match = re.search('(^\*?)([A-Z]{4})-([0-9]{4}) (.+)$', classes[cid]['name'])
        if match == None:
          efile.write(f"Invalid CLASS in {dptname}: {classes[cid]['name']}\n")
          continue
        elif match.group(2) != dptname:
          efile.write(f"Department name does not match: {dptname} and {match.groups(2)} in {classes[cid]['name']}\n")
        classnum = match.group(3)
        if (dptname, classnum) not in all_classnums:
          all_classnums.add((dptname, classnum))
        else:
          efile.write(f"Duplicate CLASS in {dptname}: {classnum}\n")
        classname = match.group(4)
        if classname not in uexceptions and not re.match("([A-Z][a-z]*|[A-Z]{4}),?(( |-)[A-Z][a-z]*,?|( |-)[A-Z]{4}| of| and| to| in| for| and| the)*( I| II| 1| 2)?$", classname):
          unlikely = True
          efile.write(f"Unlikely CLASS name listed as {dptname}-{classnum}: {classname}\n")
        if classname not in all_classnames:
          all_classnames[classname] = (dptname, classnum)
        else:
          dptname2, classnum2 = all_classnames[classname]
          if dptname2 != dptname:
            cfile.write(f"Crosslisted CLASS: {classname} is {dptname2}-{classnum2} and {dptname}-{classnum}\n")
        files = classes[cid]['children']
        for fid in files.keys():
          if files[fid]['children'] != None:
            efile.write(f"Folder in {dptname}-{classnum}: {files[fid]['name']}\n")
            continue
          dptname_capitalized = dptname[0].upper()+dptname[1:].lower()
          dptname_lower = dptname.lower()
          # This is the worst thing ever
          class_start = "(" + '(' + dptname + '|' + dptname_capitalized + '|' + dptname_lower + ')(-| )?' + classnum + "( |_|-)?( |_|-)?( |_|-)?)?(M1?|E[1-9]|Q|Q[1-9][0-9]?) ?(F|S|U|S[uU])([0-9]{2})(.*?)(\.pdf)?$"
          match = re.match(class_start, files[fid]['name'])
          if match == None:
            iffile.write(f"Invalid filename in {dptname}-{classnum}: {files[fid]['name']}\n")
            continue
          exam_num = match.group(7)
          # No M1/M2/etc
          if exam_num[0] == 'M':
            exam_num = 'M'
          semester = match.group(8)
          if semester == 'Su' or semester == 'SU':
            semester = 'U'
          year = match.group(9)
          if int(year) > current_year:
            iffile.write(f"Invalid year in {dptname}-{classnum}: {files[fid]['name']}\n")
            continue
          correct_filename = f'{dptname}-{classnum} {exam_num}{semester}{year}.pdf'
          if correct_filename != files[fid]['name']:
            rffile.write(f"Correct the name of file with id <{fid}> from <{files[fid]['name']}> to <{correct_filename}>\n")
          results.append({'classname': classname, 'dept': dptname, 'classnum': classnum, 'examtype': exam_num[0], 'examnum': exam_num[1:], 'semester': semester, 'year': year})
  if unlikely:
    efile.write(f"If a course is known to exist but its name is listed as 'unlikely', please add it to {unlikely_filename}\n")
    
  for file in open_files.values():
    file.close()
  
  return results

def main():
  """Shows basic usage of the Drive v3 API.
  Prints the names and ids of the first 10 files the user has access to.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
      token.write(creds.to_json())

  try:
    service = build('drive', 'v3', credentials=creds)
    
    parser = argparse.ArgumentParser(description='Compile backtests from Google. May require you to sign into your Google account.')
    parser.add_argument('folder_id', help='The id of the base backtest folder according to Google. For example, the id of the folder at https://drive.google.com/drive/u/0/folders/0AJ1INTLLjH1EUk9PVA is 0AJ1INTLLjH1EUk9PVA.')
    parser.add_argument('-e', '--error_file', nargs='?', const=None, default=None, help='The file to print general errors in file structure to (default is stdout)')
    parser.add_argument('-c', '--crosslisted_file', nargs='?', const=None, default=None, help='The file to print crosslisted courses to (default is stdout)')
    parser.add_argument('-i', '--invalid_file', nargs='?', const=None, default=None, help='Where to print backtest filenames which could not be parsed (default is stdout)')
    parser.add_argument('-r', '--rename_file', nargs='?', const=None, default=None, help='Where to print backtest filenames which should be renamed (default is stdout)')
    parser.add_argument('-u', '--unlikely_file', nargs='?', const='unlikely_exceptions.txt', default='unlikely_exceptions.txt', help='Class names in this file will not be listed as "unlikely" (does not follow correct English grammar) in the errors (default is unlikely_exceptions.txt)')
    
    args = parser.parse_args()
    
    folder_id = args.folder_id
    
    # DEBUG CODE: DO NOT USE THIS UNLESS YOU ARE TESTING
    # if os.path.exists('structure.pkl'):
    #   with open('structure.pkl', "rb") as file:
    #     structure = pickle.load(file)
    # else:
    #   with open('structure.pkl', "wb") as file:
    #     structure = get_recursive_structure(service, folder_id)
    #     pickle.dump(structure, file)
    structure = get_recursive_structure(service, folder_id)
    
    # This function is based off the fact that structure is constructed with an 'id' based off of the Google Drive id
    # If the backtest drive is ever moved off of Google Drive into a physical filesystem or elsewhere, I recommend to change get_recursive_structure so that the id stored is the complete path of the file
    all_backtests = interpret_backtests(structure, error_output=args.error_file, crosslisted_output=args.crosslisted_file, invalid_filename_output=args.invalid_file, rename_filename_output=args.rename_file, unlikely_filename = args.unlikely_file)
    
            
  except HttpError as error:
    # TODO(developer) - Handle errors from drive API.
    print(f'An error occurred: {error}')


if __name__ == '__main__':
  main()