import pytest
import random
import re
from ExtremeAutomation.Imports.pytestConfigHelper import PytestConfigHelper
import string
import itertools
from pytest_testconfig import config


# make active port list as global variable so that it can be used in all the methods.
global active_ports_list, min_vlan_name, max_vlan_name, base_config_flag, default_vlan_id, default_vlan_name, random_port
global test_executable
active_ports_list = []
min_vlan_name_length = 1

default_vlan_name = 'Default'
max_vlan_name_length = 32

# A and Q are reserved words cannot be used as minimun vlan name.
match = 0
while not match:
    min_vlan_name = ''.join(random.choices(string.ascii_uppercase, k=min_vlan_name_length))
    if min_vlan_name not in ['A', 'Q']:
        match = 1
        break

max_vlan_name = ''.join(random.choices(string.ascii_letters, k=1))
max_vlan_name = max_vlan_name + ''.join(
    random.choices(string.ascii_letters + string.digits, k=max_vlan_name_length - 2))
max_vlan_name = max_vlan_name[:16] + '_' + max_vlan_name[16:]
default_vlan_id = ''
min_vlan_id = ''
max_vlan_id = ''
base_config_flag = False
test_executable = 0


class XIQ15049:

    @pytest.fixture(scope="session")
    def select_random_port(self, enter_switch_cli):
        def func(node):
            global active_ports_list
            print(f"Active port list : {active_ports_list}")
            rand_port = False
            if node.platform.lower() == 'stack':
                slot_no = str(random.randint(1, len(node.serial.split(','))))
                model = node['stack']['slot' + slot_no]['model']
            else:
                model = node.model
            ports = re.search("\d+", model.split("_")[1]).group(0)
            list_ele = list(range(1, int(ports) + 1))
            while not rand_port:
                rand_port_no = str(random.choice(list_ele))
                if node.platform.lower() == 'stack':
                    rand_port_no = slot_no + ':' + rand_port_no
                print(f"random port number: {rand_port_no}")
                if rand_port_no not in active_ports_list:
                    cmd = 'show port ' + rand_port_no + ' no-refresh'
                    with enter_switch_cli(node) as dev_cmd:
                        out = dev_cmd.send_cmd(node.name, cmd, max_wait=10, interval=3)[0].return_text
                        if re.search(rf'{rand_port_no}\s+.*E\s+R', out):
                            rand_port = True
                            break
            return rand_port_no

        return func

    @pytest.fixture(scope="session")
    def generate_dhcp_snooping_cli(self):
        def func():
            # DHCP Snooping block duration for min is : 1 and max is : 172800
            block_time = random.randrange(1, 172800)
            dhcp_options = random.choice(['none', 'drop-packet'])
            block_options = block_durations = ' '

            if dhcp_options == 'drop-packet':
                block_options = random.choice(['block-mac', 'block-port'])
                block_durations = random.choice(['permanently', f'duration {block_time}'])

            cli = dhcp_options + ' ' + block_options + ' ' + block_durations
            cli = cli.strip()
            return cli

        return func

    @pytest.fixture(scope="session")
    def user_vlan_configure(self, enter_switch_cli, select_random_port, generate_dhcp_snooping_cli):
        def func(node):
            global active_ports_list, random_port, min_vlan_name, max_vlan_name, base_config_flag

            if not base_config_flag:
                random_port = select_random_port(node)
                ports_list = ','.join(active_ports_list) + ',' + random_port
                dhcp_snooping_option = generate_dhcp_snooping_cli()
                print(f"Active port list : {active_ports_list}")
                with enter_switch_cli(node) as dev_cmd:
                    # enable dhcp snooping for vlan default.
                    dev_cmd.send_cmd(node.name, f'configure stpd s0 priority 4096', max_wait=10, interval=3)
                    dev_cmd.send_cmd(node.name, f'create stpd s1', max_wait=10, interval=3)
                    dev_cmd.send_cmd(node.name, f'configure stpd s1 mode mstp msti 10', max_wait=10, interval=3)
                    dev_cmd.send_cmd(node.name, f'enable stpd s1', max_wait=10, interval=3)
                    dev_cmd.send_cmd(node.name, f'configure stpd s1 priority 4096', max_wait=10, interval=3)
                    dev_cmd.send_cmd(node.name,
                                     f'enable ip-security dhcp-snooping vlan Default ports all violation-action {dhcp_snooping_option}',
                                     max_wait=10, interval=3)

                    # create first vlan with minimum char length and enable all the attributes of the vlan.
                    dev_cmd.send_cmd(node.name, f'create vlan {min_vlan_name} tag {min_vlan_id}', max_wait=10,
                                     interval=3)
                    dev_cmd.send_cmd(node.name, f'configure vlan {min_vlan_name}  add ports {ports_list} tagged',
                                     max_wait=10, interval=3)
                    dev_cmd.send_cmd(node.name, f'configure stpd s0 add vlan {min_vlan_name} ports all', max_wait=10,
                                     interval=3)
                    dev_cmd.send_cmd(node.name, f'enable igmp snooping vlan {min_vlan_name}', max_wait=10, interval=3)
                    dev_cmd.send_cmd(node.name,
                                     f'enable ip-security dhcp-snooping vlan {min_vlan_name} ports all violation-action {dhcp_snooping_option}',
                                     max_wait=10, interval=3)

                    # create second vlan with maximum char length and disable all the attributes of the vlan.
                    dev_cmd.send_cmd(node.name, f'create vlan {max_vlan_name} tag {max_vlan_id}', max_wait=10,
                                     interval=3)
                    dev_cmd.send_cmd(node.name, f'configure vlan {max_vlan_name}  add ports {ports_list} untagged',
                                     max_wait=10, interval=3)
                    dev_cmd.send_cmd(node.name, f'disable igmp snooping vlan {max_vlan_name}', max_wait=10, interval=3)

                base_config_flag = True;

        return func

    @pytest.fixture(scope="session")
    def get_vlan_info(self):
        def func(vlan_dict):
            vlan_info = {}
            for key, value in vlan_dict.items():
                for attr_key, attr_name in value.items():
                    if attr_key == 'name':
                        vlan_info[globals()[key]] = {attr_key: globals()[attr_name]}
                    elif (attr_key == 'active_ports') and (attr_name != []):
                        vlan_info[globals()[key]][attr_key] = globals()[attr_name].copy()
                    else:
                        vlan_info[globals()[key]][attr_key] = attr_name
            return vlan_info

        return func

    @pytest.fixture(scope="session")
    def get_vlan_ports_list(self):
        def func(vlan_info, key_list, active_ports=[], total_ports=[], trunk_ports=[], lag_ports=[],
                 port_highlighted=True):
            vlan_ports_list = {}
            vlan_list = vlan_info.keys()
            for vlan in vlan_list:
                for key in key_list:
                    if key == 'oper_up_ports':
                        vlan_ports_list[vlan] = {key: active_ports}
                    elif key == 'total_ports':
                        vlan_ports_list[vlan][key] = total_ports
                    elif key == 'trunk_ports':
                        vlan_ports_list[vlan][key] = trunk_ports
                    elif key == 'lag_ports':
                        vlan_ports_list[vlan][key] = lag_ports
                    elif key == 'port_highlighted':
                        vlan_ports_list[vlan][key] = port_highlighted
                    else:
                        print("Given key doesn't match with vlan_port_list key list")
            return vlan_ports_list

        return func

    @pytest.fixture(scope="session")
    def user_vlan_unconfigure(self):
        def func(enter_switch_cli, xiq_library_at_class_level, node):
            with enter_switch_cli(node) as dev_cmd:
                global default_vlan_id
                print("VLAN Cleanup Method:")
                # Perform deletion of the extra vlan id's configured in the device.
                out = dev_cmd.send_cmd(node.name, f'show vlan {node.mgmt_vlan}', max_wait=5, interval=3)[0].return_text
                match = re.search(r'(.*)\s+Tag\s+(\d+)', out)
                if match:
                    mgmt_vlan = match.group(2)

                out = dev_cmd.send_cmd(node.name, 'show vlan', max_wait=120, interval=3)[0].return_text
                out = out.replace('\r', '')
                out = out.split("\n")
                vlan_list = []
                for line in out:
                    # match = re.search(r'create vlan \"(.*)\"', line)
                    match = re.search(r'[A-Za-z0-9_]* (\d+)(.*)---', line)
                    if match:
                        vlan_list.append(int(match.group(1)))

                print(f"Initial VLAN list {vlan_list}")

                if mgmt_vlan != default_vlan_id:
                    vlan_list.pop(vlan_list.index(int(mgmt_vlan)))

                vlan_list.pop(vlan_list.index(int(default_vlan_id)))

                if vlan_list:
                    val = []
                    for key, group in itertools.groupby(enumerate(vlan_list), lambda t: t[1] - t[0]):
                        group = list(group)
                        val.append([group[0][1], group[-1][1]])

                    result_list = []
                    for ele in val:
                        if ele[0] == ele[1]:
                            result_list.append(str(ele[0]))
                        else:
                            rang = str(ele[0]) + '-' + str(ele[1])
                            result_list.append(rang)
                    isl_string = ','.join(result_list)

                    dev_cmd.send_cmd(node.name, f'delete vlan {isl_string}', max_wait=600, interval=3)

                # Perform deletion of the extra stpd instance configured in the device.
                out = dev_cmd.send_cmd(node.name, 'show configuration stp | grep create', max_wait=10, interval=3)[
                    0].return_text
                out = out.replace('\r', '')
                out = out.split("\n")
                for line in out:
                    match = re.search(r'create stpd (.*)', line)
                    if match:
                        dev_cmd.send_cmd(node.name, f'delete stpd {match.group(1)}', max_wait=10, interval=3)

                # configure default parameters for vlan default.
                dev_cmd.send_cmd(node.name, 'configure vlan default add ports all', max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, 'configure stpd s0 add vlan default ports all', max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'disable ip-security dhcp-snooping vlan Default ports all',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'configure stpd s0 priority 32768',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'enable stpd s0', max_wait=10, interval=3)

        return func

    @pytest.fixture(scope="session")
    def configure_stp_priority(self):
        def func(xiq_library_at_class_level, logger, utils, node_policy_name, stp_priority='61440'):
            print("inside debugging mode")
            print("STP= ", stp_priority)
            if xiq_library_at_class_level.xflowsconfigureNetworkPolicy.navigate_to_np_edit_tab(node_policy_name) != 1:
                xiq_library_at_class_level.Screen.save_screen_shot()
                logger.fail(f"Failed to navigate to given network policy: '{node_policy_name}'.")

            xiq_library_at_class_level.xflowscommonNavigator.wait_until_loading_is_done()

            policy_switching_tab, _ = utils.wait_till(
                func=xiq_library_at_class_level.xflowsconfigureDeviceTemplate.device_template.device_template_web_elements.get_policy_switching_tab,
                silent_failure=True,
                exp_func_resp=True,
                delay=5
            )

            if policy_switching_tab is None:
                xiq_library_at_class_level.Screen.save_screen_shot()
                logger.fail("Failed to get the policy_switching_tab element")

            if xiq_library_at_class_level.xflowscommonAutoActions.click_reference(
                    xiq_library_at_class_level.xflowsconfigureDeviceTemplate.device_template.device_template_web_elements.get_policy_switching_tab) != 1:
                xiq_library_at_class_level.Screen.save_screen_shot()
                logger.fail("Failed to click the policy_switching_tab element")

            xiq_library_at_class_level.xflowscommonNavigator.wait_until_loading_is_done()

            common_settings_exos, _ = utils.wait_till(
                func=xiq_library_at_class_level.xflowsconfigureNetworkPolicy.np_web_elements.get_common_settings_exos,
                silent_failure=True,
                exp_func_resp=True,
                delay=5
            )

            if common_settings_exos is None:
                xiq_library_at_class_level.Screen.save_screen_shot()
                logger.fail("Failed to get the common_settings_exos element.")

            if xiq_library_at_class_level.xflowscommonAutoActions.click_reference(
                    xiq_library_at_class_level.xflowsconfigureNetworkPolicy.np_web_elements.get_common_settings_exos) != 1:
                xiq_library_at_class_level.Screen.save_screen_shot()
                logger.fail("Failed to click the common_settings_exos element.")

            xiq_library_at_class_level.xflowscommonNavigator.wait_until_loading_is_done()

            span_tree_bridge_priority_element = xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template.sw_template_web_elements.priority_dropdown()
            if not span_tree_bridge_priority_element:
                logger.fail("Unable to locate spanning tree priority option drop down")
            xiq_library_at_class_level.xflowscommonAutoActions.click(span_tree_bridge_priority_element)
            tb = xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template.sw_template_web_elements.get_priority_items_select_container()
            xiq_library_at_class_level.xflowscommonAutoActions.select_drop_down_options(
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template.sw_template_web_elements.priority_items(
                    tb), stp_priority)
            assert xiq_library_at_class_level.xflowscommonAutoActions.click_reference(
                xiq_library_at_class_level.xflowsconfigureNetworkPolicy.np_web_elements.get_common_settings_save_button) == 1, "Fail to save common settings"

        return func

    @pytest.mark.dependson("tcxm_xiq_onboarding")
    @pytest.fixture(scope="class", autouse=True)
    def setup(self, xiq_library_at_class_level, node, logger, enter_switch_cli, user_vlan_unconfigure):

        """
        Ensure extra vlan config's are not available in the switch.
        Reading the active links available in node for vlan info verification.
        """
        global active_ports_list, default_vlan_id, min_vlan_id, max_vlan_id

        if node.isl == '':
            logger.fail("Trunk port not available to perform VLAN monitor verification.")

        # For active port count all the ports need to be in STP forwarding state. So setting STP Priority to low to elected
        # as ROOT Bridge where all the ports are in forwarding state.
        with enter_switch_cli(node) as dev_cmd:
            dev_cmd.send_cmd(node.name, 'disable cli paging', max_wait=10, interval=3)

            # Reading Active port details and saved in active_ports_list global list variable that is used for vlan monitor
            # validation.
            out = dev_cmd.send_cmd(node.name, 'show ports no-refresh | grep A', max_wait=10, interval=3)[0].return_text
            out = out.replace('\r', '')
            out = out.split("\n")
            for line in out:
                match = re.search(r'(\d+|\d+:\d+|\d+:\d+:\d+)\s+(.*)\s+E\s+A', line)
                if match:
                    active_ports_list.append(match.group(1))

            # electing the default_vlan_id for each device.
            out = dev_cmd.send_cmd(node.name, 'show vlan | grep Default', max_wait=60, interval=3)[0].return_text
            out = out.replace('\r', '')
            out = out.split("\n")
            for line in out:
                match = re.search(r'Default\s+(\d+)', line)
                if match:
                    default_vlan_id = match.group(1)

        if not default_vlan_id:
            logger.fail("Default VLAN ID not learnt")

        logger.info(f"Default VLAN ID is {default_vlan_id}")

        logger.step("Executing pre cleanup before executing Testcases.")
        # user_vlan_unconfigure(enter_switch_cli, xiq_library_at_class_level, node)

        # electing min_vlan_id except default vlan
        match = 0
        while not match:
            min_vlan_id = str(random.randrange(1, 2000))
            if min_vlan_id != default_vlan_id:
                match = 1
                break

        # electing max_vlan_id except default vlan
        match = 0
        while not match:
            max_vlan_id = str(random.randrange(2001, 4094))
            if max_vlan_id != default_vlan_id:
                match = 1
                break

        logger.info(f"Default vlan id is {default_vlan_id}")
        logger.info(f"Minimum vlan id is {min_vlan_id}")
        logger.info(f"Maximum vlan id is {max_vlan_id}")
        logger.info(f"Active ports list is: {active_ports_list}")

        yield
        ###cleanup_code
        logger.step("Executing post cleanup after executing all the Testcases.")
        close_btn = xiq_library_at_class_level.xflowsmanageDevice360.dev360.get_close_dialog()
        if close_btn:
            xiq_library_at_class_level.xflowsmanageDevice360.close_device360_window()

        user_vlan_unconfigure(enter_switch_cli, xiq_library_at_class_level, node)



