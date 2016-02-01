# Ceph-Saltstack
Rapid install, create, benchmark tools for ceph storage and create
a report of hardware 

Here is our git repo

	check out the https://github.com/AvengerMoJo/Ceph-Saltstack
	$> git clone https://github.com/AvengerMoJo/Ceph-Saltstack.git


Download the kiwi image with SLES12 and SES2 in the following link

	https://files.secureserver.net/0fCLysbi0hb8cr

USB boot and install the image to the node1, node2, node3 ... node9 etc.

Network configuration still need to fix the bond ip accordingly 

	/etc/sysconfig/network/ifcfg-bond0

	e.g. node1 
		IPADDR='192.168.128.201'

	e.g. node2 
		IPADDR='192.168.128.202'

Configure node ip starting from "node1" 192.168.128.201 as above. 
Once all the nodes are install e.g. node1 node2 node3 etc. 
Reboot or restart network service to the new node online. 

Inorder to create rapid deployment, you may want to have a VM or a 
laptop with the salt-master node install ahead of time and bring to 
the test hardware environment to perform the benchmark test. 

All the kiwi image point to Salt-Master Node with 192.168.128.200. 
Inside the Salt-Master node 

	Accept all node* minion key to get all the opperation started. 
		$> sudo salt-key -A 

	Test all the node* and see they are responding
		$> sudo salt "*" test.ping

	Copy git modules ceph_sles.py to /srv/salt/_modules/
	Copy iperf service iperf.service to /srv/salt/_systemd/
	Copy iperf sls iperf.sls to /srv/salt/
		$> export GIT_ROOT=Ceph-Saltstack
		$> sudo cp -r $GIT_ROOT/modules /srv/salt/_modules
		$> sudo cp -r $GIT_ROOT/system /srv/salt/_systemd
		$> sudo cp $GIT_ROOT/stages/* /srv/salt/

	Sync all file from Salt-Master node to node* 
		$> sudo salt 'node*' saltutil.sync_all

	Getting all Disk io read 
		$> sudo salt 'node*' ceph_sles.bench_disk /dev/sda /dev/sdb ... 

	Getting all hardware information and put that into a file
	( should be create a web service to receive and store those ) 
		$> sudo salt 'node*' ceph_sles.profile_node  > hardware_info.txt

	Getting all disk information including ssd or hdd  
		$> sudo salt 'node*' ceph_sles.disk_info > disk_info.txt

	Getting network information salt-master server to all nodes following
		$> sudo salt -L 'salt-master node1 node2 node3' ceph_sles.bench_network salt-master node1 node2 node3 > network_info.txt

	Create salt-master ssh key to all nodes ( not a must after ceph-deploy is removed )
		$> sudo salt 'salt-master' ceph_sles.keygen
		$> sudo salt 'salt-master' cehp_sles.send_key node1 node2 node3

The following is starting to create the cluster 

	Create new mons 
		$> sudo salt 'salt-master' ceph_sles.new_mon node1 node2 node3

	Push the new key and configuration file back to salt-master default directory /etc/ceph/
		$> sudo salt 'salt-master' ceph_sles.push_conf salt-master
	
	Create osd journal partition in sda with a 40G in size mount in /var/lib/ceph/osd/journal/ 
		$> sudo salt -L 'node1 node2 node3' ceph_sles.prep_osd journal /dev/sda 40G 

	Remove all partition of disk partition with list of partition seperated by ',' 
		$> sudo salt 'node*' ceph_sles.clean_disk_partition "/dev/sdb,/dev/sdc,/dev/sde"

	Prepare and Activate partition disk in each node list seperated by ',' and the list of disk seperated by ','
		$> sudo salt 'salt-master' ceph_sles.prep_osd "node1,node2,node3" "/dev/sdb,/dev/sdc,/dev/sde"

	Update crushmap to create ssd,hdd,mix disktype benchmark, create ruleset for ssd,hdd,mix 2 and 3 replicate
		$> sudo salt 'salt-master' ceph_sles.crushmap_update_disktype node1 node2 node3

The following is the actual benchmark test with rados 
	Create pool for ssd,hdd,mix with 2 and 3 replication and test read and write
		$> sudo salt 'salt-master' ceph_sles.bench_rados 

	

