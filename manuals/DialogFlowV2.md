# Setup DialogFlow V2

## Download Credentials

If you want to use DialogFlowV2, follow this steps:

1.- Go to  https://cloud.google.com/docs/authentication/production

2.- Click on "Go to the create service account key page" 

3.- Make sure that you've selected your DialogFlow project (Next to Google Cloud Platform), then, select “Dialogflow" and download the json file.

4.- Once you hace the json downloaded, upload the file to `/opt/qbo/.config/dialogflowv2.json`, (You can use FileZilla with SCP connection to do this or executing the scp command if you have ssh active in your raspberry pi).

## Configure QBO

5.- Go to http://qbo.local:8000/settings and add in the "DialogFlow V2 Project ID:" your Project ID from DialogFlow (you can get it from: https://console.cloud.google.com/home/dashboard, in "Project Information").

6.- Click Save and Restart and you are done!