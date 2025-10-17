Victoria Gazette Checker
| I. Overview |
This Python script automates the process of monitoring the Victoria Government Gazette website for new publications. It downloads new gazette PDFs, scans their text for a predefined list of keywords, and sends an HTML-formatted email alert if any matches are found.

The script is designed to be run as an automated, scheduled task on a Windows server, using the system's native credential manager for secure password storage.

| II. Metadata |
Author: Anthony Haak / IT Manager

Date: August 11, 2025

Version: 1.0

Contact: ahaak89@gmail.com

| III. Setup |
The following one-time setup is required on the server where the script will run.

1. Install Python
If not already installed, download and install the latest version of Python from python.org. During installation, it is critical to check the box labeled "Add python.exe to PATH".

2. Install Required Libraries
The script depends on several third-party libraries. Install them all with a single command.
a. Create a file named requirements.txt in the same directory as the script with the following content:
requests beautifulsoup4 PyMuPDF keyring pywin32
b. Open a Command Prompt and run:
cmd pip install -r requirements.txt t

3. Set the SMTP Password Securely
The script uses the Windows Credential Manager to avoid storing the password in plain text