@pytest.mark.dependson("tcxm_xiq_onboarding")
@pytest.mark.testbed_composed(standalone_nodes='all', stack_nodes='all')
@pytest.mark.skip_if_node_system_version_lt("32.6.2.67", "exos")
@pytest.mark.skip_if_node_1_system_version_lt("32.6.2.67", "exos")
@pytest.mark.skip_if_node_cli_type("voss")
class XIQ15049Tests(XIQ15049):

    # """ Test Cases """
    @pytest.mark.tcxm_42688
    @pytest.mark.p1
    def test_Default_VLAN_with_all_ports(self, xiq_library_at_class_level, node, logger, enter_switch_cli,
                                         user_vlan_unconfigure):
        """
        Description:
        TCXM-42688 In monitoring tab -> overview -> vlan tab should present.
        """

        global active_ports_list, default_vlan_id, base_config_flag

        # clear the vlan configuration which was done by cli.
        user_vlan_unconfigure(enter_switch_cli, xiq_library_at_class_level, node)
        base_config_flag = False

        # configure stpd s0 priority to lowest one to make it as root bridge to read all enabled ports as active ports
        with enter_switch_cli(node) as dev_cmd:
            dev_cmd.send_cmd(node.name, 'configure stpd s0 priority 4096', max_wait=10, interval=3)

        # verify default vlan and mgmt vlan details in interface vlan table.
        logger.step(f"Verify Default vlan and Mgmt vlan wireframe details for node {node.name}")
        vlan_info = {
            default_vlan_id: {'name': '', 'active_ports': active_ports_list,
                              'stp_instance': {'name': 's0', 'status': 'Enabled'},
                              'igmp_snooping': '', 'dhcp_snooping': ''}}

        if node.mgmt_vr.lower() == 'vr-mgmt':
            vlan_info['4095'] = {'name': '', 'active_ports': ['Mgmt'], 'stp_instance': {}, 'igmp_snooping': '',
                                 'dhcp_snooping': ''}

        xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                               skip_d360_close=True,
                                                                                               skip_list_of_active_ports=False)

        # verify default vlan and mgmt vlan port selection in wireframe image.
        logger.step(f"Verify Default vlan and Mgmt vlan port selection in wireframe image for node {node.name}")
        vlan_ports_list = {}
        vlan_ports_list[default_vlan_id] = {'oper_up_ports': active_ports_list, 'total_ports': ['all']}

        if node.mgmt_vr.lower() == 'vr-mgmt':
            vlan_ports_list['4095'] = {'oper_up_ports': [], 'total_ports': ['mgmt']}

        xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node,
                                                                                                           vlan_ports_list,
                                                                                                           skip_d360_close=True)

    @pytest.mark.tcxm_42700
    @pytest.mark.p2
    def test_Default_VLAN_with_no_ports(self, xiq_library_at_class_level, node, enter_switch_cli, logger,
                                        user_vlan_unconfigure):
        """
        Description:
        TCXM-42700 Delete all ports from vlan.
        """
        try:
            global active_ports_list, default_vlan_id, base_config_flag

            # clear the vlan configuration which was done by cli.
            user_vlan_unconfigure(enter_switch_cli, xiq_library_at_class_level, node)
            base_config_flag = False

            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, 'configure vlan default delete ports all', max_wait=10, interval=3)

            # verify default vlan details in interface vlan table after removing all the ports.
            logger.step(
                f"verify default vlan details in interface vlan table after removing all the ports for node {node.name}")
            vlan_info = {
                default_vlan_id: {'name': '', 'active_ports': [], 'stp_instance': {'name': 'N/A', 'status': ''},
                                  'igmp_snooping': '', 'dhcp_snooping': ''}}
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True)

            # verify default vlan port selection in wireframe image after removing all the ports.
            logger.step(
                f"verify default vlan port selection in wireframe image after removing all the ports for node {node.name}")
            vlan_ports_list = {default_vlan_id: {'oper_up_ports': active_ports_list, 'total_ports': ['all'],
                                                 'port_highlighted': False}}
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=True)
        finally:
            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, 'configure vlan default add ports all', max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, 'configure stpd s0 add vlan default ports all', max_wait=10, interval=3)

    @pytest.mark.tcxm_42689
    @pytest.mark.p1
    def test_VLAN_attributes(self, xiq_library_at_class_level, test_data, node, logger, enter_switch_cli,
                             user_vlan_configure, get_vlan_info, get_vlan_ports_list,
                             generate_dhcp_snooping_cli):
        """
        Description:
        TCXM-42689 vlan tab should display all the vlans created on the device.
        """
        try:
            global active_ports_list, random_port
            global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id

            dhcp_snooping_option = generate_dhcp_snooping_cli()

            user_vlan_configure(node)

            # verify user created VLAN attributes details in D360 Monitor > Overview > Interface vlan table.
            vlan_info = get_vlan_info(test_data['vlan_info'])
            logger.step(
                f"Verify user created vlan attribute details: {vlan_info} in D360 Monitor > Overview > Interface vlan table for Device {node.name}")

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            ports_list = ','.join(active_ports_list) + ',' + random_port

            # verify user created VLAN attributes details in D360 Monitor > Overview > Interface vlan table.
            vlan_info = get_vlan_info(test_data['vlan_info'])
            logger.step(
                f"Verify user created vlan attribute details: {vlan_info} in D360 Monitor > Overview > Interface vlan table for Device {node.name}")

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            # verify user created VLAN port details in D360 Monitor > Overview > Interface vlan page wireframe image.
            total_ports = active_ports_list + [random_port]
            key_list = ['oper_up_ports', 'total_ports', 'trunk_ports', 'port_highlighted']
            vlan_ports_list = get_vlan_ports_list(vlan_info, key_list, active_ports=active_ports_list,
                                                  total_ports=total_ports, trunk_ports=total_ports)

            logger.step(
                f"Verify user created vlan port details: {vlan_ports_list} in D360 Monitor > Overview > Interface vlan table for Device {node.name}")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=True)

            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, f'configure vlan {min_vlan_name}  add ports {ports_list} untagged',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'configure stpd s0 add vlan {min_vlan_name} ports all',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name,
                                 f'enable ip-security dhcp-snooping vlan {min_vlan_name} ports all violation-action {dhcp_snooping_option}',
                                 max_wait=10, interval=3)

                # verify after moving min vlan id moved from tagged to untagged.
                del vlan_ports_list[min_vlan_id]['trunk_ports']
                del vlan_ports_list[max_vlan_id]['trunk_ports']
                vlan_ports_list[max_vlan_id]['port_highlighted'] = False

                logger.step(
                    f"Verify user created vlan port details: {vlan_ports_list} in Interface vlan table for node {node.name} after min_vlan_id ports moved from tagged to untagged.")
                xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node,
                                                                                                                   vlan_ports_list,
                                                                                                                   skip_d360_close=True)

                # All ports are removed from max_vlan_name after adding the ports as untagged in min_vlan_id.
                vlan_info[max_vlan_id]['active_ports'] = []

                logger.step(
                    f"Verify user created vlan attribute details: {vlan_info} in Interface vlan table for Device {node.name} after min_vlan_id ports moved from tagged to untagged.")
                xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                       skip_d360_close=True,
                                                                                                       skip_stp_status=
                                                                                                       test_data[
                                                                                                           'skip_stp_status'],
                                                                                                       skip_list_of_active_ports=
                                                                                                       test_data[
                                                                                                           'skip_list_of_active_ports'])

        finally:
            # Revert the min_vlan_id and max_vlan_id with base config.
            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, f'configure vlan {min_vlan_name}  add ports {ports_list} tagged',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'configure stpd s0 add vlan {min_vlan_name} ports all',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name,
                                 f'enable ip-security dhcp-snooping vlan {min_vlan_name} ports all violation-action {dhcp_snooping_option}',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'configure vlan {max_vlan_name}  add ports {ports_list} untagged',
                                 max_wait=10, interval=3)

    @pytest.mark.tcxm_44528
    @pytest.mark.p1
    def test_VLAN_STP_attribute(self, xiq_library_at_class_level, test_data, node, logger, enter_switch_cli,
                                user_vlan_configure, get_vlan_info):
        """
        Description:
        TCXM-44528 Create a vlan with switching between the stp instance.
        """
        try:
            global default_vlan_name, default_vlan_id, min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id

            user_vlan_configure(node)

            # verify user created VLAN STP attributes details in D360 Monitor > Overview > Interface vlan table.
            vlan_info = get_vlan_info(test_data['vlan_info'])
            logger.step(
                f"Verify user created vlan STP attribute details: {vlan_info} in Interface vlan table for Device {node.name}")

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            with enter_switch_cli(node) as dev_cmd:
                vlan_info[default_vlan_id] = {'name': default_vlan_name}
                vlan_info[default_vlan_id]['stp_instance'] = {'name': 's0', 'status': 'Enabled'}
                vlan_info[min_vlan_id]['stp_instance'] = {}
                vlan_info[max_vlan_id]['stp_instance'] = {'name': 's1', 'status': 'Enabled'}
                dev_cmd.send_cmd(node.name, f'configure stpd s0 delete vlan {min_vlan_name} ports all', max_wait=10,
                                 interval=3)
                dev_cmd.send_cmd(node.name, f'configure stpd s1 add vlan {max_vlan_name} ports all', max_wait=10,
                                 interval=3)

            # STP instance creation and default STP instance port deletion.
            logger.step(
                f"Verify user created vlan STP attribute details: {vlan_info} in Interface vlan table for Device {node.name} after STP instance creation and ports deletion.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            with enter_switch_cli(node) as dev_cmd:
                vlan_info[default_vlan_id] = {'name': default_vlan_name}
                vlan_info[default_vlan_id]['stp_instance'] = {'name': 's0', 'status': 'Disabled'}
                vlan_info[min_vlan_id]['stp_instance'] = {'name': 's0', 'status': 'Disabled'}
                vlan_info[max_vlan_id]['stp_instance'] = {'name': 's1', 'status': 'Disabled'}

                dev_cmd.send_cmd(node.name, f'disable stpd s1', max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'disable stpd s0', max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'configure stpd s0 add vlan {min_vlan_name} ports all', max_wait=10,
                                 interval=3)

            # STP instance disable
            logger.step(
                f"Verify user created vlan STP attribute details: {vlan_info} in Interface vlan table for Device {node.name} after STP instance disabled.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            with enter_switch_cli(node) as dev_cmd:
                vlan_info[default_vlan_id]['name'] = default_vlan_name
                vlan_info[default_vlan_id]['stp_instance'] = {'name': 's0', 'status': 'Enabled'}
                vlan_info[min_vlan_id]['stp_instance'] = {'name': 's0', 'status': 'Enabled'}
                vlan_info[max_vlan_id]['stp_instance'] = {'name': 's1', 'status': 'Enabled'}

                dev_cmd.send_cmd(node.name, f'enable stpd s0', max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'enable stpd s1', max_wait=10, interval=3)

            # STP instance enable
            logger.step(
                f"Verify user created vlan STP attribute details: {vlan_info} in Interface vlan table for Device {node.name}  after STP instance enabled.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

        finally:
            # STP instance reverted for max_vlan_id
            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, f'configure stpd s1 delete vlan {max_vlan_name} ports all', max_wait=10,
                                 interval=3)

    @pytest.mark.tcxm_44529
    @pytest.mark.p1
    def test_VLAN_IGMP_attribute(self, xiq_library_at_class_level, test_data, node, logger, enter_switch_cli,
                                 user_vlan_configure, get_vlan_info):
        """
        Description:
        TCXM-44529 IGMP snooping - enable /disable.
        """
        try:
            global active_ports_list, random_port
            global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id

            user_vlan_configure(node)

            # verify user created VLAN IGMP attributes details in D360 Monitor > Overview > Interface vlan table.
            vlan_info = get_vlan_info(test_data['vlan_info'])
            logger.step(
                f"Verify user created vlan IGMP attribute details: {vlan_info} in D360 Monitor > Overview > Interface vlan table for Device {node.name}")

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            with enter_switch_cli(node) as dev_cmd:
                vlan_info[min_vlan_id]['igmp_snooping'] = 'Disabled'
                vlan_info[max_vlan_id]['igmp_snooping'] = 'Enabled'
                dev_cmd.send_cmd(node.name, f'disable igmp snooping vlan {min_vlan_name}', max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'enable igmp snooping vlan {max_vlan_name}', max_wait=10,
                                 interval=5)

            # verify user created VLAN IGMP attributes details in D360 Monitor > Overview > Interface vlan table after IGMP disable/enable.
            logger.step(
                f"Verify user created vlan IGMP attribute details: {vlan_info} in D360 Monitor > Overview > Interface vlan table for Device {node.name} after IGMP protocol enable/disable.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

        finally:
            # IGMP attribute reverted with user vlan configure.
            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, f'enable igmp snooping vlan {min_vlan_name}', max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'disable igmp snooping vlan {max_vlan_name}', max_wait=10, interval=3)

    @pytest.mark.tcxm_44552
    @pytest.mark.p1
    def test_VLAN_DHCP_attribute(self, xiq_library_at_class_level, test_data, node, logger, enter_switch_cli,
                                 user_vlan_configure, get_vlan_info, generate_dhcp_snooping_cli):
        """
        Description:
        TCXM-44552 DHCP snooping - enable/disable.
        """
        try:
            global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id

            dhcp_snooping_option = generate_dhcp_snooping_cli()

            user_vlan_configure(node)

            vlan_info = get_vlan_info(test_data['vlan_info'])
            logger.step(
                f"Verify user created vlan DHCP attribute details: {vlan_info} in D360 Monitor > Overview > Interface vlan table for Device {node.name}")

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            with enter_switch_cli(node) as dev_cmd:
                vlan_info[default_vlan_id]['dhcp_snooping'] = 'Disabled'
                vlan_info[min_vlan_id]['dhcp_snooping'] = 'Disabled'
                vlan_info[max_vlan_id]['dhcp_snooping'] = 'Enabled'
                dev_cmd.send_cmd(node.name, f'disable ip-security dhcp-snooping vlan Default ports all',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'disable ip-security dhcp-snooping vlan {min_vlan_name} ports all',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name,
                                 f'enable ip-security dhcp-snooping vlan {max_vlan_name} ports all violation-action {dhcp_snooping_option}',
                                 max_wait=10, interval=3)

            # verify user created VLAN DHCP-Snooping attributes details in D360 Monitor > Overview > Interface vlan table after DHCP-Snooping disable/enable
            logger.step(
                f"Verify user created VLAN DHCP attribute details: {vlan_info} in D360 Monitor > Overview > Interface vlan table for Device {node.name} after dhcp-snooping state enabled and disabled.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

        finally:
            # DHCP-Snooping attribute reverted with user vlan configure.
            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, f'disable ip-security dhcp-snooping vlan {max_vlan_name} ports all',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name,
                                 f'enable ip-security dhcp-snooping vlan {min_vlan_name} ports all violation-action {dhcp_snooping_option}',
                                 max_wait=10, interval=3)

    @pytest.mark.tcxm_42692
    @pytest.mark.p2
    def test_VLAN_modifications(self, xiq_library_at_class_level, test_data, node, logger, enter_switch_cli,
                                user_vlan_configure, get_vlan_info, generate_dhcp_snooping_cli, get_vlan_ports_list):
        """
        Description:
        TCXM-42692 Delete/add all ports from vlan.
        """
        try:
            global active_ports_list, max_vlan_name, max_vlan_id, random_port

            user_vlan_configure(node)
            dhcp_snooping_option = generate_dhcp_snooping_cli()

            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, f'configure vlan {max_vlan_name} delete port all', max_wait=10, interval=3)

            vlan_info = get_vlan_info(test_data['vlan_info'])

            # verify user created VLAN attributes details in Interface vlan table after all the ports are removed from max_vlan_id.
            logger.step(
                f"verify user created VLAN attributes details: {vlan_info} in Interface vlan table for Device {node.name} after all the ports are removed from max_vlan_id.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            # verify removed ports are not highlighted in wireframe image.
            total_ports = active_ports_list + [random_port]
            key_list = ['oper_up_ports', 'total_ports', 'trunk_ports', 'port_highlighted']
            vlan_ports_list = get_vlan_ports_list(vlan_info, key_list, active_ports=active_ports_list,
                                                  total_ports=total_ports, trunk_ports=total_ports,
                                                  port_highlighted=False)

            logger.step(f"verify removed ports Details: {vlan_ports_list} are not highlighted in wireframe image.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=True)

            # modify the user created vlan to add all the ports as tagged one and verify it was updated in the vlan table properly.
            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, f'configure vlan {max_vlan_name}  add ports all tagged', max_wait=10,
                                 interval=3)
                dev_cmd.send_cmd(node.name, f'configure stpd s1 add vlan {max_vlan_name} ports all', max_wait=10,
                                 interval=3)
                dev_cmd.send_cmd(node.name, f'enable igmp snooping vlan {max_vlan_name}', max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name,
                                 f'enable ip-security dhcp-snooping vlan {max_vlan_name} ports all violation-action {dhcp_snooping_option}',
                                 max_wait=10, interval=3)

            vlan_info[max_vlan_id]['active_ports'] = active_ports_list
            vlan_info[max_vlan_id]['stp_instance'] = {'name': 's1', 'status': 'Enabled'}
            vlan_info[max_vlan_id]['igmp_snooping'] = 'Enabled'
            vlan_info[max_vlan_id]['dhcp_snooping'] = 'Enabled'

            logger.step(
                f"Modify the user created vlan to add all the ports as tagged one: {vlan_info} and verify it was updated in the vlan table properly for node {node.name}.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            # verify all the ports are highlighted in wireframe image.
            vlan_ports_list = {
                max_vlan_id: {'oper_up_ports': active_ports_list, 'total_ports': ['all'], 'trunk_ports': ['all'],
                              'port_highlighted': True}}
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=True)

            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, f'delete vlan {max_vlan_name}', max_wait=10, interval=3)

            logger.step(
                f"verify all the ports are highlighted in wireframe image : {vlan_ports_list} for node {node.name}.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   vlan_exist=False)
        finally:
            # Revert the vlan config to default user vlan config.
            ports_list = ','.join(active_ports_list) + ',' + random_port
            logger.step(f"Test Execution completed, Reverting VLAN config {max_vlan_name} with base vlan config")
            with enter_switch_cli(node) as dev_cmd:
                cmd = 'show configuration vlan | grep create'
                output = dev_cmd.send_cmd(node.name, cmd, max_wait=10, interval=3)
                output_text = output[0].cmd_obj.return_text
                out = output_text.replace('\r', '')
                logger.info(f'CLI output is {output_text}')
                if re.search(rf'{max_vlan_name}', out):
                    dev_cmd.send_cmd(node.name, f'delete vlan {max_vlan_name}', max_wait=10, interval=3)

                dev_cmd.send_cmd(node.name, f'create vlan {max_vlan_name} tag {max_vlan_id}', max_wait=10, interval=3)
                # dev_cmd.send_cmd(node.name, f'configure vlan {max_vlan_name}  add ports all untagged' , max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'configure vlan {max_vlan_name}  add ports {ports_list} untagged',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node.name, f'disable igmp snooping vlan {max_vlan_name}', max_wait=10, interval=3)

    @pytest.mark.tcxm_42691
    @pytest.mark.tcxm_42695
    @pytest.mark.dependson("tcxm_42689")
    @pytest.mark.p1
    def test_depends_on_tcxm_42689(self, logger, test_data):
        """
        Description:
        TCXM-42691 Create vlan with 32 characters.
        TCXM-42691 create a vlan with ports 2,3 tagged and 2,3 untagged in different vlan-check.
        """

        logger.info(f"Test case {test_data['tc']} is covered by tcxm_42689.")

    @pytest.mark.tcxm_52470
    @pytest.mark.dependson("tcxm_44528")
    @pytest.mark.p1
    def test_depends_on_tcxm_44528(self, logger):

        """
        Description:
        TCXM-52470 stp instance disable/enable.
        """

        logger.info("This test case is covered by tcxm_44528.")

    @pytest.mark.tcxm_42694
    @pytest.mark.p1
    def test_VLAN_with_LAG(self, xiq_library_at_class_level, test_data, node, node_1, node_2, logger, enter_switch_cli,
                           user_vlan_configure, get_vlan_info, get_vlan_ports_list,
                           generate_dhcp_snooping_cli, user_vlan_unconfigure):
        """
        Description:
        TCXM-42694 lag and add vlan to lag master port and check it.
        """
        try:
            global active_ports_list, random_port
            global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id

            if 'node_stack' in node.node_name:
                node_2 = node
            else:
                node_1 = node_2
                node_2 = node

            isl_list1 = PytestConfigHelper.create_ports_list(node_1.isl)
            isl_list2 = PytestConfigHelper.create_ports_list(node_2.isl)

            dhcp_snooping_option = generate_dhcp_snooping_cli()

            user_vlan_configure(node_2)
            print(f"node_1 value is {node_1}")
            print(f"node_2 value is {node_2}")

            logger.step("Executing pre cleanup before executing LAG Testcases on node_1.")
            user_vlan_unconfigure(enter_switch_cli, xiq_library_at_class_level, node_1)

            # create LAG in node_1
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, 'show vlan',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, 'show ip-security dhcp-snooping vlan default',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'enable sharing {isl_list1[0]} grouping {isl_list1[0]} {isl_list1[1]}',
                                 max_wait=10, interval=3)

            # create LAG and add LAG to min_vlan_name in node_2
            with enter_switch_cli(node_2) as dev_cmd:
                dev_cmd.send_cmd(node_2.name, f'disable ip-security dhcp-snooping vlan {min_vlan_name} ports all',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_2.name, f'configure stpd s0 delete vlan {min_vlan_name} ports all',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_2.name, f'enable sharing {isl_list2[0]} grouping {isl_list2[0]} {isl_list2[1]}',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_2.name,
                                 f'enable ip-security dhcp-snooping vlan {min_vlan_name} ports {isl_list2[0]} violation-action drop-packet block-port duration 1000',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_2.name, f'configure stpd s0 add vlan {min_vlan_name} ports {isl_list2[0]}',
                                 max_wait=10, interval=3)

            logger.step(f"Verify STATIC LAG Status in {node_2.name} in CLI after LAG Creation.")
            verify_cmd = []
            cmd = 'show port ' + isl_list2[0] + ' sharing'
            with enter_switch_cli(node_2) as dev_cmd:
                for port in isl_list2[0:2]:
                    verify_cmd = port + '\s+Y\s+A'
                    dev_cmd.send_cmd_verify_output_regex(node_2.name, cmd, verify_cmd, max_wait=10, interval=3)

            vlan_info = get_vlan_info(test_data['vlan_info'])
            vlan_info[min_vlan_id]['active_ports'].remove(isl_list2[1])

            # verify user created VLAN attributes details in D360 Monitor > Overview > Interface vlan table after LAG creation.
            logger.step(
                f"Verify user created vlan attribute details: {vlan_info} in Interface vlan table for Device {node_2.name} after LAG creation.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            # verify user created VLAN port details in D360 Monitor > Overview > Interface vlan page wireframe image after LAG creation.
            total_ports = active_ports_list + [random_port]
            key_list = ['oper_up_ports', 'total_ports', 'trunk_ports', 'lag_ports', 'port_highlighted']
            vlan_ports_list = get_vlan_ports_list(vlan_info, key_list, active_ports=active_ports_list,
                                                  total_ports=total_ports, trunk_ports=total_ports,
                                                  lag_ports=isl_list2[0:2])

            logger.step(
                f"Verify user created vlan port details: {vlan_ports_list} in Interface vlan table for Device {node_2.name} after LAG Creation")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node_2,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=True)

            # add ports into the LAG in node_1
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name,
                                 f'configure sharing {isl_list1[0]} add ports {isl_list1[2]} {isl_list1[3]}',
                                 max_wait=10, interval=3)

            # add ports into the LAG in node_2
            with enter_switch_cli(node_2) as dev_cmd:
                dev_cmd.send_cmd(node_2.name,
                                 f'configure sharing {isl_list2[0]} add ports {isl_list2[2]} {isl_list2[3]}',
                                 max_wait=10, interval=3)

            logger.step(f"Verify STATIC LAG Status in {node_2.name} in CLI after LAG member update.")
            verify_cmd = []
            cmd = 'show port ' + isl_list2[0] + ' sharing'
            with enter_switch_cli(node_2) as dev_cmd:
                for port in isl_list2[0:4]:
                    verify_cmd = port + '\s+Y\s+A'
                    dev_cmd.send_cmd_verify_output_regex(node_2.name, cmd, verify_cmd, max_wait=10, interval=3)

            # verify user created VLAN attributes details in D360 Monitor > Overview > Interface vlan table after LAG member update
            for port in isl_list2[2:4]:
                vlan_info[min_vlan_id]['active_ports'].remove(port)

            logger.step(
                f"Verify user created vlan attribute details: {vlan_info} in Interface vlan table for Device {node_2.name} after LAG member update.")

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            # verify user created VLAN port details in D360 Monitor > Overview > Interface vlan page wireframe image after LAG member update
            vlan_ports_list = get_vlan_ports_list(vlan_info, key_list, active_ports=active_ports_list,
                                                  total_ports=total_ports, trunk_ports=total_ports, lag_ports=isl_list2)

            logger.step(
                f"Verify user created vlan port details: {vlan_ports_list} in Interface vlan table for Device {node_2.name} after LAG member update.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node_2,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=True)

            # delete ports from the LAG in node_1
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name,
                                 f'configure sharing {isl_list1[0]} delete ports {isl_list1[2]} {isl_list1[3]}',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'configure vlan Default add ports {isl_list1[2]} {isl_list1[3]}',
                                 max_wait=10, interval=3)

            # delete ports from the LAG in node_2
            with enter_switch_cli(node_2) as dev_cmd:
                dev_cmd.send_cmd(node_2.name,
                                 f'configure sharing {isl_list2[0]} delete ports {isl_list2[2]} {isl_list2[3]}',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_2.name,
                                 f'configure vlan {min_vlan_name} add ports {isl_list2[2]} {isl_list2[3]} tagged',
                                 max_wait=10, interval=3)

            logger.step(f"Verify STATIC LAG Status in {node_2.name} in CLI after LAG member removal.")
            verify_cmd = []
            cmd = 'show port ' + isl_list2[0] + ' sharing'
            with enter_switch_cli(node_2) as dev_cmd:
                for port in isl_list2[2:4]:
                    verify_cmd = port + '\s+Y\s+A'
                    dev_cmd.send_cmd_verify_output_regex(node_2.name, cmd, verify_cmd, max_wait=10, interval=3,
                                                         exists=False)

            # verify user created VLAN attributes details in D360 Monitor > Overview > Interface vlan table after LAG Member removal.
            for port in isl_list2[2:4]:
                vlan_info[min_vlan_id]['active_ports'].append(port)

            logger.step(
                f"Verify user created vlan attribute details: {vlan_info} in D360 Interface vlan table for Device {node_2.name} after LAG Member Removal")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            # verify user created VLAN port details in D360 Monitor > Overview > Interface vlan page wireframe image after LAG Member removal.
            vlan_ports_list = get_vlan_ports_list(vlan_info, key_list, active_ports=active_ports_list,
                                                  total_ports=total_ports, trunk_ports=total_ports,
                                                  lag_ports=active_ports_list[0:2])

            logger.step(
                f"Verify user created vlan port details: {vlan_ports_list} in Interface vlan table for Device {node_2.name} after LAG Member Removal")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node_2,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=True)

            # delete the LAG in node_1
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, f'disable sharing {isl_list1[0]}', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'configure vlan Default add ports {isl_list1[0]} {isl_list1[1]}',
                                 max_wait=10, interval=3)

            # delete the LAG in node_2
            with enter_switch_cli(node_2) as dev_cmd:
                dev_cmd.send_cmd(node_2.name, f'disable sharing {isl_list2[0]}',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_2.name,
                                 f'configure vlan {min_vlan_name} add ports {isl_list2[0]} {isl_list2[1]} tagged',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_2.name,
                                 f'enable ip-security dhcp-snooping vlan {min_vlan_name} ports all violation-action {dhcp_snooping_option}',
                                 max_wait=10, interval=3)
                dev_cmd.send_cmd(node_2.name, f'configure stpd s0 add vlan {min_vlan_name} ports all',
                                 max_wait=10, interval=3)
            # verify user created VLAN attributes details in D360 Monitor > Overview > Interface vlan table after LAG Deletion.
            vlan_info[min_vlan_id]['active_ports'] = active_ports_list

            logger.step(f"Verify STATIC LAG Status in {node_2.name} in CLI after LAG Deletion.")
            verify_cmd = []
            cmd = 'show port ' + isl_list2[0] + ' sharing'
            with enter_switch_cli(node_2) as dev_cmd:
                for port in isl_list2[0:2]:
                    verify_cmd = port + '\s+Y\s+A'
                    dev_cmd.send_cmd_verify_output_regex(node_2.name, cmd, verify_cmd, max_wait=10, interval=3,
                                                         exists=False)

            logger.step(
                f"Verify user created vlan attribute details: {vlan_info} in D360 Interface vlan table for Device {node_2.name} after LAG Deletion")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   skip_stp_status=
                                                                                                   test_data[
                                                                                                       'skip_stp_status'],
                                                                                                   skip_list_of_active_ports=
                                                                                                   test_data[
                                                                                                       'skip_list_of_active_ports'])

            # verify user created VLAN port details in D360 Monitor > Overview > Interface vlan page wireframe image after LAG Deletion.
            key_list = ['oper_up_ports', 'total_ports', 'trunk_ports', 'port_highlighted']
            vlan_ports_list = get_vlan_ports_list(vlan_info, key_list, active_ports=active_ports_list,
                                                  total_ports=total_ports, trunk_ports=total_ports)

            logger.step(
                f"Verify user created vlan port details: {vlan_ports_list} in Interface vlan table for Device {node_2.name} after LAG Deletion.")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node_2,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=True)

        finally:
            logger.step('Test Execution completed, Clean the LAG configuration.')
            for node_ele in [node_1, node_2]:
                with enter_switch_cli(node_ele) as dev_cmd:
                    cmd = 'show configuration vlan | grep sharing'
                    output = dev_cmd.send_cmd(node_ele.name, cmd, max_wait=10, interval=3)
                    output_text = output[0].cmd_obj.return_text
                    out = output_text.replace('\r', '')
                    out = out.split("\n")
                    logger.info(f'CLI output is {output_text}')
                    pattern = 'enable sharing (\d+|\d+:\d+|\d+:\d+:\d+) .*'

                    for line in out:
                        match = re.search(rf'{pattern}', line)
                        if match:
                            logger.step('clearing the LAG config via CLI.')
                            cmd = 'disable sharing ' + match.group(1)
                            dev_cmd.send_cmd(node_ele.name, cmd, max_wait=10, interval=3)

                        if node_ele.name == node_2.name:
                            dev_cmd.send_cmd(node_ele.name,
                                             f'configure vlan {min_vlan_name} add ports {isl_list2[0]} {isl_list2[1]} {isl_list2[2]} {isl_list2[3]} tagged',
                                             max_wait=10, interval=3)
                            dev_cmd.send_cmd(node_ele.name,
                                             f'configure vlan {max_vlan_name} add ports {isl_list2[0]} {isl_list2[1]} {isl_list2[2]} {isl_list2[3]} untagged',
                                             max_wait=10, interval=3)
                        else:
                            dev_cmd.send_cmd(node_ele.name, f'configure vlan Default add ports all', max_wait=10,
                                             interval=3)

    @pytest.mark.tcxm_42867
    @pytest.mark.dependson("tcxm_42694")
    @pytest.mark.p1
    def test_depends_on_tcxm_42694(self, logger):
        """
        Description:
        TCXM-42867 switching ports between vlan(s).
        """
        logger.info("This test case is covered by tcxm_42694.")

    @pytest.mark.tcxm_42697
    @pytest.mark.p1
    def test_VLAN_with_cloud_config(self, xiq_library_at_class_level, node, logger, enter_switch_cli, utils,
                                    user_vlan_configure, request, user_vlan_unconfigure):
        """
        Description:
        TCXM-42697 create vlan via template and check with in 2 mins table's are updated.
        """
        try:
            global active_ports_list, random_port, base_config_flag
            global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id
            vlan_config = 0

            # clear the vlan configuration which was done by cli.
            user_vlan_unconfigure(enter_switch_cli, xiq_library_at_class_level, node)
            base_config_flag = False

            logger.info("Closing D360 window before configuring port type.")
            close_btn = xiq_library_at_class_level.xflowsmanageDevice360.dev360.get_close_dialog()
            if close_btn:
                xiq_library_at_class_level.xflowsmanageDevice360.close_device360_window()

            node_policy_name = request.getfixturevalue(f"{node.node_name}_policy_name")
            node_template_name = request.getfixturevalue(f"{node.node_name}_template_name")
            port_profile_name1 = f"vlan_monitor_Trunk_{random.randint(0, 1000)}"

            port_profile = {}
            port_profile['name'] = [port_profile_name1, port_profile_name1]
            port_profile['description'] = [None, None]
            port_profile['status'] = [None, 'on']
            port_profile['port usage'] = ['trunk port', 'TRUNK']
            port_profile['page2 trunkVlanPage'] = ['next_page', None]
            port_profile['native vlan'] = ['1', '1']
            port_profile['allowed vlans'] = ['2-1001', '2-1001']
            # port_profile['page3 instantsecureportSettings'] = ["next_page", None]
            port_profile['page4 transmissionSettings'] = ["next_page", None]
            port_profile['page5 stpPage'] = ["next_page", None]
            port_profile['page6 stormControlSettings'] = ["next_page", None]
            port_profile['page7 MACLOCKINGSettingsPage'] = ["next_page", None]
            port_profile['page8 ELRPSettingsPage'] = ["next_page", None]
            port_profile['page9 pseSettings'] = ["next_page", None]
            port_profile['page10 summary'] = ["next_page", None]

            logger.step("Create Trunk port type in LAG master port.")
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_policy_name,
                                                                                        node_template_name,
                                                                                        node.cli_type)

            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
            if node.platform.lower() == 'stack':
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.sw_template_stack_select_slot(
                    active_ports_list[0][0])

            xiq_library_at_class_level.xflowsmanageDevice360.create_new_port_type(port_profile, active_ports_list[0],
                                                                                  d360=False)

            xiq_library_at_class_level.Screen.save_screen_shot()
            save_template_button = xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template.sw_template_web_elements.save_device_template()
            if save_template_button:
                logger.info("Clicking the Save Template Button")
                xiq_library_at_class_level.xflowscommonAutoActions.click_reference(
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template.sw_template_web_elements.save_device_template)
                logger.info(f"Successfully saved {node_template_name} template")
                utils.wait_till(timeout=10)
                xiq_library_at_class_level.Screen.save_screen_shot()
            else:
                logger.fail(f"Failed to save DUT {node_template_name} Template")

            # navigate to manage---Devices page.
            xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
            # refresh the page before selecting device
            xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
            # wait till added to avoid stale element exception
            utils.wait_till(timeout=10)

            logger.step(f"View Delta Command for Mac mac: {node.mac}.")
            xiq_library_at_class_level.xflowsmanageDeviceConfig.get_device_config_audit_delta(node.mac)

            logger.step("Perform Device update after configuring Trunk port type in Device Template.")
            xiq_library_at_class_level.xflowsmanageDevices.get_update_devices_reboot_rollback(
                policy_name=node_policy_name, option='disable', device_mac=node.mac, skip_refresh=True,
                skip_navigation=True)

            logger.step("Verify the Device update status after configuration update")
            xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node.mac)

            # vlan_config flag set to 1 since vlan configured.
            vlan_config = 1

            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, 'configure stpd s0 priority 4096', max_wait=10, interval=3)

            logger.step(f"Verify vlan details for node {node.name}")
            vlan_info = {}

            for vlan_id in range(2, 1002):
                vlan_info.update({str(vlan_id): {}})
                vlan_info[str(vlan_id)] = {'name': '', 'active_ports': [active_ports_list[0]],
                                           'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                           'igmp_snooping': '', 'dhcp_snooping': ''}

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   retry_duration=30,
                                                                                                   retry_count=4)

            # verify scale vlan details in wireframe image.
            logger.step(f"Verify scale vlan details in wireframe image for node {node.name}")
            vlan_ports_list = {}

            for vlan_id in range(100, 1002, 100):
                vlan_ports_list.update({str(vlan_id): {}})
                vlan_ports_list[str(vlan_id)] = {'oper_up_ports': [active_ports_list[0]],
                                                 'total_ports': [active_ports_list[0]],
                                                 'trunk_ports': [active_ports_list[0]]}

            vlan_ports_list['1001'] = {'oper_up_ports': [active_ports_list[0]],
                                       'total_ports': [active_ports_list[0]],
                                       'trunk_ports': [active_ports_list[0]]}
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=False,
                                                                                                               retry_duration=30,
                                                                                                               retry_count=4)

            with enter_switch_cli(node) as dev_cmd:
                dev_cmd.send_cmd(node.name, 'configure stpd s0 priority 32768', max_wait=10, interval=3)

            logger.step('Unconfigure Port Type and delete the port Type and VLAN information')
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_policy_name,
                                                                                        node_template_name,
                                                                                        node.cli_type)
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
            utils.wait_till(timeout=10)
            port = active_ports_list[0]
            if node.platform.lower() == 'stack':
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.sw_template_stack_select_slot(
                    active_ports_list[0][0])
                utils.wait_till(timeout=10)
                port = active_ports_list[0].split(':')[1]

            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(
                port, 'Access Port')

            logger.step("Update the configuration after unconfiguring Port Type.")
            xiq_library_at_class_level.xflowsmanageDevices.get_update_devices_reboot_rollback(
                policy_name=node_policy_name, option='disable', device_mac=node.mac, skip_refresh=True,
                skip_navigation=True)

            logger.step("Verify the device status after configuration update for unconfiguring Port Type.")
            xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node.mac)

            # vlan_config set to 0 since vlan unconfigured successfully.
            vlan_config = 0

            logger.step(f"Delete the port profile created for testing port_type {port_profile_name1}")
            xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_port_type_profile(port_profile_name1)
        finally:
            if vlan_config:
                logger.step("Testcase Failed, vlan config not cleared within the testcase.")
                user_vlan_unconfigure(enter_switch_cli, xiq_library_at_class_level, node)

            logger.step('Test Execution completed, Configure Base VLAN Configuration.')
            user_vlan_configure(node)

    @pytest.mark.tcxm_42862
    @pytest.mark.dependson("tcxm_42697")
    @pytest.mark.p2
    def test_depends_on_tcxm_42697(self, logger):
        """
        Description:
        TCXM-42862 Pagination should be seen in vlan monitoring view.
        """
        logger.info("This test case is covered by tcxm_42697.")

    @pytest.mark.tcxm_57793
    @pytest.mark.p2
    def test_wireframe_port_info(self, xiq_library_at_class_level, node, logger, enter_switch_cli, test_data,
                                 get_vlan_info, get_vlan_ports_list, user_vlan_configure, request):
        """
        Description:
        TCXM-57793 Verify Port info popup fields.
        """
        global active_ports_list, random_port
        global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id
        poe_flag = request.getfixturevalue("node_poe_capability")
        poe_capable = 'no'
        copper_port = 'no'

        user_vlan_configure(node)

        vlan_info = get_vlan_info(test_data['vlan_info'])
        logger.step(
            f"Verify user created vlan attribute details: {vlan_info} in D360 Monitor > Overview > Interface vlan table for Device {node.name}")

        xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node, vlan_info,
                                                                                               skip_d360_close=True,
                                                                                               skip_stp_status=
                                                                                               test_data[
                                                                                                   'skip_stp_status'],
                                                                                               skip_list_of_active_ports=
                                                                                               test_data[
                                                                                                   'skip_list_of_active_ports'])

        # verify user created VLAN port details in D360 Monitor > Overview > Interface vlan page wireframe image.
        total_ports = active_ports_list + [random_port]
        key_list = ['oper_up_ports', 'total_ports', 'trunk_ports', 'port_highlighted']
        vlan_ports_list = get_vlan_ports_list(vlan_info, key_list, active_ports=active_ports_list,
                                              total_ports=total_ports, trunk_ports=total_ports)

        xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node,
                                                                                                           vlan_ports_list,
                                                                                                           skip_d360_close=True)

        with enter_switch_cli(node) as dev_cmd:
            if poe_flag:
                # Perform deletion of the extra vlan id's configured in the device.
                out = dev_cmd.send_cmd(node.name, f'show inline-power configuration ports {active_ports_list[0]}',
                                       max_wait=10, interval=3)[0].return_text
                out = out.replace('\r', '')
                out = out.split("\n")
                for line in out:
                    if re.search(rf'{active_ports_list[0]}\s*Enabled', line):
                        poe_capable = 'yes'

            out = \
                dev_cmd.send_cmd(node.name,
                                 f'show ports {active_ports_list[0]} transceiver information | grep "DDMI is"',
                                 max_wait=10, interval=3)[0].return_text
            if re.search(rf'DDMI is not supported on this port', out):
                copper_port = 'yes'

        logger.step(f"Verify VLAN port info for node {node.name}")
        vlan_ports_list = {
            str(active_ports_list[0]): {'port_status': 'up', 'access_vlan': max_vlan_id, 'tagged_vlan(s)': min_vlan_id,
                                        'poe_capable': poe_capable, 'copper_port': copper_port}}

        xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_info(node,
                                                                                                        vlan_ports_list,
                                                                                                        skip_d360_close=True)

        logger.step(f"Verify VLAN port info actions for node {node.name}")
        xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_info_actions(node, [
            active_ports_list[0]], skip_d360_close=False)

    @pytest.mark.tcxm_6000
    @pytest.mark.p1
    def test_ipp_VLAN_config(self, xiq_library_at_class_level, node_1, node_2, node, logger, enter_switch_cli, utils,
                             navigator, configure_stp_priority,
                             user_vlan_configure, request, user_vlan_unconfigure):

        try:
            if node.platform.lower() == "stack":
                node_2 = node

            node_2 = node_1
            node_1 = node

            global active_ports_list, random_port, base_config_flag
            global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id

            poe_flag = request.getfixturevalue("node_2_poe_capability")
            poe_capable = 'no'
            copper_port = 'no'

            # clear the vlan configuration which was done by cli.
            # user_vlan_unconfigure(enter_switch_cli, xiq_library_at_class_level, node)
            # base_config_flag = False

            # logger.info("Closing D360 window before configuring port type.")
            # close_btn = xiq_library_at_class_level.xflowsmanageDevice360.dev360.get_close_dialog()
            # if close_btn:
            #     xiq_library_at_class_level.xflowsmanageDevice360.close_device360_window()

            node_2_policy_name = request.getfixturevalue(f"{node_2.node_name}_policy_name")
            node_2_template_name = request.getfixturevalue(f"{node_2.node_name}_template_name")
            node_2_policy_name = "5520_POLICY"
            node_2_template_name = "5520_TEMP"
            isl_list2 = PytestConfigHelper.create_ports_list(node_2.isl)
            configure_stp_priority(xiq_library_at_class_level, logger, utils, node_2_policy_name, '4096')

            device_type_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.network_policy.get_random_name(
                "device_type")
            new_instant_port_profile_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.network_policy.get_random_name(
                "test_ipp")
            default_port_type_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.network_policy.get_random_name(
                "default_pt")
            nfw_vlan_id = min_vlan_id
            nfw_vlan_name = f"VLAN_{nfw_vlan_id}"
            action_vlan_id = str(int(min_vlan_id) + 1)
            action_vlan_name = f"VLAN_{action_vlan_id}"
            action_vlan_range = str(int(action_vlan_id) + 1) + "-" + str(int(action_vlan_id) + 10)
            default_port_vlan_id = max_vlan_id
            default_port_vlan_name = f"VLAN_{default_port_vlan_id}"
            default_port_type_vlan_range = str(int(default_port_vlan_id) + 1) + "-" + str(
                int(default_port_vlan_id) + 10)

            device_type_parameters = {"flag": "New", "name": device_type_name, "matchCategory": "LLDP Src MAC",
                                      "description": "new device type test", "createMacAddress": "Yes",
                                      "createMacAddressOui": "Yes",
                                      "macAdressValue": node_1.mac, "macAddressName": node_1.mac,
                                      "portUsage": "Trunk Port", "macOuiName": None,
                                      "actionVlanCreate": "Yes", "actionVlanName": action_vlan_name,
                                      "actionVlanID": action_vlan_id,
                                      "allowedVlansList": action_vlan_range,
                                      "voiceVlanCreate": None, "dataVlanCreate": None, "voiceVlanName": None,
                                      "voiceVlanId": None, "dataVlanName": None, "dataVlanId": None,
                                      "stormControlSettings": "No"}

            instant_port_parameters = {"createFrom": "Network Policy", "name": new_instant_port_profile_name,
                                       "description": "VLAN_IPP_PROFILE",
                                       "defaultPortName": default_port_type_name,
                                       "createNonForwardingVlan": "Yes", "nfwVlanName": nfw_vlan_name,
                                       "nfwVlanId": nfw_vlan_id,
                                       "createDefaultPortType": "Yes",
                                       "portTypeUsage": "trunk",
                                       "portTypeVlanName": default_port_vlan_name,
                                       "portTypeVlanId": default_port_vlan_id,
                                       "portTypeAllowedVl": default_port_type_vlan_range,
                                       "nonMatchAction": "Default Port Type"}

            # xiq_library_at_class_level.xflowsconfigureNetworkPolicy.network_policy.navigate_to_np_instant_port(
            #     node_2_policy_name)
            #
            # logger.info("Step 2: Create an instant port profile with non-match action 'Use non-forwarding vlan'")
            # xiq_library_at_class_level.xflowsconfigureNetworkPolicy.network_policy.configure_instant_port_profile(
            #     instant_port_parameters, [device_type_parameters])
            #
            # logger.info("Step 4: Push configuration to device")
            # xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
            #                                                                             node_2_template_name,
            #                                                                             node_2.cli_type)
            # xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
            # xiq_library_at_class_level.xflowsconfigureNetworkPolicy.network_policy.select_create_instant_port_switch_template(
            #     new_instant_port_profile_name)
            # xiq_library_at_class_level.xflowsconfigureNetworkPolicy.network_policy.enable_disable_instant_port_profile_on_ports_switch_template(
            #     isl_list2, "ON")
            # saved_template = xiq_library_at_class_level.xflowsconfigureSwitchTemplate.save_template()
            # assert saved_template == 1, "Was not able to save the device template"
            #
            # logger.step("Update the config to device")
            # xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
            # logger.step(f"View Delta Command for Mac mac: {node_2.mac}.")
            # xiq_library_at_class_level.xflowsmanageDeviceConfig.get_device_config_audit_delta(node_2.mac)
            # xiq_library_at_class_level.xflowsmanageDevices.update_device_delta_configuration(device_mac=node_2.mac)
            # xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node_2.mac)

            # collect ipp port details from device.
            logger.step(f"Verify scale vlan details in wireframe image for node {node_2.name}")
            ipp_port = ''
            count = 0
            with enter_switch_cli(node_2) as dev_cmd:
                while (count <= 120):
                    out = \
                        dev_cmd.send_cmd(node_2.name, f'show vlan {action_vlan_id} | grep Untag:', max_wait=5,
                                         interval=3)[
                            0].return_text
                    match = re.search('Untag:\s*\*(\d+:\d+|\d+)mS', out)
                    if match:
                        ipp_port = match.group(1)
                        break
                    else:
                        utils.wait_till(timeout=30)
                        count += 30

            if not ipp_port:
                logger.fail(f"Failed to read ipp port assigned in action vlan on device.")

            logger.step(f"Verify vlan details for node {node_2.name}")
            vlan_info = {}

            for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                vlan_info.update({str(vlan_id): {}})
                vlan_info[str(vlan_id)] = {'name': '', 'active_ports': ipp_port,
                                           'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                           'igmp_snooping': '', 'dhcp_snooping': ''}

            vlan_info[nfw_vlan_id] = {'name': '', 'active_ports': isl_list2,
                                      'stp_instance': {'name': 's0', 'status': 'Enabled'}, 'igmp_snooping': 'Disabled',
                                      'dhcp_snooping': ''}

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2, vlan_info,
                                                                                                   skip_d360_close=True,
                                                                                                   retry_duration=30,
                                                                                                   retry_count=4)

            vlan_ports_list = {}
            for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                vlan_ports_list.update({str(vlan_id): {}})
                vlan_ports_list[str(vlan_id)] = {'oper_up_ports': [ipp_port], 'total_ports': [ipp_port],
                                                 'trunk_ports': [ipp_port]}

            vlan_ports_list[nfw_vlan_id] = {'oper_up_ports': isl_list2, 'total_ports': isl_list2,
                                            'trunk_ports': [ipp_port]}

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node_2,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=False,
                                                                                                               retry_duration=30,
                                                                                                               retry_count=4)

            logger.step(f"Verify VLAN port info for node {node_2.name}")
            vlan_ports_list = {}
            for port in isl_list2:
                poe_capable = 'no'
                copper_port = 'no'
                with enter_switch_cli(node_2) as dev_cmd:
                    if poe_flag:
                        # Perform deletion of the extra vlan id's configured in the device.
                        out = \
                            dev_cmd.send_cmd(node_2.name, f'show inline-power configuration ports {port}', max_wait=10,
                                             interval=3)[0].return_text
                        out = out.replace('\r', '')
                        out = out.split("\n")
                        for line in out:
                            if re.search(rf'{port}\s*Enabled', line):
                                poe_capable = 'yes'

                    out = dev_cmd.send_cmd(node_2.name, f'show ports {port} transceiver information | grep "DDMI is"',
                                           max_wait=10, interval=3)[0].return_text
                    if re.search(rf'DDMI is not supported on this port', out):
                        copper_port = 'yes'

                vlan_ports_list.update({str(port): {}})
                vlan_ports_list[str(port)] = {'port_status': 'up', 'access_vlan': nfw_vlan_id, 'tagged_vlan(s)': '',
                                              'poe_capable': poe_capable, 'copper_port': copper_port}
                if port == ipp_port:
                    vlan_ports_list[port]['tagged_vlan(s)'] = action_vlan_range

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_info(node_2,
                                                                                                            vlan_ports_list,
                                                                                                            skip_d360_close=False)

        finally:
            logger.info("Test Execution completed. Cleanup the IPP Config")
            # xiq_library_at_class_level.xflowsconfigureNetworkPolicy.navigate_to_np_edit_tab(node_2_policy_name)
            # xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_policy_switching_tab()

            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                        node_2_template_name,
                                                                                        node_2.cli_type)
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
            utils.wait_till(timeout=10)
            logger.step(f"Disable instant port profile on the switch template '{node_2_template_name}'.")
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.network_policy.select_create_instant_port_switch_template(
                "-----")

            assert xiq_library_at_class_level.xflowsconfigureSwitchTemplate.save_template() == 1, "Was not able to save the device template"

            logger.step('Unconfigure Port Type and delete the port Type and VLAN information')
            navigator.wait_until_loading_is_done()
            if node_2.platform.lower() == 'stack':
                slot_list = list(set([p.split(':')[0] for p in isl_list2]))
                for slot in slot_list:
                    globals()['slot'] = slot
                    port_str = ','.join([p.split(':')[1] for p in isl_list2 if slot in p])
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                                node_2_template_name,
                                                                                                node_2.cli_type)
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.sw_template_stack_select_slot(slot)
                    utils.wait_till(timeout=10)

                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(
                        port_str, 'Access Port')
            else:
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                            node_2_template_name,
                                                                                            node_2.cli_type)
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
                port_str = ','.join(isl_list2)
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(
                    port_str, 'Access Port')
            logger.step(f"Delete instant port profile '{new_instant_port_profile_name}'.")
            # Delete instant port configuration
            is_deleted = xiq_library_at_class_level.xflowsconfigureCommonObjects.common_objects.delete_instant_port_profile_from_common_obj(
                new_instant_port_profile_name)
            assert is_deleted, "Could not delete the Instant Port Profile"

            vlan_list = [instant_port_parameters["nfwVlanName"], device_type_parameters["actionVlanName"]]
            for vlan_name in vlan_list:
                try:
                    logger.step(f"Delete vlan '{vlan_name}'.")
                    xiq_library_at_class_level.xflowsconfigureCommonObjects.common_objects.delete_vlan_profile(
                        vlan_name)
                except Exception as exc:
                    logger.warning(exc)

            if mac_list := list(
                    filter(bool, [device_type_parameters["macOuiName"], device_type_parameters["macAddressName"]])):
                try:
                    logger.step(f"Delete mac objects '{mac_list}'.")
                    xiq_library_at_class_level.xflowsconfigureCommonObjects.common_objects.delete_mac_object_oui(
                        mac_list)
                except Exception as exc:
                    logger.warning(exc)

            logger.step(f"Delete the port profile created for testing port_type {default_port_type_name}")
            xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_port_type_profile(default_port_type_name)

            logger.step("Update the config to device")
            xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
            logger.step(f"View Delta Command for Mac mac: {node_2.mac}.")
            xiq_library_at_class_level.xflowsmanageDeviceConfig.get_device_config_audit_delta(node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.update_device_delta_configuration(device_mac=node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node_2.mac)

            vlan_info = {}

            for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                vlan_info.update({str(vlan_id): {}})
                vlan_info[str(vlan_id)] = {'name': '', 'active_ports': ipp_port,
                                           'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                           'igmp_snooping': '', 'dhcp_snooping': ''}

            vlan_info[nfw_vlan_id] = {'name': '', 'active_ports': isl_list2,
                                      'stp_instance': {'name': 's0', 'status': 'Enabled'}, 'igmp_snooping': 'Disabled',
                                      'dhcp_snooping': ''}

            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2, vlan_info,
                                                                                                   skip_d360_close=False,
                                                                                                   retry_duration=30,
                                                                                                   retry_count=4,
                                                                                                   vlan_exist=False)

    @pytest.mark.tcxm_66998
    @pytest.mark.tcxm_67001
    @pytest.mark.tcxm_67002
    @pytest.mark.p1
    def test_ipp_VLAN_config(self, xiq_library_at_class_level, node_1, node_2, node, logger, enter_switch_cli, utils,
                             navigator, configure_stp_priority,
                             user_vlan_configure, request, user_vlan_unconfigure, test_data):
        """
        Description:
        TCXM-66998 "Verify D360 Overview-----Interface---vlan table for vlan's Configured using IPP from policy, select Non-Match Action:
                 Non-Forwarding VLAN and configure below Device type: LLDP src MAC - MAC match; Trunk port."

        TCXM-67001 "Verify D360 Overview-----Interface---vlan table for vlan's Configured using IPP from policy, select Non-Match Action:
                 Use Default Port Type VLAN with default port type as Trunk Port and configure below Device type: LLDP src MAC - MAC match; Trunk port
                 Trunk port."

        TCXM-67002 "Verify D360 Overview-----Interface---vlan table for vlan's Configured using IPP from policy, select Non-Match Action:
                Use Default Port Type VLAN with default port type as Voip Port  and configure below Device type: LLDP src MAC - MAC match; Voip port."
        """
        try:
            if node.platform.lower() == "stack":
                node_2 = node

            global active_ports_list, random_port, base_config_flag
            global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id
            poe_flag = request.getfixturevalue("node_2_poe_capability")

            node_2_policy_name = request.getfixturevalue(f"{node_2.node_name}_policy_name")
            node_2_template_name = request.getfixturevalue(f"{node_2.node_name}_template_name")
            # node_2_policy_name = "5420_TEMP"
            # node_2_template_name = "5420_stack"
            # node_2_policy_name = "5420
            # node_2_template_name = "5520-Series-Stack"
            logger.info(f"the min is: {min_vlan_id}")
            logger.info(f" the max is: {max_vlan_id}")

            isl_list2 = PytestConfigHelper.create_ports_list(node_2.isl)
            isl_list1 = PytestConfigHelper.create_ports_list(node_1.isl)
            isl_port = ",".join(isl_list1)

            configure_stp_priority(xiq_library_at_class_level, logger, utils, node_2_policy_name, '4096')
            device_type_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.get_random_name("device_type")
            new_instant_port_profile_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.get_random_name(
                "test_ipp")
            default_port_type_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.get_random_name(
                "default_pt")
            nfw_vlan_id = min_vlan_id
            nfw_vlan_name = f"VLAN_{nfw_vlan_id}"
            action_vlan_id = str(int(min_vlan_id) + 1)
            action_vlan_name = f"VLAN_{action_vlan_id}"
            action_vlan_range = str(int(action_vlan_id) + 1) + "-" + str(int(action_vlan_id) + 10)
            voice_vlan_id = str(int(min_vlan_id) + 2)
            voice_vlan_name = f"VLAN_{voice_vlan_id}"
            default_port_vlan_id = max_vlan_id
            default_port_vlan_name = f"VLAN_{default_port_vlan_id}"
            default_port_voice_vlan_id = str(int(max_vlan_id) + 1)
            default_port_voice_vlan_name = f"VLAN_{default_port_voice_vlan_id}"
            default_port_type_vlan_range = str(int(default_port_vlan_id) + 1) + "-" + str(
                int(default_port_vlan_id) + 10)

            if test_data['match_type'] == "non-forwarding":
                instant_port_parameters = {"createFrom": "Network Policy", "name": new_instant_port_profile_name,
                                           "description": "VLAN_IPP_PROFILE",
                                           "defaultPortName": "Access Port",
                                           "createNonForwardingVlan": "Yes", "nfwVlanName": nfw_vlan_name,
                                           "nfwVlanId": nfw_vlan_id,
                                           "createDefaultPortType": "No",
                                           "portTypeUsage": None,
                                           "portTypeVlanName": None,
                                           "portTypeVlanId": None,
                                           "portTypeAllowedVl": None,
                                           "nonMatchAction": "Non-Forwarding VLAN"}
                instant_mac = node_1.mac
                instant_vlan = action_vlan_id
            elif test_data['match_type'] == "default_port_type":
                instant_mac = node_2.mac
                instant_vlan = default_port_vlan_id
                if test_data['default_port_type'] == "voip":
                    port_profile = {}
                    port_profile['name'] = [default_port_type_name, default_port_type_name]
                    port_profile['description'] = [None, None]
                    port_profile['status'] = [None, 'on']
                    port_profile['port usage'] = ['phone port', 'Phone_data']
                    port_profile['page2 phoneVlanPage'] = ['next_page', None]
                    port_profile['voice vlan'] = [default_port_voice_vlan_id, default_port_voice_vlan_id]
                    port_profile['data vlan'] = [default_port_vlan_id, default_port_vlan_id]
                    port_profile['page summaryPage'] = ["next_all_pages", None]

                    logger.step("Create voip port type to use it as default port type.")
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                                node_2_template_name,
                                                                                                node_2.cli_type)

                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
                    if node_2.platform.lower() == 'stack':
                        select_slot = isl_list2[0].split(':')[0]
                        xiq_library_at_class_level.xflowsconfigureSwitchTemplate.sw_template_stack_select_slot(
                            select_slot)

                        xiq_library_at_class_level.xflowsmanageDevice360.create_new_port_type(port_profile,
                                                                                              isl_list2[0].split(':')[
                                                                                                  1],
                                                                                              d360=False)

                        xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(
                            isl_list2[0].split(':')[1], 'Access Port')
                    else:
                        xiq_library_at_class_level.xflowsmanageDevice360.create_new_port_type(port_profile,
                                                                                              isl_list2[0],
                                                                                              d360=False)

                        xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(
                            isl_list2[0], 'Access Port')

                    instant_port_parameters = {"createFrom": "Network Policy", "name": new_instant_port_profile_name,
                                               "description": "VLAN_IPP_PROFILE",
                                               "defaultPortName": default_port_type_name,
                                               "createNonForwardingVlan": "Yes", "nfwVlanName": nfw_vlan_name,
                                               "nfwVlanId": nfw_vlan_id,
                                               "createDefaultPortType": "No",
                                               "portTypeUsage": None,
                                               "portTypeVlanName": None,
                                               "portTypeVlanId": None,
                                               "portTypeAllowedVl": None,
                                               "nonMatchAction": "Default Port Type"}
                else:
                    instant_port_parameters = {"createFrom": "Network Policy", "name": new_instant_port_profile_name,
                                               "description": "VLAN_IPP_PROFILE",
                                               "defaultPortName": default_port_type_name,
                                               "createNonForwardingVlan": "Yes", "nfwVlanName": nfw_vlan_name,
                                               "nfwVlanId": nfw_vlan_id,
                                               "createDefaultPortType": "Yes",
                                               "portTypeUsage": "trunk",
                                               "portTypeVlanName": default_port_vlan_name,
                                               "portTypeVlanId": default_port_vlan_id,
                                               "portTypeAllowedVl": default_port_type_vlan_range,
                                               "nonMatchAction": "Default Port Type"}
            else:
                logger.fail("Unsupported IPP Match Type given for this method.")

            if test_data['action_vlan_type'] == "trunk":
                device_type_parameters = {"flag": "New", "name": device_type_name, "matchCategory": "LLDP Src MAC",
                                          "description": "new device type test", "createMacAddress": "Yes",
                                          "createMacAddressOui": "No",
                                          "macAdressValue": instant_mac, "macAddressName": instant_mac,
                                          "portUsage": "Trunk Port", "macOuiName": None,
                                          "actionVlanCreate": "Yes", "actionVlanName": action_vlan_name,
                                          "actionVlanID": action_vlan_id,
                                          "allowedVlansList": action_vlan_range,
                                          "voiceVlanCreate": None, "dataVlanCreate": None, "voiceVlanName": None,
                                          "voiceVlanId": None, "dataVlanName": None, "dataVlanId": None,
                                          "stormControlSettings": "No"}
            elif test_data['action_vlan_type'] == "voip":
                device_type_parameters = {"flag": "New", "name": device_type_name, "matchCategory": "LLDP Src MAC",
                                          "description": "new device type test", "createMacAddress": "Yes",
                                          "createMacAddressOui": "No",
                                          "macAdressValue": instant_mac, "macAddressName": instant_mac,
                                          "portUsage": "Phone Port", "macOuiName": None,
                                          "actionVlanCreate": "Yes", "actionVlanName": action_vlan_name,
                                          "actionVlanID": action_vlan_id,
                                          "allowedVlansList": None,
                                          "createVoiceVlan": "Yes", "dataVlanCreate": "Yes",
                                          "voiceVlanName": voice_vlan_name,
                                          "voiceVlanId": voice_vlan_id, "dataVlanName": action_vlan_name,
                                          "dataVlanId": action_vlan_id,
                                          "stormControlSettings": "No"}
            else:
                logger.fail("Unsupported Action vlan Type for this method.")

            logger.info(f"Step 2: Create an instant port profile with non-match action {test_data['match_type']}")
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.navigate_to_np_instant_port(node_2_policy_name)
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.configure_instant_port_profile(
                instant_port_parameters, [device_type_parameters])

            logger.info("Step 4: Push configuration to device")
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                        node_2_template_name,
                                                                                        node_2.cli_type)
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.select_create_instant_port_switch_template(
                new_instant_port_profile_name)

            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.enable_disable_instant_port_profile_on_ports_switch_template(
                isl_list2, "ON")

            saved_template = xiq_library_at_class_level.xflowsconfigureSwitchTemplate.save_template()
            assert saved_template == 1, "Was not able to save the device template"

            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, 'configure vlan Default delete port all', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'configure vlan Default add port {isl_port}', max_wait=10, interval=3)
                if test_data['match_type'] == "default_port_type":
                    dev_cmd.send_cmd(node_1.name, 'configure vlan Default ipaddress 10.10.10.1/24', max_wait=10,
                                     interval=3)
                dev_cmd.send_cmd(node_1.name, 'configure stpd s0 add vlan Default port all', max_wait=10,
                                 interval=3)
            logger.step("Update the config to device")
            xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
            logger.step(f"View Delta Command for Mac mac: {node_2.mac}.")
            xiq_library_at_class_level.xflowsmanageDevices.update_device_delta_configuration(device_mac=node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node_2.mac)
            isl_list1 = PytestConfigHelper.create_ports_list(node_1.isl)
            ports_list = ','.join(isl_list1)

            # This is done to avoid the multiple MAC address on the single port in node_2 which would cause the "No Match" for the ipp_port
            with enter_switch_cli(node_1) as dev_cmd:
                if test_data['match_type'] == "default_port_type":
                    dev_cmd.send_cmd(node_1.name, 'ping 10.10.10.2', max_wait=10, interval=3)

            # collect ipp port details from device.
            logger.step(f"Verify Ipp port assigned in action vlan on device. {node_2.name}")
            ipp_port = ''
            count = 0
            with enter_switch_cli(node_2) as dev_cmd:
                while (count <= 120):
                    out = \
                        dev_cmd.send_cmd(node_2.name, f'show vlan {instant_vlan} | grep Untag:', max_wait=5,
                                         interval=3)[
                            0].return_text
                    match = re.search('Untag:\s*\*(\d+:\d+|\d+)mS', out)
                    if match:
                        ipp_port = match.group(1)
                        break
                    else:
                        utils.wait_till(timeout=3)
                        count += 30

            if not ipp_port:
                logger.fail(f"Failed to read Ipp port assigned in action vlan on device.")

            logger.step(f"Verify IPP VLAN details for node {node_2.name}")
            if (test_data['match_type'] == "non-forwarding") and (test_data['action_vlan_type'] == "trunk"):
                vlan_info = {}
                vlan_ports_list = {}
                for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                    vlan_info.update({str(vlan_id): {}})
                    vlan_info[str(vlan_id)] = {'name': '', 'active_ports': [ipp_port],
                                               'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                               'igmp_snooping': '', 'dhcp_snooping': ''}
                    vlan_ports_list.update({str(vlan_id): {}})
                    vlan_ports_list[str(vlan_id)] = {'oper_up_ports': [ipp_port], 'total_ports': [ipp_port],
                                                     'trunk_ports': [ipp_port]}

                vlan_info[nfw_vlan_id] = {'name': '', 'active_ports': isl_list2,
                                          'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                          'igmp_snooping': 'Disabled', 'dhcp_snooping': '',
                                          'nfw_vlan_flag': 'Non-Forwarding VLAN'}
                vlan_ports_list[nfw_vlan_id] = {'oper_up_ports': isl_list2, 'total_ports': isl_list2,
                                                'trunk_ports': [ipp_port]}
            elif (test_data['match_type'] == "default_port_type") and (test_data['action_vlan_type'] == "voip"):
                vlan_info = {}
                for vlan_id in [default_port_vlan_id, default_port_voice_vlan_id]:
                    vlan_info.update({str(vlan_id): {}})
                    vlan_info[str(vlan_id)] = {'name': '', 'active_ports': [ipp_port],
                                               'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                               'igmp_snooping': '', 'dhcp_snooping': ''}

                for vlan_id in [action_vlan_id, voice_vlan_id]:
                    vlan_info.update({str(vlan_id): {}})
                    vlan_info[str(vlan_id)] = {'name': '', 'active_ports': [],
                                               'stp_instance': {'name': 'N/A', 'status': ''},
                                               'igmp_snooping': '', 'dhcp_snooping': ''}

                vlan_info[nfw_vlan_id] = {'name': '', 'active_ports': isl_list2,
                                          'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                          'igmp_snooping': 'Disabled', 'dhcp_snooping': '',
                                          'nfw_vlan_flag': 'Non-Forwarding VLAN'}

                vlan_ports_list = {}
                for vlan_id in [default_port_vlan_id, default_port_voice_vlan_id]:
                    vlan_ports_list.update({str(vlan_id): {}})
                    vlan_ports_list[str(vlan_id)] = {'oper_up_ports': [ipp_port], 'total_ports': [ipp_port],
                                                     'voip_ports': [ipp_port]}

                vlan_ports_list[nfw_vlan_id] = {'oper_up_ports': isl_list2, 'total_ports': isl_list2,
                                                'voip_ports': [ipp_port]}
            elif (test_data['match_type'] == "default_port_type") and (test_data['action_vlan_type'] == "trunk"):
                vlan_info = {}
                for vlan_id in range(int(default_port_vlan_id), int(default_port_type_vlan_range.split("-")[1]) + 1):
                    vlan_info.update({str(vlan_id): {}})
                    vlan_info[str(vlan_id)] = {'name': '', 'active_ports': [ipp_port],
                                               'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                               'igmp_snooping': '', 'dhcp_snooping': ''}

                for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                    vlan_info.update({str(vlan_id): {}})
                    vlan_info[str(vlan_id)] = {'name': '', 'active_ports': [],
                                               'stp_instance': {'name': 'N/A', 'status': ''},
                                               'igmp_snooping': '', 'dhcp_snooping': ''}

                vlan_info[nfw_vlan_id] = {'name': '', 'active_ports': isl_list2,
                                          'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                          'igmp_snooping': 'Disabled', 'dhcp_snooping': '',
                                          'nfw_vlan_flag': 'Non-Forwarding VLAN'}

                vlan_ports_list = {}
                for vlan_id in range(int(default_port_vlan_id), int(default_port_type_vlan_range.split("-")[1]) + 1):
                    vlan_ports_list.update({str(vlan_id): {}})
                    vlan_ports_list[str(vlan_id)] = {'oper_up_ports': [ipp_port], 'total_ports': [ipp_port],
                                                     'trunk_ports': [ipp_port]}

                vlan_ports_list[nfw_vlan_id] = {'oper_up_ports': isl_list2, 'total_ports': isl_list2,
                                                'trunk_ports': [ipp_port]}
            else:
                logger.fail("Invalid IPP configuration type given for VLAN Table verification on this method")

            def _check_vlan_attributes():
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                utils.wait_till(timeout=10)
                value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2,
                                                                                                               vlan_info,
                                                                                                               skip_d360_close=False,
                                                                                                               retry_duration=30,
                                                                                                               retry_count=4,
                                                                                                               IRV=False)
                return value

            utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                            msg=f"verify port info page pop up xx")
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node_2,
                                                                                                               vlan_ports_list,
                                                                                                               skip_d360_close=False,
                                                                                                               retry_duration=30,
                                                                                                               retry_count=4)

            logger.step(f"Verify VLAN port info for node {node_2.name}")
            vlan_ports_list = {}
            logger.info(f"the isl ports are : {isl_list2}")
            for port in isl_list2:
                poe_capable = 'no'
                copper_port = 'no'
                with enter_switch_cli(node_2) as dev_cmd:
                    if poe_flag:
                        # Perform deletion of the extra vlan id's configured in the device.
                        out = \
                            dev_cmd.send_cmd(node_2.name, f'show inline-power configuration ports {port}', max_wait=10,
                                             interval=3)[0].return_text
                        out = out.replace('\r', '')
                        out = out.split("\n")
                        for line in out:
                            if re.search(rf'{port}\s*Enabled', line):
                                poe_capable = 'yes'

                    out = dev_cmd.send_cmd(node_2.name, f'show ports {port} transceiver information | grep "DDMI is"',
                                           max_wait=10, interval=3)[0].return_text
                    if re.search(rf'DDMI is not supported on this port', out):
                        copper_port = 'yes'
                    ### check fdb 
                    mac_out = dev_cmd.send_cmd(node_2.name, f"show fdb | grep {port}",max_wait=10, interval=3)[0].return_text
                    mac_list = mac_out.split("\n")
                    print(f"the maclist is: {mac_list}")
                    device_type = set()
                    if mac_list == ['']:
                        logger.info(f"the mac list is empty for port: {port}")
                    else:
                        for i in mac_list:
                            mac = i.split()[0]
                            mac_check= mac.count(":")
                            if mac_check == 5:
                                mac = mac.replace(":", "")
                                logger.info(f"showing the mac address: {mac}")
                                if mac == "*" or mac == "":
                                    break
                                elif mac.lower() == instant_mac.lower():
                                    device_type.add(device_type_name)
                                elif (mac.lower() != instant_mac.lower()) and (
                                        test_data['match_type'] == "default_port_type") and (
                                        port == ipp_port):
                                    device_type.add("Any")
                                else:
                                    device_type.add("No Match")
                            else:
                                logger.info(f"the string is no having mac: {mac}")
                        device_type = list(device_type)
                        device_type = "\n".join(device_type)
                        print(f"the device type is: {device_type}")
                vlan_ports_list.update({str(port): {}})
                vlan_ports_list[str(port)] = {'port_status': 'up', 'access_vlan': nfw_vlan_id, 'tagged_vlan(s)': '',
                                              'poe_capable': poe_capable, 'copper_port': copper_port}
                # pdb.set_trace()
                if port == ipp_port:
                    if (test_data['match_type'] == "non-forwarding") and (test_data['action_vlan_type'] == "trunk"):
                        vlan_ports_list[port]['tagged_vlan(s)'] = action_vlan_range
                        vlan_ports_list[port]['instant_port_profile_device_types'] = device_type

                    elif (test_data['match_type'] == "default_port_type") and (
                            test_data['action_vlan_type'] == "trunk"):
                        vlan_ports_list[port]['tagged_vlan(s)'] = default_port_type_vlan_range
                        vlan_ports_list[port]['instant_port_profile_device_types'] = device_type
                    else:
                        vlan_ports_list[port]['tagged_vlan(s)'] = default_port_voice_vlan_id
                        vlan_ports_list[port]['instant_port_profile_device_types'] = device_type
                else:
                    vlan_ports_list.pop(port)

            logger.info("Verify VLAN port info")
            logger.info(f"vlan port is::{vlan_ports_list}")

            def _check_info():
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                utils.wait_till(timeout=10)
                value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_info(
                    node_2,
                    vlan_ports_list,
                    skip_d360_close=False, IRV=False)
                return value

            utils.wait_till(_check_info, timeout=720, delay=150,
                            msg=f"verify port info page pop up xx")

        finally:
            logger.info("Test Execution completed. Cleanup the IPP Config")
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                        node_2_template_name,
                                                                                        node_2.cli_type)
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
            logger.step(f"Disable instant port profile on the switch template '{node_2_template_name}'.")
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.select_create_instant_port_switch_template("-----")
            assert xiq_library_at_class_level.xflowsconfigureSwitchTemplate.save_template() == 1, "Was not able to save the device template"
            logger.step('Unconfigure Port Type and delete the port Type and VLAN information')
            navigator.wait_until_loading_is_done()
            if node_2.platform.lower() == 'stack':
                slot_list = list(set([p.split(':')[0] for p in isl_list2]))
                for slot in slot_list:
                    globals()['slot'] = slot
                    port_str = ','.join([p.split(':')[1] for p in isl_list2 if slot in p])
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                                node_2_template_name,
                                                                                                node_2.cli_type)
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
                    # logger.info(f"select the slot in the switch template: {select_slot}")
                    utils.wait_till(timeout=10)
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.sw_template_stack_select_slot(slot)
                    #xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(port_str, 'Access Port')
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.revert_port_configuration_template_level('Access Port')
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template_save()
            else:
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                            node_2_template_name,
                                                                                            node_2.cli_type)
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
                port_str = ','.join(isl_list2)
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.revert_port_configuration_template_level('Access Port')
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template_save()
                #xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(port_str, 'Access Port')
            logger.step(f"Delete instant port profile '{new_instant_port_profile_name}'.")
            # Delete instant port configuration
            is_deleted = xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_instant_port_profile_from_common_obj(
                new_instant_port_profile_name)
            assert is_deleted, "Could not delete the Instant Port Profile"

            if test_data['match_type'] == "default_port_type":
                logger.step(f"Delete the port profile created for testing port_type {default_port_type_name}")
                xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_port_type_profile(default_port_type_name)

            if (test_data['match_type'] == "non-forwarding") and (test_data['action_vlan_type'] == "trunk"):
                vlan_list = [action_vlan_name, nfw_vlan_name]
            elif (test_data['match_type'] == "default_port_type") and (test_data['action_vlan_type'] == "trunk"):
                vlan_list = [action_vlan_name, nfw_vlan_name, default_port_vlan_name]
            else:
                vlan_list = [action_vlan_name, nfw_vlan_name, voice_vlan_name, default_port_vlan_name,
                             default_port_voice_vlan_name]

            for vlan_name in vlan_list:
                try:
                    logger.step(f"Delete vlan '{vlan_name}'.")
                    xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_vlan_profile(vlan_name)
                except Exception as exc:
                    logger.warning(exc)

            mac_list = [device_type_parameters["macOuiName"], device_type_parameters["macAddressName"]]
            for mac in mac_list:
                try:
                    logger.step(f"Delete mac objects '{mac}'.")
                    xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_mac_object(mac)
                except Exception as exc:
                    logger.warning(exc)

            logger.step("Update the config to device")
            xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
            logger.step(f"View Delta Command for Mac mac: {node_2.mac}.")
            # xiq_library_at_class_level.xflowsmanageDeviceConfig.get_device_config_audit_delta(node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.update_device_delta_configuration(device_mac=node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node_2.mac)

            def _check_vlan_attributes():
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                utils.wait_till(timeout=10)
                value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2,
                                                                                                               vlan_info,
                                                                                                               skip_d360_close=False,
                                                                                                               retry_duration=30,
                                                                                                               retry_count=4,
                                                                                                               vlan_exist=False,
                                                                                                               IRV=False)
                return value

            utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                            msg=f"verify port info page pop up xx")

            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, 'unconfigure vlan Default ipaddress', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, 'configure vlan Default add port all', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, 'configure stpd s0 add vlan Default ports all', max_wait=10, interval=3)

    @pytest.mark.tcxm_67007
    @pytest.mark.tcxm_67008
    @pytest.mark.tcxm_67009
    @pytest.mark.tcxm_67010
    @pytest.mark.p1
    def test_vlan_attributes_modify(self, xiq_library_at_class_level, node_1, node_2, node, logger, enter_switch_cli,
                                    utils, navigator, configure_stp_priority, user_vlan_configure,
                                    request, user_vlan_unconfigure, generate_dhcp_snooping_cli, test_data):
        """
        Description:
        TCXM-67007 Verify "D360 Overview-----Interface---vlan table" attribute 'ACTIVE PORTS' for action vlan is modified.
        TCXM-67008 Verify "D360 Overview-----Interface---vlan table" attribute 'STP INSTANCE' for action vlan is modified.
        TCXM-67009 Verify "D360 Overview-----Interface---vlan table" attribute 'IGMP SNOOPING' for action vlan is modified.
        TCXM-67010 Verify "D360 Overview-----Interface---vlan table" attribute 'DHCP SNOOPING' for action vlan is modified.
        """
        try:
            if node.platform.lower() == "stack":
                node_2 = node

            global active_ports_list, random_port, base_config_flag
            global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id

            poe_flag = request.getfixturevalue("node_2_poe_capability")
            poe_capable = 'no'
            copper_port = 'no'
            #node_2_policy_name = "5420_POLICY"
            #node_2_template_name = "5420_TEMP"

            node_2_policy_name = request.getfixturevalue(f"{node_2.node_name}_policy_name")
            node_2_template_name = request.getfixturevalue(f"{node_2.node_name}_template_name")
            isl_list2 = PytestConfigHelper.create_ports_list(node_2.isl)
            isl_list1 = PytestConfigHelper.create_ports_list(node_1.isl)
            isl_port = ",".join(isl_list1)
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, f'configure vlan Default delete port all', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'configure vlan Default add port {isl_port}', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'clear fdb', max_wait=10, interval=3)

            configure_stp_priority(xiq_library_at_class_level, logger, utils, node_2_policy_name, '4096')

            device_type_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.get_random_name("device_type")
            new_instant_port_profile_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.get_random_name(
                "test_ipp")
            default_port_type_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.get_random_name(
                "default_pt")
            nfw_vlan_id = min_vlan_id
            nfw_vlan_name = f"VLAN_{nfw_vlan_id}"
            action_vlan_id = str(int(min_vlan_id) + 1)
            action_vlan_name = f"VLAN_{action_vlan_id}"
            action_vlan_range = str(int(action_vlan_id) + 1) + "-" + str(int(action_vlan_id) + 10)
            default_port_vlan_id = max_vlan_id
            default_port_vlan_name = f"VLAN_{default_port_vlan_id}"
            default_port_type_vlan_range = str(int(default_port_vlan_id) + 1) + "-" + str(
                int(default_port_vlan_id) + 10)

            device_type_parameters = {"flag": "New", "name": device_type_name, "matchCategory": "LLDP Src MAC",
                                      "description": "new device type test", "createMacAddress": "Yes",
                                      "createMacAddressOui": "No",
                                      "macAdressValue": node_1.mac, "macAddressName": node_1.mac,
                                      "portUsage": "Trunk Port", "macOuiName": None,
                                      "actionVlanCreate": "Yes", "actionVlanName": action_vlan_name,
                                      "actionVlanID": action_vlan_id,
                                      "allowedVlansList": action_vlan_range,
                                      "voiceVlanCreate": None, "dataVlanCreate": None, "voiceVlanName": None,
                                      "voiceVlanId": None, "dataVlanName": None, "dataVlanId": None,
                                      "stormControlSettings": "No"}

            instant_port_parameters = {"createFrom": "Network Policy", "name": new_instant_port_profile_name,
                                       "des66998cription": "VLAN_IPP_PROFILE",
                                       "defaultPortName": "Trunk Port",
                                       "createNonForwardingVlan": "Yes", "nfwVlanName": nfw_vlan_name,
                                       "nfwVlanId": nfw_vlan_id,
                                       "createDefaultPortType": "No",
                                       "portTypeUsage": "trunk",
                                       "portTypeVlanName": default_port_vlan_name,
                                       "portTypeVlanId": default_port_vlan_id,
                                       "portTypeAllowedVl": default_port_type_vlan_range,
                                       "nonMatchAction": "Non-Forwarding VLAN"}

            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.navigate_to_np_instant_port(
                node_2_policy_name)

            logger.info("Step 2: Create an instant port profile with non-match action 'Use non-forwarding vlan'")
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.configure_instant_port_profile(
                instant_port_parameters, [device_type_parameters])

            logger.info("Step 4: Push configuration to device")
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                        node_2_template_name,
                                                                                        node_2.cli_type)

            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()

            if node_2.platform.lower() == 'stack':
                select_slot = isl_list2[0].split(':')[0]
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.sw_template_stack_select_slot(
                    select_slot)
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.select_create_instant_port_switch_template(
                new_instant_port_profile_name)
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.enable_disable_instant_port_profile_on_ports_switch_template(
                isl_list2, "ON")
            saved_template = xiq_library_at_class_level.xflowsconfigureSwitchTemplate.save_template()
            assert saved_template == 1, "Was not able to save the device template"

            logger.step("Update the config to device")
            xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
            logger.step(f"View Delta Command for Mac mac: {node_2.mac}.")
            xiq_library_at_class_level.xflowsmanageDevices.update_device_delta_configuration(device_mac=node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node_2.mac)
            isl_list1 = PytestConfigHelper.create_ports_list(node_1.isl)
            ports_list = ','.join(isl_list1)

            #This is done to avoid the multiple MAC address on the single port in node_2 which would cause the "No Match" for the ipp_port
            with enter_switch_cli(node_2) as dev_cmd:
                dev_cmd.send_cmd(node_2.name, f'clear fdb', max_wait=10, interval=3)

            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, f'clear fdb', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'create vlan vlan_neig tag 3', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'configure vlan vlan_neig  add ports {ports_list} tagged', max_wait=10,
                                 interval=3)

            # collect ipp port details from device.
            logger.step(f"Verify scale vlan details in wireframe image for node {node_2.name}")
            ipp_port = ''
            count = 0
            with enter_switch_cli(node_2) as dev_cmd:
                while (count <= 120):
                    out = \
                        dev_cmd.send_cmd(node_2.name, f'show vlan {action_vlan_id} | grep Untag:', max_wait=5,
                                         interval=3)[
                            0].return_text
                    match = re.search('Untag:\s*\*(\d+:\d+|\d+)mS', out)
                    if match:
                        ipp_port = match.group(1)
                        break
                    else:
                        utils.wait_till(timeout=30)
                        count += 30
            logger.info(f"the ipp port is {ipp_port}")
            if not ipp_port:
                logger.fail(f"Failed to read Ipp port assigned in action vlan on device.")

            vlan_info = {}

            for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                vlan_info.update({str(vlan_id): {}})
                vlan_info[str(vlan_id)] = {'name': '', 'active_ports': [ipp_port],
                                           'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                           'igmp_snooping': '', 'dhcp_snooping': ''}

            vlan_info[nfw_vlan_id] = {'name': '', 'active_ports': isl_list2,
                                      'stp_instance': {'name': 's0', 'status': 'Enabled'}, 'igmp_snooping': 'Disabled',
                                      'dhcp_snooping': '', 'nfw_vlan_flag': "Non-Forwarding VLAN"}

            vlan_ports_list1 = {}
            for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                vlan_ports_list1.update({str(vlan_id): {}})
                vlan_ports_list1[str(vlan_id)] = {'oper_up_ports': [ipp_port], 'total_ports': [ipp_port],
                                                  'trunk_ports': [ipp_port]}

            vlan_ports_list1[nfw_vlan_id] = {'oper_up_ports': isl_list2, 'total_ports': isl_list2,
                                             'trunk_ports': [ipp_port]}

            logger.step(f"Verify VLAN port info for node {node_2.name}")
            vlan_ports_list2 = {}
            logger.info(f"the isl ports are: {isl_list2}")
            for port in isl_list2:
                poe_capable = 'no'
                copper_port = 'no'
                with enter_switch_cli(node_2) as dev_cmd:
                    if poe_flag:
                        # Perform deletion of the extra vlan id's configured in the device.
                        out = \
                            dev_cmd.send_cmd(node_2.name, f'show inline-power configuration ports {port}', max_wait=10,
                                             interval=3)[0].return_text
                        out = out.replace('\r', '')
                        out = out.split("\n")
                        for line in out:
                            if re.search(rf'{port}\s*Enabled', line):
                                poe_capable = 'yes'

                    out = dev_cmd.send_cmd(node_2.name, f'show ports {port} transceiver information | grep "DDMI is"',
                                           max_wait=10, interval=3)[0].return_text
                    if re.search(rf'DDMI is not supported on this port', out):
                        copper_port = 'yes'
                    ### check fdb
                    mac_out = dev_cmd.send_cmd(node_2.name, f"show fdb | grep {port}",max_wait=10, interval=3)[0].return_text
                    logger.info(f"the maac present inside the switch is: {mac_out}")
                    mac_list = mac_out.split("\n")
                    logger.info(f"the maclist is: {mac_list}")
                    device_type = set()
                    if mac_list == ['']:
                        logger.info(f"the mac list is empty for port: {port}")
                    else:
                        for i in mac_list:
                            instant_mac = node_1.mac
                            mac = i.split()[0]
                            mac_check= mac.count(":")
                            if mac_check == 5:
                                mac = mac.replace(":", "")
                                logger.info(f"showing the mac address: {mac}")
                                if mac == "*" or mac == "":
                                    break
                                elif mac.lower() == instant_mac.lower():
                                    device_type.add(device_type_name)
                                elif (mac.lower() != instant_mac.lower()) and (
                                        test_data['match_type'] == "default_port_type") and (
                                        port == ipp_port):
                                    device_type.add("Any")
                                else:
                                    device_type.add("No Match")
                            else:
                                logger.info(f"the string is no having mac: {mac}")
                        device_type = list(device_type)
                        device_type = "\n".join(device_type)
                        logger.info(f"the device type is: {device_type}")
                vlan_ports_list2.update({str(port): {}})
                vlan_ports_list2[str(port)] = {'port_status': 'up', 'access_vlan': nfw_vlan_id, 'tagged_vlan(s)': '',
                                               'poe_capable': poe_capable, 'copper_port': copper_port}
                if port == ipp_port:
                    vlan_ports_list2[port]['tagged_vlan(s)'] = action_vlan_range
                    vlan_ports_list2[port]['instant_port_profile_device_types'] = device_type
                else:
                    vlan_ports_list2.pop(port)
            logger.info(f"the vlan port list: {vlan_ports_list2}")
            logger.info("Verify VLAN port info")

            if test_data['TCs'] == 'Active Ports':
                logger.info("Disable the Active Ports  for action vlan via CLI")
                with enter_switch_cli(node_2) as dev_cmd:
                    dev_cmd.send_cmd(node_2.name, f'disable port {ipp_port}', max_wait=10, interval=3)
                    logger.info("Verify the port disabled using CLI")
                    dev_cmd.send_cmd_verify_output(node_2.name, f'show port {ipp_port} no-refresh', 'D', max_wait=10,
                                                   interval=3)

                # xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                    vlan_ports_list1[str(vlan_id)].pop('trunk_ports')
                    vlan_ports_list1[str(vlan_id)]['oper_up_ports'] = []
                    vlan_ports_list1[str(vlan_id)]['port_highlighted'] = False
                    vlan_info[str(vlan_id)]['active_ports'] = ''
                    vlan_info[str(vlan_id)]['stp_instance']['name'] = 'N/A'
                # Non-forwarding VLAN
                lst = vlan_info[nfw_vlan_id]['active_ports']
                lst = list(filter(lambda item: item != ipp_port, lst))
                vlan_info[nfw_vlan_id]['active_ports'] = lst
                lst = vlan_ports_list1[nfw_vlan_id]['oper_up_ports']
                lst = list(filter(lambda item: item != ipp_port, lst))
                vlan_ports_list1[nfw_vlan_id]['oper_up_ports'] = lst
                vlan_ports_list1[nfw_vlan_id].pop('trunk_ports')
                vlan_ports_list1[nfw_vlan_id]['port_highlighted'] = True
                #vlan_ports_list2[ipp_port]['port_status'] = 'down'
                logger.info("Verify the active ports are disabled in D360")

                # refresh the page
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        skip_list_of_active_ports=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")

                logger.info("Enable the Active Ports for action vlan via CLI")
                with enter_switch_cli(node_2) as dev_cmd:
                    dev_cmd.send_cmd(node_2.name, f'enable port {ipp_port}', max_wait=10, interval=3)

                    logger.info("Verify the port enabled using CLI")
                    dev_cmd.send_cmd_verify_output(node_2.name, f'show port {ipp_port} no-refresh', 'E', max_wait=10,
                                                   interval=3)

                # xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                    vlan_ports_list1[str(vlan_id)]['trunk_ports'] = [ipp_port]
                    vlan_ports_list1[str(vlan_id)]['oper_up_ports'].append(ipp_port)
                    vlan_ports_list1[str(vlan_id)]['port_highlighted'] = True
                    vlan_info[str(vlan_id)]['active_ports'] = [ipp_port]
                    vlan_info[str(vlan_id)]['stp_instance']['name'] = 's0'

                # Non-forwarding VLAN
                vlan_info[nfw_vlan_id]['active_ports'].append(ipp_port)
                vlan_ports_list1[nfw_vlan_id]['oper_up_ports'].append(ipp_port)
                vlan_ports_list1[nfw_vlan_id]['trunk_ports'] = [ipp_port]
                vlan_ports_list1[nfw_vlan_id]['port_highlighted'] = True
                #vlan_ports_list2[ipp_port]['port_status'] = 'up'
                logger.info("Verify the active ports are enabled in D360")

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        skip_list_of_active_ports=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
                xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(
                    node_2,
                    vlan_ports_list1,
                    skip_d360_close=False,
                    retry_duration=30,
                    retry_count=4)

                def _check_info():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_info(
                        node_2,
                        vlan_ports_list2,
                        skip_d360_close=False, IRV=False)
                    return value

                utils.wait_till(_check_info, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")

            if test_data['TCs'] == 'STP Instance':

                opt = []
                expected_output = ""
                logger.info("Create stpd instance s1 & add action vlan to s1 via CLI")
                with enter_switch_cli(node_2) as dev_cmd:
                    dev_cmd.send_cmd(node_2.name, f'create stpd s1', max_wait=10, interval=3)
                    dev_cmd.send_cmd(node_2.name, f'configure stpd s1 mode mstp msti 10', max_wait=10, interval=3)
                    dev_cmd.send_cmd(node_2.name, f'enable stpd s1', max_wait=10, interval=3)
                    dev_cmd.send_cmd(node_2.name, f'configure stpd s1 priority 4096', max_wait=10, interval=3)

                    for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                        vlan_id = str(vlan_id)
                        vlan_name = 'VLAN_' + vlan_id.zfill(4)
                        dev_cmd.send_cmd(node_2.name, f'configure stpd s1 add vlan {vlan_name} ports all', max_wait=10,
                                         interval=3)
                        opt.append(vlan_name)
                        expected_output = ','.join(opt)
                        # Verify stp s1 created successfully  via CLI
                        dev_cmd.send_cmd_verify_output(node_2.name, f'show stpd s1',
                                                       f'Participating vlans: {expected_output}', max_wait=10,
                                                       interval=3)

                        vlan_info[str(vlan_id)]['stp_instance']['name'] = 's1'
                        vlan_info[str(vlan_id)]['stp_instance']['status'] = 'Enabled'

                # refresh the page
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        skip_stp_status=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
                logger.info("Remove the action vlan from stpd instance s1 via CLI")
                with enter_switch_cli(node_2) as dev_cmd:
                    for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                        vlan_id = str(vlan_id)
                        vlan_name = 'VLAN_' + vlan_id.zfill(4)
                        dev_cmd.send_cmd(node_2.name, f'configure stpd s1 delete vlan {vlan_name} ports all',
                                         max_wait=10, interval=3)

                        vlan_info[str(vlan_id)]['stp_instance']['name'] = 'N/A'
                    # Verify stp s1 removed successfully  via CLI
                    dev_cmd.send_cmd_verify_output(node_2.name, f'show stpd s1', f'Participating vlans: (none)',
                                                   max_wait=10, interval=3)

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        skip_stp_status=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
                logger.info("Add action vlan to stpd instance s1 and disable stpd instance s1 via CLI")
                with enter_switch_cli(node_2) as dev_cmd:
                    for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                        vlan_id = str(vlan_id)
                        vlan_name = 'VLAN_' + vlan_id.zfill(4)
                        # Add action vlan to stpd instance s1
                        dev_cmd.send_cmd(node_2.name, f'configure stpd s1 add vlan {vlan_name} ports all',
                                         max_wait=10, interval=3)
                        vlan_info[str(vlan_id)]['stp_instance']['name'] = 's1'
                        vlan_info[str(vlan_id)]['stp_instance']['status'] = 'Disabled'
                    # Disable stpd instance s1 via CLI
                    dev_cmd.send_cmd(node_2.name, f'disable stpd s1', max_wait=10, interval=3)
                    # Verify stp s1 disabled successfully  via CLI
                    dev_cmd.send_cmd_verify_output(node_2.name, f'show stpd s1', f'Stp: DISABLED', max_wait=10,
                                                   interval=3)

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        skip_stp_status=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
                logger.info("Enable the stpd instance s1 via CLI")
                with enter_switch_cli(node_2) as dev_cmd:
                    # Enable stpd instance s1 via CLI
                    dev_cmd.send_cmd(node_2.name, f'enable stpd s1', max_wait=10, interval=3)
                    # Verify stp s1 enabled successfully  via CLI
                    dev_cmd.send_cmd_verify_output(node_2.name, f'show stpd s1', f'Stp: ENABLED', max_wait=10,
                                                   interval=3)
                    for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                        vlan_id = str(vlan_id)
                        vlan_name = 'VLAN_' + vlan_id.zfill(4)
                        vlan_info[str(vlan_id)]['stp_instance']['status'] = 'Enabled'

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        skip_stp_status=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
                # Verify the port details in D360 page
                xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(
                    node_2, vlan_ports_list1, skip_d360_close=False, retry_duration=30, retry_count=4)
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()

                def _check_info():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_info(
                        node_2,
                        vlan_ports_list2,
                        skip_d360_close=False, retry_duration=30, retry_count=4, IRV=False)
                    return value

                utils.wait_till(_check_info, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
            if test_data['TCs'] == 'IGMP Snooping':

                logger.info("Disable IGMP Snooping for action vlan via CLI")
                with enter_switch_cli(node_2) as dev_cmd:
                    dev_cmd.send_cmd(node_2.name, 'show vlan', max_wait=10, interval=3)
                    for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                        vlan_id = str(vlan_id)
                        vlan_name = 'VLAN_' + vlan_id.zfill(4)
                        dev_cmd.send_cmd(node_2.name, f'disable igmp snooping vlan {vlan_name}', max_wait=10,
                                         interval=3)
                        logger.info("Verify able to disable igmp snooping  using CLI")
                        dev_cmd.send_cmd_verify_output(node_2.name, f'show igmp snooping vlan {vlan_name}',
                                                       'Snooping=Disabled', max_wait=10, interval=3)
                        vlan_info[str(vlan_id)]['igmp_snooping'] = 'Disabled'
                logger.info("Verify the IGMP shows disabled for acton vlan in D360")
                # refresh the page
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")

                logger.info("Enable IGMP Snooping for action vlan via CLI")
                with enter_switch_cli(node_2) as dev_cmd:
                    for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                        vlan_id = str(vlan_id)
                        vlan_name = 'VLAN_' + vlan_id.zfill(4)
                        dev_cmd.send_cmd(node_2.name, f'enable igmp snooping vlan {vlan_name}', max_wait=10, interval=3)
                        logger.info("Verify able to enable igmp snooping  using CLI")
                        dev_cmd.send_cmd_verify_output(node_2.name, f'show igmp snooping vlan {vlan_name}',
                                                       'Snooping=Enabled', max_wait=10, interval=3)
                        vlan_info[str(vlan_id)]['igmp_snooping'] = 'Enabled'

                logger.info("Verify the IGMP shows enabled for acton vlan in D360")

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
                # Verify port details in D360
                xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(
                    node_2, vlan_ports_list1, skip_d360_close=False, retry_duration=30, retry_count=4)
                # for port in isl_list2:
                #     if port == ipp_port:
                #         vlan_ports_list2[port]['instant_port_profile_device_types'] = device_type
                #     else:
                #         vlan_ports_list2.pop(port)
                # logger.info(f"the vlan port list: {vlan_ports_list2}")
                # logger.info("Verify VLAN port info")

                def _check_info():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_info(
                        node_2,
                        vlan_ports_list2,
                        skip_d360_close=False, IRV=False)
                    return value

                utils.wait_till(_check_info, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")

            if test_data['TCs'] == 'DHCP Snooping':
                with enter_switch_cli(node_2) as dev_cmd:
                    dev_cmd.send_cmd(node_2.name, 'show vlan', max_wait=10, interval=3)
                logger.info("Enable DHCP Snooping for action vlan via CLI")
                dhcp_snooping_option = generate_dhcp_snooping_cli()
                with enter_switch_cli(node_2) as dev_cmd:
                    for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                        vlan_id = str(vlan_id)
                        vlan_name = 'VLAN_' + vlan_id.zfill(4)
                        dev_cmd.send_cmd(node_2.name,
                                         f'enable ip-security dhcp-snooping vlan {vlan_name} ports all violation-action {dhcp_snooping_option}',
                                         max_wait=10, interval=3)
                        logger.info("Verify able to enable dhcp snooping  using CLI")
                        dev_cmd.send_cmd_verify_output(node_2.name, f'show ip-security dhcp-snooping vlan {vlan_name}',
                                                       'DHCP Snooping enabled', max_wait=10, interval=3)
                        vlan_info[str(vlan_id)]['dhcp_snooping'] = 'Enabled'

                # refresh the page
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
                logger.info("Disable DHCP Snooping for action vlan via CLI")
                with enter_switch_cli(node_2) as dev_cmd:
                    for vlan_id in range(int(action_vlan_id), int(action_vlan_range.split("-")[1]) + 1):
                        vlan_id = str(vlan_id)
                        vlan_name = 'VLAN_' + vlan_id.zfill(4)
                        dev_cmd.send_cmd(node_2.name,
                                         f'disable ip-security dhcp-snooping vlan {vlan_name} ports all',
                                         max_wait=10, interval=3)
                        vlan_info[str(vlan_id)]['dhcp_snooping'] = 'Disabled'

                logger.info("Verify the DHCP shows disabled for acton vlan in D360")

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
                # Verify port details in D360
                xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(
                    node_2, vlan_ports_list1, skip_d360_close=False, retry_duration=30, retry_count=4)

                def _check_info():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_info(
                        node_2,
                        vlan_ports_list2,
                        skip_d360_close=False, IRV=False)
                    return value

                utils.wait_till(_check_info, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")

        finally:
            logger.info("Test Execution completed. Cleanup the IPP Config")

            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                        node_2_template_name,
                                                                                        node_2.cli_type)
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
            utils.wait_till(timeout=10)
            logger.step(f"Disable instant port profile on the switch template '{node_2_template_name}'.")
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.select_create_instant_port_switch_template(
                "-----")
            assert xiq_library_at_class_level.xflowsconfigureSwitchTemplate.save_template() == 1, "Was not able to save the device template"

            logger.step('Unconfigure Port Type and delete the port Type and VLAN information')
            navigator.wait_until_loading_is_done()
            if node_2.platform.lower() == 'stack':
                slot_list = list(set([p.split(':')[0] for p in isl_list2]))
                for slot in slot_list:
                    globals()['slot'] = slot
                    port_str = ','.join([p.split(':')[1] for p in isl_list2 if slot in p])
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                                node_2_template_name,
                                                                                                node_2.cli_type)
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
                    utils.wait_till(timeout=10)
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.sw_template_stack_select_slot(slot)
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.revert_port_configuration_template_level('Access Port')
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template_save()
                    #xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(port_str, 'Access Port')
            else:
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                            node_2_template_name,
                                                                                            node_2.cli_type)
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
                port_str = ','.join(isl_list2)
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.revert_port_configuration_template_level('Access Port')
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template_save()
                #xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(port_str, 'Access Port')
            logger.step(f"Delete instant port profile '{new_instant_port_profile_name}'.")
            # Delete instant port configuration
            is_deleted = xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_instant_port_profile_from_common_obj(
                new_instant_port_profile_name)
            assert is_deleted, "Could not delete the Instant Port Profile"

            vlan_list = [instant_port_parameters["nfwVlanName"], device_type_parameters["actionVlanName"]]
            for vlan_name in vlan_list:
                try:
                    logger.step(f"Delete vlan '{vlan_name}'.")
                    xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_vlan_profile(
                        vlan_name)
                except Exception as exc:
                    logger.warning(exc)
            mac_list = [device_type_parameters["macOuiName"], device_type_parameters["macAddressName"]]
            for mac in mac_list:
                try:
                    logger.step(f"Delete mac objects '{mac}'.")
                    xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_mac_object(mac)
                except Exception as exc:
                    logger.warning(exc)
            logger.step(f"Delete the port profile created for testing port_type {default_port_type_name}")
            xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_port_type_profile(default_port_type_name)
            logger.step("Update the config to device")
            xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
            logger.step(f"View Delta Command for Mac mac: {node_2.mac}.")
            # xiq_library_at_class_level.xflowsmanageDeviceConfig.get_device_config_audit_delta(node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.update_device_delta_configuration(device_mac=node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node_2.mac)
            # Delete vlan created in node_1
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, f'delete vlan vlan_neig ', max_wait=10, interval=3)

            xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()

            def _check_vlan_attributes():
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                utils.wait_till(timeout=10)
                value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2,
                                                                                                               vlan_info,
                                                                                                               skip_d360_close=False,
                                                                                                               retry_duration=30,
                                                                                                               retry_count=4,
                                                                                                               vlan_exist=False,
                                                                                                               IRV=False)
                return value

            utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                            msg=f"verify port info page pop up xx")
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, f'configure vlan Default add port all', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'configure stpd s0 add vlan Default ports all', max_wait=10, interval=3)

    @pytest.mark.tcxm_67011
    @pytest.mark.tcxm_67013
    @pytest.mark.p1
    def test_non_forwarding_vlan(self, xiq_library_at_class_level, node_1, node_2, node, logger, enter_switch_cli,
                                 utils,
                                 navigator, configure_stp_priority, user_vlan_configure, request, user_vlan_unconfigure,
                                 generate_dhcp_snooping_cli, test_data):
        """
        Description:
        TCXM-67011 Verify "D360 Overview-----Interface---vlan table" for Non-Forwarding vlan attribute values are reverted to IPP Default values when config applied with override
        TCXM-67013 Verify  vlan's are deleted in "D360 Overview -----Interface ----vlan table " after disabling ipp profile

        """
        try:
            if node.platform.lower() == "stack":
                node_2 = node

            global active_ports_list, random_port, base_config_flag
            global min_vlan_name, max_vlan_name, min_vlan_id, max_vlan_id

            poe_flag = request.getfixturevalue("node_2_poe_capability")
            poe_capable = 'no'
            copper_port = 'no'
            # node_2_policy_name = "5420_TEMP"
            # node_2_template_name = "5420_stack"
            node_2_policy_name = request.getfixturevalue(f"{node_2.node_name}_policy_name")
            node_2_template_name = request.getfixturevalue(f"{node_2.node_name}_template_name")
            # node_2_policy_name = "8nWu_np_XIQ_15049"
            # node_2_template_name = "zUvw_template_XIQ_15049"
            isl_list2 = PytestConfigHelper.create_ports_list(node_2.isl)
            isl_list1 = PytestConfigHelper.create_ports_list(node_1.isl)
            isl_port = ",".join(isl_list1)
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, f'configure vlan Default delete port all', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'configure vlan Default add port {isl_port}', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'clear fdb', max_wait=10, interval=3)
            configure_stp_priority(xiq_library_at_class_level, logger, utils, node_2_policy_name, '4096')
            device_type_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.get_random_name(
                "device_type")
            new_instant_port_profile_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.get_random_name(
                "test_ipp")
            default_port_type_name = xiq_library_at_class_level.xflowsconfigureNetworkPolicy.get_random_name(
                "default_pt")
            nfw_vlan_id = min_vlan_id
            nfw_vlan_name = f"VLAN_{nfw_vlan_id}"
            action_vlan_id = str(int(min_vlan_id) + 1)
            action_vlan_name = f"VLAN_{action_vlan_id}"
            action_vlan_range = str(int(action_vlan_id) + 1) + "-" + str(int(action_vlan_id) + 10)
            default_port_vlan_id = max_vlan_id
            default_port_vlan_name = f"VLAN_{default_port_vlan_id}"
            default_port_type_vlan_range = str(int(default_port_vlan_id) + 1) + "-" + str(
                int(default_port_vlan_id) + 10)
            # Create a Learning VLAN via CLI
            learning_vlan_name = nfw_vlan_name
            learning_vlan_id = nfw_vlan_id
            dhcp_snooping_option = generate_dhcp_snooping_cli()
            ports = ''
            ports = ','.join(isl_list2)
            vlan_info = {}
            vlan_info.update({learning_vlan_id: {}})

            if test_data['TCs'] == 'Learning vlan via cli':
                logger.info("Create a Learning VLAN via CLI with all its vlan attributes")
                with enter_switch_cli(node_2) as dev_cmd:
                    dev_cmd.send_cmd(node_2.name, f'create vlan {learning_vlan_name} tag {learning_vlan_id}',
                                     max_wait=10, interval=3)
                    dev_cmd.send_cmd(node_2.name, f'configure vlan {learning_vlan_name} add ports {ports} untagged',
                                     max_wait=10, interval=3)
                    dev_cmd.send_cmd(node_2.name, f'configure stpd s0 add vlan {learning_vlan_name} ports all',
                                     max_wait=10,
                                     interval=3)
                    dev_cmd.send_cmd(node_2.name, f'enable igmp snooping vlan {learning_vlan_name}', max_wait=10,
                                     interval=3)
                    dev_cmd.send_cmd(node_2.name,
                                     f'enable ip-security dhcp-snooping vlan {learning_vlan_name} ports all violation-action {dhcp_snooping_option}',
                                     max_wait=10, interval=3)
                    dev_cmd.send_cmd(node_2.name, f'show vlan', max_wait=10, interval=3)

                vlan_info[learning_vlan_id] = {'name': learning_vlan_name, 'active_ports': isl_list2,
                                               'stp_instance': {'name': 's0', 'status': 'Enabled'},
                                               'igmp_snooping': 'Enabled',
                                               'dhcp_snooping': 'Enabled'}
                logger.info("Verify the vlan attributes in D360 page")
                xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()

                def _check_vlan_attributes():
                    xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                    utils.wait_till(timeout=10)
                    value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(
                        node_2,
                        vlan_info,
                        skip_d360_close=False,
                        skip_list_of_active_ports=False,
                        retry_duration=30,
                        retry_count=4,
                        IRV=False)
                    return value

                utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                                msg=f"verify port info page pop up xx")
                # IGMP Snooping should be disabled for non-forwarding vlan after configureing IPP
                with enter_switch_cli(node_2) as dev_cmd:
                    dev_cmd.send_cmd(node_2.name, f'disable igmp snooping vlan {learning_vlan_name}', max_wait=10,
                                     interval=3)
            mac_oui = node_1.mac[0:6]
            device_type_parameters = {"flag": "New", "name": device_type_name, "matchCategory": "LLDP Src MAC",
                                      "description": "new device type test", "createMacAddress": "No",
                                      "createMacAddressOui": "Yes",
                                      "macAdressValue": None, "macAddressName": None,
                                      "portUsage": "Access Port", "macOuiName": mac_oui, "macOuiValue": mac_oui,
                                      "actionVlanCreate": "Yes", "actionVlanName": action_vlan_name,
                                      "actionVlanID": action_vlan_id,
                                      "allowedVlansList": action_vlan_range,
                                      "voiceVlanCreate": None, "dataVlanCreate": None, "voiceVlanName": None,
                                      "voiceVlanId": None, "dataVlanName": None, "dataVlanId": None,
                                      "stormControlSettings": "Yes", "enableBroadcast": "Yes", "enableMulticast": "Yes",
                                      "enableUnkUnicast": "Yes", "rateLimitValue": "1000"}

            instant_port_parameters = {"createFrom": "Network Policy", "name": new_instant_port_profile_name,
                                       "description": "VLAN_IPP_PROFILE",
                                       "defaultPortName": "Access Port",
                                       "createNonForwardingVlan": "Yes", "nfwVlanName": nfw_vlan_name,
                                       "nfwVlanId": nfw_vlan_id,
                                       "createDefaultPortType": "No",
                                       "portTypeUsage": "access",
                                       "portTypeVlanName": default_port_vlan_name,
                                       "portTypeVlanId": default_port_vlan_id,
                                       "portTypeAllowedVl": default_port_type_vlan_range,
                                       "nonMatchAction": "Non-Forwarding VLAN"}

            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.navigate_to_np_instant_port(
                node_2_policy_name)
            logger.info("Step 2: Create an instant port profile with non-match action 'Use non-forwarding vlan'")
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.configure_instant_port_profile(
                instant_port_parameters, [device_type_parameters])
            logger.info("Step 4: Push configuration to device")
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                        node_2_template_name,
                                                                                        node_2.cli_type)
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()

            if node_2.platform.lower() == 'stack':
                select_slot = isl_list2[0].split(':')[0]
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.sw_template_stack_select_slot(select_slot)
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.select_create_instant_port_switch_template(
                new_instant_port_profile_name)
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.enable_disable_instant_port_profile_on_ports_switch_template(
                isl_list2, "ON")
            saved_template = xiq_library_at_class_level.xflowsconfigureSwitchTemplate.save_template()
            assert saved_template == 1, "Was not able to save the device template"
            logger.step("Update the config to device")
            xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
            logger.step(f"View Delta Command for Mac mac: {node_2.mac}.")

            xiq_library_at_class_level.xflowsmanageDevices.update_device_delta_configuration(device_mac=node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node_2.mac)
            isl_list1 = PytestConfigHelper.create_ports_list(node_1.isl)
            ports_list = ','.join(isl_list1)
            # This is done to avoid the multiple MAC address on the single port in node_2 which would cause the "No Match" for the ipp_port
            with enter_switch_cli(node_2) as dev_cmd:
                dev_cmd.send_cmd(node_2.name, f'clear fdb', max_wait=10, interval=3)
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, f'clear fdb', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'create vlan vlan_neig tag 3', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'configure vlan vlan_neig  add ports {ports_list} tagged', max_wait=10,
                                 interval=3)
            # collect ipp port details from device.
            logger.step(f"Verify scale vlan details in wireframe image for node {node_2.name}")
            ipp_port = ''
            count = 0
            with enter_switch_cli(node_2) as dev_cmd:
                while (count <= 120):
                    out = \
                        dev_cmd.send_cmd(node_2.name, f'show vlan {action_vlan_id} | grep Untag:', max_wait=5,
                                         interval=3)[
                            0].return_text
                    # pdb.set_trace()
                    match = re.search('Untag:\s*\*(\d+:\d+|\d+)mS', out)
                    if match:
                        ipp_port = match.group(1)
                        break
                    else:
                        count += 30
            if not ipp_port:
                logger.fail(f"Failed to read ipp port assigned in action vlan on device.")
            logger.info(f"the ipp port is: {ipp_port}")
            logger.info(f"Verify vlan attributes for node {node_2.name}")

            if device_type_parameters['portUsage'] == 'Access Port':
                vlan_info.update({action_vlan_id: {}})
                vlan_info[action_vlan_id] = {'name': '', 'active_ports': [ipp_port],
                                             'stp_instance': {'name': 's0', 'status': 'Enabled'}, 'igmp_snooping': '',
                                             'dhcp_snooping': ''}

            vlan_info[nfw_vlan_id] = {'name': '', 'active_ports': isl_list2,
                                      'stp_instance': {'name': 's0', 'status': 'Enabled'}, 'igmp_snooping': 'Disabled',
                                      'dhcp_snooping': '', 'nfw_vlan_flag': "Non-Forwarding VLAN"}
            xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()

            def _check_vlan_attributes():
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                utils.wait_till(timeout=10)
                value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2,
                                                                                                               vlan_info,
                                                                                                               skip_d360_close=False,
                                                                                                               skip_stp_status=False,
                                                                                                               skip_list_of_active_ports=False,
                                                                                                               retry_duration=30,
                                                                                                               retry_count=4,
                                                                                                               IRV=False)
                return value

            utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                            msg=f"verify port info page pop up xx")
            logger.info("Verify VLAN port details")
            vlan_ports_list1 = {}

            if device_type_parameters['portUsage'] == 'Access Port':
                vlan_ports_list1.update({str(action_vlan_id): {}})
                vlan_ports_list1[action_vlan_id] = {'oper_up_ports': [ipp_port], 'total_ports': [ipp_port],
                                                    'port_highlighted': True}
            vlan_ports_list1[nfw_vlan_id] = {'oper_up_ports': isl_list2, 'total_ports': isl_list2,
                                             'port_highlighted': True}
            xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_details(node_2,
                                                                                                               vlan_ports_list1,
                                                                                                               skip_d360_close=False,
                                                                                                               retry_duration=30,
                                                                                                               retry_count=4)
            vlan_ports_list2 = {}
            logger.info(f"the isl ports are : {isl_list2}")
            for port in isl_list2:
                poe_capable = 'no'
                copper_port = 'no'
                with enter_switch_cli(node_2) as dev_cmd:
                    if poe_flag:
                        # Perform deletion of the extra vlan id's configured in the device.
                        out = \
                            dev_cmd.send_cmd(node_2.name, f'show inline-power configuration ports {port}', max_wait=10,
                                             interval=3)[0].return_text
                        out = out.replace('\r', '')
                        out = out.split("\n")
                        for line in out:
                            if re.search(rf'{port}\s*Enabled', line):
                                poe_capable = 'yes'
                    out = dev_cmd.send_cmd(node_2.name, f'show ports {port} transceiver information | grep "DDMI is"',
                                           max_wait=10, interval=3)[0].return_text
                    if re.search(rf'DDMI is not supported on this port', out):
                        copper_port = 'yes'
                    ### check fdb
                    mac_out = dev_cmd.send_cmd(node_2.name, f"show fdb | grep {port}",max_wait=10, interval=3)[0].return_text
                    mac_list = mac_out.split("\n")
                    logger.info(f"the maclist is: {mac_list}")
                    device_type = set()
                    if mac_list == ['']:
                        logger.info(f"the mac list is empty for port: {port}")
                    else:
                        for i in mac_list:
                            instant_mac = mac_oui
                            mac = i.split()[0]
                            mac_check= mac.count(":")
                            if mac_check == 5:
                                mac = mac.replace(":", "")[:6]
                                logger.info(f"showing the mac address: {mac}")
                                if mac == "*" or mac == "":
                                    break
                                elif mac.lower() == instant_mac.lower():
                                    device_type.add(device_type_name)
                                elif (mac.lower() != instant_mac.lower()) and (
                                        test_data['match_type'] == "default_port_type") and (
                                        port == ipp_port):
                                    device_type.add("Any")
                                else:
                                    device_type.add("No Match")
                            else:
                                logger.info(f"the string is no having mac: {mac}")
                        device_type = list(device_type)
                        device_type = "\n".join(device_type)
                        logger.info(f"the device type is: {device_type}")
                logger.info(f"Verify VLAN port info ")
                if device_type_parameters['portUsage'] == 'Access Port':
                    vlan_ports_list2.update({str(port): {}})
                    vlan_ports_list2[str(port)] = {'port_status': 'up', 'access_vlan': nfw_vlan_id,
                                                   'tagged_vlan(s)': '',
                                                   'poe_capable': poe_capable, 'copper_port': copper_port}

                    if port == ipp_port:
                        vlan_ports_list2[port]['instant_port_profile_device_types'] = device_type
                    else:
                        vlan_ports_list2.pop(port)
            logger.info(f"the vlan port list: {vlan_ports_list2}")
            logger.info("Verify VLAN port info")

            def _check_info():
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                utils.wait_till(timeout=10)
                value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_wireframe_port_info(
                    node_2,
                    vlan_ports_list2,
                    skip_d360_close=False, IRV=False)
                return value

            utils.wait_till(_check_info, timeout=720, delay=150,
                            msg=f"verify port info page pop up xx")
        finally:
            logger.info("Test Execution completed. Cleanup the IPP Config")

            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                        node_2_template_name,
                                                                                        node_2.cli_type)
            xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
            # utils.wait_till(timeout=10)
            logger.step(f"Disable instant port profile on the switch template '{node_2_template_name}'.")
            xiq_library_at_class_level.xflowsconfigureNetworkPolicy.select_create_instant_port_switch_template(
                "-----")
            assert xiq_library_at_class_level.xflowsconfigureSwitchTemplate.save_template() == 1, "Was not able to save the device template"
            logger.step('Unconfigure Port Type and delete the port Type and VLAN information')
            navigator.wait_until_loading_is_done()
            if node_2.platform.lower() == 'stack':
                slot_list = list(set([p.split(':')[0] for p in isl_list2]))
                for slot in slot_list:
                    globals()['slot'] = slot
                    port_str = ','.join([p.split(':')[1] for p in isl_list2 if slot in p])
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                                node_2_template_name,
                                                                                                node_2.cli_type)
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
                    utils.wait_till(timeout=10)
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.sw_template_stack_select_slot(slot)
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.revert_port_configuration_template_level('Access Port')
                    xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template_save()
                    #xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(port_str, 'Access Port')
            else:
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.select_sw_template(node_2_policy_name,
                                                                                            node_2_template_name,
                                                                                            node_2.cli_type)
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.go_to_port_configuration()
                port_str = ','.join(isl_list2)
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.revert_port_configuration_template_level('Access Port')
                xiq_library_at_class_level.xflowsconfigureSwitchTemplate.switch_template_save()
                #xiq_library_at_class_level.xflowsconfigureSwitchTemplate.template_assign_ports_to_an_existing_port_type(port_str, 'Access Port')
            logger.step(f"Delete instant port profile '{new_instant_port_profile_name}'.")
            # Delete instant port configuration
            is_deleted = xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_instant_port_profile_from_common_obj(
                new_instant_port_profile_name)
            assert is_deleted, "Could not delete the Instant Port Profile"

            vlan_list = [instant_port_parameters["nfwVlanName"], device_type_parameters["actionVlanName"]]
            for vlan_name in vlan_list:
                try:
                    logger.step(f"Delete vlan '{vlan_name}'.")
                    xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_vlan_profile(
                        vlan_name)
                except Exception as exc:
                    logger.warning(exc)
            mac_list = [device_type_parameters["macOuiName"], device_type_parameters["macAddressName"]]
            for mac in mac_list:
                try:
                    logger.step(f"Delete mac objects '{mac}'.")
                    xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_mac_object(mac)
                except Exception as exc:
                    logger.warning(exc)
            logger.step(f"Delete the port profile created for testing port_type {default_port_type_name}")
            xiq_library_at_class_level.xflowsconfigureCommonObjects.delete_port_type_profile(default_port_type_name)
            logger.step("Update the config to device")
            xiq_library_at_class_level.xflowscommonNavigator.navigate_to_devices()
            logger.step(f"View Delta Command for Mac mac: {node_2.mac}.")
            # xiq_library_at_class_level.xflowsmanageDeviceConfig.get_device_config_audit_delta(node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.update_device_delta_configuration(device_mac=node_2.mac)
            xiq_library_at_class_level.xflowsmanageDevices.check_device_update_status_by_using_mac(node_2.mac)
            # Delete vlan created in node_1
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, f'delete vlan vlan_neig ', max_wait=10, interval=3)
            xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
            def _check_vlan_attributes():
                xiq_library_at_class_level.xflowscommonDevices.refresh_devices_page()
                utils.wait_till(timeout=10)
                value = xiq_library_at_class_level.xflowsmanageDevice360.verify_d360_interface_vlan_attributes(node_2,
                                                                                                               vlan_info,
                                                                                                               skip_d360_close=False,
                                                                                                               retry_duration=30,
                                                                                                               retry_count=4,
                                                                                                               vlan_exist=False,
                                                                                                               IRV=False)
                return value

            utils.wait_till(_check_vlan_attributes, timeout=720, delay=150,
                            msg=f"verify port info page pop up xx")
            with enter_switch_cli(node_1) as dev_cmd:
                dev_cmd.send_cmd(node_1.name, f'configure vlan Default add port all', max_wait=10, interval=3)
                dev_cmd.send_cmd(node_1.name, f'configure stpd s0 add vlan Default ports all', max_wait=10, interval=3)
