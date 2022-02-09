#!/usr/bin/env python3
import dbus
import time
import logging
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from subprocess import STDOUT, check_output, Popen, PIPE, CalledProcessError
import urllib.request
import os
from datetime import date
from typing import List


class Blocks:
    BLACK = u'\u2b1b'
    EMPTY = u'\u2b1c'
    YELLOW = u'\U0001f7e8'
    GREEN = u'\U0001f7e9'


class Wordle:

    def __init__(self, config: str):
        self.logger = logging.getLogger("Wordle")

        self.config_dir = config
        if not os.path.exists(config):
            os.mkdir(config)
            self.logger.info(f"Creating wordle config dir: {config}")

        if not os.path.exists(config+"/wordlist"):
            self.logger.info(f"Fetching wordlist")
            guesslist = "https://gist.githubusercontent.com/cfreshman/cdcdf777450c5b5301e439061d29694c/raw/de1df631b45492e0974f7affe266ec36fed736eb/wordle-allowed-guesses.txt"
            with open(config+"/wordlist", 'w') as wordlist:
                for line in urllib.request.urlopen(guesslist):
                    wordlist.write(line.decode('utf-8'))

        self.logger.info("Loading wordlist")
        self.wordlist = []
        with open(config+"/answers", 'r') as answers:
            self.wordlist = [l.strip() for l in answers]

        with open(config+"/wordlist", 'r') as wordlist:
            self.wordlist += [l.strip() for l in wordlist]

    def getTodayDir(self) -> str:
        path = f"{self.config_dir}/{date.today()}"
        if not os.path.exists(path):
            os.mkdir(path)
            self.logger.info(f"Creating directory for today: {date.today()}")
        return path

    def getWotd(self) -> str:
        num = (date.today() - date(2021, 6, 19)).days
        # self.logger.info(f"Today is {date.today()}: #{num}")
        return self.wordlist[num]

    def getUserData(self, user: str) -> List[str]:
        path = f"{self.getTodayDir()}/{user}"
        if not os.path.exists(path):
            return []
        with open(path, 'r') as f:
            return [g.strip() for g in f if len(g.strip()) > 0]

    def setUserData(self, user: str, guesses: List[str]):
        path = f"{self.getTodayDir()}/{user}"
        with open(path, 'w') as f:
            for g in guesses:
                f.write(g + '\n')

    def guessWord(self, user: str, word: str, update: bool = True) -> (str, str):
        word = word.lower()

        if len(word) != 5:
            return None, "Wordle guesses must be 5 letters wrong"

        if word not in self.wordlist:
            return None, f"Word \"{word}\" is not a valid word in wordle"

        wotd = self.getWotd()
        guesses = self.getUserData(user)

        res = ""
        for e, a in zip(wotd, word):
            if e == a:
                res += Blocks.GREEN
            elif a in wotd:
                res += Blocks.YELLOW
            else:
                res += Blocks.BLACK

        if update:
            if word in guesses:
                res = f"Word \"{word}\" already guessed\n" + res
            else:
                guesses.append(word)
                self.setUserData(user, guesses)

        return res, None

    def getBoard(self, user: str) -> str:
        guesses = self.getUserData(user)

        fin = len(guesses) == 6
        res = ""
        for i in range(6):
            if i < len(guesses):
                r, _ = self.guessWord(user, guesses[i], False)
                res += r
                if guesses[i] == self.getWotd():
                    fin = True
                    break
            else:
                res += Blocks.EMPTY*5
            res += "\n"

        num = (date.today() - date(2021, 6, 19)).days
        status = f"Wordle {num} {len(guesses)}/6"
        if not fin and len(guesses) < 6:
            status = self.getInstruction() + "\n" + status

        return status + "\n\n" + res

    def getInstruction(self) -> str:
        return f"""Welcome to Wordle!
{Blocks.BLACK}: Wrong guess
{Blocks.GREEN}: Correct guess
{Blocks.YELLOW}: Incorrect position
{Blocks.EMPTY}: No guesses yet

Use '!wordle [guess]' enter a guess
Use '!wordle' to see this message
Use '!wordle -g' to see your guesses

"""


class SignalBot:

    DATA_BASE_DIR = "/signal-data"
    USERS_FILE = DATA_BASE_DIR + "/users"
    WORDLE_DIR = DATA_BASE_DIR + "/wordle"

    def __init__(self):
        self.logger = logging.getLogger("SignalBot")
        self.logger.info(" == Brian's Signal Bot v0.5 == ")

        # Set up some things while DBus is initializing
        self.commands = {
                "help"     : (self.helpHandler,     "HALP"),
                "ping"     : (self.pingHandler,     "Returns pong"),
                "whoami"   : (self.whoamiHandler,   "Returns registered name"),
                "echo"     : (self.echoHandler,     "Echos sent message back"),
                "register" : (self.registerHandler, "Register user"),
                "fortune"  : (self.fortuneHandler,  "Want a fortune?"),
                "wordle"   : (self.wordleHandler,   "Play wordle"),
                }
        adminCmdOnly = {
                "mkadmin"  : (self.mkadminHandler,  "*Make user admin"),
                "sh"       : (self.shHandler,       "*Shell"),
                "users"    : (self.usersHandler,    "*List all registered users"),
                "msg"      : (self.msgHandler,      "*Message someone"),
                }

        self.adminCmd = self.commands.copy()
        self.adminCmd.update(adminCmdOnly)

        self.users = {}
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

        self.wordle = Wordle(self.WORDLE_DIR)

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
        if len(s) < 2:
            self.sendMessage("Usage: !msg [number] [message to send]", sender, group)
            return
        dest = s[0]
        msg = s[1:]
        name = self.users[sender][0]
        self.sendMessage(f"Sent on behalf of {sender} ({name}):\n====================================\n{' '.join(msg)}", dest, [])

    def wordleHandler(self, msg, sender, group):
        s = msg.split()
        if len(s) < 2:
            if len(group) == 0:
                self.sendMessage(self.wordle.getBoard(sender), sender, group)
            else:
                try:
                    msg = f"For user '{self.users[sender][0]}':"
                except KeyError:
                    msg = f"For user 'unknown' ({sender}):"
                msg += "\n" + self.wordle.getBoard(sender)
                self.sendMessage(msg, sender, group)
        else:
            if s[1] == "-g":
                if len(group) != 0:
                    self.sendMessage("Cannot show guesses in group chats", sender, group)
                    return

                g = self.wordle.getUserData(sender)
                if len(g) == 0:
                    msg = "You have no guesses yet"
                else:
                    x = [self.wordle.guessWord(sender, c, False)[0] + " " + c for c in g]
                    num = (date.today() - date(2021, 6, 19)).days
                    msg = f"Your guesses for {num}:"
                    msg += "\n" + '\n'.join(x)
                self.sendMessage(msg, sender, group)
            else:
                res, error = self.wordle.guessWord(sender, s[1])
                self.sendMessage(res if error is None else error, sender, group)


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

    wlogger = logging.getLogger("Wordle")
    wlogger.setLevel(logging.DEBUG)
    wlogger.addHandler(console)
    wlogger.addHandler(logfile)
        
    bot = SignalBot()
    bot.start()
