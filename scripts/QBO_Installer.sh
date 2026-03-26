#!/bin/bash

## QBO Installer v1.1


# Parameters

REPO_QBO="https://gitlab.com/thecorpora/QBO.git"
REPO_RPI_I2S_AUDIO="https://github.com/PaulCreaser/rpi-i2s-audio.git"
REPO_SNOWBOY="https://github.com/Kitt-AI/snowboy"

# Functions

function INSTALL_OR_UPDATE_DEPENDENCIES {

    # Removing rpi-update
    apt-get remove rpi-update -y

    # Update packages
    apt-get update
    apt-get upgrade -y

    # Install apt dependencies
    apt-get install raspberrypi-kernel-headers git python-pip python-pil python-opencv python-numpy python-pigpio python-zbar python-urllib3 python-serial python-simplejson python-pyasn1-modules python-yaml alsa-base esound-common libttspico-utils portaudio19-dev flac espeak libwebsockets-dev winbind libnss-winbind samba libffi-dev libssl-dev libmpg123-dev swig swig3.0 sox python-pyaudio libatlas-base-dev ffmpeg libhdf5-serial-dev hdf5-tools -y

    # Install python dependencies
    /usr/bin/pip install apiai argparse google-assistant-grpc google-assistant-library google-assistant-sdk google-oauth SpeechRecognition PyAudio Django djangorestframework pyyaml pyOpenSSL pyasn1 watson-developer-cloud youtube-dl dialogflow
    /usr/bin/pip install -U pyasn1
    /usr/bin/pip install --no-cache-dir tensorflow

    # Remove old packages
    apt-get autoclean -y
    apt-get autoremove --purge -y
    apt-get clean all -y

    # Check if kernel changed
    if [ ! -d "/lib/modules/$(uname -r)" ]
    then
        # Show Warning
        printf "\n**WARNING**\nThe kernel has changed after updating the system.\nPlease, reboot the system and re-run the install/update script.\n"
        
        # Wait to user confirmation
        read -n 1 -s -r -p "Press any key to reboot"

        # Reboot & exit
        reboot
        exit 1
    fi

    # Avoid future kernel updates
    apt-mark hold raspberrypi-kernel raspberrypi-kernel-headers

}

function INSTALL_I2S_AUDIO_KERNEL_MODULE {

    # Download source code for i2s-audio
    mkdir /tmp/rpi-i2s-audio
    /usr/bin/git clone ${REPO_RPI_I2S_AUDIO} /tmp/rpi-i2s-audio

    # Set source libraries for make, setting Makefile
    echo "KDIR := /lib/modules/$(uname -r)/build" >> /tmp/rpi-i2s-audio/Makefile
    echo "PWD := /tmp/rpi-i2s-audio" >> /tmp/rpi-i2s-audio/Makefile
    printf "\nall:\n\t\$(MAKE) -C \$(KDIR) M=\$(PWD) modules\n" >> /tmp/rpi-i2s-audio/Makefile
    printf "\nclean:\n\t\$(MAKE) -C \$(KDIR) M=\$(PWD) clean\n" >> /tmp/rpi-i2s-audio/Makefile
    printf "\ninstall:\n\t\$(MAKE) -C \$(KDIR) M=\$(PWD) modules modules_install\n" >> /tmp/rpi-i2s-audio/Makefile

    # Compile, Install & Clean
    make all --directory=/tmp/rpi-i2s-audio
    make install  --directory=/tmp/rpi-i2s-audio
    make clean  --directory=/tmp/rpi-i2s-audio

    # Remove sources
    rm -Rf /tmp/rpi-i2s-audio

    # Enable rpi-i2s-audio
    depmod -ae
    if [ -z `cat /etc/modules | grep my_loader` ]
    then
        echo "my_loader" >> /etc/modules
    fi
    modprobe my_loader

}

function INSTALL_SNOWBOY {

    # Remove if exist & Install Snowboy library
    rm -f /opt/qbo/snowboy
    rm -Rf /opt/snowboy
    /usr/bin/git clone ${REPO_SNOWBOY} /opt/snowboy

    # Install library
    python2 /opt/snowboy/setup.py install

    # Make libraries
    make all --directory=/opt/snowboy/swig/Python

    # Create link
    sudo -u qbo ln -s /opt/snowboy/examples/Python /opt/qbo/snowboy

}

