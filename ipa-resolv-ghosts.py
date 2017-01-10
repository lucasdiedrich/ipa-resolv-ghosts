#!/usr/bin/python

#
#   This is script search for broken agreements (aka Ghost Replicas) 
#   over the Directory 389/Freeipa database. All the logic are based  
#   over this page: http://www.port389.org/docs/389ds/howto/howto-cleanruv.html#cleanallruv
#
#   Created by: Lucas Diedrich
#

import socket
import getpass
import ldap
import ldap.modlist as modlist
import sys, getopt

NSDS='nsds50ruv'

v_hostname = socket.gethostbyaddr(socket.gethostname())[0]
v_binddn = "cn=Directory Manager"
v_bindpw = ""
v_basedn = ""
v_search_scope = ldap.SCOPE_SUBTREE
v_ghost_attr = [NSDS]
v_ghost_filter = "(&(nsuniqueid=ffffffff-ffffffff-ffffffff-ffffffff)(objectclass=nstombstone))"
v_ghosts = []
v_version = "01.10.17"

# Generic confirm function taken from:
# http://code.activestate.com/recipes/541096-prompt-the-user-for-confirmation/
def confirm(prompt=None, resp=False):
    if prompt is None:
        prompt = 'Confirm'

    if resp:
        prompt = '%s [%s]|%s: ' % (prompt, 'y', 'n')
    else:
        prompt = '%s [%s]|%s: ' % (prompt, 'n', 'y')

    while True:
        ans = raw_input(prompt)
        if not ans:
            return resp
        if ans not in ['y', 'Y', 'n', 'N']:
            print 'please enter y or n.'
            continue
        if ans == 'y' or ans == 'Y':
            return True
        if ans == 'n' or ans == 'N':
            return False

def f_init_ldap():
    ''' Opens the ldap connection for further use and set it as global variable v_ldap_con.
        Params: []
        Return: no
    '''
    try:
        global v_ldap_con
        v_ldap_con = ldap.open(v_hostname)
        v_ldap_con.protocol_version = ldap.VERSION3  
        v_ldap_con.simple_bind(v_binddn, v_bindpw)
    except ldap.LDAPError, e:
        print "Sorry, it wasn't possible to contact the server (", v_hostname ,"), error: " + e[0]['desc']
        sys.exit()

def f_ldap_search(args):
    ''' Querie ldap with the based ldap filter and attrs, return an array of ldap items.
        Params: [args] - arg[0] - Ldap search filter
                       - arg[1] - ldap return attrs
        Return: [Array]
    '''    
    if not 'v_ldap_con' in globals():
        f_init_ldap()

    array_of_itens = []

    try:
        t_results_id = v_ldap_con.search(v_basedn, v_search_scope, args[0], args[1])
        while 1:
            t_result_type, t_result_data = v_ldap_con.result(t_results_id, 0)
            if (t_result_data == []):
                break
            else:
                if t_result_type == ldap.RES_SEARCH_ENTRY:
                    array_of_itens.append(t_result_data)
    except ldap.LDAPError, e:
        print "Sorry, it wasn't possible to ldap-search the server: " + e[0]['desc']
        sys.exit()

    return array_of_itens

def f_ldap_modify(dn, ldif):
    ''' Execute the ldap ldif command using ldap-modify command.
        Params: - dn - Base DN where the command should be executed
                - ldif - Ldif script generated by modlist
        Return: no
    '''    
    if not 'v_ldap_con' in globals():
        f_init_ldap()

    return v_ldap_con.modify_s(dn,ldif)

def f_get_ruvs():
    ''' Get all RUV's from the server.
        Params: no
        Return: [Array]
    '''    
    t_ruvs = f_ldap_search([v_ghost_filter,v_ghost_attr])
    parsed_ruvs = []
    
    if t_ruvs:
        for ruv in t_ruvs[0][0][1][NSDS]:
            parsed_ruvs.append(ruv)

    return parsed_ruvs


