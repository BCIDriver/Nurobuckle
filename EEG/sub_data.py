import os
import json
import time
import threading
from cortex import Cortex
import logging

# Suppress unwanted logs from specific libraries
logging.getLogger("websocket").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger().setLevel(logging.ERROR)

class Subcribe:
    def __init__(self, app_client_id, app_client_secret, **kwargs):
        self.c = Cortex(app_client_id, app_client_secret, debug_mode=False, **kwargs)
        self.c.bind(create_session_done=self.on_create_session_done)
        self.c.bind(new_data_labels=self.on_new_data_labels)
        self.c.bind(new_eeg_data=self.on_new_eeg_data)
        self.c.bind(new_mot_data=self.on_new_mot_data)
        self.c.bind(new_dev_data=self.on_new_dev_data)
        self.c.bind(new_met_data=self.on_new_met_data)
        self.c.bind(new_pow_data=self.on_new_pow_data)
        self.c.bind(inform_error=self.on_inform_error)
        self.metrics_log = []

    def start(self, streams, headsetId=''):
        self.streams = streams 
        if headsetId:
            self.c.set_wanted_headset(headsetId)
        self.c.open()
        threading.Timer(10, self.stop).start()

    def stop(self):
        self.unsub(self.streams)
        self.c.close()
        os._exit(0)  # Force exit to stop lingering threads

    def sub(self, streams):
        self.c.sub_request(streams)

    def unsub(self, streams):
        self.c.unsub_request(streams)

    def on_new_data_labels(self, *args, **kwargs):
        pass

    def on_new_eeg_data(self, *args, **kwargs):
        pass

    def on_new_mot_data(self, *args, **kwargs):
        pass

    def on_new_dev_data(self, *args, **kwargs):
        pass

    def on_new_met_data(self, *args, **kwargs):
        data = kwargs.get('data')
        timestamp = data.get('time', None)
        met_values = data.get('met', [])
        raw_attention = met_values[12]  # 'foc'
        scaled_attention = round(raw_attention * 10, 2) if raw_attention is not None else None
        print(f"{timestamp}:  Attention = {scaled_attention}/10")

    def connect_to_mcp(self):
        pass

    def on_inform_error(self, *args, **kwargs):
        pass

    def on_new_pow_data(self, *args, **kwargs):
        pass

    def on_create_session_done(self, *args, **kwargs):
        self.sub(self.streams)

def main():
    your_app_client_id = 'fuzggT9x1AydQhgGJ2adj6vDC4KM5Hm3tEFY5hJO'
    your_app_client_secret = 'bQgM4tjsSmxSF0N4qmKiMA46HkogPQnvn92Tkvl8iXYfoUWuC49n9NFgbd3MXXqCZ35MqEmmGqrkEecmtRmvmmGmweZyRD7cETdbDQegW033hxK8vGsbwQImhLSlXlSj'
    s = Subcribe(
        your_app_client_id,
        your_app_client_secret,
        license='0657f307-6ab8-4f14-9c93-be103633fd58'
    )
    streams = ['met']
    s.start(streams)

if __name__ == '__main__':
    main()