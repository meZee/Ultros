"""
Authorization handler. This is in charge of logins and accounts.

If this is one of the authorization handlers being used, you can get access
to its instance from the command manager. In all other cases, you'll have to
get an instance of the Auth plugin and get the instance from there.

This class is in charge of managing user accounts - logins and passwords. It
also includes a rudimentary password blacklist system.

If you want to write your own auth handler, be sure to implement all the
documented methods.
"""

__author__ = 'Gareth Coles'

# Required: authorized(caller, source, protocol)

from utils.password import mkpasswd
import hashlib

from system.translations import Translations
_ = Translations().get()


class authHandler(object):
    """
    Authorization handler class
    """

    def __init__(self, plugin, data, blacklist):
        """
        Initialise the auth handler.

        This will also create a default account and default password
        blacklist if one doesn't already exist.
        """

        self.data = data
        self.blacklist = blacklist
        self.plugin = plugin

        self.create_superadmin_account()
        self.create_blacklisted_passwords()

    def create_blacklisted_passwords(self):
        """
        Create the default password blacklist, if one doesn't exist already.

        This blacklist contains the top 20 most popular passwords of 2013 by
        default, and will prevent them for being used to register. They are
        as follows.

        "password", "123456", "12345678", "1234", "qwerty", "12345", "dragon",
        "pussy", "baseball", "football", "letmein", "monkey", "696969",
        "abc123", "mustang", "michael", "shadow", "master", "jennifer",
        "111111"
        """
        if not len(self.blacklist):
            # Top 20 passwords of 2013
            passwords = ["password", "123456", "12345678", "1234", "qwerty",
                         "12345", "dragon", "pussy", "baseball", "football",
                         "letmein", "monkey", "696969", "abc123", "mustang",
                         "michael", "shadow", "master", "jennifer", "111111"]

            with self.blacklist:
                self.blacklist["all"] = passwords
                self.blacklist["users"] = {}
                self.plugin.logger.info(_("Created password blacklist with "
                                          "the 20 most popular passwords of "
                                          "2013."))

    def create_superadmin_account(self):
        """
        Creates the default superadmin account, if no accounts exist.

        If the superadmin setting is enabled, this account will have access
        to all available permissions. It's given a 32-length randomly
        generated password. We test for uniqueness in the unit tests!
        """

        if len(self.data):
            if _("superadmin") in self.data:
                self.plugin.logger.warn(_("Superadmin account exists!"))
                self.plugin.logger.warn(_("You should remove this account "
                                          "as soon as possible!"))
            return
        self.plugin.logger.info(_("Generating a default auth account and "
                                  "password."))
        self.plugin.logger.info(_("You will need to either use this to add "
                                  "permissions to your user account, or just "
                                  "create an account and edit the permissions "
                                  "file."))
        self.plugin.logger.info(_("Remember to delete this account when "
                                  "you've created your own admin account!"))

        password = mkpasswd(32, 11, 11, 10)

        self.create_user(_("superadmin"), password)

        self.plugin.logger.info("============================================")
        self.plugin.logger.info(_("Super admin username: superadmin"))
        self.plugin.logger.info(_("Super admin password: %s") % password)
        self.plugin.logger.info("============================================")

        p_handler = self.plugin.get_permissions_handler()

        if p_handler:
            if not p_handler.create_user(_("superadmin")):
                self.plugin.logger.warn(_("Unable to create permissions "
                                          "section for the superadmin "
                                          "account!"))
            if not p_handler.set_user_option(_("superadmin"),
                                             _("superadmin"),
                                             True):
                self.plugin.logger.warn(_("Unable to set 'superadmin' flag on "
                                          "the superadmin account!"))
        else:
            self.plugin.logger.warn(_("Unable to set permissions for the "
                                      "superadmin account as the bundled "
                                      "permissions system isn't being used."))
            self.plugin.logger.warn(_("Please do this manually!"))

    def hash(self, salt, password):
        """
        Returns the hash for a given password and salt.

        :param salt: The salt to use in the hash
        :param password: The password itself

        :type salt: str
        :type password: str

        :return: The hashed salt and password
        :rtype: str
        """

        return hashlib.sha512(salt + password).hexdigest()

    def reload(self):
        """
        Performs a dumb reload of the data file.
        """

        self.data.reload()

    def check_login(self, username, password):
        """
        Check whether a password is the valid login for a user.

        :param username: The username to check against
        :param password: The attempted password

        :type username: str
        :type password: str

        :return: Whether the password was correct
        :rtype: bool
        """

        username = username.lower()
        with self.data:
            if username not in self.data:
                return False
            user_data = self.data[username]
        calculated = self.hash(user_data["salt"], password)
        real_hash = user_data["password"]

        if calculated == real_hash:
            return True
        return False

    def create_user(self, username, password):
        """
        Create a new user account with a given username and password.

        The salt will be generated randomly, at a length of 64. Creation will
        fail if the user account already exists.

        :param username: The username of the account
        :param password: The password to be used

        :type username: str
        :type password: str

        :return: Whether the account was created successfully
        :rtype: bool
        """

        username = username.lower()

        with self.data:
            if username in self.data:
                return False

            salt = mkpasswd(64, 21, 22, 21)
            hashed = self.hash(salt, password)

            self.data[username] = {
                "password": hashed,
                "salt": salt
            }

        return True

    def change_password(self, username, old, new):
        """
        Change a user's password.

        This function requires the user's old password, and will fail if the
        user's account doesn't exist or the old password doesn't match.

        A new salt will also be generated.

        :param username: The username of the account
        :param old: The old password to check
        :param new: The new password to change to

        :type username: str
        :type old: str
        :type new: str

        :return: Whether the password was changed
        :rtype: bool
        """

        username = username.lower()
        with self.data:
            if username not in self.data:
                return False
            user_data = self.data[username]
            calculated = self.hash(user_data["salt"], old)
            real_hash = user_data["password"]
            if calculated != real_hash:
                return False

            salt = mkpasswd(64, 21, 22, 21)
            hashed = self.hash(salt, new)

            self.data[username]["password"] = hashed
            self.data[username]["salt"] = salt
        return True

    def delete_user(self, username):
        """
        Delete a user's account.

        This will fail if the user account doesn't exist.

        :param username: The username of the account to remove
        :type username: str

        :return: Whether the account was removed
        :rtype: bool
        """

        username = username.lower()
        with self.data:
            if username in self.data:
                del self.data[username]
                return True
        return False

    def login(self, user, protocol, username, password):
        """
        Log a user in.

        This requires a user and protocol object, as well as their username
        and password. The user and username are not the same thing!

        :param user: The User object of the person trying to log in
        :param protocol: The Protocol object relating to the User
        :param username: The username of the account that's being tried
        :param password: The password of the account

        :type user: User
        :type protocol: Protocol
        :type username: str
        :type password: str

        :return: Whether the user was logged in successfully.
        :rtype: bool
        """

        username = username.lower()
        with self.data:
            if username not in self.data:
                return False
            user_data = self.data[username]
        calculated = self.hash(user_data["salt"], password)
        real_hash = user_data["password"]

        if calculated == real_hash:
            user.authorized = True
            user.auth_name = username
            return True
        return False

    def logout(self, user, protocol):
        """
        Log a logged-in user out.

        This will fail if the user isn't logged in.

        :param user: The User to log out
        :param protocol: The Protocol object relating to the User

        :type user: User
        :type protocol: Protocol

        :return: Whether the user was logged out successfully
        :rtype: bool
        """

        if user.authorized:
            user.authorized = False
            del user.auth_name
            return True
        return False

    def authorized(self, caller, source, protocol):
        """
        Check whether a User has logged in.

        :param caller: The User to check against
        :param source: The User or Channel relating to the request
        :param protocol: The Protocol relating to the User

        :type caller: User
        :type source: User, Channel
        :type protocol: Protocol

        :return: Whether the user is logged in
        :rtype bool:
        """

        return caller.authorized

    def user_exists(self, username):
        """
        Check whether an account exists.

        :param username: The username to check
        :type username: str

        :return: Whether an account for the specified username exists
        :rtype: bool
        """

        username = username.lower()
        return username in self.data

    def blacklist_password(self, password, username=None):
        """
        Add a password to the blacklist, optionally only for a specific
        username.

        This will fail if the password already exists in the relevant
        blacklist.

        :param password: The password to blacklist
        :param username: Optionally, the username to blacklist it for

        :type password: str
        :type username: str, None

        :return: Whether the password was added to the blacklist
        :rtype: bool
        """

        with self.blacklist:
            password = password.lower()
            if username is None:
                if password not in self.blacklist["all"]:
                    self.blacklist["all"].append(password)
                    return True
                return False
            username = username.lower()
            if username not in self.blacklist["users"]:
                self.blacklist["users"][username] = [password]
                return True
            else:
                if password in self.blacklist["users"][username]:
                    return False
            self.blacklist["users"][username].append(password)
            return True

    def password_backlisted(self, password, username=None):
        """
        Check whether a password has been blacklisted, optionally only for
        a specific username.

        :param password: The password to check against
        :param username: Optionally, the username to check against

        :type username: str
        :type password: str

        :return: Whether the password is blacklisted
        :rtype: bool
        """

        password = password.lower()
        if password in self.blacklist["all"]:
            return True
        if username is None:
            return False
        username = username.lower()
        if username in self.blacklist["users"]:
            return password in self.blacklist["users"][username]
        return False
