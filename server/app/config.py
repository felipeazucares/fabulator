from logging import NOTSET
from dotenv import load_dotenv


# load contents of .env variables file
logfile_name = "fab.log"
logfile_level = NOTSET
load_dotenv()
# Now the variables in the .env file can be access as though they are os variables
