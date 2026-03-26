# QBO Software

QBO robot system in Raspberry Pi devices.


## Install

To install the QBO software you will need a clean Raspbian image running on the Raspberry Pi 3 in your QBO robot.

Download latest version of Raspbian from: https://www.raspberrypi.org/downloads/raspbian/

Before installing the QBO Software it is necessary that you activate the SERIAL interface. To activate the serial runs in the terminal execute the following command:

```bash
$ sudo raspi-config
```

Select option 5 'Interfacing Options' and then option P6 'Serial'. Finally, indicate the option 'Yes' to confirm the activation of the Serial port.

Once finished, restart the raspberry pi before continuing with the following steps. You can execute the following command to restart:

```bash
$ sudo reboot
```

Now, execute the following commands in terminal and the QBO system will be installed automatically. If any action is necessary, the installer will indicate it.

```bash
$ wget https://gitlab.com/thecorpora/QBO/raw/master/scripts/QBO_Installer.sh
$ chmod +x QBO_Installer.sh
$ sudo ./QBO_Installer.sh install # Add 'develop' if you prefer to install QBO software the development repositories. (Not recommended)
```

Once the Qbo installation is completed the system will restart and the QBO robot will be ready

##### Update

If you want to see the changes before updating, you can execute the following command.

```bash
$ sudo /opt/qbo/scripts/QBO_Installer.sh update changelog
```

You can execute the following command to update.

```bash
$ sudo /opt/qbo/scripts/QBO_Installer.sh update
```

## QBO Robot Web Panel

Access this url. You must be in the same network as the qbo robot to access.

```
http://qbo.local:8000/ or http://qbo:8000/ (Only Windows)
```

##### Web project tests

```bash
python web/manage.py test
```

## Scratch

Set the Scratch mode on the configuration web.

Open the following url in your browser:

```
http://scratchx.org/?url=http://qbo.local:8000/static/scratch/robot_control.js#scratch
```

Or (Only Windows)

```
http://scratchx.org/?url=http://qbo:8000/static/scratch/robot_control.js#scratch
```

Remember that you must be on the same LAN as the QBO robot.

## Help us to improve

We need help for the robot to correctly understand the "Hi QBO" hotword. If you have less than 5 minutes, collaborate with us and provide your voice.

[Enter here](https://snowboy.kitt.ai/hotword/24548) and record your voice. We need 500 recordings of different people so that recognition works universally.

## Manuals

* [How to enable Google Assistant](https://gitlab.com/thecorpora/QBO/blob/master/manuals/GoogleAssistant.md)
* [How to enable IBM Watson](https://gitlab.com/thecorpora/QBO/blob/master/manuals/IBMWatson.md)
* [How to use Visual Recognition (Command)](https://gitlab.com/thecorpora/QBO/blob/master/manuals/VisualRecognition.md)
* [How to setup DialogflowV2](https://gitlab.com/thecorpora/QBO/blob/master/manuals/DialogFlowV2.md)
* [How to trigger TensorFlow](https://gitlab.com/thecorpora/QBO/blob/master/manuals/TensorFlow.md)

## License

```
MIT License

Copyright (c) 2018 Thecorpora

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
 ```