install_iperf:
  pkg.installed:
    - name: iperf


/usr/lib/systemd/system/iperf.service:
  file.managed:
    - source:
      - salt://_systemd/iperf.service
    - mode: 644

enable iperf systemd:
  module.run:
    - name: service.enable
    - m_name: iperf

start iperf systemd:
  module.run:
    - name: service.start
    - m_name: iperf

make_sure_iperf_is_running:
  service.running:
    - name: iperf
    - enable: True
    - require:
      - pkg:  install_iperf
