import signal
from threading import Event

from django.core.management.base import BaseCommand
from swo.mpt.extensions.runtime.events.dispatcher import Dispatcher
from swo.mpt.extensions.runtime.events.producers import OrderEventProducer
from swo_aws_extension.shared import mpt_client


class Command(BaseCommand):
    help = "Consume events from the MPT platform"
    producer_classes = [
        OrderEventProducer,
    ]
    producers = []

    def handle(self, *args, **options):
        self.shutdown_event = Event()
        self.dispatcher = Dispatcher(mpt_client)
        self.dispatcher.start()

        def shutdown(signum, frame):
            self.shutdown_event.set()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        for producer_cls in self.producer_classes:
            producer = producer_cls(mpt_client, self.dispatcher)
            self.producers.append(producer)
            producer.start()

        self.shutdown_event.wait()
        for producer in self.producers:
            producer.stop()
        self.dispatcher.stop()
