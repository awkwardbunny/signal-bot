#!/usr/bin/env python3
import dbus
import time
import logging
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from enum import Enum
from subprocess import STDOUT, check_output, Popen, PIPE, CalledProcessError

class SignalBot:

    DATA_BASE_DIR = "/signal-data"
    USERS_FILE = DATA_BASE_DIR + "/users"

    def __init__(self):
        self.logger = logging.getLogger("SignalBot")
        self.logger.info(" == Brian's Signal Bot v0.4 == ")

        # Set up some things while DBus is initializing
        self.commands = {
                "help"     : (self.helpHandler,     "HALP"),
                "ping"     : (self.pingHandler,     "Returns pong"),
                "whoami"   : (self.whoamiHandler,   "Returns registered name"),
                "echo"     : (self.echoHandler,     "Echos sent message back"),
                "register" : (self.registerHandler, "Register user"),
                "fortune"  : (self.fortuneHandler,  "Want a fortune?"),
                }
        adminCmdOnly = {
                "mkadmin"  : (self.mkadminHandler,  "*Make user admin"),
                "sh"       : (self.shHandler,       "*Shell"),
                "users"    : (self.usersHandler,    "*List all registered users"),
                "msg"      : (self.msgHandler,      "*Message someone"),
                }

        self.adminCmd = self.commands.copy()
        self.adminCmd.update(adminCmdOnly)

        self.loadUsers()

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.loop = GLib.MainLoop()

        system_bus = dbus.SystemBus()
        while True:
            try:
                self.signal_bus = system_bus.get_object('org.asamk.Signal', '/org/asamk/Signal')
                self.logger.info("DBus object found!")
                break
            except:
                self.logger.info("Cannot find DBus object. Waiting...")
                time.sleep(1)

        self.logger.info("Using signal-cli version %s", str(self.signal_bus.version()))
        self.connectHandlers()

    def loadUsers(self):
        self.users = {}
        with open(self.USERS_FILE, 'r') as rf:
            for user in rf:
                num, name, isAdmin = user.strip().split(":")
                self.users[num] = (name, isAdmin == "1")
            self.logger.info("%d users loaded", len(self.users))

            for num, data in self.users.items():
                self.logger.debug("%s:%s %s", num, data[0], "(ADMIN)" if data[1] else "")

    def addUser(self, name, number):
        #with open(self.USERS_FILE, 'a') as f:
        #    f.write(f"{number}:{name}:0\n")
        self.users[number] = (name, False)
        self.saveUsers()

    def mkadmin(self, number):
        try:
            if self.users[number][1]:
                return 0 # Already an admin

            self.users[number] = (self.users[number][0], True)
            self.saveUsers()
            self.sendMessage("Congrats! You now have access to admin commands. See '!help' for more info.", number, [])
            return 0
        except KeyError:
            return -1

    def saveUsers(self):
        with open(self.USERS_FILE, 'w') as f:
            for num,data in self.users.items():
                f.write(f"{num}:{data[0]}:{1 if self.isAdmin(num) else 0}\n")

    def connectHandlers(self):
        self.signal_bus.connect_to_signal("MessageReceived", self.receiveHandler)
    
    def start(self):
        self.logger.info(" == Starting == ")
        self.loop.run()

    def receiveHandler(self, timestamp, sender, groupId, message, attachments):
        if len(message) == 0:
            return

        if len(groupId) == 0:
            self.logger.info(f"Message from {sender}: {message}")
        else:
            self.logger.info(f"Message from {sender} (group): {message}")

        # If no prefix
        if message[0] != "!":
            #logging.info("Not a command; ignoring message...")
            #logging.info("Sending response: {}")
            if len(groupId) == 0:
                self.sendMessage("Hello, I am a bot! Try sending '!help'", sender, groupId)
            else:
                self.logger.info("Ignoring regular message from group")
            return

        # Remove prefix
        message = message[1:]
        if len(message) == 0:
            return

        if message[0] == "!":
            self.logger.info("Ignoring message")
            return

        # Dispatch handlers
        try:
            if self.isAdmin(sender):
                self.adminCmd[message.split()[0].lower()][0](message, sender, groupId)
            else:
                self.commands[message.split()[0].lower()][0](message, sender, groupId)
        except KeyError:
            self.sendMessage("Unknown command! Try '!help'", sender, groupId)

    def sendMessage(self, message, receipient, group):
        if len(group) != 0:
            self.signal_bus.sendGroupMessage(message, dbus.Array([], signature=dbus.Signature('s')), group)
        else:
            self.signal_bus.sendMessage(message, dbus.Array([], signature=dbus.Signature('s')), receipient)

    def helpHandler(self, message, sender, group):
        #self.sendMessage("<Insert help here>", sender)
        self.sendMessage("Available commands:\n  {}\n\nNote: Messages starting with two exclamation (!!) are ignored.".format('\n  '.join(["!"+cmd+": "+desc[1] for cmd,desc in (self.adminCmd.items() if self.isAdmin(sender) else self.commands.items())])), sender, group)

    def pingHandler(self, message, sender, group):
        self.sendMessage("Pong!", sender, group)

    def echoHandler(self, message, sender, group):
        message = message[5:]
        self.sendMessage(message, sender, group)

    def whoamiHandler(self, message, sender, group):
        try:
            self.sendMessage("You are {}.".format(self.users[sender][0]), sender, group)
        except KeyError:
            self.sendMessage("You are an unknown user. Use '!register [name]' to register.", sender, group)
        return

    def isAdmin(self, sender):
        try:
            return self.users[sender][1];
        except KeyError:
            return False

    def registerHandler(self, msg, sender, group):
        #self.sendMessage("<Insert implementation here>", sender)
        try:
            self.sendMessage("You are already registered as {}.".format(self.users[sender][0]), sender, group)
        except KeyError:
            name = msg[8:].strip()
            if len(name) == 0:
                self.sendMessage("Missing name parameter: '!register [name]'", sender, group)
            else:
                self.addUser(name, sender)
                self.sendMessage("You are now {}.".format(name), sender, group)


    def shHandler(self, msg, sender, group):
        if "/signal-data" in msg:
            self.sendMessage("Restricted command :P", sender, group)
            return

        try:
            output = check_output(msg[3:].split(), stderr=STDOUT, timeout=5)
            self.sendMessage(output, sender, group)
        except CalledProcessError as e:
            self.sendMessage(f"[Error code {e.returncode}]: {e.output.decode()}", sender, group)
        except Exception as e:
            self.sendMessage(str(e), sender, group)

    def mkadminHandler(self, msg, sender, group):
        num = msg[7:].strip()
        if len(num) == 0:
            self.sendMessage("Missing number parameter: '!mkadmin [number]'", sender, group)
            return

        if self.mkadmin(num) == 0:
            self.sendMessage("Success!", sender, group)
        else:
            self.sendMessage("User not registered!", sender, group)

    def usersHandler(self, msg, sender, group):
        self.sendMessage("\n".join(f"{num}:{data[0]}:{1 if self.isAdmin(num) else 0}" for num,data in self.users.items()), sender, group)

    def fortuneHandler(self, msg, sender, group):
        ps = Popen("fortune", stdout=PIPE)
        output = check_output("cowsay -f hellokitty".split(), stderr=STDOUT, stdin=ps.stdout, timeout=5)
        self.sendMessage(output, sender, group)

    def msgHandler(self, msg, sender, group):
        s = msg[4:].split()
        dest = s[0]
        msg = s[1:]
        name = self.users[sender][0]
        #TODO Input checking for missing params
        self.sendMessage(f"Sent on behalf of {sender} ({name}):\n====================================\n{' '.join(msg)}", dest, [])

if __name__ == '__main__':

    # Set up logging
    formatter = logging.Formatter("%(asctime)s:%(name)s: %(levelname)7s - %(message)s", "%Y-%m-%d_%H:%M:%S")

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)

    logfile = logging.FileHandler("/signal-data/signal-bot.log")
    logfile.setLevel(logging.INFO)
    logfile.setFormatter(formatter)

    logger = logging.getLogger("SignalBot")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console)
    logger.addHandler(logfile)
        
    bot = SignalBot()
    bot.start()
