# -*- coding: utf-8 -*-

import logging
# import os
import re
import socket
import time
from netaddr import IPNetwork, IPAddress
# from subprocess import PIPE, Popen

import salt.client

'''
lttng runner to conduct all the lttng in different nodes
'''
log = logging.getLogger(__name__)


def run(cluster=None, exclude=None, cmd=None, cmd_server=None, **kwargs):
    '''
    lttng tracing the cluster networkj
    CLI Example: (Before DeepSea with a cluster configuration)
    .. code-block:: bash
        sudo salt-run lttng_trace.run cluster=ceph exclude=10.0.0.2
        cmd='/full/path' cmd_server=minion_node
    or we can test it with a cluster
    '''
    cluster_addresses = []
    cluster_networks = []
    exclude_string = exclude_iplist = None
    if exclude:
        exclude_string, exclude_iplist = _exclude_filter(exclude)
    local = salt.client.LocalClient()
    # cluster mode run only the ip in private network
    if cluster:
        search = "I@cluster:{}".format(cluster)
        if exclude_string:
            search += " and not ( " + exclude_string + " )"
            log.debug("lttng.run: search {} ".format(search))

        cluster_networks = local.cmd(search, 'pillar.item', ['cluster_network'],
                                     expr_form="compound")
        log.debug("lttng.run: cluster_network {} ".format(cluster_networks))
        total = local.cmd(search, 'grains.get', ['ipv4'], expr_form="compound")
        log.debug("lttng.run: total grains.get {} ".format(total))

        for host in sorted(total.iterkeys()):
            if 'cluster_network' in cluster_networks[host]:
                cluster_addresses.extend(
                    _address(total[host],
                             cluster_networks[host]['cluster_network']))
            log.debug("lttng.run: cluster_network {}".format(cluster_addresses))

        log.debug("lttng.run: start {}".format(cluster_addresses))
        reports = _start(cluster_addresses)
        log.debug("lttng.run: report {}".format(reports))

    else:
        search = "*"
        if exclude_string:
            search += " and not ( " + exclude_string + " )"
            log.debug("lttng.run: search {} ".format(search))
        cluster_networks = local.cmd(search,
                                     'grains.get',
                                     ['ipv4'],
                                     expr_form="compound")
        log.debug("lttng.run: total grains.get {} ".format(cluster_networks))

        for host in sorted(cluster_networks.iterkeys()):
            log.debug("lttng.run: hostname minid{}".format(
                cluster_networks[host]))
            try:
                cluster_networks[host].remove('127.0.0.1')
            except ValueError:
                log.debug("lttng.run remove local interface fail")
                pass
            cluster_addresses.extend(cluster_networks[host])
            log.debug("lttng.run: cluster_network {}".format(cluster_addresses))

        log.debug("lttng.run: start {}".format(cluster_addresses))
        reports = _start(cluster_addresses)
        log.debug("lttng.run: report {}".format(reports))

    time.sleep(3)
    if not cmd_server:
        cmd_server = socket.gethostname()
    local = salt.client.LocalClient()
    log.debug("lttng.run cmd = {}".format(cmd))
    p = local.cmd("E@" + cmd_server, 'lttng.do_run', cmd, expr_form="compound")
    time.sleep(3)

    log.debug("lttng.run: cluster {}".format(cluster_addresses))
    reports = _finish(cluster_addresses, reports)
    log.debug("lttng.run: report_final {}".format(reports))
    return p


def _exclude_filter(excluded):
    """
    Internal exclude_filter return string in compound format

    Compound format = {'G': 'grain', 'P': 'grain_pcre', 'I': 'pillar',
                       'J': 'pillar_pcre', 'L': 'list', 'N': None,
                       'S': 'ipcidr', 'E': 'pcre'}
    IPV4 address = "255.255.255.255"
    hostname = "myhostname"
    """

    log.debug("_exclude_filter: excluding {}".format(excluded))
    excluded = excluded.split(",")
    log.debug("_exclude_filter: split ',' {}".format(excluded))

    pat_compound = re.compile("^.*([GPIJLNSE]\@).*$")
    pat_iplist = re.compile("^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]"
                            "|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}"
                            "|2[0-4][0-9]|25[0-5])$")
    pat_ipcidr = re.compile("^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25"
                            "[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4]"
                            "[0-9]|25[0-5])(\/([0-9]|[1-2][0-9]|3[0-2]))$")
    pat_hostlist = re.compile("^(([a-zA-Z]|[a-zA-Z][a-zA-Z0-9-]*[a-zA-Z0-9])"
                              ".)*([A-Za-z]|[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9])$"
                              ".)*([A-Za-z]|[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9])$")
    compound = []
    ipcidr = []
    iplist = []
    hostlist = []
    regex_list = []
    for para in excluded:
        if pat_compound.match(para):
            log.debug("_exclude_filter: Compound {}".format(para))
            compound.append(para)
        elif pat_iplist.match(para):
            log.debug("_exclude_filter: ip {}".format(para))
            iplist.append(para)
        elif pat_ipcidr.match(para):
            log.debug("_exclude_filter: ipcidr {}".format(para))
            ipcidr.append("S@"+para)
        elif pat_hostlist.match(para):
            hostlist.append("L@"+para)
            log.debug("_exclude_filter: hostname {}".format(para))
        else:
            regex_list.append("E@"+para)
            log.debug("_exclude_filter: not sure what this is "
                      "but likely Regex host {}".format(para))

    new_compound_excluded = " or ".join(
        compound + hostlist + regex_list + ipcidr)
    log.debug("_exclude_filter new formed compound excluded list = {}"
              .format(new_compound_excluded))
    if new_compound_excluded and iplist:
        return new_compound_excluded, iplist
    elif new_compound_excluded:
        return new_compound_excluded, None
    elif iplist:
        return None, iplist
    else:
        return None, None


def _address(addresses, network):
    """
    Return all addresses in the given network

    Note: list comprehension vs. netaddr vs. simple
    """
    matched = []
    for address in addresses:
        log.debug("_address: ip {} in network {} ".format(address, network))
        if IPAddress(address) in IPNetwork(network):
            matched.append(address)
    return matched


def _start(addresses, block_off=None):
    result = []
    local = salt.client.LocalClient()
    lttng_prepare = 'lttng.prepare'
    if(block_off):
        lttng_prepare = 'lttng.prepare block_off=ture'
    for server in addresses:
        log.debug("lttng._start: node {} ".format(server))
        local.cmd("S@" + server, 'lttng.clean_output', expr_form="compound")
        node_ip, dir_name = local.cmd("S@" + server, lttng_prepare,
                                      expr_form="compound").popitem()
        log.debug("lttng._start: dir_name {} ".format(dir_name))
        result.append(dir_name)
    return result


def _finish(addresses, reports):
    result = []
    local = salt.client.LocalClient()
    for server, report in zip(addresses, reports):
        log.debug("lttng._finish: {} get report {}".format(server, report))
        local.cmd("S@" + server, 'lttng.finish', expr_form="compound")
        node_ip, [node_name, isok] = local.cmd("S@" + server,
                                               'lttng.collect_file',
                                               [report],
                                               expr_form="compound").popitem()
        log.debug("lttng._finish: ip {} get node {} up {}".format(node_ip,
                                                                  node_name,
                                                                  isok))
        result.append([node_ip, node_name])
    return result