function INSTALL {

    # Clean screen
    clear

    # Presentation
    printf "\n ** QBO Installer **\n\nThis software will update the Raspbian, install the dependencies\nand install the QBO Software. Once the installation is complete,\nthe system will reboot and the QBO Software will be ready.\n\nNOTICE: It is recommended to perform this installation\non a clean Raspbian Stretch image.\n\n"    read -n 1 -s -r -p "Press any key to continue"
    clear

    # Additional Screen if install from development repositories
    if [ ${REPO_QBO_BRANCH} == "develop" ]
    then
        printf "\n ** QBO Installer **\n\n**WARNING**\nAre you sure you want to install from the development repositories?\nThe development version is unstable and may contain critical errors.\n\n"
        read -n 1 -s -r -p "Press any key to continue or Ctrl+C to cancel"
        clear
    fi

    # Setting default value for DISTRO
    DISTRO='undefined'

    # Presentation
    printf "\n ** QBO Installer **\n\nSelect the distribution of QBO Software to install:\n\n\t[1] Standalone: Main version. It works with Google services.\n\t[2] IBM Watson: This distribution only works with IBM Watson services.\n\n\n"

    # Ask distribution
    while [ ${DISTRO} != 'standalone' ] && [ ${DISTRO} != 'ibmwatson' ]
    do
        read -r -p "Enter number of distribution and press enter: " DISTRONUM
        case "$DISTRONUM" in
            1)
                DISTRO='standalone'
            ;;
            2)
                DISTRO='ibmwatson'
            ;;
            *)
                printf "\n **WARNING** The entered value is wrong.\n\n"
        esac
    done

    # Installing dependencies
    printf "Installing dependencies...\n"
    INSTALL_OR_UPDATE_DEPENDENCIES

    # Show action info
    printf "Enabling i2c-dev & bcm2835 modules...\n"

    # Load modules required by qbo
    echo "i2c-dev" >> /etc/modules
    echo "snd-bcm2835" >> /etc/modules
    modprobe i2c-dev
    modprobe snd-bcm2835

    # Show action info
    printf "Settings hdmi config...\n"

    # Settings hdmi & i2s config
    sed -i 's/#hdmi_force_hotplug=1/hdmi_force_hotplug=1/g' /boot/config.txt
    sed -i 's/#hdmi_group=1/hdmi_group=2/g' /boot/config.txt
    sed -i 's/#hdmi_mode=1/hdmi_mode=82/g' /boot/config.txt

    # Show action info
    printf "Enabling i2s-audio module...\n"

    # Enable i2s audio
    sed -i 's/#dtparam=i2s=on/dtparam=i2s=on/g' /boot/config.txt
    printf "\n# Enable i2s-mmap audio\ndtoverlay=i2s-mmap\n" >> /boot/config.txt

    # Installing i2s-audio kernel module
    printf "Installing i2s-audio kernel module...\n"
    INSTALL_I2S_AUDIO_KERNEL_MODULE

    # Show action info
    printf "Setting asound.conf...\n"

    # Setting asound config
    echo "
pcm.!default {
    pcm \"hw:1,0\"    
}

pcm.dmicQBO {
    type hw
    card sndrpisimplecar
    channels 2
    rate 16000
    format S16_LE
}

pcm.dmicQBO_sv {
    type softvol
    slave.pcm dmicQBO
    control {
        name \"Boost Capture Volume\"
        card sndrpisimplecar
    }
    min_dB -10.0
    max_dB 30.0
}

pcm_slave.sl1 {
    pcm \"hw:1,0\"
    channels 2
    rate 16000
    format S16_LE
}

