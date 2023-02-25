from struct import unpack_from, pack
from datetime import datetime
from sys import argv
import time

filein = open("/dev/stdin", "rb")

data = filein.read(1200)

if len(argv) > 1 and argv[1] == "-p":
      header = pack(">II", 0x0, int(time.time()))
      data = header + b'\x00'*28 + data

sequence, timestamp = unpack_from(">II", data, 0x0)
date = datetime.fromtimestamp(timestamp)

inverter_type, = unpack_from(">H", data, 0x22)

# 0024 - 2 byte, Anno (eg: 2022 in decimale)
# 0026 - 1 byte, Mese (eg: in decimale 12)
# 0027 - 1 byte, Giorno (eg: in decimale 24)
# 0028 - 1 byte, Ora (eg: in decimale 14)
# 0029 - 1 byte, Minuto (eg: in decimale 50)
# 002a - 1 byte, Secondo (eg: in decimale 7)
year, month, day, hour, minute, second = unpack_from(">HBBBBB", data, 0x24)

inverter_work_mode, = unpack_from(">H", data, 0x2c)
heatsink_temp, earth_leakage, iso4, conn_time = unpack_from(">HxxhxxxxxxHxxxxH", data, 0x44)
heatsink_temp /= 10

# 0086 2 byte, RGridVolt, tensione in decivolt
# 0088 2 byte, ROutCurr, corrente in centiampere
# 0090 2 byte, ROutFreq, frequenza in centihz
# 0092 2 byte, RGridDCI, componente dc ?
# 0094 2 byte, ROutPowerWatt, potenza attiva W?
# 0096 2 byte, RGridPowerVA, potenza apparente VA?
# 0098 2 byte, RGridPowerPF, fattore di correzione di potenza
rgrid_volt, rgrid_curr, rgrid_freq, rgrid_dci, rgrid_power_watt, rgrid_power_va, rgrid_power_pf = unpack_from(">HhHhhhh", data, 0x86)
rgrid_volt /= 10
rgrid_curr /= 100
rgrid_freq /= 100
rgrid_power_pf /= 1000

# 00b0 2 byte, RInvVolt
# 00b2 2 byte, RInvCurrent
# 00b4 2 byte, RInvFreq
# 00b6 2 byte, RInvPowerWatt
# 00b8 2 byte, RInvPowerVA
rinv_volt, rinv_current, rinv_freq, rinv_power_watt, rinv_power_va = unpack_from(">HhHhh", data, 0xb0)
rinv_volt /= 10
rinv_current /= 100
rinv_freq /= 100
rinv_pf = rinv_power_watt / rinv_power_va

# 00ce 2 byte, ROutVolt
# 00d0 2 byte, ROutCurr
# 00d2 2 byte, ROutFreq
# 00d4 2 byte, ROutDVI (forse è ROutDCI?)
# 00d6 2 byte, ROutPowerWatt
# 00d8 2 byte, ROutPowerVA
rout_volt, rout_curr, rout_freq, rout_dvi, rout_power_watt, rout_power_va = unpack_from(">HhHhhh", data, 0xce)
rout_volt /= 10
rout_curr /= 100
rout_freq /= 100
rout_pf = rout_power_watt / rout_power_va

# 00f2 2 byte, BusVoltMaster
# 00f4 2 byte, BusVoltSlave
bus_volt_master, bus_volt_slave = unpack_from(">HH", data, 0xf2)
bus_volt_master /= 10
bus_volt_slave /= 10

# 00f6 2 byte, BatVolt - tensione pacco batterie
# 00f8 2 byte, BatCurr - corrente pacco batterie
# 00fa 2 byte, BatCurr1 - controllo corrente batterie
# 00fc 2 byte, BatCurr2 - controllo corrente batterie
# 00fe 2 byte, BatPower - potenza batterie (valori da controllare)
# 0100 2 byte, BatTempC - temperatura batterie (valori da controllare)
# 0102 2 byte, BatEnergyPercent - energia residua batterie (valori da controllare)
bat_volt, bat_curr, bat_curr1, bat_curr2, bat_power, bat_tempc, bat_percent = unpack_from(">HhhhhhH", data, 0xf6)
bat_volt /= 10
bat_curr /= 100
bat_curr1 /= 100
bat_curr2 /= 100
bat_tempc /= 10
bat_percent /= 100
bat_power2 = bat_volt * bat_curr

