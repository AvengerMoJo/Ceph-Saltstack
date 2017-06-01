install_lttng:
  pkg.installed:
    - name: lttng-modules lttng-tools lttng-ust 


/usr/lib/systemd/system/lttng.service:
  file.managed:
    - source:
      - salt://_systemd/lttng.service
    - mode: 644

enable lttng systemd:
  module.run:
    - name: service.enable
    - m_name: lttng

start lttng systemd:
  module.run:
    - name: service.start
    - m_name: lttng

make_sure_lttng_is_running:
  service.running:
    - name: lttng
    - enable: True
    - require:
      - pkg:  install_lttng
