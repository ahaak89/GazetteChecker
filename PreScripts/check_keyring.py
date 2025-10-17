import keyring
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

SERVICE_NAME = 'gazette-checker-service'

logging.info("Attempting to get password from keyring...")
try:
    password = keyring.get_password(SERVICE_NAME, 'smtp_password')
    if password:
        logging.info("SUCCESS: Keyring call completed and retrieved a password.")
    else:
        logging.info("FAILURE: Keyring call completed, but no password was found.")
except Exception as e:
    logging.error(f"FAILURE: Keyring call failed with an exception: {e}")

logging.info("Test script finished.")