pcm.convertQBO {
    type plug
    slave sl1
}
" > /etc/asound.conf

    # Show action info
    printf "Setting alsa.conf...\n"

    # Setting alsa config
    sed -i 's/pcm.front cards.pcm.front/#pcm.front cards.pcm.front/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.rear cards.pcm.rear/#pcm.rear cards.pcm.rear/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.center_lfe cards.pcm.center_lfe/#pcm.center_lfe cards.pcm.center_lfe/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.side cards.pcm.side/#pcm.side cards.pcm.side/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.surround21 cards.pcm.surround21/#pcm.surround21 cards.pcm.surround21/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.surround40 cards.pcm.surround40/#pcm.surround40 cards.pcm.surround40/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.surround41 cards.pcm.surround41/#pcm.surround41 cards.pcm.surround41/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.surround50 cards.pcm.surround50/#pcm.surround50 cards.pcm.surround50/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.surround51 cards.pcm.surround51/#pcm.surround51 cards.pcm.surround51/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.surround71 cards.pcm.surround71/#pcm.surround71 cards.pcm.surround71/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.iec958 cards.pcm.iec958/#pcm.iec958 cards.pcm.iec958/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.spdif iec958/#pcm.spdif iec958/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.hdmi cards.pcm.hdmi/#pcm.hdmi cards.pcm.hdmi/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.modem cards.pcm.modem/#pcm.modem cards.pcm.modem/g' /usr/share/alsa/alsa.conf
    sed -i 's/pcm.phoneline cards.pcm.phoneline/#pcm.phoneline cards.pcm.phoneline/g' /usr/share/alsa/alsa.conf

    # Show action info
    printf "Disabling console serial service...\n"

    # Disabling console serial service
    systemctl stop serial-getty@ttyS0.service
    systemctl disable serial-getty@ttyS0.service
    sed -i 's/ console=serial0,115200 / /g' /boot/cmdline.txt

    # Show action info
    printf "Creating user qbo...\n"

    # Creating user qbo
    adduser --system --home /opt/qbo --shell /bin/bash --disabled-password --disabled-login qbo
    usermod -G adm,dialout,sudo,audio,video,plugdev,input,netdev,spi,i2c,gpio qbo
    printf "\n# Allow qbo user to exec commands\nqbo ALL=(ALL) NOPASSWD: ALL\n" >> /etc/sudoers

    # Show action info
    printf "Cloning repository...\n"

    # Cloning repository
    /usr/bin/git clone -b ${REPO_QBO_BRANCH} ${REPO_QBO} /opt/qbo
    chown -R qbo:nogroup /opt/qbo

    # Show action info
    printf "Creating pipes...\n"

    # Creating Pipes
    sudo -u qbo mkdir /opt/qbo/pipes
    sudo -u qbo mkfifo /opt/qbo/pipes/pipe_cmd
    sudo -u qbo mkfifo /opt/qbo/pipes/pipe_feel
    sudo -u qbo mkfifo /opt/qbo/pipes/pipe_findFace
    sudo -u qbo mkfifo /opt/qbo/pipes/pipe_listen
    sudo -u qbo mkfifo /opt/qbo/pipes/pipe_say

    # Show action info
    printf "Creating logs folder & setting logrotate...\n"

    # Creating logs directory
    sudo -u qbo mkdir /opt/qbo/logs
    echo "
