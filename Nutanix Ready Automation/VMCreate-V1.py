import json
import getpass
import pprint
import sys
import requests
from tqdm import tqdm
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class RestApi:

    def __init__(self, IP_Address, Username, Password):
        self.IP_Address = IP_Address
        self.username = Username
        self.password = Password
        self.base_url = "https://"+self.IP_Address+":9440/PrismGateway/services/rest/v2.0"
        self.session = self.get_server_session(self.username, self.password)

    # Obtaining a session object for Nutanix API Authentication and Request
    def get_server_session(self, username, password):
        session = requests.session()
        session.auth = (username, password)
        session.verify = False
        session.headers.update({'Content-Type': 'application/json; charset=utf-8'})
        return session

    # Obtaining Storage Container Information
    def get_container(self, container_name):
        clusterURL = self.base_url + "/storage_containers" + "?search_string=" + container_name
        serverResponse = self.session.get(url=clusterURL)
        container_data = json.loads(serverResponse.text)
        if int(container_data["metadata"]["count"]) > 0:
            container_id = str(container_data["entities"][0]["storage_container_uuid"])
            return container_id
        else:
            print("The container you're looking for does not exist!")
            return None


    # Uploading the ISO/Disk Image to Nutanix Images Store
    def upload_image(self, container_id):
        clusterURL = self.base_url + "/images"
        image_name = input("Enter Image Name: ")
        image_type_value = int(input('''Enter Image Type
        [Enter "1" for DISK_IMAGE]
        [Enter "2" for ISO_IMAGE]: '''))
        url = input("Enter URL for the Image: ")
        if image_type_value == 1:
            image_type = "DISK_IMAGE"
        else:
            image_type = "ISO_IMAGE"
        serverResponse = self.session.post(url=clusterURL, json={
            "image_import_spec": {
                "storage_container_uuid": container_id,
                "url": url
            },
            "image_type":image_type,
            "name": image_name,
        })
        return json.loads(serverResponse.text)


    # Obtaining information about the uploaded Image
    def get_image(self, image_id ):
        clusterURL = self.base_url + "/images/" + image_id
        serverResponse = self.session.get(url=clusterURL)
        return json.loads(serverResponse.text)


    # Creating a VM
    def create_vm(self, vmdisk_id, container_id):
        clusterURL = self.base_url + "/vms/"
        vm_name = input("Enter VM Name: ")
        serverResponse = self.session.post(url=clusterURL, json={
            "boot": {
                "boot_device_type": "CDROM",
                "disk_address": {
                    "device_bus": "IDE",
                    "device_index": 0,
                    "vmdisk_uuid": vmdisk_id
                                }
                    },
            "memory_mb": 2048,
            "name": vm_name,
            "num_cores_per_vcpu": 1,
            "num_vcpus": 2,
            "storage_container_uuid": container_id,
            "vm_features": {},
            "vm_disks": [{
                "disk_address": {
                    "device_bus": "IDE",
                    "device_index": 0
                                },
                "is_cdrom": True,
                "is_empty": False,
                "vm_disk_clone": {
                    "disk_address": {
                        "vmdisk_uuid": vmdisk_id
                                    }
                        }
                        }]
        })
        result = json.loads(serverResponse.text)
        return json.loads(serverResponse.text)

    # Determining Job Progress
    def Progress(self, task):
        clusterURL = self.base_url + "/tasks/" + task + "?include_subtasks_info=false"
        serverResponse = self.session.get(url=clusterURL)
        task_progress = json.loads(serverResponse.text)
        task_status = str(task_progress["progress_status"])
        percentage_1 = int(task_progress["percentage_complete"])
        with tqdm(total=100, desc="Uploading…", ascii=False, ncols=75) as pbar:
            pbar.update(percentage_1)
            while percentage_1 < 100:
                serverResponse = self.session.get(url=clusterURL)
                task_progress = json.loads(serverResponse.text)
                percentage_2 = int(task_progress["percentage_complete"])
                task_status = str(task_progress["progress_status"])
                if percentage_2 > percentage_1:
                    pbar.update(percentage_2 - percentage_1)
                    percentage_1 = percentage_2
                else:
                    continue
        if task_status == "Succeeded":
            print("The job completed successfully")
            return task_progress
        else:
            print("The job did not complete successfully")
            return None

# --------------------------------------------------------
if __name__ == "__main__":
    try:
        Cluster_IP = input("Enter Prism Element IP: ")
        Username = input("Enter Username: ")
        Password = getpass.getpass("Enter Password: ")
        testRestApi = RestApi(Cluster_IP, Username, Password)
        pp = pprint.PrettyPrinter(indent=2)
        container_name = input("Enter Container Search String for Image Upload: ")
        container_id = testRestApi.get_container(container_name)
        task_result = None
        if container_id != None:
            image_copy_task = testRestApi.upload_image(container_id)
            print("Initiating Image copy...please wait")
            task_result = testRestApi.Progress(image_copy_task["task_uuid"])
            print("=" * 79)
        if task_result !=None:
            image_disk_id = testRestApi.get_image(task_result["entity_list"][0]["entity_id"])
            vm_create_task = testRestApi.create_vm(image_disk_id["vm_disk_id"], container_id)
            print("Initiating VM create...please wait")
            task_result = testRestApi.Progress(vm_create_task["task_uuid"])
            print("=" * 79)



    except Exception as ex:
        print (ex)
        sys.exit(1)