#!/bin/bash
#
# This turns a flashed-but-not-booted-yet Raspberry Pi OS Lite (Trixie) SD card
# into a composite USB OTG gadget with a getty on CDC-ACM serial and SSH on a
# CDC-NCM virtual network interface. I suggest using the 32-bit OS image so the
# same card will work on either of Pi Zero W or Pi Zero 2 W.
#
# You should run this script from Debian or Raspberry Pi (for the ext4 driver)
# with a USB SD card reader. Use lsblk and pmount to detect and mount the SD
# card partitions. Mount the fat32 as piboot and the ext4 as piroot. After
# running this script to modify the SD card partitions, pumount them and move
# the SD card to a Pi Zero. Connect the microUSB cable from the host computer
# to the Pi Zero's data port (closer to the HDMI connector).
#
# I've been testing this with macOS as the host. I use internet connection
# sharing from the Mac so the Pi can get apt packages without needing to
# configure wifi. I haven't tested whether this works with Linux or Windows.
# Probably Linux is fine. From what I read, there's a good chance that the
# Windows 11 NCM driver will work, but Windows 10 likely won't.
#
# CAUTION: This hardcodes an insecure password hash. You might wanna change it.
# you can generate a new one with `openssl passwd -6` on Linux.

# exit immediately on errors
set -e

# These mountpoints should be created by pmount (run pmount before this script)
BOOT=/media/piboot
ROOT=/media/piroot

# Check that the expected mount points exist
if [[ ! -d "$BOOT" ]] || [[ ! -d "$ROOT" ]]; then
    echo "Error: $BOOT or $ROOT not found."
    echo "Use 'lsblk' to find SD partitions and mount with pmount."
    echo "(sudo apt install pmount if needed)"
    exit 1
fi

# Enable SSH
touch $BOOT/ssh

# Set pi password to "password" (don't do this if you're using wifi!).
# You can generate a hash for a proper password with `openssl passwd -6`, but
# note that macos openssl passwd does not support the `-6` option (use Linux)
cat > "$BOOT/userconf.txt" << 'EOF'
pi:$6$7Tfs12Dgkrt2LMqS$16.XfLHBMd2oZIpGZtsPCYSXFe9Qncbf5b0l6qxOxGtZBMnSzG3P8ckqJzk9AG9LaP6YIrTc0q.4M9UfPHFox1
EOF

# Ensure dwc2 overlay exists in config.txt
cat >> "$BOOT/config.txt" << 'EOF'
[pi0]
dtoverlay=dwc2
EOF

# Create gadget setup script
# NOTE: this is using a quoted heredoc (<< 'EOF') to escape "$", etc.
GADGET_SCRIPT="$ROOT/usr/bin/setup-usb-gadget.sh"
sudo mkdir -p "$ROOT/usr/bin"
sudo tee "$GADGET_SCRIPT" > /dev/null << 'EOF'
#!/bin/bash
modprobe libcomposite
GADGET=/sys/kernel/config/usb_gadget/g1
mkdir -p $GADGET
cd $GADGET

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "0123456789" > strings/0x409/serialnumber
echo "Raspberry Pi" > strings/0x409/manufacturer
echo "Pi Zero Composite" > strings/0x409/product

mkdir -p configs/c.1
mkdir -p functions/acm.usb0
mkdir -p functions/ncm.usb0

ln -sf functions/acm.usb0 configs/c.1/
ln -sf functions/ncm.usb0 configs/c.1/

# Bind gadget
ls /sys/class/udc > UDC

# Bring up NCM interface so dhcpcd can assign DHCP IP
ip link set usb0 up || true
dhclient -v usb0
EOF

sudo chmod +x "$GADGET_SCRIPT"

# Create systemd service
SERVICE_FILE="$ROOT/etc/systemd/system/usb-gadget.service"
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Setup USB composite gadget
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/setup-usb-gadget.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Enable service
sudo mkdir -p "$ROOT/etc/systemd/system/multi-user.target.wants"
sudo ln -sf /etc/systemd/system/usb-gadget.service \
        "$ROOT/etc/systemd/system/multi-user.target.wants/usb-gadget.service"

# Enable getty on USB ACM
sudo mkdir -p "$ROOT/etc/systemd/system/getty.target.wants"
sudo ln -sf /lib/systemd/system/serial-getty@.service \
        "$ROOT/etc/systemd/system/getty.target.wants/serial-getty@ttyGS0.service"

# At this point, we're assuming that dhcpcd is running and that it will use
# DHCP to set a suitable address for the NCM usb0 interface.

echo "SD card prepared: Pi Zero will boot headless with USB ACM + NCM + DHCP + SSH."
