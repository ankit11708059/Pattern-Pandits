import requests
import pprint


pprint.pprint(requests.get("https://gist.githubusercontent.com/ankitslice/3a0a82c3d55cf4e74882638d2c3e7d4e/raw/872d678faf84a66c73d2ad9e105701af09972e6e/gistfile1.json").json())