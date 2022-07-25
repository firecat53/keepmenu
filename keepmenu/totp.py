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
          time_step - The length of time in seconds each otp is valid for
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
    if parsed_otp_url.scheme == "otpauth":
        query_string = parse.parse_qs(parsed_otp_url.query)
    else:
        query_string = parse.parse_qs(otp_url)
    params = {}

    if 'secret' in query_string:
        params['key'] = query_string['secret'][0]
        try:
            params['time_step'] = int(query_string['periods'][0])
        except KeyError:
            pass
        try:
            params['digits'] = int(query_string['digits'][0])
        except KeyError:
            pass
        try:
            params['digest'] = query_string['algorithm'][0].lower()
        except KeyError:
            pass
        try:
            params["steam"] = query_string['encoder'][0] == "steam"
        except KeyError:
            pass
    # support keeotp format
    elif 'key' in query_string:
        params['key'] = query_string['key'][0]
        try:
            params['time_step'] = int(query_string['step'][0])
        except KeyError:
            pass
        try:
            params['digits'] = int(query_string['size'][0])
        except KeyError:
            pass
        try:
            params['digest'] = query_string['otpHashMode'][0].lower()
        except KeyError:
            pass
    else:
        return ''

    return totp(**params)


def get_otp_url(kp_entry):
    """ Shim to return otp url from KeePass entry
    This is required to fully support pykeepass>=4.0.0
    "otp" was upgraded to a reserved property in pykeepass==4.0.3

    Args: kp_entry - KeePassXC entry
    Returns: otp url string or None

    """
    otp = ""
    if hasattr(kp_entry, "otp"):
        otp = kp_entry.deref("otp")
    else:
        otp = kp_entry.get_custom_property("otp")
    if otp:
        return otp

    # Support some TOTP schemes that use custom properties "TOTP Seed" and "TOTP Settings"
    seed = kp_entry.get_custom_property("TOTP Seed")
    digits, period = (6, 30)
    settings = kp_entry.get_custom_property("TOTP Settings") or ""
    try:
        period, digits = settings.split(";")
    except ValueError:
        pass
    if seed:
        return f"otpauth://totp/Entry?secret={seed}&period={period}&digits={digits}"

    # TODO: Support keepass2's default TOTP properties

    return ""
