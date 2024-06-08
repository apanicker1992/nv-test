#!/usr/bin/python

import argparse
import io
import json
import requests
import sys
import time
import zlib

import client

def import_config(c, filename, raw):
    tid = ""
    tempToken = ""
    status = ""
    isOldCtlerVer = False # old version means 4.2.2 or older
    resp = c.importConfig("file/config", filename, raw, tid, 0, "")
    if tid == "":
        if resp.status_code == requests.codes.partial:
            respJson = resp.json()
            if "data" in respJson:
                respData = respJson["data"]
                tid = respData["tid"]
                print("[progress: {:3d}%] {}".format(respData["percentage"], respData["status"]))
                tempToken = respData["temp_token"]
        elif resp.status_code == requests.codes.ok and resp.text == "":
            isOldCtlerVer = True
            status = "done"

    if tid != "" and not isOldCtlerVer:
        i = 1
        #print("Info: import task transaction id is {}".format(tid))
        while resp.status_code == requests.codes.partial:
            time.sleep(3)
            resp = c.importConfig("file/config", filename, raw, tid, i, tempToken)
            respJson = resp.json()
            if "data" in respJson:
                respData = respJson["data"]
                if "status" in respData:
                    status = respData["status"]
                if status != "":
                    print("[progress: {:3d}%] {}".format(respData["percentage"], status))
            i = i + 1
        #print("--------------------------")
        if resp.status_code == requests.codes.ok:
            respJson = resp.json()
            if "data" in respJson:
                respData = respJson["data"]
                if "status" in respData:
                    status = respData["status"]

    print("")
    if resp.status_code == requests.codes.ok and status == "done":
        # print("Uploaded configuration file {}. Please login again.".format(filename))
        return True
    else:
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Import/export configuration')
    parser.add_argument('action', choices=['import', 'export'])
    parser.add_argument('-d', '--debug', action="store_true", help='Enable debug')
    parser.add_argument('-s', '--server', default="127.0.0.1", help='Controller IP address.')
    parser.add_argument('-p', '--port', type=int, default=443, help='Controller port.')
    parser.add_argument('-u', '--username', default="admin", help='Username')
    parser.add_argument('-w', '--password', default="admin", help='Password')
    parser.add_argument('-f', '--filename', help='Filename')
    parser.add_argument('--section', nargs='*', help='Export sections')

    args = parser.parse_args()

    ret = 1

    # import pdb; pdb.set_trace()
    url = "https://%s:%s" % (args.server, args.port)
    c = client.RestClient(url, args.debug)

    try:
        token = c.login(args.username, args.password)
    except client.RestException as e:
        print("Error: " + e.msg)
        sys.exit(ret)

    if args.action == "export":
        # export
        if args.section and len(args.section) > 0:
            secs = ','.join(args.section)
            print("secs = {}".format(secs))
            headers, body = c.download("file/config?section=" + secs + "&raw=true")
        else:
            headers, body = c.download("file/config?raw=true")

        if args.filename and len(args.filename) > 0:
            try:
                f = open(args.filename, 'wb')
                f.write(body.content)
                print("Wrote to {}".format(args.filename))
            except IOError:
                print("Error: Failed to write to {}".format(args.filename))
        else:
            print(body.content)

    elif args.action == "import":
        # import
        if not args.filename:
            print("Error: Import filename is not specified.")
        else:
            try:
                #c.upload("file/config", args.filename)
                import_config(c, args.filename, False)

                ret = 0
                print("Uploaded configuration file %s" % args.filename)
            except IOError:
                print("Error: Failed to upload configuration file %s" % args.filename)
            except Exception as err:
                print("Error: Failed to upload configuration file {} ({})".format(args.filename, err.msg))
    else:
        print("Error: Unsupported action.")

    try:
        c.logout()
    except client.RestException:
        pass

    sys.exit(ret)
