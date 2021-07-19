from logging import NOTSET
from dotenv import load_dotenv

# load contents of .env variables file
load_dotenv()
logfile_name = "fab.log"
logfile_level = NOTSET
# Now the variables in the .env file can be access as though they are os variables
