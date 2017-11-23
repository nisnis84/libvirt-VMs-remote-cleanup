#linuxversion.py

# BigBrotherTool is used to monitor VMs without any owner and destroy them (all of them!)
# The tool should be used only for KVM based hypervisors and one should consider the use of it carefully
# For each new server user should do the following:
	#1. Copy ssh keys to remote server: "ssh-copy-id -i <username>@<host>" so you will not need password
	#2. Add IP, username and password to hosts_list (ip), hosts_user_map (username) and hosts_pass_map (password)
	#3. Change permission for libvirt directoris so tool will be able to delete the files:
		#For example, Login as root to host and execute: "chmod -R a+rwX /var/lib/libvirt/images/" and "chmod -R a+rwX /home" 

# There is a need to create and maintain file list_of_vms.txt which will be used to map a certain VM to his owner
# <vm name> <owner: add your domain email address. for example: username@domain.com>
#author: nisnis84



from datetime import datetime, timedelta
import libvirt
import os
import time
import paramiko
import string
import webbrowser
import logging
import socket
import fcntl
import struct
import fileinput
# Import smtplib for the actual sending function
import smtplib
import  stat
from xml.dom import minidom

# Install postfix on linux
# If need to reconfigure, use "dpkg-reconfigure postfix"
# Change configuration use: "/etc/postfix/main.cf"
# After modifying main.cf, be sure to run '/etc/init.d/postfix reload'

# Mail configuration
sender = 'BigBrotherTool@domain.com'
receivers = ['user@domain.com']
warning_receivers = ["user@domain.com"]

#return True if remote file exist and False otherwise
def rexists(sftp, path):
    """os.path.exists for paramiko's SCP object
    """
    try:
        sftp.stat(path)
    except IOError, e:
        if e[0] == 2:
            return False
        raise
    else:
        return True


# get IP address per interface
def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

# Create a dictionary from VM names as appear in list_of_vms.txt init the val as 0 for all
def create_dictionary_from_vm_names(line_list, vm_dict):
    #go over each line in the owners file, seperate vm name from user name and compare with file
    for indx in range(len(line_list)-1):
        #skip lines with comments
        if "#" in total_tokens[indx]:
            continue
        tokens_per_line = line_list[indx].split()
        str_vm_name = tokens_per_line[0]
        vm_dict[str_vm_name] = 0 

#Go over all VMs in list_of_vms.txt and remove the ones not in any of the hosts
def vm_garbage_collector(vm_dict):
    for line in fileinput.input('/path/to/list_of_vms.txt', inplace=True):
        #skip lines with comments
        if "#" in line:
            print(line),
            continue
        tokens_per_line = line.split()
        str_vm_name = tokens_per_line[0]
        if vm_dict[str_vm_name] == 0:
            continue    
        print(line),



