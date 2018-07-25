**This repository is a fork of the [multiplayer tools included in 0ad][1] with the goal to
significantly improve them and make them easier to use for mod-admins to set up alternative game
lobbies. All of the changes made in this fork are meant to be ported back again to 0ad
eventually!**

# Introduction

This README contains details about *XpartaMuPP* and *EcheLOn*, two XMPP-bots, which provide a
multiplayer lobby and game rating capabilities for 0ad.

## XpartaMuPP - XMPP Multiplayer Game Manager

XpartaMuPP is responsible for managing available multiplayer games so players have an overview what
kind of games are currently available. It currently also serves as a proxy for EcheLOn and relays
all rating related requests from players to EcheLOn and vice versa.

## EcheLOn

EcheLOn is responsible for everything related to player ratings like providing access to
leaderboards and player profiles as well as updating ratings based on game outcomes.

# Setup

The instructions below assume they a run on a Debian-based Linux distribution. XpartaMuPP and
EcheLOn should work with other distributions as well, but might require different steps for setup.

Whenever `lobby.wildfiregames.com` is mentioned, it should be replaced by your own domain name
(or `localhost`) in all commands below.

## ejabberd

These instructions for ejabberd assume you're running a Debian version where at least ejabberd
17.03 is available (currently Debian Stretch with enabled backports), as that's the minimum
ejabberd version which is required for the custom ejabberd module to work.

### Install ejabberd

* Install `ejabberd`:

    $ apt-get install ejabberd

* Configure it, by setting the domain name (e.g. `localhost` if you installed it on your
  development computer) and add an admin user.:

    $ dpkg-reconfigure ejabberd

You should now be able to connect to this XMPP server using a normal XMPP client.

### Installation of the custom ejabberd module

* Adjust `/etc/ejabberd/ejabberdctl.cfg` and set `CONTRIB_MODULES_PATH` to the directory where
  you want to store `mod_ipstamp`:

    CONTRIB_MODULES_PATH=/opt/ejabberd-modules

* Ensure the target directory is readable by ejabberd.
* Copy the `mod_ipstamp` directory from `XpartaMuPP/` to `CONTRIB_MODULES_PATH/sources/`.
* Check that the module is available and compatible with your ejabberd:

    $ ejabberdctl modules_available
    $ ejabberdctl module_check mod_ipstamp

* Install `mod_ipstamp`:

    $ ejabberdctl module_install mod_ipstamp

* Add `mod_ipstamp` to the modules ejabberd should load in`/etc/ejabberd/ejabberd.yml`:

    modules:
      mod_ipstamp: {}

* Reload ejabberd's configuration:

    $ ejabberdctl reload_config

If something goes wrong, check `/var/log/ejabberd/ejabberd.log`

### Ejabberd configuration

A web administration interface is available at http://localhost:5280/admin. Use the admin user
credentials (full JID (user@domain)) to log in. Changing settings there is also possible, but some
of those might not persist on restart.

The rest of this section should be done by editing `/etc/ejabberd/ejabberd.yml`.

* Allow users to create accounts using the game via in-band registration:

    access:
      register:
        all: allow

* Check list of registered users:

    $ ejabberdctl registered_users lobby.wildfiregames.com

* `XpartaMuPP` and `EcheLOn` need user accounts to function, so create them using:

    $ ejabberdctl register echelon lobby.wildfiregames.com secure_password
    $ ejabberdctl register xpartamupp lobby.wildfiregames.com secure_password

* The bots also need to be able to get the IPs of users hosting a match, which is what
 `mod_ipstamp` does.

  * Create an ACL for the bot (or bots):

    acl:
      bots:
        user:
          - "echelon@lobby.wildfiregames.com"
          - "xpartamupp@lobby.wildfiregames.com"

* Add an access rule (name it `ipbots` since that is what the module expects):

    access:
      ipbots:
        bots: allow

* Due to the amount of traffic the bot may process, give the group containing bots either unlimited
  or a very high traffic shaper:

    c2s_shaper:
      admin: none
      bots: none
      all: normal

* The bots need the real JIDs of the MUC users, which are only available for admin users,
  therefore the following setting is necessary:

    access:
      muc_admin:
        admin: allow
        bots: allow

## General bot setup

To enable the bot to send the game list to players it needs the JIDs of the players, so the MUC
room has to be configured as non-anonymous room. In case that you want to host multiple lobby
rooms adding an ACL for MUC admins to which the bots are added, which is used for `access_admin`
in the `mod_muc` configuration would be advisable.

You need to have Python 3 and SleekXMPP (>=1.3.1) installed.

    $ sudo apt-get install python3 python3-sleekxmpp

If you would like to run the leaderboard database, you need to install SQLAlchemy:

    $ sudo apt-get install python3-sqlalchemy

Then execute the following command to setup the database.

    $ python3 LobbyRanking.py

### XpartaMuPP

Execute the following command to run the bot with default options:

    $ python3 XpartaMuPP.py

or rather a similar command to run a properly configured program:

    $ python3 XpartaMuPP.py --domain localhost --login wfgbot --password XXXXXX \
                            --nickname WFGbot --room arena

or if you want to run XpartaMuPP with the corresponding rating bot detailed in the next section:

    $ python3 XpartaMuPP.py --domain localhost --login wfgbot --password XXXXXX \
                            --nickname WFGbot --room arena --elo echelonBot

Run `python3 XpartaMuPP.py --help` for the full list of options

If everything is fine you should see something along these lines in your console

    INFO     Negotiating TLS
    INFO     Using SSL version: 3
    INFO     Node set to: wfgbot@lobby.wildfiregames.com/CC
    INFO     XpartaMuPP started

Congratulations, you are now running XpartaMuPP - the 0 A.D. Multiplayer Game Manager.

### EcheLOn

This bot can be thought of as a module of XpartaMuPP in that IQs stanzas sent to XpartaMuPP are
forwarded onto EcheLOn if its corresponding EcheLOn is online and ignored otherwise. This is by no
means necessary for the operation of a lobby in terms of creating/joining/listing games.

EcheLOn handles all aspects of operation related to ELO.

To run EcheLOn:

    ```
    $ python3 EcheLOn.py --domain localhost --login echelon --password XXXXXX \
                         --nickname Ratings --room arena
    ```

## Run tests

XpartaMuPP is partially covered by tests. To run the tests execute:

    $ ./setup.py test

If you also when to look into the test coverage, install `coverage` and execute:

    $ coverage setup.py test
    $ coverage html

Afterwards statistics about the code coverage are stored in the `htmlcov`-subdirectory.

### Vagrant

    ```
    $ sudo apt-get install vagrant
    $ VAGRANT_DISABLE_STRICT_DEPENDENCY_ENFORCEMENT=1 vagrant plugin install vagrant-docker-compose
    $ vagrant up
    ```

[1]: https://trac.wildfiregames.com/browser/ps/trunk/source/tools/XpartaMuPP
