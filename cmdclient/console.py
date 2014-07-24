#! /usr/bin/env python
""" Starts a synapse client console. """

from twisted.internet import reactor, defer
from http import TwistedHttpClient

import argparse
import cmd
import json
import shlex
import sys
import time
import urllib
import urlparse

CONFIG_JSON = "cmdclient_config.json"


class SynapseCmd(cmd.Cmd):

    """Basic synapse command-line processor.

    This processes commands from the user and calls the relevant HTTP methods.
    """

    def __init__(self, http_client, server_url, username, token):
        cmd.Cmd.__init__(self)
        self.http_client = http_client
        self.http_client.verbose = True
        self.config = {
            "url": server_url,
            "user": username,
            "token": token,
            "verbose": "on"
        }
        self.event_stream_token = "START"
        self.prompt = ">>> "

    def do_EOF(self, line):  # allows CTRL+D quitting
        return True

    def emptyline(self):
        pass  # else it repeats the previous command

    def _usr(self):
        return self.config["user"]

    def _tok(self):
        return self.config["token"]

    def _url(self):
        return self.config["url"]

    def do_config(self, line):
        """ Show the config for this client: "config"
        Edit a key value mapping: "config key value" e.g. "config token 1234"
        Config variables:
            user: The username to auth with.
            token: The access token to auth with.
            url: The url of the server.
            verbose: [on|off] The verbosity of requests/responses.
        Additional key/values can be added and can be substituted into requests
        by using $. E.g. 'config roomid room1' then 'raw get /rooms/$roomid'.
        """
        if len(line) == 0:
            print json.dumps(self.config, indent=4)
            return

        try:
            args = self._parse(line, ["key", "val"], force_keys=True)
            if args["key"] == "verbose":
                if args["val"] not in ["on", "off"]:
                    print "Value must be 'on' or 'off'."
                    return
                self.http_client.verbose = "on" == args["val"]
            self.config[args["key"]] = args["val"]
            print json.dumps(self.config, indent=4)
            save_config(self.config)
        except Exception as e:
            print e

    def do_register(self, line):
        """Registers for a new account: "register <userid> <noupdate>"
        <userid> : The desired user ID
        <noupdate> : Do not automatically clobber config values.
        """
        args = self._parse(line, ["userid", "noupdate"])
        path = "/register"
        body = {}
        if "userid" in args:
            body["user_id"] = args["userid"]

        reactor.callFromThread(self._do_register, "POST", path, body,
                               "noupdate" not in args)

    @defer.inlineCallbacks
    def _do_register(self, method, path, data, update_config):
        url = self._url() + path
        json_res = yield self.http_client.do_request(method, url, data=data)
        print json.dumps(json_res, indent=4)
        if update_config and "user_id" in json_res:
            self.config["user"] = json_res["user_id"]
            self.config["token"] = json_res["access_token"]
            save_config(self.config)

    def do_join(self, line):
        """Joins a room: "join <roomid>" """
        try:
            args = self._parse(line, ["roomid"], force_keys=True)
            self._do_membership_change(args["roomid"], "join", self._usr())
        except Exception as e:
            print e

    def do_topic(self, line):
        """"topic [set|get] <roomid> [<newtopic>]"
        Set the topic for a room: topic set <roomid> <newtopic>
        Get the topic for a room: topic get <roomid>
        """
        try:
            args = self._parse(line, ["action", "roomid", "topic"])
            if "action" not in args or "roomid" not in args:
                print "Must specify set|get and a room ID."
                return
            if args["action"].lower() not in ["set", "get"]:
                print "Must specify set|get, not %s" % args["action"]
                return

            path = "/rooms/%s/topic" % args["roomid"]

            if args["action"].lower() == "set":
                if "topic" not in args:
                    print "Must specify a new topic."
                    return
                body = {
                    "topic": args["topic"]
                }
                reactor.callFromThread(self._run_and_pprint, "PUT", path, body)
            elif args["action"].lower() == "get":
                reactor.callFromThread(self._run_and_pprint, "GET", path)
        except Exception as e:
            print e

    def do_invite(self, line):
        """Invite a user to a room: "invite <userid> <roomid>" """
        try:
            args = self._parse(line, ["userid", "roomid"], force_keys=True)
            self._do_membership_change(args["roomid"], "invite", args["userid"])
        except Exception as e:
            print e

    def do_leave(self, line):
        """Leaves a room: "leave <roomid>" """
        try:
            args = self._parse(line, ["roomid"], force_keys=True)
            path = ("/rooms/%s/members/%s/state" %
                    (urllib.quote(args["roomid"]), self._usr()))
            reactor.callFromThread(self._run_and_pprint, "DELETE", path)
        except Exception as e:
            print e

    def do_send(self, line):
        """Sends a message. "send <roomid> <body>" """
        args = self._parse(line, ["roomid", "body"])
        msg_id = "m%s" % int(time.time())
        path = "/rooms/%s/messages/%s/%s" % (urllib.quote(args["roomid"]),
                                             self._usr(),
                                             msg_id)
        body_json = {
            "msgtype": "sy.text",
            "body": args["body"]
        }
        reactor.callFromThread(self._run_and_pprint, "PUT", path, body_json)

    def do_list(self, line):
        """List data about a room.
        "list members <roomid> [query]" - List all the members in this room.
        "list messages <roomid> [query]" - List all the messages in this room.

        Where [query] will be directly applied as query parameters, allowing
        you to use the pagination API. E.g. the last 3 messages in this room:
        "list messages <roomid> from=END&to=START&limit=3"
        """
        args = self._parse(line, ["type", "roomid", "qp"])
        if not "type" in args or not "roomid" in args:
            print "Must specify type and room ID."
            return
        if args["type"] not in ["members", "messages"]:
            print "Unrecognised type: %s" % args["type"]
            return
        room_id = args["roomid"]
        path = "/rooms/%s/%s/list" % (room_id, args["type"])

        qp = {"access_token": self._tok()}
        if "qp" in args:
            for key_value_str in args["qp"].split("&"):
                try:
                    key_value = key_value_str.split("=")
                    qp[key_value[0]] = key_value[1]
                except:
                    print "Bad query param: %s" % key_value
                    return

        reactor.callFromThread(self._run_and_pprint, "GET", path,
                               query_params=qp)

    def do_create(self, line):
        """Creates a room.
        "create [public|private] <roomid>" - Create a room <roomid> with the
                                             specified visibility.
        "create <roomid>" - Create a room <roomid> with default visibility.
        "create [public|private]" - Create a room with specified visibility.
        "create" - Create a room with default visibility.
        """
        args = self._parse(line, ["vis", "roomid"])
        # fixup args depending on which were set
        body = {}
        if "vis" in args and args["vis"] in ["public", "private"]:
            body["visibility"] = args["vis"]

        room_id = None
        if "roomid" in args:
            room_id = args["roomid"]
        elif "vis" in args and args["vis"] not in ["public", "private"]:
            room_id = args["vis"]

        if room_id:
            path = "/rooms/%s" % urllib.quote(room_id)
            reactor.callFromThread(self._run_and_pprint, "PUT", path, body)
        else:
            reactor.callFromThread(self._run_and_pprint, "POST", "/rooms", body)

    def do_raw(self, line):
        """Directly send a JSON object: "raw <method> <path> <data> <notoken>"
        <method>: Required. One of "PUT", "GET", "POST", "xPUT", "xGET",
        "xPOST". Methods with 'x' prefixed will not automatically append the
        access token.
        <path>: Required. E.g. "/events"
        <data>: Optional. E.g. "{ "msgtype":"custom.text", "body":"abc123"}"
        """
        args = self._parse(line, ["method", "path", "data"])
        # sanity check
        if "method" not in args or "path" not in args:
            print "Must specify path and method."
            return

        args["method"] = args["method"].upper()
        valid_methods = ["PUT", "GET", "POST", "DELETE",
                         "XPUT", "XGET", "XPOST", "XDELETE"]
        if args["method"] not in valid_methods:
            print "Unsupported method: %s" % args["method"]
            return

        if "data" not in args:
            args["data"] = None
        else:
            try:
                args["data"] = json.loads(args["data"])
            except Exception as e:
                print "Data is not valid JSON. %s" % e
                return

        qp = {"access_token": self._tok()}
        if args["method"].startswith("X"):
            qp = {}  # remove access token
            args["method"] = args["method"][1:]  # snip the X
        else:
            # append any query params the user has set
            try:
                parsed_url = urlparse.urlparse(args["path"])
                qp.update(urlparse.parse_qs(parsed_url.query))
                args["path"] = parsed_url.path
            except:
                pass

        reactor.callFromThread(self._run_and_pprint, args["method"],
                                                     args["path"],
                                                     args["data"],
                                                     query_params=qp)

    def do_stream(self, line):
        """Stream data from the server: "stream <longpoll timeout ms>" """
        args = self._parse(line, ["timeout"])
        timeout = 5000
        if "timeout" in args:
            try:
                timeout = int(args["timeout"])
            except ValueError:
                print "Timeout must be in milliseconds."
                return
        reactor.callFromThread(self._do_event_stream, timeout)

    @defer.inlineCallbacks
    def _do_event_stream(self, timeout):
        res = yield self.http_client.get_json(
                self._url() + "/events",
                {
                    "access_token": self._tok(),
                    "timeout": str(timeout),
                    "from": self.event_stream_token
                })
        print json.dumps(res, indent=4)
        if "end" in res:
            self.event_stream_token = res["end"]

    def _do_membership_change(self, roomid, membership, userid):
        path = "/rooms/%s/members/%s/state" % (urllib.quote(roomid), userid)
        data = {
            "membership": membership
        }
        reactor.callFromThread(self._run_and_pprint, "PUT", path, data=data)

    def _parse(self, line, keys, force_keys=False):
        """ Parses the given line.

        Args:
            line : The line to parse
            keys : A list of keys to map onto the args
            force_keys : True to enforce that the line has a value for every key
        Returns:
            A dict of key:arg
        """
        line_args = shlex.split(line)
        if force_keys and len(line_args) != len(keys):
            raise IndexError("Must specify all args: %s" % keys)

        # do $ substitutions
        for i, arg in enumerate(line_args):
            for config_key in self.config:
                if ("$" + config_key) in arg:
                    line_args[i] = arg.replace("$" + config_key,
                                               self.config[config_key])

        return dict(zip(keys, line_args))

    @defer.inlineCallbacks
    def _run_and_pprint(self, method, path, data=None,
                        query_params={"access_token": None}):
        """ Runs an HTTP request and pretty prints the output.

        Args:
            method: HTTP method
            path: Relative path
            data: Raw JSON data if any
            query_params: dict of query parameters to add to the url
        """
        url = self._url() + path
        if "access_token" in query_params:
            query_params["access_token"] = self._tok()

        json_res = yield self.http_client.do_request(method, url,
                                                    data=data,
                                                    qparams=query_params)

        print json.dumps(json_res, indent=4)


