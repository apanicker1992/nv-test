#!/usr/bin/python2

import subprocess
import schedule
import time
import datetime

# Configuration
controller_ip = "your_controller_ip"
controller_port = "your_controller_port"
username = "admin"
password = "admin"

# Function to run the export command
def run_export():
    # Get the current date and time
    date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = "backup_config_{}.conf.gz".format(date)

    # Command to execute
    command = [
        "./config.py", "export",
        "-u", username,
        "-w", password,
        "-s", controller_ip,
        "-p", controller_port,
        "-f", filename
    ]

    try:
        # Execute the command
        subprocess.check_call(command)
        print("Configuration successfully exported to {}".format(filename))
    except subprocess.CalledProcessError as e:
        print("Error: Failed to export configuration")
        print(e)

# Schedule the task to run once every day
schedule.every().day.at("00:00").do(run_export)

# Run the scheduler
while True:
    schedule.run_pending()
    time.sleep(1)
