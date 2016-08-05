

sudo salt "salt-master" ceph_sles.new_ceph_cfg mon-osd-node1 mon-osd-node2 mon-osd-node3

sudo salt 'salt-master' ceph_sles.new_key_pillar

sudo salt 'salt-master' ceph_sles.new_osd_pillar "mon-osd-node1,mon-osd-node2,mon-osd-node3" "/dev/sdb,/dev/sdc"

sudo salt '*' state.sls ses.ceph.ceph_create


