Custom IBID Plugins (IRC Bot Plugins)
====================

URL Process
---------------------
Processes any links posted through reddit, twitch, and youtube. Returns info about them if available.

Twitch Broadcaster
---------------------
Notifies a source/target (needs to be configured) with information about when a twitch broadcaster starts streaming or switches games. ibid-db --upgrade needs to create the database schema.

For the database support, please note the following issue: https://bugs.launchpad.net/ibid/+bug/1211986

Wolfram Alpha
---------------------
Uses the Wolfram Alpha API and responds to the user with a query when a message is prefixed with ?

Bitcoin
---------------------
Small plugin to respond with the price of bitcoin using MtGox when you type "!btc"

Steam Processor
---------------------
Currently only gets information about a steam user when you type "!steam <user_vanity>"

Copycat
---------------------
Annoying simple plugin which makes the bot copy what a user says.


Plugins were written pretty quickly, if there's any improvements they will be appreciated.