def f_del_reg(ruv):
    ''' Delete the selected ruv from the server by invoking the nsds5task delete task.
        Params: {ruv}
        Return: no
    '''
    v_dn = "cn=replica,cn=" + v_basedn.replace("=","\\3D") + ",cn=mapping tree,cn=config"
    v_tmp = {'nsds5task':''}
    v_new = {'nsds5task': 'CLEANRUV' + ruv.split(' ')[1][:-1]} 

    # Create the ldif instructions
    ldif = modlist.modifyModlist(v_tmp, v_new)

    if confirm("Are you certain that you can delete this ghost record? "):
        f_ldap_modify(v_dn, ldif)

def f_resolv_ruv(all_ruvs):
    ''' Print all Ghost RUVs one by one, prompting if want's to ignore or erase the selected RUV
        Params: [ruvs]
        Return: no
    '''    
    ghost_ruvs = [r for r in all_ruvs if ("replicageneration" not in r) and ("ldap://" not in r)]

    for ruv in ghost_ruvs:

        print "\n======================================"
        print "Ghost: ", ruv
        
        try:
            dict = {1: f_del_reg}
            dict[input("\n 0 - Ignore \t 1 - Delete Ghost RUV: ")](ruv)
        except:
            print "Ghost RUV ignored."

    return

def f_see_all(ruvs):
    ''' Print all RUVs from the environment.
        Params: [ruvs]
        Return: no
    '''
    print "\n All RUVs:"
    for ruv in ruvs:
        ruv_type = " Normal"  if ("replicageneration" and "ldap://" in ruv) else " *Ghost"
        print ruv_type, " - ", ruv
    raw_input("[Enter to continue]")

def f_print_usage():
    print 'Usage:', sys.argv[0], '<opts>'
    print '\n\t-d <base-dn> \n\t-s <server> (Default: local fqdn)'
    print '\t-p <password> (If not passed will be prompted)'
    # print '\n\t-U (Unattended, will erase all ghost replicas automatically - TODO)'
    sys.exit(2)

def f_parse_args(argv):
    global v_bindpw
    global v_hostname
    global v_basedn

    try:
        opts, args = getopt.getopt(argv,"hd:s:p:")
    except getopt.GetoptError:
        f_print_usage()
   
    for opt, arg in opts:
        if opt == '-h':
            f_print_usage()
        elif opt == ("-d"):
            v_basedn = arg
        elif opt == ("-s"):
            v_hostname = arg
        elif opt == ("-p"):
            v_bindpw = arg

    if v_bindpw == "":
        v_bindpw = getpass.getpass(prompt="'" + v_binddn + "' password: ")

def f_menu():
    v_all_ruvs = f_get_ruvs()
    v_gen_ruvs = [r for r in v_all_ruvs if ("replicageneration" in r)]
    v_nor_ruvs = [r for r in v_all_ruvs if ("ldap://" in r)]
    v_gho_ruvs = [r for r in v_all_ruvs if ("replicageneration" not in r) and ("ldap://" not in r)]

    if (v_all_ruvs):
        print "\n\n======================================"
        print " Ghost Replicas Fixer (clean-all-ruv) "
        print " Version: ", v_version
        print " Host: ", v_hostname
        print "======================================"
        print "               RUV's"
        print " Ghosts: ", v_gho_ruvs.__len__(), "!!!!!!!!!!!!!!" if (v_gho_ruvs.__len__() > 0) else ""
        print " Generation: ", v_gen_ruvs.__len__()
        print " Normal: ", v_nor_ruvs.__len__()
        print " Total: ", v_all_ruvs.__len__()
        print "======================================"
        
        # try:
        dict_str = ' 0 - Exit \t 1 - See all %s' %('\t 2 - Fix Ghost RUVs: ' if v_gho_ruvs.__len__() > 0 else ': ')

        sel_value = raw_input(dict_str)

        if sel_value == "0":
            sys.exit()
        elif sel_value == "1":
            f_see_all(v_all_ruvs)
        elif sel_value == "2":
            f_resolv_ruv(v_all_ruvs)            

        return
    else:
        print 'No RUVs were found at ', v_hostname
        sys.exit()

def main(argv):
    f_parse_args(argv)
    
    while True:
        f_menu()
    
if __name__ == "__main__":
    main(sys.argv[1:])
