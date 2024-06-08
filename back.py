
# Use an official Python runtime as a parent image
FROM python:2.7-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir requests

# Make port 80 available to the world outside this container
EXPOSE 80

# Run backup_neuvector.py when the container launches
CMD ["python", "./backup_neuvector.py"]


docker build -t neuvector-backup .



docker run -v /path/to/backup/folder:/usr/src/app/backups neuvector-backup


#!/usr/bin/python2
def manage_backups(folder):
    backups = sorted(
        (os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.conf.gz')),
        key=os.path.getctime
    )

    # Delete the oldest backup if there are more than 3
    while len(backups) > 3:
        oldest_backup = backups.pop(0)
        try:
            os.remove(oldest_backup)
            print("Deleted oldest backup: {}".format(oldest_backup))
        except OSError as e:
            print("Error: Failed to delete {} ({})".format(oldest_backup, e))


import requests
import json
import datetime
import sys

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

# Configuration
neuvector_ip = "<neuvector_ip>"
port = "<port>"
username = "admin"
password = "admin_password"

# Get current date and time
date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = "backup_config_{}.conf.gz".format(date)

# Get the API token
def get_api_token():
    url = "https://{}:{}/v1/auth".format(neuvector_ip, port)
    payload = {
        "username": username,
        "password": password
    }
    try:
        response = requests.post(url, json=payload, verify=False)
        response.raise_for_status()
        return response.json().get('token')
    except requests.exceptions.RequestException as e:
        print("Error: Unable to obtain token")
        print(e)
        sys.exit(1)

# Export configuration
def export_configuration(token):
    url = "https://{}:{}/v1/file/config?raw=true".format(neuvector_ip, port)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer {}'.format(token)
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            f.write(response.content)
        print("Configuration successfully exported to {}".format(filename))
    except requests.exceptions.RequestException as e:
        print("Error: Failed to export configuration")
        print(e)
        sys.exit(1)

if __name__ == "__main__":
    token = get_api_token()
    export_configuration(token)
