#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Found here: http://stackoverflow.com/a/15074754

"""
This is a convenience function for generating random passwords.
You can also run this file directly if you want a 32-length password.
"""

import string
from time import time
from itertools import chain
from random import seed, choice, sample


def mkpasswd(length=8, digits=2, upper=2, lower=2):
    """
    Create a random password

    Create a random password with the specified length and no. of
    digit, upper and lower case letters.

    :param length: Maximum no. of characters in the password
    :type length: int

    :param digits: Minimum no. of digits in the password
    :type digits: int

    :param upper: Minimum no. of upper case letters in the password
    :type upper: int

    :param lower: Minimum no. of lower case letters in the password
    :type lower: int

    :returns: A random password with the above constraints
    :rtype: str
    """

    seed(time())

    lowercase = string.lowercase.translate(None, "o")
    uppercase = string.uppercase.translate(None, "O")
    letters = "{0:s}{1:s}".format(lowercase, uppercase)

    password = list(
        chain(
            (choice(uppercase) for _ in range(upper)),
            (choice(lowercase) for _ in range(lower)),
            (choice(string.digits) for _ in range(digits)),
            (choice(letters) for _ in range((length - digits - upper - lower)))
        )
    )

    return "".join(sample(password, len(password)))

if __name__ == "__main__":
    pword = mkpasswd(32, 11, 11, 10)
    print "Random password: %s" % pword
