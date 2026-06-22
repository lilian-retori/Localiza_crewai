from colorama import Fore, Style, init

init(autoreset=True)

def info(message: str):
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}")

def success(message: str):
    print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} {message}")

def warning(message: str):
    print(f"{Fore.YELLOW}[AVISO]{Style.RESET_ALL} {message}")

def error(message: str):
    print(f"{Fore.RED}[ERRO]{Style.RESET_ALL} {message}")

def step(message: str):
    print(f"{Fore.MAGENTA}[PASSO]{Style.RESET_ALL} {message}")
