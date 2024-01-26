# saj_mqtt
Home Assistant integration for SAJ H1 inverters
This custom integration provides MQTT integration for SAJ H1 inverters and some other compatibile models. \
**DISCLAIMER:** this is a heavy work in progress, I won't be responsible for any kind of loss during it usage, the integration is provided AS-IS.

## Configure Home Assistant MQTT broker
This integration uses the MQTT services already configured in Home Assistant to communicate with the inverter and retrieve the data, for this reason you need to first setup a broker and configure Home Assistant to talk to using the standard MQTT integration. Of course, if you already have MQTT configured, you don't need to do this again.

## Install the integration
Copy content of **custom_components** into your Home Assistant custom components directory (for example: `/home/homeassistant/.homeassistant/custom_components/saj_mqtt`).

Edit Home Assistant **configuration.yaml** (usually found in `/home/homeassistant/.homeassistant/configuration.yaml`) and add the following section:
```YAML
saj_mqtt:
    serial_number: {inverter_serial_number}
    scan_interval: {scan_interval}
    scan_interval_inverter_info: {scan_interval_inverter_info}
    scan_interval_battery_info: {scan_interval_battery_info}
    scan_interval_battery_controller: {scan_interval_battery_controller}
    scan_interval_config: {scan_interval_config}
    debug_mqtt: {debug_mqtt}
```

- `{inverter_serial_number}` is the inverter serial number (required, f.e. `H1S2xxxxxxxxxxxxxx`)
- `{scan_interval}` is the scan interval for the realtime data (optional, defaults to `60`)
- `{scan_interval_inverter_info}` is the scan interval for the inverter info data (optional, defaults to `None`)
- `{scan_interval_battery_info}` is the scan interval for the battery info data (optional, defaults to `None`)
- `{scan_interval_battery_controller}` is the scan interval for the battery controller data (optional, defaults to `None`)
- `{scan_interval_config}` is the scan interval for the config data (optional, defaults to `None`)
- `{debug_mqtt}` is the flag to indicate detailed mqtt debugging is needed (optional, defaults to `False`)

All scan intervals can be configured as a positive timedelta:

- in seconds: `60`
- in time string: `"00:01:00"`
- in timedelta dict format:
  ```
  scan_interval:
    days: 0
    hours: 0
    minutes: 0
    seconds: 60
  ```

If a scan interval is not defined, the related dataset and sensors will not be fetched and loaded.

Only the realtime dataset will always be fetched by default.

## Configure the inverter
The last step is to configure the inverter (actually the Wifi communication module AIO3 attached to the inverter) to talk with the local MQTT broker and not directly with the SAJ broker; to do that, you have two options:

- Change the MQTT broker using eSAJ Home app (see [this](https://play.google.com/store/apps/details?id=com.saj.esolarhome)) to your local MQTT broker.
- Poison your local DNS to redirect the MQTT messages to your broker. This consists in telling your home router to point to your broker IP when domain **mqtt.saj-solar.com** is queried by the inverter, so refer to your router capabilities to handle this. This may require some time for the inverter to discover that the broker IP changed, so you may want to remove and reinstall the Wifi AIO3 module to restart it. Optionally, you can additionally bridge your local MQTT broker to SAJ mqtt broker if you still want to use the eSAJ Home app. For instructions, see [this](https://github.com/paolosabatino/saj-mqtt-ha/discussions/4).

