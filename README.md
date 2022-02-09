# Signal Bot
A signal bot written in Python using AsamK/signal-cli

# Usage
This project uses AsamK's [signal-cli](https://github.com/AsamK/signal-cli)  
Head over there to see install/usage directions for that.

This bot expects the signal data to be in `/signal-data` directory.

Once the account is registered/verified and signal-cli is running in daemon mode, the bot interacts with signal-cli via DBus.  
Some linux packages are necessary to run some of the commands:  

* `!fortune` needs `fortune cowsay`
* Miscellaneous tools I wanted available: ` iputils-ping figlet sysvbanner`

Install python dependencies: `$ pip install -r requirements.txt` you can just run `$ python3 ./bot.py`

See "Details" section to see how to interact with it.

# Docker
The dockerfile is provided.  
Take a look to see how it needs to be set up.

You will need to add the number that the bot operates on in the last line of Dockerfile:  
```
CMD ["+11234567890"]
```

Assuming the signal data is at `./data`, you can run:
```
$ docker build -t brian/signal .
$ docker run -it --rm -v "$(pwd)"/data:/signal-data brian/signal
```

# Details
Signal-cli data is expected to in the `/signal-data` directory.  
`/signal-data/signal-bot.log` will log incoming messages.  
`/signal-data/users` will be created when users register.  

The formatting of the users file is: `<phone number>:<registered name>:<1 or 0 depending on admin or not>`

List of commands:

* `!help` - shows list of commands
* `!ping` - will reply with "Pong!"
* `!whoami` - if registered, will tell you the registered name
* `!echo [message]` - will reply back with `message`
* `!register [name]` - will register your number with the name `name`
* `!fortune` - Hello Kitty will tell you a fortune

If the user is admin, there are some extra commands available to them:

* `!sh [command]` - runs shell commands
* `!msg [receipient] [message]` - sends message to another account
* `!users` - lists registered users
* `!mkadmin [number of another user]` - makes another account admin

Any messages starting with two exclamation marks `!!` will be ignored.  
Also, messages without the `!` prefix will be ignored in a group chat.

# Wordle
The '!wordle' command will let you play wordle.
The only requirement is to place a file into the wordle config directory that's automatically created and then restart.
It should look something like:
```bash
cp wordle-answers <data mount point>/wordle/answers
```

The answers file contains a word per line for each day since 06/19/2021 (June 19th, 2021)
This list can be found by looking at the javascript source for the original game.
For a custom list of words, just replace the file with your own.

Rest of the guess words will be downloaded from the web.


# Notes
Written kinda hastly bc excited to see it work. Need to rewrite much more nicely.  
I wanna add a `!bf [program]` command that interprets brainfuck.  
Uhh... better error handling...?
