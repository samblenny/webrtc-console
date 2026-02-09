<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: Copyright 2026 Sam Blenny -->
# WebRTC Console

**DRAFT: WORK IN PROGRESS**

[Note: Following my typical work pattern, this readme is a combination of
planning document, aspirational statement of intent, and notes on work in
progress. Assuming things go to plan, the readme will evolve into documentation
for working code. If the experiment flops, I'll document that instead.]


Goals:

1. Experiment with running apps on a tethered USB gadget device using the host
   computer for a virtual console with video out, audio out, and human input.
   I'm going for something that's like VNC plus audio output and gamepad input.

2. Validate whether it's reasonable to use WebRTC as the front end for a
   tethered USB NCM gadget. (main complexity is browser secure origin policy)

3. Experiment with PocketBeagle 2, Raspberry Pi Zero 2 W, and perhaps Raspberry
   Pi Zero W (old 32-bit version) with Linux ConfigFS composite USB OTG gadget
   configurations for ACM serial and NCM virtual network.

4. Learn how to do the HTTP handshake for WebRTC SDP answer/offer and peer
   connection candidates.

5. Learn how to set up gstreamer to stream VP8 video and Opus audio from an X
   virtual framebuffer desktop.

6. Learn how to use human input streamed from a browser to the gadget device by
   RTP (or whatever) to control the X virtual desktop


## Files

- [index.html](index.html): HTML for the WebRTC client

- [main.js](main.js): JavaScript for the WebRTC client

- [mock_server.py](mock_server.py): Testing server to validate network
  connectivity and the WebRTC connection setup negotiation handshake. Run this
  on the USB gadget.

- [pi-sd-ext4-setup.sh](pi-sd-ext4-setup.sh): Script to transform a newly
  flashed Raspberry Pi OS Lite SD card into a USB OTG gadget for Pi Zero W with
  a getty on ACM serial and SSH on NCM virtual network.

- [rtc-tunnel.py](rtc-tunnel.py): This tunnel proxies the HTTP and RTP
  connections from the USB gadget's IP to localhost so that Chrome will agree
  to connect to them (currently, Chrome on macOS treats private IP addresses as
  unreachable, but localhost works)


## Pi Zero W OTG Gadget Setup

1. Go to https://www.raspberrypi.com/software/operating-systems/

2. Pick Raspberry Pi OS (32-bit) > Raspberry Pi OS Lite (download it)

3. On macOS, flash SD image with dd

   ☠️DANGER☠️: **Double-check disk number!**

   ```
   diskutil list
   diskutil unmountDisk /dev/disk4
   sudo dd if=2025-12-04-raspios-trixie-armhf-lite.img of=/dev/rdisk4 bs=1M
   sync
   diskutil unmountDisk /dev/disk4
   ```

   Arguably, it might make more sense to do the Linux equivalent of this on a
   Debian box. But, by habit, I do this part on macOS.

   Note that using the Raspberry Pi Imager tool won't work here because it does
   its own thing for customizing the stock SD card image. In a minute, we'll
   run a script that expects fresh, unmodified SD card partitions.

4. Switch the SD card to a USB SD card reader on a Debian box or Raspberry Pi.
   We can't use macOS here because we need to mount and modify the ext4
   partition.

5. Copy the `pi-sd-ext4-setup.sh` script to the Debian or Raspberry Pi. If
   needed, make it executable with `chmod +x pi-sd-ext4-setup.sh`.

6. Use `lsblk` (before and after inserting the SD card) to find the device
   files for the fat32 boot partion and the ext4 root partition.

7. If you don't already have `pmount`, do `sudo apt install pmount`.

8. Pmount the boot partition as `piboot` (should appear at /media/piboot) and
   the root partition as `piroot` (should appear at /media/piroot):

   ```
   lsblk  # find partition device files (e.g. /dev/sdb1 and /dev/sdb2)
   pmount /dev/sdb1 piboot
   pmount /dev/sdb2 piroot
   ```

9. Run `./pi-sd-ext4-setup.sh` to drop config files, make systemd symlinks, and
   so on to prepare the SD partitions for first boot.

10. Unmount the partions with `pumount piboot; pumount piroot`.

11. Move the SD card to the Pi Zero W

12. Connect the host computer (macOS) to the Pi Zero's USB data port (the one
    closer to the HDMI jack).

13. In macOS System Settings > Network, wait for the Pi Zero Composite
    interface to show up.

14. In System Settings > General > Sharing > Internet Sharing, click the (i)
    button for the detailed popup. Make sure the main "Internet Sharing" switch
    at the top is off, flip the switch for "Pi Zero Composite" to On, then flip
    the main switch at the top to On.

15. Use `netstat -rn | grep 'Gateway\|bridge'` to check for the ICS
    bridge address assigned to the Pi Zero. The first time you boot the Pi
    Zero, it might take on the order of 2-4 minutes to reach this stage.

    Something like this is what you want to see:

    ```
    $ netstat -rn | grep 'Gateway\|bridge' | grep -v '^f...::\| \{20\}'
    Destination        Gateway            Flags               Netif Expire
    default            link#22            UCSIg           bridge100      !
    192.168.2          link#22            UC              bridge100      !
    192.168.2.5        xx.xx.xx.xx.xx.xx  UHLWIi          bridge100   1195
    ```

    This means the USB NCM internet connection sharing bridge is active and
    that its DHCP server assigned the Pi Zero IP address 192.168.2.5.