# 0106 2 byte - PV1Volt - tensione pannelli array 1
# 0108 2 byte - PV1Curr - corrente pannelli array 1
# 010a 2 byte - PVPower - potenza pannelli array 1
pv1_volt, pv1_curr, pv1_power = unpack_from(">HHH", data, 0x106)
pv1_volt /= 10
pv1_curr /= 100

# 010c 2 byte - PV2Volt - tensione pannelli array 2
# 010f 2 byte - PV2Curr - corrente pannelli array 2
# 0110 2 byte - PV2Power - potenza pannelli array 2
pv2_volt, pv2_curr, pv2_power = unpack_from(">HHH", data, 0x10c)
pv2_volt /= 10
pv2_curr /= 100

# 014e 2 byte - PVDirection - direzione flusso pannelli fotovoltaici (presumibilmente 0 è riceve corrente e 1 è produce corrente)
# 0150 2 byte - Battery Direction - direzione flusso batteria, 0 è riceve corrente e 1 è produce corrente)
# 0152 2 byte - Grid Direction - direzione flusso di rete, 0 riceve corrente, 1 produce corrente)
# 0154 2 byte - Output Direction - direzione flusso output (non è chiaro il senso, presumibilmente 0 riceve e 1 produce)
dir_pv, dir_bat, dir_grid, dir_output = unpack_from(">HhhH", data, 0x14e)
dir_pv = "ingoing" if dir_pv == 0 else "outgoing"
dir_bat = "discharging" if dir_bat == 0 else "charging"
dir_grid = "fetching" if dir_grid == 0 else "putting"
dir_output = "ingoing" if dir_output == 0 else "outgoing"

# 0164 2 byte - SysTotalLoadWatt - Totale della potenza attiva dell'inverter (valore da controllare, riporta 18 Watt, ma può ben essere la potenza del carico)
# ... buco di 8 byte, riprende a 016e modbus 40a5h
# 016e 2 byte - TotalPVPower - Totale potenza pannelli (la documentazione riporta una descrizione errata, i dati sono in accordo con la potenza dei pannelli)
# 0170 2 byte - TotalBatteryPower - Totale potenza batteria (Riporta 10 watt dai dati)
# 0172 2 byte - TotalGridPowerWatt - potenza di rete (3191 Watt)
# 0174 2 byte - TotalGridPowerVA - potenza apparente di rete (risulta pari a 0, forse il dato è mancante)
# 0176 2 byte - TotalInvPowerW - potenza attiva di inversione (3202 Watt)
# 0178 2 byte - TotalInvPowerVA - potenza apparente di inversione (risulta pari a 0, forse il data anche qui è mancante)
# 017a 2 byte - BackupTotalLoadPowerWatt - carico totale del backup in watt in potenza attiva (dai dati risultano 18 watt)
# 017c 2 byte - BackupTotalLoadPowerVA - carico totale del backup in potenza apparente (risulta pari a 0, dato mancante?)
# 017e 2 byte - non documentato, dai dati sembrerebbe una potenza poiché si legge 3183
sys_total_load_watt, smart_meter_load_watt = unpack_from(">Hh", data, 0x164)
total_pv_power, total_battery_power, total_grid_power_watt, total_grid_power_va = unpack_from(">Hhhh", data, 0x16e)
total_inverter_power_watt, total_inverter_power_va = unpack_from(">hh", data, 0x176)
backup_total_load_power_watt, backup_total_load_power_va, unknown_power = unpack_from(">HHh", data, 0x17a)

