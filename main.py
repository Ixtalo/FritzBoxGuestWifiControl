#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""FastAPI Web-App to control the Fritz!Box guest WiFi, i.e., turn it on/off."""
import sys
import os
import logging
from time import sleep
import fritzconnection  # https://github.com/kbr/fritzconnection
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

__version__ = "1.3.3"
__date__ = "2021-11-27"
__updated__ = "2022-10-16"
__author__ = "Ixtalo"
__license__ = "AGPL-3.0+"
__email__ = "ixtalo@gmail.com"
__status__ = "Production"

FRITZBOX_GUESTWIFI_ENABLED = "Up"

# check for Python3
if sys.version_info < (3, 0):
    sys.stderr.write("Minimum required version is Python 3.x!\n")
    sys.exit(1)

# load configuration environment variables from .env file
load_dotenv()
assert os.getenv("FRITZBOX_ADDRESS")
assert os.getenv("FRITZBOX_USER")
assert os.getenv("FRITZBOX_PASS")


class FritzBoxGuestWiFiControl:
    """FritzBox Control of the guest WiFi."""

    def __init__(self, connection: fritzconnection.FritzConnection):
        """Control the FritzBox guest WiFi.

        :param connection: a valid FritzBox connection object.
        """
        self.fritzbox = connection

    def get_info(self):
        """Get general information on the FritzBox."""
        return {
            "fritzbox": {
                "version": self.fritzbox.system_version,
                "model": self.fritzbox.modelname,
                "guestwifi": {
                    "enabled": self.__get_guestwifi_status(),
                    "ssid": self.__guestwifi_action("GetSSID").get("NewSSID"),
                    "stats": self.__guestwifi_action("GetStatistics")
                }
            }
        }

    def get_guestwifi_status(self):
        """Get the guest WiFi status (on/off)."""
        return {"enabled": self.__get_guestwifi_status()}

    def set_guestwifi_status(self, enable: bool):
        """Set the status of the FritzBox' guest WiFi (on/off)."""
        status = self.__get_guestwifi_status()
        logging.debug("response: %s", status)
        if enable:
            # check if already enabled
            if status == FRITZBOX_GUESTWIFI_ENABLED:
                logging.info("already up - nothing to do")
                return {"enabled": status}
        else:
            # check if already disabled
            if status != FRITZBOX_GUESTWIFI_ENABLED:
                logging.info("already disabled - nothing to do")
                return {"enabled": status}

        # set new status
        self.__guestwifi_action("SetEnable", {'NewEnable': enable})
        logging.info("wait 5 seconds for status change...")
        sleep(5)  # needs >3 seconds for status change
        return self.get_guestwifi_status()

    def __get_guestwifi_status(self):
        return self.__guestwifi_action("GetInfo").get("NewStatus")

    def __guestwifi_action(self, action_name, arguments=None):
        if arguments is None:
            arguments = {}
        try:
            return self.fritzbox.call_action('WLANConfiguration3', action_name, arguments=arguments)
        except fritzconnection.core.exceptions.FritzConnectionException as ex:
            logging.exception(ex)
            return {"error": str(ex)}

    def close(self):
        """Close the FritzBox connection."""
        del self.fritzbox


def setup_fritzbox_connection():
    """Establish a connection to the FritzBox."""
    connection = fritzconnection.FritzConnection(
        address=os.getenv("FRITZBOX_ADDRESS"),
        user=os.getenv("FRITZBOX_USER"),
        password=os.getenv("FRITZBOX_PASS")
    )
    return FritzBoxGuestWiFiControl(connection)


# ----------------------------------------------------------------------------
# Main

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)-15s - %(levelname)-7s - %(message)s")
logging.getLogger("fritzconnection").setLevel(logging.WARNING)

# initial connection check
logging.info("Checking FritzBox connection (%s with user %s) ...",
             os.getenv("FRITZBOX_ADDRESS"), os.getenv("FRITZBOX_USER"))
fritz_connection = fritzconnection.FritzConnection(
    address=os.getenv("FRITZBOX_ADDRESS"),
    user=os.getenv("FRITZBOX_USER"),
    password=os.getenv("FRITZBOX_PASS")
)
# check connection
logging.info("FritzBox version: %s", fritz_connection.system_version)
assert fritz_connection.system_version
del fritz_connection  # ... close connection (reopened later, on demand)

# ----------------------------------------------------------------------------
# FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    """Main/home page."""
    fritzbox = setup_fritzbox_connection()
    status = fritzbox.get_guestwifi_status()
    fritzbox.close()
    context = {
        "request": request,
        "guestwifi_enabled": status.get("enabled") == FRITZBOX_GUESTWIFI_ENABLED,
        "header_message": os.getenv("HEADER_MESSAGE", ""),
        "version": __version__,
        "updated": __updated__
    }
    return templates.TemplateResponse("index.html", context)


@app.get("/guestwifi")
def guestwifi():
    """Get FritzBox information, e.g., the status of the guest WiFi."""
    fritzbox = setup_fritzbox_connection()
    res = fritzbox.get_info()
    fritzbox.close()
    return res


@app.get("/guestwifi/enable")
def guestwifi_enable():
    """Enable the guest WiFi."""
    fritzbox = setup_fritzbox_connection()
    fritzbox.set_guestwifi_status(1)
    fritzbox.close()
    return RedirectResponse(url=os.getenv("BASE_URL", "/"))


@app.get("/guestwifi/disable")
def guestwifi_disable():
    """Disable the guest WiFi."""
    fritzbox = setup_fritzbox_connection()
    fritzbox.set_guestwifi_status(0)
    fritzbox.close()
    return RedirectResponse(url=os.getenv("BASE_URL", "/"))


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=5000, log_level="info", reload=True)
