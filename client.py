import json
import requests
import string

UserDomainDelimiter = "@"

class RestException(Exception):
    message = "An unknown exception occurred."

    def __init__(self, **kwargs):
        try:
            super(RestException, self).__init__(self.message % kwargs)
            self.msg = self.message % kwargs
        except Exception:
            super(RestException, self).__init__(self.message)

class ConnectionError(RestException):
    message = "Fail to connect to server"

class ConnectTimeout(RestException):
    message = "Connection timeout"

class RequestError(RestException):
    message = "Request error"

class LoginFailure(RestException):
    message = "Invalid login credential."

class TooManyLogin(RestException):
    message = "Too many login."

class AlreadyLogin(RestException):
    message = "User %(user)s already login."

class ResponseError(RestException):
    message = "Unable to parse response: %(msg)s"

class Unauthorized(RestException):
    message = "Not authorized! Login first."

class LoginBlocked(RestException):
    message = "This user is temporarily blocked for login because of too many failed login attempts."

class LoginPwsExpired(RestException):
    message = "Login password is already expired."

class ObjectNotFound(RestException):
    message = "Object not found."

class NotEnoughFilter(RestException):
    message = "More search criteria required."

class RestRequestError(RestException):
    message = "%(err)s: %(msg)s"

class InvalidInputError(RestException):
    message = "%(msg)s"

