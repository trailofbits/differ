from pathlib import Path
from unittest.mock import MagicMock

from differ.comparators.pcap import Flow, Payload, PcapComparator
from differ.core import ComparisonResult


class TestIntegrationPcapFile:
    def test_compare_tcp(self):
        original = MagicMock(cache={})
        debloated = MagicMock(cwd=Path(__file__).parent)

        ext = PcapComparator({'filename': 'memcached.pcap', 'port': '11211', 'protocol': 'tcp'})
        original.cache[ext.flow_cache_key()] = [
            Flow(
                '127.0.0.1:36024',
                '127.0.0.1:11211',
                [
                    Payload('client', b'stats settings'),
                    Payload('client', b'\r\n'),
                    Payload(
                        'server',
                        b'STAT maxbytes 67108864\r\nSTAT maxconns 1024\r\nSTAT tcpport 11211\r\nSTAT udpport 0\r\nSTAT inter 127.0.0.1\r\nSTAT verbosity 0\r\nSTAT oldest 0\r\nSTAT evictions on\r\nSTAT domain_socket NULL\r\nSTAT umask 700\r\nSTAT growth_factor 1.25\r\nSTAT chunk_size 48\r\nSTAT num_threads 4\r\nSTAT num_threads_per_udp 4\r\nSTAT stat_key_prefix :\r\nSTAT detail_enabled no\r\nSTAT reqs_per_event 20\r\nSTAT cas_enabled yes\r\nSTAT tcp_backlog 1024\r\nSTAT binding_protocol auto-negotiate\r\nSTAT auth_enabled_sasl no\r\nSTAT auth_enabled_ascii no\r\nSTAT item_size_max 1048576\r\nSTAT maxconns_fast yes\r\nSTAT hashpower_init 0\r\nSTAT slab_reassign yes\r\nSTAT slab_automove 1\r\nSTAT slab_automove_ratio 0.80\r\nSTAT slab_automove_window 30\r\nSTAT slab_chunk_max 524288\r\nSTAT lru_crawler yes\r\nSTAT lru_crawler_sleep 100\r\nSTAT lru_crawler_tocrawl 0\r\nSTAT tail_repair_time 0\r\nSTAT flush_enabled yes\r\nSTAT dump_enabled yes\r\nSTAT hash_algorithm murmur3\r\nSTAT lru_maintainer_thread yes\r\nSTAT lru_segmented yes\r\nSTAT hot_lru_pct 20\r\nSTAT warm_lru_pct 40\r\nSTAT hot_max_factor 0.20\r\nSTAT warm_max_factor 2.00\r\nSTAT temp_lru no\r\nSTAT temporary_ttl 61\r\nSTAT idle_timeout 0\r\nSTAT watcher_logbuf_size 262144\r\nSTAT worker_logbuf_size 65536\r\nSTAT track_sizes no\r\nSTAT inline_ascii_response no\r\nSTAT ssl_enabled no\r\nSTAT ssl_chain_cert (null)\r\nSTAT ssl_key (null)\r\nSTAT ssl_verify_mode 0\r\nSTAT ssl_keyformat 1\r\nSTAT ssl_ciphers NULL\r\nSTAT ssl_ca_cert NULL\r\nSTAT ssl_wbuf_size 16384\r\nEND\r\n',
                    ),
                    Payload('client', b'set x 0 0 5'),
                    Payload('client', b'\r\n'),
                    Payload('client', b'hello'),
                    Payload('client', b'\r\n'),
                    Payload('server', b'STORED\r\n'),
                    Payload('client', b'\r\n'),
                    Payload('server', b'ERROR\r\n'),
                    Payload('client', b'\r\n'),
                    Payload('server', b'ERROR\r\n'),
                    Payload('client', b'get x'),
                    Payload('client', b'\r\n'),
                    Payload('server', b'VALUE x 0 5\r\nhello\r\nEND\r\n'),
                    Payload('client', b'add x 0 0 4'),
                    Payload('client', b'\r\n'),
                    Payload('client', b'help'),
                    Payload('client', b'\r\n'),
                    Payload('server', b'NOT_STORED\r\n'),
                ],
            )
        ]
        assert ext.compare(original, debloated) == ComparisonResult.success(ext, debloated)
