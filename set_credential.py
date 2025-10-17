import keyring
import sys
import getpass

# --- THIS IS A TEMPORARY, SINGLE-USE SCRIPT ---

# This service name must EXACTLY match the one in your main gazette_checker.py script
SERVICE_NAME = 'gazette-checker-service'
USERNAME_KEY = 'smtp_password' # This is just a key, not your actual username

# 1. PASTE YOUR PLAIN-TEXT PASSWORD BETWEEN THE QUOTES
# For security, we'll use a prompt. If this fails in psexec,
# replace the line below with: SMTP_PASSWORD_PLAINTEXT = "YourActualPassword"
try:
    SMTP_PASSWORD_PLAINTEXT = getpass.getpass(f"Enter SMTP password for '{SERVICE_NAME}': ")
except Exception:
    print("Could not use password prompt. You may need to hardcode the password in the script for the psexec step.")
    sys.exit(1)


# Safety check to make sure a password was entered
if not SMTP_PASSWORD_PLAINTEXT:
    print("ERROR: No password was provided.")
    sys.exit(1)

try:
    # 2. Store the password in the system's credential store
    keyring.set_password(SERVICE_NAME, USERNAME_KEY, SMTP_PASSWORD_PLAINTEXT)
    print(f"\nSUCCESS: Password for '{SERVICE_NAME}' was set in the system credential store.")
    print("You can now DELETE THIS SCRIPT FILE.")
    
except Exception as e:
    print(f"\nAn error occurred: {e}")