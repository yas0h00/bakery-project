import os
from dotenv import load_dotenv

load_dotenv()

email = os.getenv("MAIL_USERNAME")
print(email)