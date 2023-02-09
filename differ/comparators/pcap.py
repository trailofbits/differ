# spell-checker:ignore rdpcap scapy sport dport
# import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from scapy.layers.inet import IP, TCP, UDP
from scapy.packet import Packet, Raw
from scapy.plist import PacketList
from scapy.utils import rdpcap

from differ.core import Comparator, ComparisonResult, CrashResult, Trace

from . import register

# logger = logging.getLogger(__name__)


@dataclass
class Payload:
    """
    A single packet payload for a flow. The payload ``data`` should be extracted based on the
    underlying protocol. For example, an HTTP flow should set ``data`` to the request or response
    body.
    """

    #: The origin of the payload, either ``client`` or ``server``.
    origin: str
    data: bytes

    @classmethod
    def extract(cls, protocol: 'Protocol', origin: str, pkt: Packet) -> Optional['Payload']:
        """
        Attempt to extract the payload from the packet on a protocol-specific basis.

        :param protocol: configured protocol
        :param origin: the packet origin, either ``client`` or ``server``
        :param pkt: the packet
        :returns: the extracted payload if the payload is not empty
        """
        if protocol in (Protocol.tcp, Protocol.udp) and Raw in pkt:
            if data := pkt[Raw].load:
                return Payload(origin, data)
        return None


@dataclass
class Flow:
    """
    A single flow within a pcap file. A flow is a unique set of source and destination address and
    port. The ``client`` is the address that initiated the communication, either by the TCP CONNECT
    or the first UDP packet and the serve is the address that receives the first packet.

    Each flow may have multiple application layer ``payloads``.
    """

    client: str
    server: str
    payloads: list[Payload] = field(default_factory=list)

    def describe(self) -> str:
        """
        :returns: a brief description of the flow
        """
        return f'{self.client}->{self.server}'


class Protocol(Enum):
    """
    Supported network protocols.
    """

    tcp = TCP
    udp = UDP


@dataclass
class PcapComparatorConfig:
    """
    The configuration for the pcap comparator.
    """

    #: The pcap filename, relative to the trace working directory
    filename: Path
    #: Filter packets to a specific protocol
    protocol: Protocol
    #: Filter packets to a specific port matching on either the source or destination port
    port: int
    #: Filter packets to a specific address matching on either the source or destination address
    address: str = ''
    #: Compare flow payloads
    compare_payload: bool = True
    #: The flow must exist
    exists: bool = True

    @classmethod
    def parse(cls, config: dict) -> 'PcapComparatorConfig':
        return cls(
            filename=Path(config['filename']),
            protocol=Protocol[config['protocol']],
            port=int(config['port']),
            address=config.get('address', ''),
            compare_payload=config.get('compare_payload', True),
            exists=config.get('exists', True)
        )

    def describe_filter(self) -> str:
        return f'{self.protocol.name}/{self.address or "*"}:{self.port}'

    def pcap_filename(self, trace: Trace) -> Path:
        if self.filename.is_absolute():
            return self.filename
        return trace.cwd / self.filename


