import os
import threading
import logging
from cortex import Cortex
import time

# Silence unwanted logs
logging.getLogger().setLevel(logging.ERROR)

class MetAttentionLogger:
    def __init__(self, client_id, client_secret, **kwargs):
        self.cortex = Cortex(client_id, client_secret, debug_mode=False, **kwargs)
        self.cortex.bind(create_session_done=self.on_session_ready)
        self.cortex.bind(new_met_data=self.on_new_met_data)
        self.last_print_time = 0
        self.print_interval = 10  # seconds

    def start(self, duration=10, headset_id=''):
        self.streams = ['met']
        if headset_id:
            self.cortex.set_wanted_headset(headset_id)
        self.cortex.open()
        threading.Timer(duration, self.stop).start()

    def stop(self):
        self.cortex.unsub_request(self.streams)
        self.cortex.close()
        os._exit(0)

    def on_session_ready(self, *args, **kwargs):
        print("Connected to Cortex. Subscribing to 'met' stream...")
        self.cortex.sub_request(self.streams)

    def on_new_met_data(self, *args, **kwargs):
        current_time = time.time()
        if current_time - self.last_print_time < self.print_interval:
            return

        data = kwargs.get('data', {})
        met = data.get('met', [])
        timestamp = data.get('time', None)

        # foc.isActive = index 11, foc = index 12
        if len(met) > 12 and met[11] and met[12] is not None:
            raw_attention = met[12]
            if not (0 <= raw_attention <= 1):
                print(f"⚠️ Unexpected attention value: {raw_attention}")
            attention = round(min(max(raw_attention, 0), 1) * 10, 2)
            status = "Attention Low" if attention < 8.2 else "Normal"
            print(f"{timestamp}: Attention={attention} → {status}")
            self.last_print_time = current_time

def main():
    print("🔧 Starting met.py...")

    your_app_client_id = 'fuzggT9x1AydQhgGJ2adj6vDC4KM5Hm3tEFY5hJO'
    your_app_client_secret = 'bQgM4tjsSmxSF0N4qmKiMA46HkogPQnvn92Tkvl8iXYfoUWuC49n9NFgbd3MXXqCZ35MqEmmGqrkEecmtRmvmmGmweZyRD7cETdbDQegW033hxK8vGsbwQImhLSlXlSj'

    logger = MetAttentionLogger(
        client_id=your_app_client_id,
        client_secret=your_app_client_secret,
        license='0657f307-6ab8-4f14-9c93-be103633fd58'
    )

    logger.start(duration=30)

if __name__ == '__main__':
    print("hello")
    main()