16. Try to find the mDNS SSH service advertisement by running `dns-sd` from the
    macOS Terminal (Ctrl-C to exit):

    ```
    $ dns-sd -B _ssh._tcp
    Browsing for _ssh._tcp
    DATE: ---Sun 08 Feb 2026---
    17:45:23.821  ...STARTING...
    Timestamp     A/R    Flags  if Domain               Service Type         Instance Name
    17:45:23.822  Add        2  22 local.               _ssh._tcp.           raspberrypi
    17:45:23.995  Add        2  28 local.               _ssh._tcp.           raspberrypi
    ^C
    ```

    In this case, it's showing us that `ssh pi@raspberrypi.local` should work.
    Note that mDNS can be a bit unpredictable. If you don't see any lines with
    `_ssh._tcp` in the output, then mDNS name resolution might not work. In
    that case, try using the IP address detected by `netstat`.

17. Try to SSH into the pi using the mDNS name or the IP from netstat, for
    example:

    ```
    ssh pi@raspberrypi.local   # password is "password"
    ```
    or

    ```
    ssh pi@192.168.2.5   # password is "password"
    ```

    NOTE: For various reasons, doing this type of thing may result in a scary
    warning from SSH complaining about incorrect server key fingerprints. This
    can happen if you re-flash the SD card, if you use two Pi Zeros that both
    report their hostname as raspberrypi.local, if your DHCP server does not
    assign long-term consistent IP addresses, etc. There's an easy fix with
    `ssh-keygen -R`. Suppose you try to connect to 192.168.2.5 and SSH
    complains about the key fingerprint. You can fix the warning by removing
    the old key fingerprint for that server (192.168.2.5):

    ```
    ssh-keygen -R 192.168.2.5
    ```
    you can also do
    ```
    ssh-keygen -R raspberrypi.local
    ```

    ☠️DANGER☠️: Don't casually use this trick for SSH servers outside of your
    own private test networks. If you see SSH key fingerprint errors for an SSH
    server hosted on the public internet, take the warning seriously.

18. If SSH didn't work, try connecting to the ACM serial device

    ```
    $ ls /dev/tty.usbmodem*
    /dev/tty.usbmodem01234567891
    $ screen -fn /dev/tty.usbmodem01234567891 115200
    ```

    You may see something like this (note garbage on the login line):

    ```
    Raspbian GNU/Linux 13 raspberrypi ttyGS0

    My IP address is 127.0.1.1 xxxx::xxxx:xxxx:xxxx:xxxx

    raspberrypi login:
    Raspbian GNU/Linux 13 raspberrypi ttyGS0

    My IP address is 192.168.2.5 xxxx::xxxx:xxxx:xxxx:xxxx

    raspberrypi login: ^[[1;1R^[[32;125R^[[32;125R^[[32;125R
    ```

    Backspace to get rid of the terminal position report escape sequence
    garbage then log in as pi:password.

**TODO:** Research if there is a good way to suppress the terminal position
report escape sequence stuff. This may be happening as a consequence of:
1. One of macOS, `agetty`, or `login` probing the serial port with a cursor
   position query (`ESC[6n`)
2. Potentially some kind of weird echo loop thing happening
3. macOS Terminal seeing the query sequence and sending a response
4. `agetty` or `login` treating the query response escape sequence as a
   typed response to the login prompt

I'm not at all sure about that. Just guessing.


## Additional Pi Setup

Once I have SSH and an internet connection working, I like to do these
additional configuration steps:

1. `sudo apt update && sudo apt upgrade`
2. `sudo raspi-config`
   - Localisation Options > {Locale, Timezone} (set them both)
   - Advanced Options > Logging > Volatile


## MacOS mDNS Browsing

To find the Pi Zero's advertised mDNS services from avahi-daemon, you can use
`dns-sd` (Ctrl-C to stop browsing):

```
$ dns-sd -B _ssh._tcp
Browsing for _ssh._tcp
DATE: ---Sun 08 Feb 2026---
17:26:58.569  ...STARTING...
Timestamp     A/R    Flags  if Domain               Service Type         Instance Name
17:26:58.571  Add        2  22 local.               _ssh._tcp.           raspberrypi
17:26:58.731  Add        2  27 local.               _ssh._tcp.           raspberrypi
^C
$ dns-sd -B _http._tcp
Browsing for _http._tcp
DATE: ---Sun 08 Feb 2026---
17:27:12.038  ...STARTING...
Timestamp     A/R    Flags  if Domain               Service Type         Instance Name
17:27:12.039  Add        2  22 local.               _http._tcp.          raspberrypi
17:27:12.264  Add        2  27 local.               _http._tcp.          raspberrypi
^C
```

In the above example, `dns-sd` is telling us that `raspberrypi.local` should
work for SSH and HTTP.

You can try:
1. From macOS Terminal: `ssh pi@raspberrypi.local` (password = "password")
2. In the resulting SSH shell, do `python3 -m http.server` to start a web
   server on 0.0.0.0:8000.
3. From macOS Safari, load `http://raspberrypi.local:8000`. You should see a
   file listing for pi's home directory dot files on the Pi Zero.

Note: Chrome will likely refuse to talk to the IP address because it's in a
private address range ("This site can't be reached...
ERR\_ADDRESS\_UNREACHABLE"). This is a known issue with Chrome. Safari should
work. A python localhost proxy script should work.
