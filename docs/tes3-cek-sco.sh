#!/bin/bash
# Tes 3 pendamping: ambil status HFP/SCO saat telepon tersambung ke jam.
# Cara pakai: telepon tersambung + audio ke jam, lalu jalankan skrip ini dari laptop.
echo "=== HFP state ==="
adb shell dumpsys bluetooth_manager 2>&1 | grep -oE "HeadsetStateMachine state=[A-Za-z]+"
echo "=== SCO audio ==="
adb shell dumpsys audio 2>&1 | grep -iE "bt_sco.*(on|true)|sco.*connected" | head -5
echo "=== telecom call ==="
adb shell dumpsys telecom 2>&1 | grep -iE "call.*(active|dialing)|phoneAccount|bluetooth" | head -10
