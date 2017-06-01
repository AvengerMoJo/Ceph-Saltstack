# -*- coding: utf-8 -*-
'''
AvengerMoJo (alau@suse.com)
A lttng modules for salt to create and gether trace
result for lttng
'''

from __future__ import absolute_import

# python libs
from datetime import datetime
import logging
import os
import socket   # gethostname
from subprocess import PIPE, Popen

# salt libs
# import salt.client
# import salt.utils

__virtual_name__ = 'lttng'


log = logging.getLogger(__name__)

try:
    from salt.utils import which
except:
    from distutils.spawn import which

lttng_bin = which('lttng')

if lttng_bin is None:
    log.error("Error: could not find lttng on path")


def __virtual__():
    if not lttng_bin:
        return False
    return __virtual_name__


def run(cmd):
    '''
    CLI Example:
        .. code-block:: bash
        sudo salt 'node' lttng.run [ <cmd>, "arg", "arg2"....]

    lttng start and run cmd and the capture result for reporting as following:

    lttng create -o .
    lttng enable-channel --num-subbuf 16 --subbuf-size 8M -k c0
    lttng enable-event \
            sched_switch,\
            sched_process_fork,\
            sched_process_exec,\
            sched_process_exit,\
            sched_waking,\
            irq_handler_entry,\
            irq_handler_exit,\
            irq_softirq_entry,\
            irq_softirq_exit,\
            irq_softirq_raise,\
            sched_ttwu,\
            sched_process_wait,\
            sched_wait_task,\
            sched_migrate_task,\
            timer_init,\
            timer_start,\
            timer_expire_entry,\
            timer_expire_exit,\
            timer_hrtimer_init,\
            timer_hrtimer_start,\
            timer_hrtimer_cancel,\
            timer_hrtimer_expire_entry,\
            timer_hrtimer_expire_exit,\
            timer_itimer_expire,\
            sched_process_free,\
            sched_wakeup_new,\
            sched_wakeup,\
            sched_pi_setprio,\
            lttng_statedump_process_state,\
            x86_irq_vectors_ipi_entry,\
            x86_irq_vectors_ipi_exit,\
            inet_sock_local_in,\
            inet_sock_local_out,\
            lttng_statedump_interrupt -k -c c0
    lttng enable-event --syscall -a -k -c c0
    lttng start

    [cmd being run here]

    lttng stop
    lttng destroy
    '''
    lttng_run_path = '/var/run/lttng/'
    lttng_output_path = lttng_run_path + 'output/'
    date_now = datetime.now().strftime('%Y_%m_%d-%H_%M_%S')
    node = socket.gethostname()
    report_path = node + '-' + date_now

    if not os.path.exists(lttng_output_path):
        Popen(['/usr/bin/mkdir', '-p', lttng_output_path])
    lttng_log = __salt__['cmd.run']('lttng create -o ' + report_path,
                                    cwd=lttng_output_path)
    lttng_log += __salt__['cmd.run']('lttng enable-channel --num-subbuf 16'
                                     '--subbuf-size 8M -k c0',
                                     cwd=lttng_output_path)
    lttng_log += __salt__['cmd.run']('lttng enable-event \
            sched_switch,\
            sched_process_fork,\
            sched_process_exec,\
            sched_process_exit,\
            sched_waking,\
            irq_handler_entry,\
            irq_handler_exit,\
            irq_softirq_entry,\
            irq_softirq_exit,\
            irq_softirq_raise,\
            sched_ttwu,\
            sched_process_wait,\
            sched_wait_task,\
            sched_migrate_task,\
            timer_init,\
            timer_start,\
            timer_expire_entry,\
            timer_expire_exit,\
            timer_hrtimer_init,\
            timer_hrtimer_start,\
            timer_hrtimer_cancel,\
            timer_hrtimer_expire_entry,\
            timer_hrtimer_expire_exit,\
            timer_itimer_expire,\
            sched_process_free,\
            sched_wakeup_new,\
            sched_wakeup,\
            sched_pi_setprio,\
            lttng_statedump_process_state,\
            x86_irq_vectors_ipi_entry,\
            x86_irq_vectors_ipi_exit,\
            inet_sock_local_in,\
            inet_sock_local_out,\
            lttng_statedump_interrupt -k -c c0', cwd=lttng_output_path)
    lttng_log += __salt__['cmd.run']('lttng enable-event --syscall -a -k -c c0',
                                     cwd=lttng_output_path)
    lttng_log += __salt__['cmd.run']('lttng start', cwd=lttng_output_path)
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
    proc.wait()
    lttng_log += __salt__['cmd.run']('lttng stop', cwd=lttng_output_path)
    lttng_log += __salt__['cmd.run']('lttng destroy', cwd=lttng_output_path)
    return node, proc.returncode, proc.stdout.__read(), proc.stderr.__read()
