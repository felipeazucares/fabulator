import datetime
from colorama import Fore, Style
import colorama


class TextColours:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class ConsoleDisplay:
    def __init__(self):
        # Initialise colorama if we're on Windows
        colorama.init()

    def __format_message(self, message_to_show, message_type):
        """format the message provided depending on message_type parameter """
        self.text_colours = TextColours
        self.__message_type = message_type
        self.__message_to_show = message_to_show
        self._dt_date = datetime.datetime.now().strftime('%d/%m/%y %I:%M %S %p')
        if self.__message_type == 1:
            self.__message_to_show = f"{Fore.GREEN}{Style.BRIGHT}|{self._dt_date} : {self.__message_to_show} |{Style.RESET_ALL}"
            self.__message_padding = Fore.GREEN + "-" * \
                (len(self.__message_to_show)-9) + Style.RESET_ALL
        elif self.__message_type == 2:
            self.__message_to_show = f"{Fore.CYAN}{Style.BRIGHT}|{self._dt_date} : DEBUG :{self.__message_to_show} |{Style.RESET_ALL}"
            self.__message_padding = Fore.CYAN + "-" * \
                (len(self.__message_to_show)-9) + Style.RESET_ALL
        elif self.__message_type == 3:
            self.__message_to_show = f"{Fore.RED}{Style.BRIGHT}|{self._dt_date} : EXCEPTION :{self.__message_to_show} |{Style.RESET_ALL}"
            self.__message_padding = Fore.RED + "-" * \
                (len(self.__message_to_show)-9) + Style.RESET_ALL
        print(self.__message_padding)
        print(self.__message_to_show)
        print(self.__message_padding)

    def show_message(self, message_to_show: str = None):
        """ Format & output standard message along with timestamp"""
        self.__message_to_show = message_to_show
        self.__format_message(
            message_to_show=self.__message_to_show, message_type=1)

    def show_debug_message(self, message_to_show):
        self.__message_to_show = message_to_show
        """ Format & output debug message along with timestamp"""
        self.__message_to_show = message_to_show
        self.__format_message(
            message_to_show=self.__message_to_show, message_type=2)

    def show_exception_message(self, message_to_show: str = None):
        """ Format & output exception message along with timestamp"""
        self.__message_to_show = message_to_show
        self.__format_message(
            message_to_show=self.__message_to_show, message_type=3)
