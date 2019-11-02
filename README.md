# homeassistant-sds011
 Home-Assistant Component for SDS011 Particulate Matter Sensor, with support for turning off sensor between measurements for longer laser life.

Place the sds011 directory in your configuration/custom_components directory

Add the following to configuration.yml:
```
sensor:
 - platform: sds011
   serial_device: /dev/ttyUSB0  # required
   name: outside  # optional
   measure_interval: 150  # optional
   warmup_delay: 25  # optional
   number_of_measurements: 5  # optional
```
