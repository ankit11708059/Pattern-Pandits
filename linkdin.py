import os
import requests

from dotenv import load_dotenv

load_dotenv()


def scrape_linkedin_profile():
    """
    Scrape information from linkedin profile , manually scarape information from
    linkedin profile
    """
    linkdine_profile_url = "https://gist.githubusercontent.com/ankitslice/3a0a82c3d55cf4e74882638d2c3e7d4e/raw/872d678faf84a66c73d2ad9e105701af09972e6e/gistfile1.json"
    response = requests.get(linkdine_profile_url,timeout=10)

    data = response.json().get("person")
    return data


if __name__== "__main__":
    print(scrape_linkedin_profile())


