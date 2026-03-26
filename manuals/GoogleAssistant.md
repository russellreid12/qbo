# Install Google Assistant

In order to have Google Assistant on your QBO robot, it is necessary to carry out the following steps.

## Configure a Developer Project and Account Settings

To begin, follow the steps in the Google documentation where you must create a new Google Actions project.

[Click here to go to the documentation](https://developers.google.com/assistant/sdk/guides/library/python/embed/config-dev-project-and-account)

## Register the Device Model

Once the previous manual has been completed and have a project created and API enabled. It is necessary to follow the following manual to register QBO device.

[Click here to go to the documentation](https://developers.google.com/assistant/sdk/guides/library/python/embed/register-device)

Remember to follow the instructions for Raspberry Pi and copy the OAuth 2.0 file to "/home/pi" as indicated in the manual.

## Generate credentials

 1. Connect via SSH or VNC to the QBO robot and prepare the terminal to execute the following commands.

 2. Generate credentials to be able to run the Google Assistant in QBO. Reference the JSON file you downloaded in a previous step; you may need to copy it the device. Do not rename this file.

    ```bash
    sudo /opt/qbo/scripts/QBO_Installer.sh gassistant /home/pi/client_secret_client-id.json
    ```

    Warning: The file name may be different.
    
    You should see a URL displayed in the terminal:

    ```
    Please visit this URL to authorize this application: https://...
    ```

 3. Copy the URL and paste it into a browser (this can be done on any machine). The page will ask you to sign in to your Google account. Sign into the Google account that created the developer project in the previous step.

 4. After you approve the permission request from the API, a code will appear in your browser, such as "4/XXXX". Copy and paste this code into the terminal:

    ```
    Enter the authorization code:
    ```
    
    If authorization was successful, you will see a response similar to the following:
    
    ```
    credentials saved: /opt/qbo/.config/google-oauthlib-tool/credentials.json
    ```
    
    If instead you see InvalidGrantError, then an invalid code was entered. Try again, taking care to copy and paste the entire code.
    
## Set Project ID in Settings

Look in Google Actions Console the Project ID and set in QBO Settings:
```
http://qbo.local:8000/settings or http://qbo:8000/settings (Only Windows)
```
Set the Google Assistant mode and press Save and restart.

