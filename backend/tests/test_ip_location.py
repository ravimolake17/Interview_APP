from services.ip_location import normalize_client_ip, resolve_location_label


def test_normalize_strips_azure_forwarded_port():
    assert normalize_client_ip("152.59.63.215:49833") == "152.59.63.215"
    assert normalize_client_ip("36.255.8.59:64955") == "36.255.8.59"


def test_normalize_ipv6_brackets():
    assert normalize_client_ip("[2001:db8::1]:443") == "2001:db8::1"


def test_localhost_and_private_labels():
    assert resolve_location_label("127.0.0.1") == "Localhost"
    assert resolve_location_label("10.0.0.8") == "Private network"
    assert resolve_location_label("192.168.1.20:443") == "Private network"
    assert resolve_location_label("172.16.0.4") == "Private network"
