Introduction
============

Some commands assume some apt-get based distribution. `lobby.wildfiregames.com` should be replaced
by your own domain name (or localhost) in all commands below.


Install ejabberd
================

* Install `ejabberd`:

    ```
    # apt-get install ejabberd
    ```

* Configure it, by setting the domain name (e.g. localhost if you installed it on your development
  computer) and add an admin user.:

    ```
    # dpkg-reconfigure ejabberd
    ```

You should now be able to connect to this XMPP server using a normal XMPP client.

Installation of the custom ejabberd module
======================================

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

Ejabberd configuration
======================

A web administration interface is available at http://localhost:5280/admin. Use the admin user
credentials (full JID (user@domain)) to log in. Changing settings there is also possible, but some
of those might not persist on restart.

The rest of this section should be done by editing `/etc/ejabberd/ejabberd.yml`.

* Allow users to create accounts using the game via in-band registration:

    access:
      register:
        all: allow

* Check list of registered users:

    ```
    $ ejabberdctl registered_users lobby.wildfiregames.com
    ```

* `XpartaMuPP` and `EcheLOn` need a user accountsto function, so create them using:

    ```
    $ ejabberdctl register echelon lobby.wildfiregames.com secure_password
    $ ejabberdctl register xpartamupp lobby.wildfiregames.com secure_password
    ```

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

Run XpartaMuPP - XMPP Multiplayer Game Manager
==============================================

You need to have python 3 and SleekXmpp installed (tested for 1.3.1, not compatible with 1.0-beta5).
You will most likely need to use pip to install 1.3.1, as it is not in most default repositories.

    $ sudo apt-get install python3

If you would like to run the leaderboard database,

    $ sudo apt-get install python3-sqlalchemy

Then execute the following command to setup the database.

    $ python3 LobbyRanking.py

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

Congratulations, you are running XpartaMuPP - the 0ad Multiplayer Game Manager.

Run EcheLOn - XMPP Rating Bot
=============================

This bot can be thought of as a module of XpartaMuPP in that IQs stanzas sent to XpartaMuPP are
forwarded onto EcheLOn if its corresponding EcheLOn is online and ignored otherwise. This is by no
means necessary for the operation of a lobby in terms of creating/joining/listing games.

EcheLOn handles all aspects of operation related to ELO.

To run EcheLOn:

    $ python3 EcheLOn.py --domain localhost --login echelon --password XXXXXX \
                         --nickname Ratings --room arena

Run tests
=========

XpartaMuPP is partially covered by tests. To run the tests execute:

    $ ./setup.py test

If you also when to look into the test coverage, install `coverage` and execute:

    $ coverage setup.py test
    $ coverage html

Afterwards statistics about the code coverage are stored in the `htmlcov`-subdirectory.

Vagrant
=======

    ```
    $ sudo apt-get install vagrant
    $ VAGRANT_DISABLE_STRICT_DEPENDENCY_ENFORCEMENT=1 vagrant plugin install vagrant-docker-compose
    $ vagrant up
    ```
