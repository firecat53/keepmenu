""" TOTP generation

"""
import base64
import hmac
import struct
import time
from urllib import parse


def hotp(key, counter, digits=6, digest='sha1', steam=False):
    """ Generates HMAC OTP.  Taken from https://github.com/susam/mintotp

    Args: key - Secret key
          counter - Moving factor
          digits - The number of characters/digits that the otp should have
          digest - Algorithm to use to generate the otp
          steam - whether or not to use steam settings

    Returns: otp

    """
    key = base64.b32decode(key.upper() + '=' * ((8 - len(key)) % 8))
    counter = struct.pack('>Q', counter)
    mac = hmac.new(key, counter, digest).digest()
    offset = mac[-1] & 0x0f
    binary = struct.unpack('>L', mac[offset:offset + 4])[0] & 0x7fffffff
    code = ''

    if steam:
        chars = '23456789BCDFGHJKMNPQRTVWXY'
        full_code = int(binary)
        for _ in range(digits):
            code += chars[full_code % len(chars)]
            full_code //= len(chars)
    else:
        code = str(binary)[-digits:].rjust(digits, '0')

    return code


def totp(key, time_step=30, digits=6, digest='sha1', steam=False):
    """ Generates Time Based OTP

    Args: key - Secret key
          counter - The length of time in seconds each otp is valid for
          digits - The number of characters/digits that the otp should have
          digest - Algorithm to use to generate the otp
          steam - whether or not to use steam settings

    Returns: otp

    """
    return hotp(key, int(time.time() / time_step), digits, digest, steam)


def gen_otp(otp_url):
    """ Generates one time password

    Args: otp_url - KeePassXC url encoding with information on how to generate otp
    Returns: otp

    """
    parsed_otp_url = parse.urlparse(otp_url)
    query_string = parse.parse_qs(parsed_otp_url.query)

    for required in ('secret', 'period', 'digits'):
        if required not in query_string:
            return ''

    try:
        steam = query_string['encoder'][0] == "steam"
    except KeyError:
        steam = False

    return totp(
        query_string['secret'][0], int(query_string['period'][0]),
        int(query_string['digits'][0]), 'sha1' if 'algorihm'
        not in query_string else query_string['algorithm'][0].lower(), steam)
