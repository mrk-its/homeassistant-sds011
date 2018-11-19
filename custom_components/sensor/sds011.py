"""
Support for SDS011 Particulate matter sensor
"""
import datetime
import logging
import threading
import time

import voluptuous as vol

from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

REQUIREMENTS = ["https://github.com/mrk-its/py-sds011/archive/v0.9.zip#py-sds011==0.9"]

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_DEVICE = "serial_device"
CONF_MEASURE_INTERVAL = "measure_interval"
CONF_WARMUP_DELAY = "warmup_delay"
CONF_NUMBER_OF_MEASUREMENTS = "number_of_measurements"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERIAL_DEVICE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_MEASURE_INTERVAL): cv.time_period,
        vol.Optional(CONF_WARMUP_DELAY): cv.time_period,
        vol.Optional(CONF_NUMBER_OF_MEASUREMENTS): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    collector = Collector(
        config.get(CONF_SERIAL_DEVICE),
        config.get(CONF_NAME),
        config.get(CONF_MEASURE_INTERVAL, datetime.timedelta(seconds=60)),
        config.get(CONF_WARMUP_DELAY, datetime.timedelta(seconds=15)),
        config.get(CONF_NUMBER_OF_MEASUREMENTS, 5),
    )

    add_entities(collector.get_entities())
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, lambda *args: collector.terminate())

    collector.start()


def avg(data):
    data = [v for v in data if v is not None]
    if data:
        return sum(data) / len(data)


class Collector(threading.Thread):
    def __init__(
        self, device, name, measure_interval, warmup_delay, number_of_measurements
    ):
        import sds011

        super(Collector, self).__init__()
        self._finish_event = threading.Event()

        self._sleep = warmup_delay.total_seconds() > 0
        self._warmup_delay = warmup_delay
        self._measure_interval = measure_interval
        self._number_of_measurements = number_of_measurements

        _LOGGER.info("measure_interval: %s", self._measure_interval.total_seconds())
        _LOGGER.info("warmup_delay: %s", self._warmup_delay.total_seconds())

        self._sensor = sds011.SDS011(device, use_query_mode=True)
        self._sensor.sleep(self._sleep)

        self._entities = [Sensor(name, "PM2.5"), Sensor(name, "PM10")]

    def get_entities(self):
        return self._entities

    def _wait(self, t):
        self._finish_event.wait(t)

    def run(self):

        while not self._finish_event.is_set():
            t0 = time.time()
            if self._sleep:
                _LOGGER.debug("Warming up sensor, delay: %s", self._warmup_delay)
                self._sensor.sleep(sleep=False)
                self._wait(self._warmup_delay.total_seconds())

            measurements = []
            for _ in range(self._number_of_measurements):
                measurements.append(self._sensor.query())
                self._wait(1.0)

            avg_measurements = [avg(values) for values in zip(*measurements)]

            for entity, value in zip(self._entities, avg_measurements):
                if value is not None:
                    entity.state = round(value, 1)

            if self._sleep:
                self._sensor.sleep()

            delay = time.time() - t0

            self._wait(max(0, self._measure_interval.total_seconds() - delay))

        _LOGGER.info("Collector thread finished")

    def terminate(self):
        self._finish_event.set()
        self.join()


class Sensor(Entity):
    unit_of_measurement = "µg/m³"

    def __init__(self, name, kind):
        self._name = name
        self._kind = kind
        self._state = None

    def should_poll(self):
        return False

    @property
    def name(self):
        return " ".join(filter(bool, (self._name, self._kind)))

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value
        _LOGGER.info("%s: %s", self.name, value)

        if self.hass:
            self.schedule_update_ha_state()