#init logger
logging.basicConfig(filename='/path/to/BigBrotherLogger.log',level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%d/%m/%Y %I:%M:%S %p')

# Connect to remote file mapping VMs-owners (list_of_vms.txt)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('z.z.z.z', username='user', password='pswd')

#list for all hosts IPs we are working on - add new host IP to here
hosts_list = ["y.y.y.y", "x.x.x.x"]

#dictionaries of username and password mapping per each host - add new host username and password to below structures
hosts_user_map = {'y.y.y.y': 'root', 'x.x.x.x': 'admin'}
hosts_pass_map = {'y.y.y.y': 'root', 'x.x.x.x': 'admin'}

message = """From: BigBrotherTool <BigBrotherTool@domain.com>
To: Brothers
"""
message+="Subject: BigBrotherTool: updated status for libvirt hosts \n"

message+="Your VMs are gone....\n\n"

message_vm_not_used = """From: BigBrotherTool <BigBrotherTool@domain.com>
To: Brothers
Subject: BigBrotherTool: VMs not in use for long time

Note that following VMs are not in use for more than 7 days:\n
"""


# Open a file , read it and split it to tokens
ftp = ssh.open_sftp()
fo=ftp.file('/path/to/list_of_vms.txt', "r", -1)

#logging.info("script has been started! device:"+ get_ip_address('mgmt') )

str = fo.read();
total_tokens = str.split( "\n")
print total_tokens

#will hold vm list as presented in list_of_vms.txt  - will be used for garbage collector of VMs presented in list_of_vms.txt but not there in any of the hosts 
vm_dict = {}
create_dictionary_from_vm_names(total_tokens,vm_dict)

#will indicate if any vm got removed (from any host)
vm_deleted = False
assigned_VM_warnning = False

for host_indx in range(len(hosts_list)):
    #connect to remote qemu
    #generate ssh keys using ssh-keygen
    #copy the ssh keys to remote server: ssh-copy-id -i <username>@<host> so you wont need password
    #qemu+ssh://user@host/system?socket=/var/run/libvirt/libvirt-sock
    try:
       conn=libvirt.open("qemu+ssh://"+hosts_user_map[hosts_list[host_indx]]+"@"+hosts_list[host_indx]+"/system?socket=/var/run/libvirt/libvirt-sock")
    except:
       logging.info("Not able to connect to host " + hosts_list[host_indx])
       continue
    logging.info("Connected to host " + hosts_list[host_indx])
    #conn.close()
    #exit(0)
    
    #connect to remote host file
    ssh_remote = paramiko.SSHClient()
    ssh_remote.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_remote.connect(hosts_list[host_indx], username=hosts_user_map[hosts_list[host_indx]], password=hosts_pass_map[hosts_list[host_indx]])
    #need to change permission to libvirt dir so we will be able to delete the files
    #login as root to the server and issue: "chmod -R a+rwX /var/lib/libvirt/images/"
    #TODO add the above change using exec_command() in SSHClient.
    ftp_remote = ssh_remote.open_sftp()

    #get all domains in the host (running and idle)
    #list_all_domains = conn.listAllDomains()
    list_active_domains = conn.listDomainsID()
    list_idle_domains = conn.listDefinedDomains()

    #go over all running VMs
    #for id in range(len(list_all_domains)):
    for id in list_active_domains:
        dom = conn.lookupByID(id)
        #get the xml of the domain so we will be able to find out the exact location of the qcow image
        raw_xml = dom.XMLDesc(0)
        xml = minidom.parseString(raw_xml)
        sources = xml.getElementsByTagName('source') 
        for source in sources:
            if len(source.getAttribute('file')) > 0:
                dom_image_location = source.getAttribute('file')
        #dom = list_all_domains[id]
        infos = dom.info()
        found_vm = False
        
        #go over each line in the owners file, seperate vm name from user name and compare with file
        for indx in range(len(total_tokens)-1):
            #skip lines with comments
            if "#" in total_tokens[indx]:
                continue   
            tokens_per_line = total_tokens[indx].split()
            str_vm_name = tokens_per_line[0]
            str_user_name = tokens_per_line[1]
            
            if dom.name() == str_vm_name:
                found_vm = True;
                vm_dict[str_vm_name] = 1
                break
           
           
        # remove the VM from host if there is no owner found
        if found_vm==False:
           logging.info("No owner for \""+dom.name()+"\" VM in host " + hosts_list[host_indx] +" , removing all of his content" )
           vm_deleted = True
           message+="\n\""+dom.name() + "\" VM in host "+ hosts_list[host_indx] +"\n"

           #destroy only if the VM is in running state
           if infos[0] == libvirt.VIR_DOMAIN_RUNNING:
               dom.destroy()
               logging.info("\""+dom.name()+"\" VM in host "+ hosts_list[host_indx] +" is in running state, destroy it..." )
               
           #undefine the VM
           dom.undefine()
           logging.info("undefine \""+dom.name()+"\" VM in host "+ hosts_list[host_indx])
           #delete qcow image only if its there
           if rexists(ftp_remote, dom_image_location):
               ftp_remote.remove(dom_image_location)
               logging.info("remove qcow image of \""+dom.name()+"\" VM in host "+ hosts_list[host_indx] + "image location "+ dom_image_location)
           else:
               logging.info("\""+dom.name()+"\" VM in host "+ hosts_list[host_indx] + " does't have qcow2 image." )

        else:
            logging.info("\""+dom.name() + "\" VM in host "+hosts_list[host_indx]+" is in running state and assigned with owner, nothing to do" )

        
    #go over all idle VMs
    for id in range(len(list_idle_domains)):
        dom = conn.lookupByName(list_idle_domains[id])
        #dom = list_all_domains[id]
        #get the xml of the domain so we will be able to find out the exact location of the qcow image
        raw_xml = dom.XMLDesc(0)
        xml = minidom.parseString(raw_xml)
        sources = xml.getElementsByTagName('source')
        for source in sources:
            if len(source.getAttribute('file')) > 0:
                dom_image_location = source.getAttribute('file')

        infos = dom.info()
        found_vm = False

       #go over each line in the owners file, seperate vm name from user name and compare with file
        for indx in range(len(total_tokens)-1):
            #skip lines with comments
            if "#" in total_tokens[indx]:
                continue
            tokens_per_line = total_tokens[indx].split()
            str_vm_name = tokens_per_line[0]
            str_user_name = tokens_per_line[1]
            #print str_user_name
            #print str_vm_name
            if dom.name() == str_vm_name:
                found_vm = True;
                vm_dict[str_vm_name] = 1
                break
       
        # remove the VM from host if there is no owner found
        if found_vm==False:
           logging.info("No owner for \""+dom.name()+"\" VM in host " + hosts_list[host_indx] +" , removing all of his content" )
           vm_deleted = True
           message+="\n\""+dom.name() + "\" VM in host "+ hosts_list[host_indx] +"\n"

           #destroy only if the VM is in running state
           if infos[0] == libvirt.VIR_DOMAIN_RUNNING:
               dom.destroy()
               logging.info("\""+dom.name()+"\" VM in host "+ hosts_list[host_indx] +" is in running state, destroy it..." )

           #undefine the VM
           dom.undefine()
           logging.info("undefine \""+dom.name()+"\" VM in host "+ hosts_list[host_indx])
           #delete qcow image only if its there
           if rexists(ftp_remote, dom_image_location):
               ftp_remote.remove(dom_image_location)
               logging.info("remove qcow image of \""+dom.name()+"\" VM in host "+ hosts_list[host_indx] + "image location "+ dom_image_location)
           else:
               logging.info("\""+dom.name()+"\" VM in host "+ hosts_list[host_indx] + " does't have qcow2 image." )

        else:
            logging.info("\""+dom.name() + "\" VM in host "+hosts_list[host_indx]+" is in idle state and assigned with owner, check if it was in use for the last days" )
            #check the time since last use
            if rexists(ftp_remote, dom_image_location):
                utime = ftp_remote.stat(dom_image_location).st_mtime
                last_modified = datetime.fromtimestamp(utime)
                #delete the VM after 10 days not in use
                if (datetime.now()-last_modified)>timedelta(days=12):
                    vm_deleted = True
                    message+="\n\""+dom.name() + "\" VM in host "+ hosts_list[host_indx] +"\n"
                    #undefine the VM
                    dom.undefine()
                    logging.info("undefine \""+dom.name()+"\" VM not in use in host "+ hosts_list[host_indx])
                    #delete qcow image only if its there
                    if rexists(ftp_remote, dom_image_location):
                        ftp_remote.remove(dom_image_location)
                        logging.info("remove qcow image of \""+dom.name()+"\" VM not in use in host "+ hosts_list[host_indx] + "image location "+ dom_image_location)
                    else:
                        logging.info("\""+dom.name()+"\" VM not in use in host "+ hosts_list[host_indx] + " does't have qcow2 image." )
                #do something only if the VM wasnt used for more than 7 days - send notification to owner
                elif (datetime.now()-last_modified)>timedelta(days=7):
                    logging.info("\""+dom.name() + "\" VM in host "+hosts_list[host_indx]+" owner is "+str_user_name+" is not in use for more than 7 days, sending mail about it!" ) 
                    assigned_VM_warnning = True
                    warning_receivers.append(str_user_name)
                    message_vm_not_used += "\n\""+dom.name() + "\" VM in host "+ hosts_list[host_indx] +" owner is "+str_user_name+ " image location is: " + dom_image_location +"\n"
                
               

    #close the connections
    ftp_remote.close()
    ssh_remote.close()
    conn.close()

#send mail only if at least one vm was removed
smtpObj = smtplib.SMTP('localhost')
if (vm_deleted == True):
    message+="\nThanks,\nBigBrother"
    smtpObj.sendmail(sender, receivers, message)
    logging.info("Sent mail to group of users about deletion of unassigned VMs")
    print "Successfully sent email"

#send mail to warn before deleting defined VMs
if (assigned_VM_warnning == True):
    message_vm_not_used+= """\nIf you are still using your VM, execute the following command in the relevant host:\n "touch <location of qcow image>"
\n\nIf you are not using the VM, it will be deleted automatically within few days.
    \nThanks,\nBigBrother
"""

    smtpObj.sendmail(sender, warning_receivers, message_vm_not_used)
    logging.info("Sent mail to group of users about warnning of assigned VMs not in use")
    print "Successfully sent email"

# Remove any VM written in the vm file but not in any host
vm_garbage_collector(vm_dict)

smtpObj.quit()
fo.close()
ftp.close()
ssh.close()