class RestClient(object):
    RESTErrNotFound         = 1
    RESTErrMethodNotAllowed = 2
    RESTErrUnauthorized     = 3
    RESTErrOpNotAllowed     = 4
    RESTErrTooManyLoginUser = 5
    RESTErrInvalidRequest   = 6
    RESTErrObjectNotFound   = 7
    RESTErrNotEnoughFilter  = 12
    RESTErrUserLoginBlocked = 47
    RESTErrPasswordExpired  = 48

    def __init__(self, url, debug):
        self.url = url
        self.debug = debug
        self.sess = requests.Session()
        self.sess.headers.update({"Content-Type": "application/json"})

        try:
            if hasattr(requests.packages.urllib3, "disable_warnings"):
                requests.packages.urllib3.disable_warnings()
        except AttributeError:
            pass

    def _request(self, method, url, body=None, files=None, decode=True):
        if self.debug:
            print("URL: {} {}".format(method, url))
            # for key in self.sess.headers:
            #     print("{}: {}".format(key, self.sess.headers[key]))
            print("Body:")
            if decode:
                if body:
                    print("  {}".format(json.dumps(body)))
                else:
                    print("")

        try:
            if decode:
                body_data = json.dumps(body) if body else ""
                resp = self.sess.request(method, url, data=body_data, files=files,
                                         verify=False)
            else:
                resp = self.sess.request(method, url, data=body, files=files,
                                         verify=False)
        except requests.exceptions.ConnectionError:
            raise ConnectionError()
        except requests.exceptions.Timeout:
            raise ConnectTimeout()
        except requests.exceptions.RequestException:
            raise RequestError()

        try:
            if decode:
                if self.debug:
                    print("Response:")
                    print("  {} {}".format(resp.status_code, resp.text))
                data = resp.json()
            else:
                data = resp
        except Exception as e:
            data = None

        return resp.status_code, resp.headers, resp.text, data

    def _token(self):
        return self.sess.headers.get("X-Auth-Token")

    def _clear_token(self):
        self.sess.headers.pop("X-Auth-Token", None)

    def _errcode(self, data):
        return data.get("code")

    def _errtxt(self, data):
        return data.get("error")

    def _errmsg(self, data):
        return data.get("message")

    def _handle_common_error(self, data):
        if self._errcode(data) == self.RESTErrUnauthorized:
            self._clear_token()
            raise Unauthorized()
        elif self._errcode(data) == self.RESTErrObjectNotFound:
            raise ObjectNotFound()
        elif self._errcode(data) == self.RESTErrNotEnoughFilter:
            raise NotEnoughFilter()
        else:
            raise RestRequestError(err=self._errtxt(data), msg=self._errmsg(data))

    def login(self, username, password):
        if self._token():
            raise AlreadyLogin(user=username)

        body = {"password": {"username": username, "password": password}}
        status, _, text, data = self._request("POST",
                                              self.url + '/v1/auth',
                                              body=body)
        if status == requests.codes.ok:
            if not data:
                raise ResponseError(msg=text)

            if data.get("token") and data["token"].get("token"):
                token = data["token"]["token"]
                self.sess.headers.update({"X-Auth-Token": token})
            else:
                raise ResponseError(msg=data)
        else:
            if self._errcode(data) == self.RESTErrTooManyLoginUser:
                raise TooManyLogin()
            elif self._errcode(data) == self.RESTErrUserLoginBlocked:
                raise LoginBlocked()
            elif self._errcode(data) == self.RESTErrPasswordExpired:
                raise LoginPwsExpired()
            else:
                raise LoginFailure()

    def logout(self):
        if not self._token():
            return

        status, _, _, data = self._request("DELETE",
                                           self.url + '/v1/auth')

        if status == requests.codes.ok:
            self._clear_token()
        elif self._errcode(data) == self.RESTErrUnauthorized:
            self._clear_token()

    def list(self, path, obj, sort=None, sort_dir=None, **kwargs):
        if not self._token():
            raise Unauthorized()

        # Make query url with sort parameters
        url = "%s/v1/%s" % (self.url, path)
        if sort or len(kwargs) > 0:
            url += "?"
            if sort:
                if not sort_dir or (sort_dir != "asc" and sort_dir != "desc"):
                    sort_dir = "asc"

                url += "s_%s=%s&" % (sort, sort_dir)
            for key, value in kwargs.iteritems():
                if key == 'start':
                    url += "start=%s&" % value
                elif key == 'limit':
                    url += "limit=%s&" % value
                elif key == 'brief':
                    url += "brief=%s&" % value
                else:
                    url += "f_%s=%s&" % (key, value)
            url = string.rstrip(url, "&")

        status, _, _, data = self._request("GET", url)

        json_header = obj + "s"
        if status == requests.codes.ok:
            # Don't use 'get', array can be empty
            if json_header in data:
                return data[json_header]
            else:
                raise ResponseError(msg=data)
        else:
            self._handle_common_error(data)

    def show(self, path, obj, obj_id):
        if not self._token():
            raise Unauthorized()

        status, _, _, data = self._request("GET",
                                           "%s/v1/%s/%s" % (self.url, path, obj_id))

        json_header = obj
        if status == requests.codes.ok:
            if data.get(json_header):
                return data[json_header]
            else:
                raise ResponseError(msg=data)
        else:
            self._handle_common_error(data)

    def create(self, path, body):
        if not self._token():
            raise Unauthorized()

        status, _, _, data = self._request("POST",
                                           "%s/v1/%s" % (self.url, path),
                                           body=body)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def config(self, path, obj, obj_id, body):
        if not self._token():
            raise Unauthorized()

        status, _, _, data = self._request("PATCH",
                                           "%s/v1/%s/%s" % (self.url, path, obj_id),
                                           body={obj: body})

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def delete(self, path, obj_id):
        if not self._token():
            raise Unauthorized()

        if obj_id == None:
            status, _, _, data = self._request("DELETE", "%s/v1/%s" % (self.url, path))
        else:
            status, _, _, data = self._request("DELETE", "%s/v1/%s/%s" % (self.url, path, obj_id))
        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def clear(self, path, **kwargs):
        url = "%s/v1/%s" % (self.url, path)
        if len(kwargs) > 0:
            url += "?"
            for key, value in kwargs.iteritems():
                url += "f_%s=%s&" % (key, value)
            url = string.rstrip(url, "&")

        status, _, _, data = self._request("DELETE", url)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def request(self, path, obj, obj_id):
        if not self._token():
            raise Unauthorized()

        if obj_id == None:
            status, _, _, data = self._request("POST",
                                          "%s/v1/%s/%s" % (self.url, path, obj))
        else:
            status, _, _, data = self._request("POST",
                                          "%s/v1/%s/%s/%s" % (self.url, path, obj, obj_id))
        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def show_obj_data(self, obj, obj_id, attr):
        if not self._token():
            raise Unauthorized()

        url = "%s/v1/%s/%s/%s" % (self.url, obj, obj_id, attr)
        status, _, _, data = self._request("GET", url)

        if status == requests.codes.ok:
            return data
        else:
            self._handle_common_error(data)

    def get(self, obj, attr, **kwargs):
        if not self._token():
            raise Unauthorized()

        url = "%s/v1/%s/%s" % (self.url, obj, attr)
        if len(kwargs) > 0:
            url += "?"
            for key, value in kwargs.iteritems():
                url += "f_%s=%s&" % (key, value)
            url = string.rstrip(url, "&")

        status, _, _, data = self._request("GET", url)

        json_header = attr
        if status == requests.codes.ok:
            if data.get(json_header):
                return data[json_header]
            else:
                raise ResponseError(msg=data)
        else:
            self._handle_common_error(data)

    def download(self, path):
        if not self._token():
            raise Unauthorized()

        url = "%s/v1/%s" % (self.url, path)
        status, headers, _, data = self._request("GET", url, decode=False)
        if status == requests.codes.ok:
            return headers, data
        else:
            self._handle_common_error(data.json())

    def upload(self, path, filename):
        if not self._token():
            raise Unauthorized()

        url = "%s/v1/%s" % (self.url, path)
        headers = {"X-Auth-Token": self._token()}
        files = {'configuration': open(filename, 'rb')}

        if self.debug:
            print("URL: POST {}".format(url))

        try:
            resp = requests.post(url, headers=headers, files=files, verify=False)
        except requests.exceptions.ConnectionError:
            raise ConnectionError()
        except requests.exceptions.Timeout:
            raise ConnectTimeout()
        except requests.exceptions.RequestException:
            raise RequestError()

        if resp.status_code == requests.codes.ok or resp.status_code == requests.codes.partial:
            return True

        self._handle_common_error(resp.json())
        
    def config_workload(self, wl_id, **kwargs):
        if not self._token():
            raise Unauthorized()

        conf = {}
        for key, value in kwargs.iteritems():
            if key == "monitor":
                conf['monitor'] = True if value == "enable" else False
        body = {"config": conf}

        status, _, _, data = self._request("PATCH",
                                           "%s/v1/workload/%s" % (self.url, wl_id),
                                           body=body)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def config_controller(self, controller_id, **kwargs):
        if not self._token():
            raise Unauthorized()

        conf = {}
        for key, value in kwargs.iteritems():
            if key == "debug":
                conf["debug"] = value
        body = {"config": conf}

        status, _, _, data = self._request("PATCH",
                                           "%s/v1/controller/%s" % (self.url, controller_id),
                                           body=body)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def config_enforcer(self, enforcer_id, **kwargs):
        if not self._token():
            raise Unauthorized()

        conf = {}
        for key, value in kwargs.iteritems():
            if key == "debug":
                conf["debug"] = value
        body = {"config": conf}

        status, _, _, data = self._request("PATCH",
                                           "%s/v1/enforcer/%s" % (self.url, enforcer_id),
                                           body=body)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def importConfig(self, path, filename, raw, tid, iter, tempToken):
        # iter=0 means triggers import. iter>=1 means starting query import status
        if not self._token():
            raise Unauthorized()

        url = "%s/v1/%s" % (self.url, path)
        headers = {"X-Auth-Token": self._token()}

        if self.debug:
            print("URL: POST {}".format(url))

        try:
            # import pdb; pdb.set_trace()
            if tid != "":
                headers["X-Transaction-ID"] = tid
                resp = requests.post(url, headers=headers, data="", verify=False)
            elif raw:
                f = open(filename)
                data = f.read()
                f.close()
                headers["Content-Type"] = "text/plain"
                resp = requests.post(url, headers=headers, data=data, verify=False)
            else:
                files = {'configuration': open(filename, 'rb')}
                resp = requests.post(url, headers=headers, files=files, verify=False)
        except requests.exceptions.ConnectionError:
            raise ConnectionError()
        except requests.exceptions.Timeout:
            raise ConnectTimeout()
        except requests.exceptions.RequestException:
            raise RequestError()

        if self.debug:
            print("Response:")
            print("  {} {}".format(resp.status_code, resp.text))
        if resp.status_code == requests.codes.ok:
            return resp

        if tid != "" and iter >= 1:
            if self._errcode(resp.json()) == self.RESTErrUnauthorized and (resp.status_code == 401 or resp.status_code == 408):
                # Use temp token
                self.sess.headers.update({"X-Auth-Token": tempToken})
                resp = self.importConfig(path, filename, raw, tid, iter, "")
                self._clear_token()
                return resp

        if resp.status_code != requests.codes.partial:
            self._handle_common_error(resp.json())

        return resp

    def config_system(self, **kwargs):
        if not self._token():
            raise Unauthorized()

        conf = {}
        for key, value in kwargs.iteritems():
            if key == "policy_mode":
                if value == 'learn':
                    conf["policy_mode"] = 'Learn'
                elif value == 'evaluate':
                    conf["policy_mode"] = 'Evaluate'
                elif value == 'enforce':
                    conf["policy_mode"] = 'Enforce'
                else:
                    raise InvalidInputError(msg='Invalid policy_mode value')
            else:
                conf[key] = value

        body = {"config": conf}

        status, _, _, data = self._request("PATCH",
                                           "%s/v1/system/config" % self.url,
                                           body=body)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def create_user(self, username, password, role, **kwargs):
        if not self._token():
            raise Unauthorized()

        body = {"user": {"username": username,
                         "password": password,
                         "role": role}}
        for key, value in kwargs.iteritems():
            if key == 'email':
                body["user"]["email"] = value 
            if key == 'locale':
                body["user"]["locale"] = value 
        status, _, _, data = self._request("POST",
                                           self.url + '/v1/user',
                                           body=body)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def config_user(self, username, **kwargs):
        if not self._token():
            raise Unauthorized()

        body = {"config": {"username": username}}
        for key, value in kwargs.iteritems():
            if key == 'password':
                body["config"]["new_password"] = value 
            elif key == 'current':
                body["config"]["password"] = value
            elif key == 'role':
                body["config"]["role"] = value
            elif key == 'email':
                body["config"]["email"] = value
            elif key == 'locale':
                body["config"]["locale"] = value
            elif key == 'timeout':
                body["config"]["timeout"] = value
        status, _, _, data = self._request("PATCH",
                                           self.url + '/v1/user/' + username,
                                           body=body)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def delete_user(self, username):
        if not self._token():
            raise Unauthorized()

        status, _, _, data = self._request("DELETE", self.url + '/v1/user/' + username)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

    def config_scanner(self, **kwargs):
        if not self._token():
            raise Unauthorized()

        conf = {}
        for key, value in kwargs.iteritems():
            if key == "auto_scan":
                if value == 'enable':
                    conf["auto_scan"] = True
                elif value == 'disable':
                    conf["auto_scan"] = False
                else:
                    raise InvalidInputError(msg='Invalid scan auto mode')
            else:
                raise InvalidInputError(msg='Invalid scan auto mode')

        body = {"config": conf}
        status, _, _, data = self._request("PATCH",
                                           "%s/v1/scan/config" % self.url,
                                           body=body)

        if status == requests.codes.ok:
            return True

        self._handle_common_error(data)

