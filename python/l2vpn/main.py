# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service


# ------------------------
# SERVICE CALLBACK EXAMPLE
# ------------------------
class ServiceCallbacks(Service):

    # The create() callback is invoked inside NCS FASTMAP and
    # must always exist.
    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        # import pydevd_pycharm
        # pydevd_pycharm.settrace('localhost', port=30000, stdoutToServer=True, stderrToServer=True)
        
        self.log.info('Service create(service=', service._path, ')')

        service_name = service.name
        self.log.info('Provisioning L2VPN-VPWS Service custommer ID:', service_name)
        endpoint = service.endpoint
        if len(endpoint) != 2:
            self.log.debug('Error: VPWS service must have 2 endpoints')
        vcid = service.vcid

        for device in endpoint:
            device_name = device.device
            instance_id = device.instance_id
            platform = self.get_device_platform(root, service, device_name)
            remote_ip_loopback = self.get_remote_ip_loopback(root, service, device_name, endpoint)
            interface_type, interface_num = self.get_interface(root, service, device, platform)
            encapsulation = device.encapsulation
            vlan = device.vlan_id
            mtu = device.mtu

            vars = ncs.template.Variables()
            vars.add('DEVICE_NAME', device_name)
            vars.add('INST_ID', instance_id)
            vars.add('VC_ID', vcid)
            vars.add('INTERFACE_TYPE', interface_type)
            vars.add('INTERFACE_NUM', interface_num)
            vars.add('ENCAPSULATION', encapsulation)
            vars.add('VLAN', vlan)
            vars.add('MTU', mtu)
            for remote_name, remote_ip in remote_ip_loopback.items():
                self.log.debug("Add XC neighbor", remote_name, "IP", remote_ip)
                vars.add('NEIGHBOR', remote_ip)

            template = ncs.template.Template(service)
            template.apply('l2vpn-template', vars)

    def get_interface(self, root, service, device, platform):
        interface_type = ''
        interface_num = ''

        if platform == 'cisco-ios':
            interface = device.interface_ios
            for int_type in interface:
                if int_type.endswith('Ethernet'):
                    int_type = int_type.split(':')[-1]
                    if interface[int_type] is not None:
                        interface_type = int_type
                        interface_num = interface[int_type]
            # for int_type, int_num in interface:
            #     interface_type = int_type
            #     interface_num = int_num
        elif platform == 'cisco-iosxr':
            interface = device.interface_ios_xr
            for int_type in interface:
                if int_type.endswith('Ethernet'):
                    int_type = int_type.split(':')[-1]
                    if interface[int_type] is not None:
                        interface_type = int_type
                        interface_num = interface[int_type]
        else:
            self.log.info('No platform was found.')

        return interface_type, interface_num

    def get_device_platform(self, root, service, device_name):
        """
        Get device platform by looking in capability. eg: urn:ios, http://tail-f.com/ned/cisco-ios-xr.
        :param root:
        :param service:
        :return: dict of { device_name: str:platform, ... }
        """
        self.log.debug(" Executing in Module: get_device_platform ")

        device_platform = ''
        device_capability = root.devices.device[device_name].capability
        if 'urn:ios' in device_capability:
            device_platform = 'cisco-ios'
        elif 'http://tail-f.com/ned/cisco-ios-xr' in device_capability:
            device_platform = 'cisco-iosxr'
        else:
            self.log.debug("No device platform was found.")

        return device_platform

    def get_ip_loopback(self, root, service, device_name, platform, loopback_id=0):
        """
        Get IPv4 from interface loopback (default=0)
        :param root:
        :param service:
        :return:
        """
        self.log.debug(" Executing in Module: get_remote_ip_loopback ")

        ip_loopback = ''
        device_loopback_config = root.devices.device[device_name].config.interface.Loopback[str(loopback_id)]
        if platform == 'cisco-ios':
            ip_loopback = device_loopback_config.ip.address.primary.address
        if platform == 'cisco-iosxr':
            ip_loopback = device_loopback_config.ipv4.address.ip

        return ip_loopback

    def get_remote_ip_loopback(self, root, service, local_device, endpoint, loopback_id=0):
        """
        :param root:
        :param service:
        :param local: Device name
        :param endpoint: list of Devices
        :param loopback_id: default=0
        :return:
        """
        endpoints = endpoint
        remote_ip_loopback = dict()

        for endpoint in endpoints:
            device_name = endpoint.device
            if device_name != local_device:
                platform = self.get_device_platform(root, service, device_name)
                remote_ip_loopback[device_name] = self.get_ip_loopback(root, service, device_name, platform)

        return remote_ip_loopback




    # The pre_modification() and post_modification() callbacks are optional,
    # and are invoked outside FASTMAP. pre_modification() is invoked before
    # create, update, or delete of the service, as indicated by the enum
    # ncs_service_operation op parameter. Conversely
    # post_modification() is invoked after create, update, or delete
    # of the service. These functions can be useful e.g. for
    # allocations that should be stored and existing also when the
    # service instance is removed.

    # @Service.pre_lock_create
    # def cb_pre_lock_create(self, tctx, root, service, proplist):
    #     self.log.info('Service plcreate(service=', service._path, ')')

    # @Service.pre_modification
    # def cb_pre_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service premod(service=', kp, ')')

    # @Service.post_modification
    # def cb_post_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service premod(service=', kp, ')')


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        # The application class sets up logging for us. It is accessible
        # through 'self.log' and is a ncs.log.Log instance.
        self.log.info('Main RUNNING')

        # Service callbacks require a registration for a 'service point',
        # as specified in the corresponding data model.
        #
        self.register_service('l2vpn-servicepoint', ServiceCallbacks)

        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')
