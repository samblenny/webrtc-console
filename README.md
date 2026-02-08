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

3. On macOS, flash SD image with dd (☠️DANGER☠️ **Double-check disk number!**)

   ```
   diskutil list
   diskutil unmountDisk /dev/disk4
   sudo dd if=2025-12-04-raspios-trixie-armhf-lite.img of=/dev/rdisk4 bs=1M
   sync
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

10. Unmount the partions with `pumount piboot` and `pumount piroot`.

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
    bridge address assigned to the Pi Zero. Something like this is good:

    ```
    $ netstat -rn | grep 'Gateway\|bridge' | grep -v '^f...::\| \{20\}'
    Destination        Gateway            Flags               Netif Expire
    default            link#22            UCSIg           bridge100      !
    192.168.2          link#22            UC              bridge100      !
    192.168.2.5        xx.xx.xx.xx.xx.xx  UHLWIi          bridge100   1195
    ```

    This means the Pi Zero was assigned 192.168.2.5

16. Try to SSH into the pi using the IP from netstat, for example:

    ```
    ssh pi@192.168.2.5   # password is "password" unless you edited the hash
    ```

    NOTE: Your internet connection sharing bridge's DHCP server might not give
    the Pi Zero a consistent IP address across multiple connections. In that
    case, SSH may complain about server key fingerprints because it expects
    servers to have a consistent IP. Suppose you try to connect to 192.168.2.5
    and you get a scary warning from SSH about the key fingerprint changing
    from what it expected. You can fix the warning by removing the old key
    fingerprint with `ssh-keygen -R`:

    ```
    ssh-keygen -R 192.168.2.5
    ```


17. If SSH didn't work, try connecting to the ACM serial device

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
1. macOS probing the serial port with a cursor position query (`ESC[6n`)
2. The getty echoing the query characters back to the macOS Terminal
3. Terminal typing its answer to the echoed copy of its own terminal position
   query, which the getty then erroneously treats as a typed username

I'm not at all sure about that. Just guessing.