@register('pcap')
class PcapComparator(Comparator):
    """
    The pcap file comparator.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.config = PcapComparatorConfig.parse(config)

    def verify_original(self, original: Trace) -> Optional[CrashResult]:
        filename = self.config.pcap_filename(original)
        if not filename.is_file():
            return CrashResult(original, f'pcap file does not exist: {filename}', self)

        pcap = rdpcap(filename.open('rb'))
        packets = self._filter_pcap(pcap)

        if packets and not self.config.exists:
            # There are packets that we did not expect
            return CrashResult(
                original, f'unexpected flow in pcap: {self.config.describe_filter()}', self
            )
        elif self.config.exists and not packets:
            # There are no packets when we expected some
            return CrashResult(
                original, f'flow does not exist in pcap: {self.config.describe_filter()}', self
            )

        original.cache[self.flow_cache_key()] = self.extract_flows(packets)

    def compare(self, original: Trace, debloated: Trace) -> ComparisonResult:
        original_flows = original.cache[self.flow_cache_key()]

        filename = self.config.pcap_filename(debloated)
        if not filename.is_file():
            return ComparisonResult.error(self, debloated, f'pcap file does not exist: {filename}')

        pcap = rdpcap(filename.open('rb'))
        packets = self._filter_pcap(pcap)

        if not self.config.exists:
            # We expect that the flow does not exist
            if packets:
                # Error: the flow exists
                return ComparisonResult.error(self, debloated, f'unexpected flow in pcap: {self.config.describe_filter()}')
            else:
                return ComparisonResult.success(self, debloated)

        debloated_flows = self.extract_flows(packets)

        if error := self.compare_flows(original_flows, debloated_flows):
            return ComparisonResult.error(self, debloated, error)

        return ComparisonResult.success(self, debloated)

    def compare_flows(
        self, original_flows: list[Flow], debloated_flows: list[Flow]
    ) -> Optional[str]:
        diff_count = len(original_flows) - len(debloated_flows)
        if diff_count:
            direction = 'more' if diff_count > 0 else 'less'
            return f'the original trace has {direction} flows than the debloated trace'

        for original_flow, debloated_flow in zip(original_flows, debloated_flows):
            if error := self.compare_flow(original_flow, debloated_flow):
                return error

        return None

    def compare_flow(self, original_flow: Flow, debloated_flow: Flow) -> Optional[str]:
        if (
            original_flow.client != debloated_flow.client
            and original_flow.server != debloated_flow.server
        ):
            return f'flows do not match: {original_flow.describe()} != {debloated_flow.describe()}'

        if not self.config.compare_payload:
            # do not compare flow payloads
            return None

        diff_count = len(original_flow.payloads) - len(debloated_flow.payloads)
        if diff_count:
            direction = 'more' if diff_count > 0 else 'less'
            return (
                f'the original flow has {direction} payloads than the debloated flow: '
                f'{original_flow.describe()}'
            )

        for original_payload, debloated_payload in zip(
            original_flow.payloads, debloated_flow.payloads
        ):
            if original_payload != debloated_payload:
                return f'mismatch payload for flow {original_flow.describe()}'

        return None

    def flow_cache_key(self) -> str:
        return f'{self.config.describe_filter()}_flows'

    def extract_flows(self, packets: list[Packet]) -> list[Flow]:
        flows_lookup: dict[str, Flow] = {}
        flows: list[Flow] = []
        proto = self.config.protocol.value
        for pkt in packets:
            source = f'{pkt[IP].src}:{pkt[proto].sport}'
            dest = f'{pkt[IP].dst}:{pkt[proto].dport}'
            key = '|'.join(sorted([source, dest]))
            flow = flows_lookup.get(key)
            if not flow:
                # logger.debug('detected new flow: %s -> %s', source, dest)
                flow = flows_lookup[key] = Flow(source, dest)
                flows.append(flow)

            origin = 'client' if source == flow.client else 'server'
            payload = Payload.extract(self.config.protocol, origin, pkt)
            if payload:
                # logger.debug(
                #     'detected new payload: %s -> %s: %s', source, dest, repr(payload.data)
                # )
                flow.payloads.append(payload)

        return flows

    def _filter_pcap(self, pcap: PacketList) -> list[Packet]:
        proto = self.config.protocol.value
        checks: list[Callable[[Packet], bool]] = [
            lambda pkt: proto in pkt and IP in pkt,
            lambda pkt: self.config.port in (pkt[proto].sport, pkt[proto].dport),
        ]

        if self.config.address:
            checks.append(lambda pkt: self.config.address in (pkt[IP].src, pkt[IP].dst))

        predicate = lambda pkt: all(check(pkt) for check in checks)  # noqa: E731
        return [pkt for pkt in pcap if predicate(pkt)]