# A partire da 0x1a2 ci sono le statistiche per ogni elemento. Ciascun elemento ha quattro statistiche da 4 byte
# ciascuno: totale del giorno, del mese, dell'anno, e totale globale.
# Gli elementi sono:
# - Photovoltaic energy
# - Energy used for battery charge
# - Energy supplied by battery
# - Load power consumption
# - Backup power consumption
# - Energy exported to grid
# - Energy imported from grid
stats = []
ENERGY_MAP = (
      ("photovoltaic", 0x1a2),
      ("battery charge", 0x1b2),
      ("battery supplied", 0x1c2),
      ("load power" ,0x1e2),
      ("backup load", 0x1f2),
      ("exported to grid", 0x202),
      ("imported from grid", 0x212)
)
for item, offset in ENERGY_MAP:
      stat_data = unpack_from(">IIII", data, offset)
      stat_data= (item,) + tuple(value / 100 for value in stat_data)
      stats.append(stat_data)

print("Sequence number: %08d, packet datetime: %s" % (sequence, date))
print("Inverter type: %4x, working mode: %d" % (inverter_type, inverter_work_mode))
print("Sample datetime: %4d-%02d-%02d %02d:%02d:%02d" % (year, month, day, hour, minute, second))
print("Heatsink temp: %d, leakage current: %dma, iso4: %d, Reconnection time: %d" % (heatsink_temp, earth_leakage, iso4, conn_time))
print()
print("Grid data:")
print("Voltage: %3.1fV\t\tCurrent: %1.3fA\t\tFrequency: %2.2fHz" % (rgrid_volt, rgrid_curr, rgrid_freq))
print("DC current: %dma\tActive power: %dW\tApparent power: %dW\tPower factor: %3.1f" %
      (rgrid_dci, rgrid_power_watt, rgrid_power_va, rgrid_power_pf))
print()
print("Inverter data:")
print("Voltage: %3.1fV\t\tCurrent: %1.3fA\t\tFrequency: %2.2fHz" % (rinv_volt, rinv_current, rinv_freq))
print("Active Power: %dW\tApparent Power: %dW\tPower factor: %1.3f" % (rinv_power_watt, rinv_power_va, rinv_pf))
print("Master Bus voltage: %3.1fV\tSlave bus voltage:%3.1fV" % (bus_volt_master, bus_volt_slave))
print()
print("Output data:")
print("Voltage: %3.1fV\t\tCurrent: %1.3fA\t\tFrequency: %2.2fHz" % (rout_volt, rout_curr, rout_freq))
print("DC voltage: %dmV\tActive Power: %dW\tApparent power: %dW\tPower factor: %3.1f" % (rout_dvi, rout_power_watt, rout_power_va, rout_pf))
print()
print("Battery data:")
print("Voltage: %3.1fV\t\tCurrent: %1.3fA\t\tControl Current 1: %1.3fA\tControl Current 2: %1.3fA" % (bat_volt, bat_curr, bat_curr1, bat_curr2))
print("Power: %dW, %dVA\t\tTemperature: %3.1f °C\tCharge: %3.2f%%" % (bat_power, bat_power2, bat_tempc, bat_percent))
print()
print("Photovoltaic Arrays:")
print("Array #1:\tVoltage: %3.1fV\t\tCurrent: %3.1fA\t\tPower: %dW" % (pv1_volt, pv1_curr, pv1_power))
print("Array #2:\tVoltage: %3.1fV\t\tCurrent: %3.1fA\t\tPower: %dW" % (pv2_volt, pv2_curr, pv2_power))
print()
print("Current direction:")
print("Photovoltaic: %s - Battery: %s - Grid: %s - Output: %s" % (dir_pv, dir_bat, dir_grid, dir_output))
print()
print("Power summary:")
print("System total: %dW\t\tPhotovoltaic total: %dW\tBattery total: %dW\tGrid total: %dW (%dVA)" % (sys_total_load_watt, total_pv_power, total_battery_power, total_grid_power_watt, total_grid_power_va))
print("Inverter power: %dW (%dVA)\tBackup load: %dW (%dVA)\tunkown parameter: %dW" % (total_inverter_power_watt, total_grid_power_va,
                                                                                      backup_total_load_power_watt, backup_total_load_power_va,
                                                                                    unknown_power))
print("Smart meter power: %dW" % (smart_meter_load_watt,))

print()
for item in stats:
      name, daily, monthly, yearly, total = item
      print("%s energy\tToday: %0.2f KWh\t\tMonth: %0.2f KWh\t\tYear: %0.2f KWh\t\tTotal: %0.2f KWh" % (name, daily, monthly, yearly, total))
