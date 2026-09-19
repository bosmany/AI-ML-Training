from helpers import NOW

from lab import AuditConfig, audit_security_groups, exposed_ports


def cfg(**kw):
    return AuditConfig(now=NOW, sleep=lambda s: None, **kw)


def make_sg(ec2, name, permissions):
    gid = ec2.create_security_group(GroupName=name, Description=name)["GroupId"]
    if permissions:
        ec2.authorize_security_group_ingress(GroupId=gid, IpPermissions=permissions)
    return gid


def tcp(frm, to, cidr="0.0.0.0/0", v6=False):
    rng = {"Ipv6Ranges": [{"CidrIpv6": cidr}]} if v6 else {"IpRanges": [{"CidrIp": cidr}]}
    return {"IpProtocol": "tcp", "FromPort": frm, "ToPort": to, **rng}


def flagged(result):
    return sorted({f.resource for f in result.findings if f.check == "sg-open-ingress"})


def test_ssh_open_to_the_world_is_flagged_as_high(ec2):
    sg = make_sg(ec2, "ssh", [tcp(22, 22)])
    result = audit_security_groups(ec2, cfg())
    (f,) = [f for f in result.findings if f.resource == sg]
    assert f.severity == "high" and f.details["cidr"] == "0.0.0.0/0" and 22 in f.details["ports"]


def test_port_range_that_contains_a_sensitive_port_is_flagged(ec2):
    inside = make_sg(ec2, "range", [tcp(20, 30)])
    edge_low = make_sg(ec2, "edge", [tcp(22, 22 + 5)])
    below = make_sg(ec2, "below", [tcp(1, 21)])
    above = make_sg(ec2, "above", [tcp(23, 3305)])
    result = audit_security_groups(ec2, cfg())
    assert flagged(result) == sorted([inside, edge_low]), "range boundaries are inclusive; 1-21 and 23-3305 miss every sensitive port"
    assert below not in flagged(result) and above not in flagged(result)


def test_all_ports_range_lists_every_sensitive_port(ec2):
    sg = make_sg(ec2, "wide", [tcp(0, 65535)])
    (f,) = [f for f in audit_security_groups(ec2, cfg()).findings if f.resource == sg]
    assert f.details["ports"] == [22, 3306, 3389, 5432, 6379, 27017]


def test_protocol_minus_one_means_all_ports(ec2):
    sg = make_sg(ec2, "allproto", [{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
    (f,) = [f for f in audit_security_groups(ec2, cfg()).findings if f.resource == sg]
    assert f.details["ports"] == "all", "-1 has no FromPort/ToPort in the API response; treat it as everything"


def test_safe_rules_are_not_flagged(ec2):
    make_sg(ec2, "web", [tcp(80, 80), tcp(443, 443)])  # public but not sensitive
    make_sg(ec2, "internal", [tcp(22, 22, "10.0.0.0/8")])  # sensitive but private
    make_sg(ec2, "narrow", [tcp(22, 22, "0.0.0.0/32")])  # not the whole internet
    custom = make_sg(ec2, "custom", [tcp(8080, 8080)])  # only sensitive if the caller says so
    assert audit_security_groups(ec2, cfg()).findings == []
    assert flagged(audit_security_groups(ec2, cfg(sensitive_ports=frozenset({8080})))) == [custom]


def test_ipv4_and_ipv6_world_cidrs_each_get_a_finding(ec2):
    sg = make_sg(ec2, "both", [{"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
                                "IpRanges": [{"CidrIp": "0.0.0.0/0"}], "Ipv6Ranges": [{"CidrIpv6": "::/0"}]}])
    cidrs = sorted(f.details["cidr"] for f in audit_security_groups(ec2, cfg()).findings if f.resource == sg)
    assert cidrs == ["0.0.0.0/0", "::/0"], "IPv6 ::/0 is just as open as 0.0.0.0/0"


def test_exposed_ports_handles_protocol_variants():
    sensitive = frozenset({22, 3306})
    cases = [
        ({"IpProtocol": "icmp", "FromPort": -1, "ToPort": -1}, []),
        ({"IpProtocol": "6", "FromPort": 22, "ToPort": 22}, [22]),
        ({"IpProtocol": "udp", "FromPort": 3306, "ToPort": 3306}, [3306]),
        ({"IpProtocol": "-1"}, "all"),
    ]
    for perm, expected in cases:
        assert exposed_ports(perm, sensitive) == expected, f"wrong exposure for {perm}"
