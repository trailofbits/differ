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
from differ.core import ComparisonResult

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

    def test_pcap_filename_abs(self):
        trace = MagicMock(cwd=Path('/path/to/trace'))
        config = PcapComparatorConfig(Path('/capture.pcap'), Protocol.tcp, 8080)
        assert config.pcap_filename(trace) == Path('/capture.pcap')

    def test_pcap_filename_rel(self):
        trace = MagicMock(cwd=Path('/path/to/trace'))
        config = PcapComparatorConfig(Path('capture.pcap'), Protocol.tcp, 8080)
        assert config.pcap_filename(trace) == Path('/path/to/trace/capture.pcap')

    def test_describe_filter(self):
        config = PcapComparatorConfig(Path('capture.pcap'), Protocol.tcp, 8080)
        assert len(config.describe_filter()) > 0


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

    def test_compare_flow_match(self):
        orig = Flow(
            'client', 'server', [Payload('client', b'hello'), Payload('server', 'goodbye')]
        )
        debloated = Flow(
            'client', 'server', [Payload('client', b'hello'), Payload('server', 'goodbye')]
        )
        ext = PcapComparator(TCP_CONFIG)

        assert ext.compare_flow(orig, debloated) is None

    def test_compare_flow_client_not_equal(self):
        orig = Flow('client', 'server', [])
        debloated = Flow('client2', 'server2', [])
        ext = PcapComparator(TCP_CONFIG)
        assert ext.compare_flow(orig, debloated) is not None

    def test_compare_flow_count_not_equal(self):
        orig = Flow('client', 'server', [Payload('client', b'hello')])
        debloated = Flow('client', 'server', [])
        ext = PcapComparator(TCP_CONFIG)
        assert ext.compare_flow(orig, debloated) is not None

    def test_compare_flow_payload_not_equal(self):
        orig = Flow('client', 'server', [Payload('client', b'hello')])
        debloated = Flow('client', 'server', [Payload('client', b'goodbye')])
        ext = PcapComparator(TCP_CONFIG)
        assert ext.compare_flow(orig, debloated) is not None

    def test_compare_flows_match(self):
        orig = [Flow('client', 'server')]
        debloated = [Flow('client', 'server')]
        ext = PcapComparator(TCP_CONFIG)
        ext.compare_flow = MagicMock(return_value=None)
        assert ext.compare_flows(orig, debloated) is None
        ext.compare_flow.assert_called_once_with(orig[0], debloated[0])

    def test_compare_flows_count_not_equal(self):
        orig = [Flow('client', 'server'), Flow('client2', 'server')]
        debloated = [Flow('client', 'server')]
        ext = PcapComparator(TCP_CONFIG)
        ext.compare_flow = MagicMock(return_value=None)
        assert ext.compare_flows(orig, debloated) is not None

    def test_compare_flows_not_equal(self):
        orig = [Flow('client', 'server')]
        debloated = [Flow('client', 'server')]
        ext = PcapComparator(TCP_CONFIG)
        ext.compare_flow = MagicMock(return_value='uh oh')
        assert ext.compare_flows(orig, debloated) == 'uh oh'
        ext.compare_flow.assert_called_once_with(orig[0], debloated[0])

    @patch('differ.comparators.pcap.rdpcap')
    def test_verify_original_success(self, mock_rdpcap):
        pcap_file = MagicMock()
        trace = MagicMock(cache={})
        ext = PcapComparator(TCP_CONFIG)
        ext.config.pcap_filename = MagicMock(return_value=pcap_file)
        ext._filter_pcap = MagicMock()
        ext.extract_flows = MagicMock()

        assert ext.verify_original(trace) is None
        mock_rdpcap.assert_called_once_with(pcap_file.open.return_value)
        ext._filter_pcap.assert_called_once_with(mock_rdpcap.return_value)
        assert trace.cache[ext.flow_cache_key()] is ext.extract_flows.return_value

    @patch('differ.comparators.pcap.rdpcap')
    def test_verify_original_no_packets(self, mock_rdpcap):
        pcap_file = MagicMock()
        trace = MagicMock(cache={})
        ext = PcapComparator(TCP_CONFIG)
        ext.config.pcap_filename = MagicMock(return_value=pcap_file)
        ext._filter_pcap = MagicMock(return_value=[])
        ext.extract_flows = MagicMock()

        result = ext.verify_original(trace)
        assert result
        assert result.comparator is ext
        assert result.trace is trace

    @patch('differ.comparators.pcap.rdpcap')
    def test_verify_original_no_file(self, mock_rdpcap):
        pcap_file = MagicMock()
        pcap_file.is_file.return_value = False
        trace = MagicMock(cache={})
        ext = PcapComparator(TCP_CONFIG)
        ext.config.pcap_filename = MagicMock(return_value=pcap_file)
        ext._filter_pcap = MagicMock()
        ext.extract_flows = MagicMock()

        result = ext.verify_original(trace)
        assert result
        assert result.comparator is ext
        assert result.trace is trace

    @patch('differ.comparators.pcap.rdpcap')
    def test_compare(self, mock_rdpcap):
        pcap_file = MagicMock()
        orig_flows = MagicMock()
        orig = MagicMock(cache={})
        debloated = MagicMock()
        ext = PcapComparator(TCP_CONFIG)

        ext.config.pcap_filename = MagicMock(return_value=pcap_file)
        ext._filter_pcap = MagicMock()
        ext.extract_flows = MagicMock()
        ext.compare_flows = MagicMock(return_value=None)
        orig.cache = {ext.flow_cache_key(): orig_flows}

        assert ext.compare(orig, debloated) == ComparisonResult.success(ext, debloated)
        mock_rdpcap.assert_called_once_with(pcap_file.open.return_value)
        ext._filter_pcap.assert_called_once_with(mock_rdpcap.return_value)
        ext.extract_flows.assert_called_once_with(ext._filter_pcap.return_value)
        ext.compare_flows.assert_called_once_with(orig_flows, ext.extract_flows.return_value)

    def test_compare_no_file(self):
        pcap_file = MagicMock()
        pcap_file.is_file.return_value = False
        orig = MagicMock()
        debloated = MagicMock()

        ext = PcapComparator(TCP_CONFIG)
        ext.config.pcap_filename = MagicMock(return_value=pcap_file)

        result = ext.compare(orig, debloated)
        assert result == ComparisonResult.error(ext, debloated, result.details)

    @patch('differ.comparators.pcap.rdpcap')
    def test_compare_error(self, mock_rdpcap):
        pcap_file = MagicMock()
        orig_flows = MagicMock()
        orig = MagicMock(cache={})
        debloated = MagicMock()
        ext = PcapComparator(TCP_CONFIG)

        ext.config.pcap_filename = MagicMock(return_value=pcap_file)
        ext._filter_pcap = MagicMock()
        ext.extract_flows = MagicMock()
        ext.compare_flows = MagicMock(return_value='uh oh')
        orig.cache = {ext.flow_cache_key(): orig_flows}

        assert ext.compare(orig, debloated) == ComparisonResult.error(ext, debloated, 'uh oh')
        mock_rdpcap.assert_called_once_with(pcap_file.open.return_value)
        ext._filter_pcap.assert_called_once_with(mock_rdpcap.return_value)
        ext.extract_flows.assert_called_once_with(ext._filter_pcap.return_value)
        ext.compare_flows.assert_called_once_with(orig_flows, ext.extract_flows.return_value)
