install_iperf:
    pkg.installed:
        - name: iperf

make sure iperf is running:
    service.running:
        - name: iperf
        - enable: True
        - require:
            - pkg:  install_iperf
