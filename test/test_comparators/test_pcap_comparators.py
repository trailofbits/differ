from pathlib import Path
from unittest.mock import MagicMock, patch

from scapy.layers.inet import IP, TCP, UDP
from scapy.packet import Raw

from differ.comparators.pcap import (
    Flow,
    Payload,
    PcapComparator,
    PcapComparatorConfig,
    Protocol,
)

TCP_CONFIG = {
    'filename': 'capture.pcap',
    'protocol': 'tcp',
    'port': 8080,
}


class TestPayload:
    def test_extract_raw(self):
        data = object()
        pkt = {Raw: MagicMock(load=data)}
        assert Payload.extract(Protocol.tcp, 'client', pkt) == Payload('client', data)

    def test_extract_none(self):
        pkt = {}
        assert Payload.extract(Protocol.udp, 'server', pkt) is None


class TestFlow:
    def test_describe(self):
        assert Flow('127.0.0.1:8080', '8.8.8.8:443').describe() == '127.0.0.1:8080->8.8.8.8:443'


class TestComparatorConfig:
    def test_parse(self):
        assert PcapComparatorConfig.parse(
            {'filename': '/path/to/pcap', 'protocol': 'tcp', 'port': 8080, 'address': '127.0.0.1'}
        ) == PcapComparatorConfig(
            filename=Path('/path/to/pcap'), protocol=Protocol.tcp, port=8080, address='127.0.0.1'
        )

    def test_parse_no_address(self):
        assert PcapComparatorConfig.parse(
            {
                'filename': '/path/to/pcap',
                'protocol': 'tcp',
                'port': 8080,
            }
        ) == PcapComparatorConfig(
            filename=Path('/path/to/pcap'), protocol=Protocol.tcp, port=8080, address=''
        )


class TestPcapComparator:
    def test_filter_pcap(self):
        tcp1 = {TCP: MagicMock(sport=8081, dport=9091), IP: MagicMock()}
        tcp2 = {TCP: MagicMock(sport=8080, dport=9091), IP: MagicMock()}
        tcp3 = {TCP: MagicMock(sport=9091, dport=8080), IP: MagicMock()}
        udp = {UDP: MagicMock(sport=8080, dport=9091), IP: MagicMock()}
        packets = [tcp1, tcp2, udp, tcp3]
        ext = PcapComparator(TCP_CONFIG)
        assert ext._filter_pcap(packets) == [tcp2, tcp3]

    def test_filter_pcap_address(self):
        tcp1 = {
            TCP: MagicMock(sport=8081, dport=9091),
            IP: MagicMock(src='127.0.0.1', dst='127.0.0.1'),
        }
        tcp2 = {
            TCP: MagicMock(sport=8080, dport=9091),
            IP: MagicMock(src='8.8.8.8', dest='127.0.0.1'),
        }
        tcp3 = {
            TCP: MagicMock(sport=9091, dport=8080),
            IP: MagicMock(src='127.0.0.1', dst='8.8.8.8'),
        }
        udp = {UDP: MagicMock(sport=8080, dport=9091), IP: MagicMock()}
        packets = [tcp1, tcp2, udp, tcp3]
        ext = PcapComparator(TCP_CONFIG)
        ext.config.address = '8.8.8.8'
        assert ext._filter_pcap(packets) == [tcp2, tcp3]

    @patch.object(Payload, 'extract')
    def test_extract_flows(self, mock_extract):
        f1p1 = {
            IP: MagicMock(src='127.0.0.1', dst='8.8.8.8'),
            TCP: MagicMock(sport=8080, dport=443),
        }
        f1p2 = {
            IP: MagicMock(dst='127.0.0.1', src='8.8.8.8'),
            TCP: MagicMock(dport=8080, sport=443),
        }
        f2p1 = {
            IP: MagicMock(dst='127.0.0.1', src='1.1.1.1'),
            TCP: MagicMock(sport=9090, dport=80),
        }
        f2p2 = {
            IP: MagicMock(dst='127.0.0.1', src='1.1.1.1'),
            TCP: MagicMock(sport=9090, dport=80),
        }
        packets = [f1p1, f2p1, f1p2, f2p2]

        f1p1_payload = MagicMock()
        f1p2_payload = MagicMock()
        f2p1_payload = MagicMock()
        f2p2_payload = None
        mock_extract.side_effect = [f1p1_payload, f2p1_payload, f1p2_payload, f2p2_payload]

        ext = PcapComparator(TCP_CONFIG)
        assert ext.extract_flows(packets) == [
            Flow('127.0.0.1:8080', '8.8.8.8:443', [f1p1_payload, f1p2_payload]),
            Flow('1.1.1.1:9090', '127.0.0.1:80', [f2p1_payload]),
        ]
