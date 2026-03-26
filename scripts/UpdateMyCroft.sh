#! /bin/bash

# What does this script do?

### This Script will check if MyCroft need to be updated, if so, it will update trough crontab
### 0 15 * * * bash /opt/qbo/scripts/UpdateMyCroft

launchOutput=`bash /opt/qbo/mycroft-core/start-mycroft.sh | head -n1`

### Comment this out if you want to trigger manually the update (suitable for testing).
# launchOutput="Please update dependencies by running ./dev_setup.sh again."

textToTriggerUpdate="Please update dependencies by running ./dev_setup.sh again."

detectMyCroft=`cat /opt/qbo/config.yml | grep -o "interactive-mycroft"`

if [ ! -z $detectMyCroft ]
then
    if [ "$launchOutput" = "$textToTriggerUpdate" ]
    then
        echo "Starting Update..."
        sudo -u qbo /opt/qbo/Speak.py custom "I've found an update for MyCroft and I'll begin to update it, I'll talk again then it finish, in the mainwhile, MyCroft will be unavailable"
        # Getting new files
        cd /opt/qbo/mycroft-core/
        /usr/bin/git stash
        /usr/bin/git pull origin master
        /usr/bin/git stash pop
        # Updating MyCroft
        ./update_dev.sh
        # Update complete
        sudo -u qbo /opt/qbo/Speak.py custom "Update complete, wait until I restart."
        sudo reboot

    else
        echo "MyCroft is up to date."
    fi
fi