def save_config(config):
    with open(CONFIG_JSON, 'w') as out:
        json.dump(config, out)


def main(server_url, username, token):
    print "Synapse command line client"
    print "==========================="
    print "Server: %s" % server_url
    print "Type 'help' to get started."
    print "Close this console with CTRL+C then CTRL+D."
    if not username or not token:
        print "-  'register <username>' - Register an account"
        print "-  'stream' - Connect to the event stream"
        print "-  'create <roomid>' - Create a room"
        print "-  'send <roomid> <message>' - Send a message"
    http_client = TwistedHttpClient()

    # the command line client
    syn_cmd = SynapseCmd(http_client, server_url, username, token)

    # load synapse.json config from a previous session
    try:
        with open(CONFIG_JSON, 'r') as config:
            syn_cmd.config = json.load(config)
            print "Loaded config from %s" % CONFIG_JSON
    except:
        pass

    # Twisted-specific: Runs the command processor in Twisted's event loop
    # to maintain a single thread for both commands and event processing.
    # If using another HTTP client, just call syn_cmd.cmdloop()
    reactor.callInThread(syn_cmd.cmdloop)
    reactor.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Starts a synapse client.")
    parser.add_argument(
        "-s", "--server", dest="server", default="http://localhost:8080",
        help="The URL of the server to talk to.")
    parser.add_argument(
        "-u", "--username", dest="username",
        help="Your username on the server.")
    parser.add_argument(
        "-t", "--token", dest="token",
        help="Your access token.")
    args = parser.parse_args()

    if not args.server:
        print "You must supply a server URL to communicate with."
        parser.print_help()
        sys.exit(1)

    server = args.server
    if not server.startswith("http://"):
        server = "http://" + args.server

    main(server, args.username, args.token)
