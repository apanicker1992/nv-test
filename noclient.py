#!/usr/bin/python

import argparse
import requests
import sys

def list_containers(server, port, username, password, debug=False):
    url = "https://{}:{}/v1/hosts".format(server, port)
    headers = {"Content-Type": "application/json"}
    login_url = "https://{}:{}/v1/auth".format(server, port)
    
    # Login to get the token
    login_payload = {"password": {"username": username, "password": password}}
    try:
        login_response = requests.post(login_url, json=login_payload, headers=headers, verify=False)
        if login_response.status_code != 200:
            print("Login failed with status code {}".format(login_response.status_code))
            return False
        token = login_response.json().get("token", {}).get("token")
        if not token:
            print("Login failed: no token received")
            return False
    except requests.exceptions.RequestException as e:
        print("Login failed: {}".format(e))
        return False

    # Add the token to headers
    headers["X-Auth-Token"] = token

    # Get the list of hosts
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            hosts = response.json().get('hosts', [])
            for host in hosts:
                print("ID: {}".format(host['id']))
            return True
        else:
            print("Failed to retrieve hosts with status code {}".format(response.status_code))
            return False
    except requests.exceptions.RequestException as e:
        print("Failed to retrieve hosts: {}".format(e))
        return False
    finally:
        # Logout
        try:
            logout_url = "https://{}:{}/v1/auth".format(server, port)
            requests.delete(logout_url, headers=headers, verify=False)
        except requests.exceptions.RequestException as e:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='List all container IDs')
    parser.add_argument('-d', '--debug', action="store_true", help='Enable debug')
    parser.add_argument('-s', '--server', default="127.0.0.1", help='Controller IP address.')
    parser.add_argument('-p', '--port', type=int, default=443, help='Controller port.')
    parser.add_argument('-u', '--username', default="admin", help='Username')
    parser.add_argument('-w', '--password', default="admin", help='Password')

    args = parser.parse_args()

    ret = 1

    if list_containers(args.server, args.port, args.username, args.password, args.debug):
        ret = 0

    sys.exit(ret)
