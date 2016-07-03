#!pyobjects

with Pkg.installed("ceph", names=["ceph", "salt-ceph", "python-ceph-cfg"]):
        File.managed("/etc/ceph/ceph.conf", source='file://home/ceph/.ceph_sles_cluster_config/ceph.conf', user='root', group='root', mode='644', makedir=True)


