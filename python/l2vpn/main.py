# -*- mode: python; python-indent: 4 -*-
import ncs
import re
from ncs.application import Service
from ncs.dp import Action


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
        devices = endpoint
        if len(devices) != 2:
            self.log.debug('Error: VPWS service must have 2 devices')
        vcid = service.vcid

        policy = service.policy
        policy_flag = False
        if policy is not None:
            unit = policy[-1]
            speed = policy[:-1]
            policy_name = "NSO-{}".format(policy)

            if unit == 'K':
                factor = 1000
            elif unit == 'M':
                factor = 1000000
            
            police_cir = int(int(speed)*1.1*factor)
            police_bc = int(round(police_cir/8/1.5))
            shape_avg = police_cir

            policy_flag = True

        for device in devices:
            device_name = device.name
            description = device.description
            platform = self.get_device_platform(root, service, device_name)
            remote_ip_loopback = self.get_remote_ip_loopback(root, service, device_name, devices)
            interface_type, interface_num = self.get_interface(root, service, device, platform)
            # encapsulation = device.encapsulation
            vlan = device.vlan_id
            mtu = device.mtu
            
            vars = ncs.template.Variables()
            if policy_flag:
                qos_vars = ncs.template.Variables()
                qos_vars.add('DEVICE_NAME', device_name)
                qos_vars.add('POLICY_NAME', policy_name)
                # qos_vars.add('SPEED', speed)
                qos_vars.add('POLICE_CIR', police_cir)
                qos_vars.add('POLICE_BC', police_bc)
                qos_vars.add('SHAPE_AVG', shape_avg)

                template = ncs.template.Template(service)
                template.apply('l2vpn-qos', qos_vars)

                policy_in = policy_name + '-IN'
                policy_out = policy_name + '-OUT'

                vars.add('POLICY_IN', policy_in)
                vars.add('POLICY_OUT', policy_out)

            vars.add('DEVICE_NAME', device_name)
            vars.add('DESCRIPTION', description)
            vars.add('VC_ID', vcid)
            vars.add('INTERFACE_TYPE', interface_type)
            vars.add('INTERFACE_NUM', interface_num)
            vars.add('VLAN', vlan)
            vars.add('MTU', mtu)
            
            for remote_name, remote_ip in remote_ip_loopback.items():
                self.log.info("Add XC neighbor", remote_name, "IP", remote_ip)
                vars.add('NEIGHBOR', remote_ip)

            template = ncs.template.Template(service)
            template.apply('l2vpn-template', vars)

    def get_interface(self, root, service, device, platform):
        """
        Get interface type and interface number
        :param root:
        :param service:
        :param device:
        :param platform:
        :return:
        """
        self.log.debug(" Executing in Module: get_interface")
        interface_type = ''
        interface_num = ''
        interface = device.interface

        # if platform == 'cisco-ios':
        #     interface = device.interface_ios
        # elif platform == 'cisco-iosxr':
        #     interface = device.interface_ios_xr
        # else:
        #     return None, None

        int_rex = re.search('(\S+Ethernet)((\d\/?)+)', interface)
        interface_type = int_rex.group(1)
        interface_num = int_rex.group(2)
        self.log.info("Int type:", interface_type)
        self.log.info("Int num:", interface_num)

        # for int_type in interface:
        #     if int_type.endswith('Ethernet'):
        #         int_type = int_type.split(':')[-1]
        #         if interface[int_type] is not None:
        #             interface_type = int_type
        #             interface_num = interface[int_type]

        return interface_type, interface_num

    def get_device_platform(self, root, service, device_name):
        """
        Get device platform by looking in capability. eg: urn:ios, http://tail-f.com/ned/cisco-ios-xr.
        :param root:
        :param service:
        :return: dict of { device_name: str:platform, ... }
        """
        self.log.debug(" Executing in Module: get_device_platform")

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
            device_name = endpoint.name
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

class ActionHandler(Action):
    """This class implements the dp.Action class."""

    @Action.action
    def cb_action(self, uinfo, name, kp, input, output):
        try:
            with ncs.maapi.Maapi() as m:
                with ncs.maapi.Session(m,uinfo.username,uinfo.clearpass):
                    with m.start_write_trans() as t:
                        root = ncs.maagic.get_root(t)

                        if input.dry_run:
                            # now lets see what I want to perform the commit dry-run
                            # I use native format to detect changes in device
                            input_dr = root.ncs__services.commit_dry_run.get_input()
                            input_dr.outformat = 'native'
                            dry_output = root.ncs__services.commit_dry_run(input_dr)
                            
                            output.message += "Commit Dry Run Device Changes: \n"
                            # Let me check that no device will be modified:
                            
                            if len(dry_output.native.device) == 0:
                                output.status = True
                                output.message += "No Changes \n"
                            else:
                                for device in dry_output.native.device:
                                    output.message += "Device: %s \n" % device.name
                                    output.message += str(device.data)
                                    output.message += "\n"
                            
                            output.message += "Commit Dry Run Service Changes: \n"
                            myiter = DiffIterator()
                            m.diff_iterate(t.th,myiter,ncs.ITER_WANT_ATTR)
                            for item in myiter.changes:
                                op = item["op"]
                                kp = item["kp"]
                                oldv = item["oldv"]
                                newv = item["newv"]
                                output.message += "Operation: %s - KeyPath: %s - Old Value: %s - New Value: %s \n" % (op,kp,oldv,newv)
                    
                            return
                        
                        # I now apply changes
                        t.apply()
                        
                        # If requested, I will reconciliate only my l2VPN services
                        # I may need to reconciliate more services

                        if input.reconciliate:
                            self.log.info("Entering reconciliation")
                            services = root.l2vpn__l2vpn_vpws.l2vpn
                            
                            for service_tbd in changed_services:
                                service = services[service_tbd]
                                redeploy_inputs = service.re_deploy.get_input()
                                redeploy_inputs.reconcile.create()
                                redeploy_outputs = service.re_deploy(redeploy_inputs)
                                           
                        output.status = True

        except Exception as e:
            self.log.error("Exception...")
            raise 


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

        self.log.info('Main RUNNING - L2VPN discovery')
        self.register_action('l2vpn-discovery', ActionHandler)

        # If we registered any callback(s) above, the Application class
        # took care of creating a daemon (related to the service/action point).

        # When this setup method is finished, all registrations are
        # considered done and the application is 'started'.

    def teardown(self):
        # When the application is finished (which would happen if NCS went
        # down, packages were reloaded or some error occurred) this teardown
        # method will be called.

        self.log.info('Main FINISHED')