/opt/qbo/logs/*.log {
        rotate 12
        weekly
        missingok
        notifempty
        compress
        delaycompress
        copytruncate
        create 0640 qbo nogroup
}" > /etc/logrotate.d/qbo

    # Show action info
    printf "Compile websocket...\n"

    # Compile websocket
    sudo -u qbo make all --directory=/opt/qbo/websocket

    # Installing snowboy
    printf "Installing snowboy...\n"
    INSTALL_SNOWBOY

    # Show action info
    printf "Changing hostname...\n"

    # Set qbo hostname
    echo "qbo" > /etc/hostname
    sed -i 's/files mdns4_minimal/files wins mdns4_minimal/g' /etc/nsswitch.conf
    sed -i 's/raspberrypi/qbo/g' /etc/hosts

    # Show action info
    printf "Setting Crontab...\n"

    # Set crontab
    echo "@reboot qbo /opt/qbo/Start.py" >> /etc/crontab
    echo "@reboot qbo python3 /opt/qbo/web/manage.py runserver 0.0.0.0:8000" >> /etc/crontab
    echo "* * * * * qbo bash /opt/qbo/scripts/WiFiSearchQR.sh" >> /etc/crontab
    echo "0 15 * * * root bash /opt/qbo/scripts/UpdateMyCroft.sh" >> /etc/crontab

    # Show action info
    printf "Create config.yml...\n"

    # Create config.yml
    case "$DISTRO" in
        standalone)
            sudo -u qbo echo "{distro: standalone, language: english, microphoneGain: 100, camera: 0, servoSpeed: 100, tokenAPIai: , gassistant_proyectid: , dialogflowv2_projectid: , startWith: interactive-dialogflow, volume: 100 }" > /opt/qbo/config.yml
            chown qbo:nogroup /opt/qbo/config.yml
        ;;
        ibmwatson)
            sudo -u qbo echo "{distro: ibmwatson, language: english, microphoneGain: 100, camera: 0, servoSpeed: 100, AssistantAPIKey: , AssistantURL: , AssistantID: , TextToSpeechAPIKey: , TextToSpeechURL: , SpeechToTextAPIKey: , SpeechToTextURL: , SpeechToTextListeningTime: , VisualRecognitionAPIKey: , VisualRecognitionURL: , startWith: interactive-dialogflow, volume: 100 }" > /opt/qbo/config.yml
            chown qbo:nogroup /opt/qbo/config.yml
        ;;
        *)
            printf "\n\n **CRITICAL ERROR** Distribution undefined\n\n"
            exit 1
    esac

    # Install MyCroft Software

    /usr/bin/git clone -b master https://github.com/MycroftAI/mycroft-core.git /opt/qbo/mycroft-core
    bash /opt/qbo/mycroft-core/dev_setup.sh --allow-root

    /usr/bin/pip3 install certifi monotonic

    sed -i 's/paplay %1 --stream-name=mycroft-voice/aplay -D convertQBO %1/g' /opt/qbo/mycroft-core/mycroft/configuration/mycroft.conf

    # Show action info
    printf "Complete! Rebooting in 5 seconds...\n"

    # Removing installer
    if [ -f "`pwd`/`basename "$0"`" ]
    then
        rm -f "`pwd`/`basename "$0"`"
    fi

    # Wait 5 seconds & reboot
    sleep 5
    reboot

}

function UPDATE {

    # Get current branch
    CURRENT_BRANCH=`git -C /opt/qbo rev-parse --abbrev-ref HEAD`

    # Obtain changes from origin
    printf "Downloading updates...\n"
    sudo -u qbo /usr/bin/git -C /opt/qbo fetch origin

    # Obtain if QBO_Installer file changed
    QBO_INSTALLER_CHANGED=`sudo -u qbo /usr/bin/git -C /opt/qbo diff origin/${CURRENT_BRANCH} --name-only | grep QBO_Installer.sh | wc -l`

    # Applying changes
    printf "Applying updates...\n"
    sudo -u qbo /usr/bin/git -C /opt/qbo merge FETCH_HEAD

    # Check if QBO_Installer file changed, process of update is restarted
    if [ ${QBO_INSTALLER_CHANGED} == "1" ]
    then
        printf "New installer detected. Restarting update process ...\n"
        /opt/qbo/scripts/QBO_Installer.sh update
        exit 1
    fi

    # Add Chrome to startup
    if [ -f /home/pi/.config/lxsession/LXDE-pi/autostart ]
    then
        if [ -z `cat /home/pi/.config/lxsession/LXDE-pi/autostart | grep chromium` ]
        then
            echo "@/usr/bin/chromium-browser --kiosk --noerrordialogs --incognito --disable-infobars --disable-session-crashed-bubble http://localhost:8000" >> /home/pi/.config/lxsession/LXDE-pi/autostart
        else
            printf "Already configured chromium at startup.\n"
        fi
    else
        echo "@lxpanel --profile LXDE-pi" > /home/pi/.config/lxsession/LXDE-pi/autostart
        echo "@pcmanfm --desktop --profile LXDE-pi" >> /home/pi/.config/lxsession/LXDE-pi/autostart
        echo "@xscreensaver -no-splash" >> /home/pi/.config/lxsession/LXDE-pi/autostart
        echo "@point-rpi" >> /home/pi/.config/lxsession/LXDE-pi/autostart
        echo "@/usr/bin/chromium-browser --kiosk --noerrordialogs --incognito --disable-infobars --disable-session-crashed-bubble http://localhost:8000" >> /home/pi/.config/lxsession/LXDE-pi/autostart
    fi

    # Updating dependencies
    printf "Updating dependencies...\n"
    INSTALL_OR_UPDATE_DEPENDENCIES

    # Clean previous version & Compile websocket
    printf "Compile websocket...\n"
    sudo -u qbo make clean --directory=/opt/qbo/websocket
    sudo -u qbo make all --directory=/opt/qbo/websocket

    # Updating snowboy
    printf "Updating snowboy...\n"
    INSTALL_SNOWBOY

    # Show action info
    printf "Complete! Rebooting in 3 seconds...\n"

    # Speak
    sudo -u qbo /opt/qbo/Speak.py update

    # Wait 3 seconds & reboot
    sleep 3
    reboot

}

function UPDATE_CHANGELOG {

    # Get current branch
    CURRENT_BRANCH=`git -C /opt/qbo rev-parse --abbrev-ref HEAD`

    # Obtain changes from origin
    sudo -u qbo /usr/bin/git -C /opt/qbo fetch origin > /dev/null 2>&1

    # Show changes
    sudo -u qbo /usr/bin/git -C /opt/qbo log HEAD..origin/${CURRENT_BRANCH} --pretty=format:"%cd - %s" --date=format:"%d/%m/%Y %H:%M"

}

function UPDATE_CHANGE_BRANCH {

    # Screen if update from development repositories
    if [ ${REPO_QBO_BRANCH} == "develop" ]
    then
        printf "**WARNING**\n\nAre you sure you want to update from the development repositories? The development version is unstable and may contain critical errors.\n\n"
        read -n 1 -s -r -p "Press any key to continue or Ctrl+C to cancel"
        clear
    fi

    # Obtain changes from origin
    printf "Downloading updates...\n"
    sudo -u qbo /usr/bin/git -C /opt/qbo fetch origin

    # Checkout branch
    printf "Changing branch...\n"
    sudo -u qbo /usr/bin/git -C /opt/qbo checkout ${REPO_QBO_BRANCH}

    # Restart process update
    printf "Restarting update process ...\n"
    /opt/qbo/scripts/QBO_Installer.sh update
    exit 1

}

function GASSISTANT_CREDENTIALS {

    # Command to generate credentials
    sudo -u qbo /usr/local/bin/google-oauthlib-tool --scope https://www.googleapis.com/auth/assistant-sdk-prototype --scope https://www.googleapis.com/auth/gcm --save --headless --client-secrets ${GOOGLE_CLIENT_SECRET_FILE}

}


# Script init

if [ `whoami` == "root" ]
then
	if [ `lsb_release -i -s` == "Raspbian" ]
	then
		if [ -e /dev/ttyS0 ]
		then
            case "$1" in
                install)
                    if [ -d "/opt/qbo" ]
                    then
                        printf "An installation of the QBO Software has been found. If you want to reinstall it, first remove that installation, or reinstall Raspbian.\n"
                        exit 1
                    fi
                    case "$2" in
                        develop)
                            REPO_QBO_BRANCH="develop"
                        ;;
                        *)
                            REPO_QBO_BRANCH="master"
                    esac
                    INSTALL
                    ;;
                update)
                    if [ ! -d "/opt/qbo" ]
                    then
                        printf "The QBO Software installed has not been found. Please install the QBO software before trying to update it.\n"
                        exit 1
                    fi
                    case "$2" in
                        changelog)
                            UPDATE_CHANGELOG
                        ;;
                        develop)
                            REPO_QBO_BRANCH="develop"
                            UPDATE_CHANGE_BRANCH
                        ;;
                        master)
                            REPO_QBO_BRANCH="master"
                            UPDATE_CHANGE_BRANCH
                        ;;
                        *)
                            UPDATE
                    esac
                    ;;
                gassistant)
                    if [ ! -d "/opt/qbo" ]
                    then
                        printf "The QBO Software installed has not been found. Please install the QBO software before trying to register gassistant it.\n"
                        exit 1
                    fi
                    if [ ! -e "$2" ]
                    then
                        printf "The specified file does not exist.\n"
                        exit 1
                    fi
                    GOOGLE_CLIENT_SECRET_FILE=$2
                    GASSISTANT_CREDENTIALS
                    ;;
                *)
                    echo $"Usage: $0 {install|install develop|update|update changelog|update develop|update master|gassistant [path credentials json file]}"
                    exit 1
            esac
		else
			echo "You must enable the SERIAL interface. Run 'sudo raspi-config' and activate it in Interfacing Options."
			echo "You may have to restart the computer once you enable it."
		fi
	else
		echo "Qbo program can only be installed on Raspberry pi devices running with Raspbian."
	fi
else
	echo "Only superuser ROOT can execute this script. Try: 'sudo bash QBO_Installer.sh'"
fi
