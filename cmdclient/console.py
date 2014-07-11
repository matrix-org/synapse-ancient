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
        Valid config variables:
            user: The username to auth with.
            token: The access token to auth with.
            url: The url of the server.
            verbose: [on|off] The verbosity of requests/responses.
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

    def do_join(self, line):
        """Joins a room: "join <roomid>" """
        try:
            args = self._parse(line, ["roomid"], force_keys=True)
            self._do_membership_change(args["roomid"], "join", self._usr())
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
            self._do_membership_change(args["roomid"], "leave", self._usr())
        except Exception as e:
            print e

    def do_send(self, line):
        """Sends a message. "send <roomid> <body>" """
        args = self._parse(line, ["roomid", "body"])
        msg_id = "m%s" % int(time.time())
        path = "/rooms/%s/messages/%s/%s" % (args["roomid"], self._usr(),
                                             msg_id)
        body_json = {
            "msgtype": "sy.text",
            "body": args["body"]
        }
        reactor.callFromThread(self._run_and_pprint, "PUT", path, body_json)

    def do_raw(self, line):
        """Directly send a JSON object: "raw <method> <path> <data> <notoken>"
        <method>: Required. One of "PUT", "GET"
        <path>: Required. E.g. "/events"
        <data>: Optional. E.g. "{ "msgtype":"custom.text", "body":"abc123"}"
        <notoken>: Optional. "true" to not append the access token to the path.
        """
        args = self._parse(line, ["method", "path", "data", "notoken"])
        # sanity check
        if "method" not in args or "path" not in args:
            print "Must specify path and method."
            return

        args["method"] = args["method"].upper()
        if args["method"] not in ["PUT", "GET"]:
            print "Unsupported method %s" % args["method"]
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
        if "notoken" in args:
            qp = {}

        reactor.callFromThread(self._run_and_pprint, args["method"],
                                                     args["path"],
                                                     args["data"],
                                                     query_params=qp)

    def do_stream(self, line):
        """Stream data from the server: "stream" """
        reactor.callFromThread(self._do_event_stream, line)

    @defer.inlineCallbacks
    def _do_event_stream(self, line):
        res = yield self.http_client.get_json(
                self._url() + "/events",
                {
                    "access_token": self._tok(),
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


def main(server_url, username, token):
    print "Synapse command line client"
    print "==========================="
    print "Server: %s" % server_url
    print "Type 'help' to get started."
    print "Close this console with CTRL+C then CTRL+D."
    if not username or not token:
        print "-  Register an account: 'register <username>'"
        print "-  Connect to the event stream: 'stream'"
        print "-  Join a room: 'join <roomid>'"
        print "-  Send a message: 'send <roomid> <message>'"
    http_client = TwistedHttpClient()

    # the command line client
    syn_cmd = SynapseCmd(http_client, server_url, username, token)

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
